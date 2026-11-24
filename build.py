#!/usr/bin/env python3
"""NOTICE LAB 정적 사이트 빌드 스크립트.

표준 라이브러리만 사용합니다. (Node.js, npm, 별도 패키지 설치 불필요)

    python3 build.py            # posts/*.md -> dist/
    python3 build.py --clean    # dist/를 지우고 다시 빌드

posts/ 에 마크다운 파일을 하나 추가하고 다시 실행하면
목록 페이지, 개별 글 페이지, sitemap.xml, rss.xml, robots.txt 가 함께 갱신됩니다.

마크다운 문법 지원 범위
    ## / ### / #### 제목, 문단, **굵게**, `코드`, [링크](주소),
    - 순서 없는 목록, 1. 순서 있는 목록, > 인용, --- 구분선,
    ![대체텍스트](/assets/images/파일.png "설명") 단독 이미지(캡션 포함)
"""

from __future__ import annotations

import argparse
import html
import json
import math
import os
import re
import shutil
import struct
import sys
from datetime import datetime, timedelta, timezone
from email.utils import format_datetime

ROOT = os.path.dirname(os.path.abspath(__file__))
POSTS_DIR = os.path.join(ROOT, "posts")
TEMPLATE_DIR = os.path.join(ROOT, "templates")
ASSETS_DIR = os.path.join(ROOT, "assets")
DIST_DIR = os.path.join(ROOT, "dist")
CONFIG_PATH = os.path.join(ROOT, "site.json")

KST = timezone(timedelta(hours=9))
VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
             "meta", "param", "source", "track", "wbr"}


# --------------------------------------------------------------------------
# 기본 유틸
# --------------------------------------------------------------------------
def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as fh:
        return json.load(fh)


def esc(text: str) -> str:
    return html.escape(str(text), quote=True)


def base_url(config: dict) -> str:
    return config["baseUrl"].rstrip("/")


def url_for(config: dict, path: str) -> str:
    """사이트 내부 경로('/insights/')를 절대 URL로 바꿉니다."""
    path = "/" + path.lstrip("/")
    return base_url(config) + path


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def image_size(path: str) -> tuple[int, int] | None:
    """PNG·JPEG 파일의 가로·세로를 읽습니다 (레이아웃 흔들림 방지용)."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                width, height = struct.unpack(">II", head[16:24])
                return width, height
            if head[:2] != b"\xff\xd8":
                return None
            fh.seek(2)
            while True:
                marker = fh.read(2)
                if len(marker) < 2 or marker[0] != 0xFF:
                    return None
                code = marker[1]
                if code in (0xD8, 0xD9):
                    continue
                raw_length = fh.read(2)
                if len(raw_length) < 2:
                    return None
                length = struct.unpack(">H", raw_length)[0]
                if 0xC0 <= code <= 0xCF and code not in (0xC4, 0xC8, 0xCC):
                    block = fh.read(5)
                    if len(block) < 5:
                        return None
                    height, width = struct.unpack(">HH", block[1:5])
                    return width, height
                fh.seek(length - 2, 1)
    except OSError:
        return None


def slugify(text: str) -> str:
    out = []
    for ch in text.strip().lower():
        if ch.isalnum():
            out.append(ch)
        elif out and out[-1] != "-":
            out.append("-")
    slug = "".join(out).strip("-")
    return slug or "section"


def strip_markdown(text: str) -> str:
    text = re.sub(r"```.*?```", " ", text, flags=re.S)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"(\*\*|__)(.+?)\1", r"\2", text)
    text = re.sub(r"^#{1,6}\s*", "", text, flags=re.M)
    text = re.sub(r"^\s*[-*]\s+", "", text, flags=re.M)
    text = re.sub(r"^\s*\d+\.\s+", "", text, flags=re.M)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


# --------------------------------------------------------------------------
# 이미지
# --------------------------------------------------------------------------
def load_image_index() -> dict:
    """assets/images 안의 PNG 크기와 WebP 파생본을 색인합니다."""
    index: dict[str, dict] = {}
    if not os.path.isdir(ASSETS_DIR):
        return index
    image_dir = os.path.join(ASSETS_DIR, "images")
    derivatives = {}
    derivative_path = os.path.join(image_dir, "derivatives.json")
    if os.path.exists(derivative_path):
        with open(derivative_path, encoding="utf-8") as fh:
            derivatives = json.load(fh)

    def existing(names: list[str]) -> list[str]:
        return [name for name in names if name and os.path.exists(os.path.join(image_dir, name))]

    for name in sorted(os.listdir(image_dir)):
        if not name.lower().endswith((".png", ".jpg", ".jpeg")):
            continue
        full = os.path.join(image_dir, name)
        size = image_size(full)
        info = derivatives.get(name, {})
        webp = info.get("webp")
        srcset = ""
        entries = info.get("webp_srcset")
        if entries:
            pairs = []
            for part in entries.split(","):
                bits = part.split()
                if not bits or not os.path.exists(os.path.join(image_dir, bits[0])):
                    continue
                pairs.append(f"/assets/images/{bits[0]}" + (" " + " ".join(bits[1:]) if len(bits) > 1 else ""))
            srcset = ", ".join(pairs)
        index[f"/assets/images/{name}"] = {
            "width": size[0] if size else None,
            "height": size[1] if size else None,
            "webp": f"/assets/images/{webp}" if existing([webp]) else None,
            "srcset": srcset,
        }
    return index


IMAGE_INDEX: dict[str, dict] = {}


def picture(src: str, alt: str, *, cls: str = "", eager: bool = False, sizes: str | None = None) -> str:
    """WebP 우선, PNG 폴백 <picture> 를 만듭니다 (가로·세로 값으로 레이아웃 흔들림 방지)."""
    info = IMAGE_INDEX.get(src, {})
    width, height, webp = info.get("width"), info.get("height"), info.get("webp")
    attrs = [f'src="{esc(src)}"', f'alt="{esc(alt)}"']
    if width and height:
        attrs += [f'width="{width}"', f'height="{height}"']
    attrs.append('loading="eager"' if eager else 'loading="lazy"')
    attrs.append('decoding="async"')
    if eager:
        attrs.append('fetchpriority="high"')
    if cls:
        attrs.append(f'class="{esc(cls)}"')
    img = f'<img {" ".join(attrs)}>'
    candidates = info.get("srcset") or webp
    if candidates:
        srcset = f'srcset="{esc(candidates)}"'
        if sizes:
            srcset += f' sizes="{esc(sizes)}"'
        return f'<picture><source type="image/webp" {srcset}>{img}</picture>'
    return img


# --------------------------------------------------------------------------
# 마크다운 -> HTML
# --------------------------------------------------------------------------
class MarkdownRenderer:
    def __init__(self):
        self.headings: list[dict] = []
        self._used_ids: dict[str, int] = {}

    def unique_id(self, text: str) -> str:
        base = slugify(text)
        count = self._used_ids.get(base, 0)
        self._used_ids[base] = count + 1
        return base if count == 0 else f"{base}-{count + 1}"

    def inline(self, text: str) -> str:
        stash: list[str] = []

        def keep(markup: str) -> str:
            stash.append(markup)
            return f"\x00{len(stash) - 1}\x00"

        text = re.sub(r"`([^`]+)`", lambda m: keep(f"<code>{esc(m.group(1))}</code>"), text)
        text = esc(text)
        text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: self._link(m.group(1), m.group(2)), text)
        text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
        text = text.replace("\\*", "*")
        for i, markup in enumerate(stash):
            text = text.replace(f"\x00{i}\x00", markup)
        return text

    @staticmethod
    def _link(label: str, url: str) -> str:
        # inline() 에서 이미 HTML 이스케이프된 문자열을 받으므로 다시 이스케이프하지 않습니다.
        href = url
        if re.match(r"^https?://", url):
            return (f'<a href="{href}" target="_blank" rel="noopener noreferrer">{label}'
                    f'<span class="sr-only"> (새 탭에서 열림)</span></a>')
        return f'<a href="{href}">{label}</a>'

    def heading(self, level: int, raw: str) -> str:
        text = self.inline(raw.strip())
        plain = strip_markdown(raw)
        anchor = self.unique_id(plain)
        self.headings.append({"level": level, "text": plain, "id": anchor})
        return (f'<h{level} id="{anchor}">{text}'
                f'<a class="anchor" href="#{anchor}" aria-label="{esc(plain)} 섹션 링크">#</a>'
                f"</h{level}>")

    def render(self, markdown: str) -> str:
        lines = markdown.splitlines()
        out: list[str] = []
        i = 0
        total = len(lines)

        while i < total:
            line = lines[i]
            stripped = line.strip()

            if not stripped:
                i += 1
                continue

            if stripped in {"---", "***", "___"}:
                out.append("<hr>")
                i += 1
                continue

            heading = re.match(r"^(#{2,4})\s+(.*)$", stripped)
            if heading:
                out.append(self.heading(len(heading.group(1)), heading.group(2)))
                i += 1
                continue

            figure = re.match(r"^!\[([^\]]*)\]\((\S+?)(?:\s+\"([^\"]*)\")?\)$", stripped)
            if figure:
                alt, src, caption = figure.group(1), figure.group(2), figure.group(3)
                figcaption = caption or alt
                out.append(
                    '<figure class="post-figure">'
                    + picture(src, alt, cls="post-figure-img")
                    + (f"<figcaption>{esc(figcaption)}</figcaption>" if figcaption else "")
                    + "</figure>"
                )
                i += 1
                continue

            if stripped.startswith("> "):
                quote: list[str] = []
                while i < total and lines[i].strip().startswith(">"):
                    quote.append(lines[i].strip()[1:].strip())
                    i += 1
                body = self.inline(" ".join(part for part in quote if part))
                out.append(f'<blockquote><p>{body}</p></blockquote>')
                continue

            if re.match(r"^[-*]\s+", stripped):
                items: list[str] = []
                while i < total and re.match(r"^[-*]\s+", lines[i].strip()):
                    items.append(re.sub(r"^[-*]\s+", "", lines[i].strip()))
                    i += 1
                lis = "".join(f"<li>{self.inline(item)}</li>" for item in items)
                out.append(f"<ul>{lis}</ul>")
                continue

            if re.match(r"^\d+\.\s+", stripped):
                items = []
                while i < total and re.match(r"^\d+\.\s+", lines[i].strip()):
                    items.append(re.sub(r"^\d+\.\s+", "", lines[i].strip()))
                    i += 1
                lis = "".join(f"<li>{self.inline(item)}</li>" for item in items)
                out.append(f"<ol>{lis}</ol>")
                continue

            if stripped.startswith("|"):
                rows: list[list[str]] = []
                while i < total and lines[i].strip().startswith("|"):
                    cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                    rows.append(cells)
                    i += 1
                if len(rows) >= 2 and all(
                    c and set(c) <= set("-: ") for c in rows[1]
                ):
                    head, body_rows = rows[0], rows[2:]
                else:
                    head, body_rows = [], rows
                thead = ""
                if head:
                    thead = (
                        "<thead><tr>"
                        + "".join(f"<th>{self.inline(c)}</th>" for c in head)
                        + "</tr></thead>"
                    )
                def body_cell(value: str, index: int) -> str:
                    # 모바일 카드형 표에서 각 값 위에 머리글을 붙일 수 있도록 data-label 을 남깁니다.
                    if head and index < len(head):
                        label = strip_markdown(head[index])
                        if label:
                            return f'<td data-label="{esc(label)}">{self.inline(value)}</td>'
                    return f"<td>{self.inline(value)}</td>"

                tbody = "<tbody>" + "".join(
                    "<tr>" + "".join(body_cell(c, i) for i, c in enumerate(row)) + "</tr>"
                    for row in body_rows
                ) + "</tbody>"
                width = len(head) if head else (len(rows[0]) if rows else 0)
                cols = f' data-cols="{width}"' if 2 <= width <= 4 else ""
                out.append(f'<div class="table-wrap"{cols}><table>{thead}{tbody}</table></div>')
                continue

            paragraph: list[str] = []
            while i < total:
                peek = lines[i].strip()
                if not peek:
                    break
                if re.match(r"^(#{2,4})\s+", peek) or re.match(r"^[-*]\s+", peek):
                    break
                if re.match(r"^\d+\.\s+", peek) or peek.startswith("> "):
                    break
                if peek in {"---", "***", "___"} or re.match(r"^!\[", peek) or peek.startswith("|"):
                    break
                paragraph.append(peek)
                i += 1
            out.append(f"<p>{self.inline(' '.join(paragraph))}</p>")

        return "\n".join(out)


def extract_faq(markdown: str, heading_text: str) -> list[dict]:
    """본문의 FAQ 섹션(### 질문 + 답변 문단)을 FAQPage 스키마용으로 뽑아냅니다."""
    lines = markdown.splitlines()
    faq: list[dict] = []
    inside = False
    question: str | None = None
    answer: list[str] = []

    def flush():
        nonlocal question, answer
        if question and answer:
            faq.append({"q": strip_markdown(question), "a": strip_markdown(" ".join(answer))})
        question, answer = None, []

    for line in lines:
        stripped = line.strip()
        if stripped.startswith("## "):
            flush()
            inside = strip_markdown(stripped[3:]) == heading_text
            continue
        if not inside:
            continue
        if stripped.startswith("### "):
            flush()
            question = stripped[4:]
            continue
        if question is not None and stripped and not stripped.startswith(("#", "-", ">", "!")):
            answer.append(stripped)
        elif question is not None and stripped.startswith(("-", ">")):
            answer.append(stripped.lstrip("-> "))
    flush()
    return faq


# --------------------------------------------------------------------------
# 글 파싱
# --------------------------------------------------------------------------
def parse_front_matter(text: str) -> tuple[dict, str]:
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    meta: dict = {}
    for raw in parts[1].splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"front matter 형식 오류: {line!r}")
        key, value = line.split(":", 1)
        value = value.strip()
        if value.startswith("[") and value.endswith("]"):
            items = [item.strip().strip('"').strip("'") for item in value[1:-1].split(",")]
            meta[key.strip()] = [item for item in items if item]
        else:
            meta[key.strip()] = value.strip('"').strip("'")
    return meta, parts[2].lstrip("\n")


def as_list(value) -> list[str]:
    """front matter 값을 목록으로 정리합니다. 쉼표 구분 문자열도 받습니다."""
    if isinstance(value, list):
        return [item.strip() for item in value if item and item.strip()]
    if not value:
        return []
    return [item.strip() for item in str(value).split(",") if item.strip()]


def parse_date(value: str) -> datetime:
    value = value.strip()
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        dt = datetime.strptime(value, "%Y-%m-%d").replace(hour=9)
    return dt if dt.tzinfo else dt.replace(tzinfo=KST)


def load_posts() -> list[dict]:
    posts: list[dict] = []
    for name in sorted(os.listdir(POSTS_DIR)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(POSTS_DIR, name)
        meta, body = parse_front_matter(read_text(path))
        required = ["title", "slug", "description", "category", "date"]
        missing = [key for key in required if not meta.get(key)]
        if missing:
            raise ValueError(f"{name}: front matter 누락 {missing}")

        renderer = MarkdownRenderer()
        body_html = renderer.render(body)
        plain = strip_markdown(body)
        chars = len(re.sub(r"\s", "", plain))
        faq = extract_faq(body, meta.get("faq_heading", "자주 묻는 질문"))

        posts.append({
            "file": name,
            "title": meta["title"],
            "slug": meta["slug"],
            "description": meta["description"],
            "category": meta["category"],
            "date": parse_date(meta["date"]),
            "updated": parse_date(meta["updated"]) if meta.get("updated") else parse_date(meta["date"]),
            "cover": meta.get("cover", ""),
            "cover_alt": meta.get("cover_alt", meta["title"]),
            "og_image": meta.get("og_image", ""),
            "og_image_alt": meta.get("og_image_alt", meta["title"]),
            "keywords": as_list(meta.get("keywords")),
            "related": as_list(meta.get("related")),
            "image": meta.get("image", ""),
            "image_caption": meta.get("image_caption", ""),
            "body_html": body_html,
            "plain": plain,
            "chars": chars,
            "reading_time": max(3, math.ceil(chars / 500)),
            "headings": [h for h in renderer.headings if h["level"] == 2],
            "faq": faq,
            "path": f"/insights/{meta['slug']}/",
        })

    posts.sort(key=lambda post: post["date"], reverse=True)
    slugs = {post["slug"] for post in posts}
    for post in posts:
        post["related"] = [slug for slug in post["related"] if slug in slugs and slug != post["slug"]]
        if not post["related"]:
            post["related"] = [other["slug"] for other in posts if other["slug"] != post["slug"]][:2]
    return posts


# --------------------------------------------------------------------------
# 템플릿
# --------------------------------------------------------------------------
TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


def render_template(name: str, context: dict) -> str:
    template = read_text(os.path.join(TEMPLATE_DIR, name))

    def replace(match: re.Match) -> str:
        key = match.group(1)
        if key not in context:
            raise KeyError(f"{name}: 템플릿 변수 '{key}' 값이 없습니다")
        value = context[key]
        return "" if value is None else str(value)

    return TOKEN_RE.sub(replace, template)


def ph(value: str) -> str:
    """[대표자명] 처럼 대괄호로 표시한 입력 대기 자리를 강조해 표시합니다."""
    escaped = esc(value)
    return re.sub(r"(\[[^\]]+\])", r'<span class="ph">\1</span>', escaped)


def mail_order_row(value: str) -> str:
    """통신판매업 신고번호는 값이 있을 때만 표시합니다(빈 값이면 빈 dd 줄을 남기지 않음)."""
    if not value.strip():
        return ""
    return f'\n        <div><dt>통신판매업</dt><dd>{ph(value.strip())}</dd></div>'


def analytics_snippet(config: dict) -> str:
    """Cloudflare Web Analytics 비콘 스니펫.

    site.json 의 analytics.cloudflareBeaconToken 값이 있을 때만 출력합니다.
    토큰은 사이트별 공개 식별자라 페이지에 노출되어도 안전하지만, 형식이 어긋난 값은
    HTML 을 깨뜨리지 않도록 빌드 단계에서 거부합니다.
    """
    analytics = config.get("analytics") or {}
    token = str(analytics.get("cloudflareBeaconToken", "")).strip()
    if not token:
        return ""
    if not re.fullmatch(r"[A-Za-z0-9_-]{16,64}", token):
        raise ValueError("site.json 의 analytics.cloudflareBeaconToken 값이 올바르지 않습니다 "
                         "(영문·숫자·-·_ 16~64자)")
    return ("\n<script defer src='https://static.cloudflareinsights.com/beacon.min.js' "
            f'data-cf-beacon=\'{{"token": "{token}"}}\'></script>')


def build_base_context(config: dict) -> dict:
    business = config["business"]
    verification = config.get("verification", {})
    verify_tags = []
    if verification.get("google"):
        verify_tags.append(f'<meta name="google-site-verification" content="{esc(verification["google"])}">')
    for extra in verification.get("googleExtra") or []:
        if str(extra).strip():
            verify_tags.append(f'<meta name="google-site-verification" content="{esc(str(extra).strip())}">')
    if verification.get("naver"):
        verify_tags.append(f'<meta name="naver-site-verification" content="{esc(verification["naver"])}">')
    if not verify_tags:
        verify_tags.append("<!-- 검색 등록 확인: site.json 의 verification.google / verification.naver 에 "
                           "Search Console·서치어드바이저 확인값을 넣으면 메타 태그가 자동 생성됩니다. -->")
    return {
        "verify_meta": "\n".join(verify_tags),
        "analytics_head": analytics_snippet(config),
        "brand": esc(config["siteName"]),
        "brand_ko": esc(config["siteNameKo"]),
        "slogan": esc(config["slogan"]),
        "consult_url": esc(config["consultUrl"]),
        "consult_label": esc(config["consultLabel"]),
        "business_name": ph(business["name"]),
        "business_ceo": ph(business["ceo"]),
        "business_registration": ph(business["registrationNumber"]),
        "business_mail_order_row": mail_order_row(business["mailOrderNumber"]),
        "business_address": ph(business["address"]),
        "business_email": ph(business["email"]),
        "business_phone": ph(business["phone"]),
        "business_industries": ph(business["industries"]),
        "year": datetime.now(KST).year,
        "nav": "",
        "jsonld": "",
        "body_class": "",
        "robots": "index,follow,max-image-preview:large",
        "og_type": "website",
        "extra_meta": "",
    }


def nav_html(config: dict, active: str) -> str:
    items = [
        ("home", "/", "01", "HOME", "홈"),
        ("structure", "/#structure", "02", "APPROACH", "전환 구조"),
        ("services", "/#services", "03", "CAPABILITIES", "핵심 서비스"),
        ("samples", "/#samples", "04", "WORK SAMPLES", "작업 예시"),
        ("pricing", "/#pricing", "05", "PRICING", "기준 가격"),
        ("insights", "/insights/", "06", "INSIGHTS", "인사이트"),
        ("social", "/#social", "07", "SOCIAL", "사회공헌"),
    ]
    rows = []
    for key, href, number, label, ko in items:
        current = ' aria-current="page"' if key == active else ""
        rows.append(
            f'<li class="nav-item"><a class="nav-link" href="{href}"{current}>'
            f'<span class="nav-no">{number}</span>'
            f'<span class="nav-en">{esc(label)}</span>'
            f'<span class="nav-ko">{esc(ko)}</span>'
            f'<span class="nav-arrow" aria-hidden="true">→</span></a></li>'
        )
    rows.append(
        f'<li class="nav-item nav-item--talk"><a class="nav-link" href="{esc(config["consultUrl"])}" '
        'target="_blank" rel="noopener noreferrer">'
        '<span class="nav-no">08</span><span class="nav-en">TALK</span>'
        f'<span class="nav-ko">{esc(config["siteNameKo"])} 상담</span>'
        '<span class="nav-arrow" aria-hidden="true">→</span></a></li>'
    )

    business = config["business"]
    return (
        '<div class="nav-overlay" id="site-nav">\n'
        f'  <p class="nav-topline"><span>MENU</span><span>{esc(config["siteName"])} — {esc(config["siteNameKo"])}</span></p>\n'
        '  <div class="nav-overlay-inner">\n'
        '    <nav class="nav-main" aria-label="주 메뉴">\n'
        '      <ol class="nav-list">\n        ' + "\n        ".join(rows) + "\n      </ol>\n"
        '    </nav>\n'
        '    <div class="nav-meta">\n'
        '      <div class="nav-meta-col">\n'
        '        <p class="nav-meta-label">CONSULT</p>\n'
        f'        <a href="{esc(config["consultUrl"])}" target="_blank" rel="noopener noreferrer">'
        f'{esc(config["consultLabel"])} →</a>\n'
        f'        <a href="tel:{esc(business["phone"])}">{esc(business["phone"])}</a>\n'
        f'        <a href="mailto:{esc(business["email"])}">{esc(business["email"])}</a>\n'
        '      </div>\n'
        '      <div class="nav-meta-col">\n'
        '        <p class="nav-meta-label">STUDIO</p>\n'
        f'        <p>{esc(business["address"])}</p>\n'
        f'        <p>사업자등록번호 {esc(business["registrationNumber"])}</p>\n'
        '      </div>\n'
        '    </div>\n'
        '  </div>\n'
        '</div>'
    )


def organization_jsonld(config: dict) -> dict:
    business = config["business"]
    data = {
        "@context": "https://schema.org",
        "@type": "ProfessionalService",
        "@id": url_for(config, "/#organization"),
        "name": config["siteName"],
        "alternateName": config["siteNameKo"],
        "slogan": config["slogan"],
        "url": url_for(config, "/"),
        "logo": url_for(config, "/assets/images/logo.png"),
        "image": url_for(config, "/assets/images/logo.png"),
        "description": config["description"],
        "address": {
            "@type": "PostalAddress",
            "addressCountry": "KR",
            "addressRegion": "경기도",
            "addressLocality": "용인시",
            "streetAddress": business["address"],
        },
        "areaServed": [{"@type": "AdministrativeArea", "name": region} for region in config["regions"]],
        "knowsAbout": [service["title"] for service in config["services"]],
        "sameAs": [config["consultUrl"]],
        "priceRange": "무료 점검 0원 · 입문 첫 세팅 5만 원~ · 월간 브랜드 관리 월 30만 원~",
    }
    if not business["email"].startswith("["):
        data["email"] = business["email"]
    if not business["phone"].startswith("["):
        data["telephone"] = business["phone"]
    return data


def jsonld_block(*objects: dict) -> str:
    blocks = []
    for obj in objects:
        if not obj:
            continue
        payload = json.dumps(obj, ensure_ascii=False, indent=2)
        payload = payload.replace("</", "<\\/")
        blocks.append(f'<script type="application/ld+json">\n{payload}\n</script>')
    return "\n".join(blocks)


# --------------------------------------------------------------------------
# 페이지 조각
# --------------------------------------------------------------------------
def cta_box(config: dict, variant: str = "inline") -> str:
    return f"""<aside class="cta-box cta-box--{variant}" aria-label="무료 3가지 점검 안내">
  <div class="cta-box-text">
    <p class="cta-box-kicker">FREE CHECK <span aria-hidden="true">/</span> 무료 3가지 점검</p>
    <p class="cta-box-title">가게 이름이나 플레이스 링크만 보내 주시면, 빠진 정보와 바로 고칠 3가지를 정리해 드립니다.</p>
    <p class="cta-box-sub">0원 · 카톡으로 전달하면 24시간 내 요약 · 영업 전화 없음</p>
  </div>
  <div class="cta-box-actions">
    <a class="btn btn--kakao" href="{esc(config['consultUrl'])}" target="_blank" rel="noopener noreferrer">
      카톡으로 3가지 무료 점검<span aria-hidden="true"> →</span><span class="sr-only"> (카카오톡 채널, 새 탭에서 열림)</span>
    </a>
  </div>
</aside>"""


def post_card(config: dict, post: dict, *, eager: bool = False, heading_level: str = "h3",
              excerpt: bool = True) -> str:
    media = ""
    if post["cover"]:
        media = (f'<a class="card-media" href="{post["path"]}" tabindex="-1" aria-hidden="true">'
                 + picture(post["cover"], post["cover_alt"], eager=eager,
                           sizes="(max-width: 720px) 100vw, (max-width: 1200px) 50vw, 420px")
                 + "</a>")
    text = f'\n    <p class="card-text">{esc(post["description"])}</p>' if excerpt else ""
    return f"""<article class="card" data-category="{esc(post['category'])}">
  {media}
  <div class="card-body">
    <p class="card-meta"><span class="card-cat">{esc(post['category'])}</span><span class="card-sep" aria-hidden="true">/</span><time datetime="{post['date'].isoformat()}">{post['date'].strftime('%Y.%m.%d')}</time><span class="card-sep" aria-hidden="true">/</span><span>읽기 {post['reading_time']}분</span></p>
    <{heading_level} class="card-title"><a href="{post['path']}">{esc(post['title'])}</a></{heading_level}>{text}
    <span class="card-link" aria-hidden="true">READ <span>→</span></span>
  </div>
</article>"""


def toc_html(post: dict, consult_url: str) -> str:
    if len(post["headings"]) < 2:
        return ""
    items = "".join(f'<li><a href="#{h["id"]}">{esc(h["text"])}</a></li>' for h in post["headings"])
    count = len(post["headings"])
    # 모바일(980px 이하)에서는 기본 접힘 — <button> 토글로 펼칩니다. PC 에서는 버튼을 숨기고 목록을 그대로 둡니다.
    return f"""<nav class="toc is-collapsed" aria-label="이 글의 목차">
  <button class="toc-toggle" type="button" aria-expanded="false" aria-controls="toc-panel">
    <span class="toc-toggle-text">목차 보기 <span class="toc-toggle-count">({count})</span></span>
    <span class="toc-toggle-icon" aria-hidden="true"></span>
  </button>
  <div class="toc-panel" id="toc-panel">
    <p class="toc-title">CONTENTS</p>
    <ol class="toc-list">{items}</ol>
    <a class="toc-cta" href="{esc(consult_url)}" target="_blank" rel="noopener noreferrer">카카오톡으로 질문하기 <span aria-hidden="true">→</span></a>
  </div>
</nav>"""


# --------------------------------------------------------------------------
# 페이지 빌드
# --------------------------------------------------------------------------
def write(path: str, content: str, depth: int = 0, root_absolute: bool = False) -> None:
    """파일을 쓰기 전에 사이트 내부 절대 경로(/assets/...)를 상대 경로로 바꿉니다.

    GitHub Pages 처럼 /저장소명/ 하위 경로에 배포해도 CSS·이미지·링크가 그대로 동작합니다.
    canonical, OG, JSON-LD 의 절대 URL(https://...)은 건드리지 않습니다.

    root_absolute=True 면 변환하지 않고 루트 절대 경로(/assets/...)를 그대로 둡니다.
    404.html 은 어떤 주소 깊이에서도 로드되므로(예: /foo/bar/baz/) 상대 경로를 쓸 수 없습니다.
    """
    prefix = "../" * depth if depth else "./"

    def rewrite(match: re.Match) -> str:
        attr, value = match.group(1), match.group(2)
        if attr == "srcset":
            parts = []
            for part in value.split(","):
                bit = part.strip()
                if not bit:
                    continue
                if bit.startswith("/"):
                    bit = prefix + bit[1:]
                parts.append(bit)
            return f'{attr}="{esc(", ".join(parts))}"'
        return f'{attr}="{prefix}{value[1:]}"'

    content = re.sub(r'(href|src|srcset)="(/[^"]*)"', rewrite, content) if not root_absolute else content
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(content)


SAMPLES = [
    {
        "tag": "01 — NAVER PLACE",
        "title": "네이버 플레이스 첫인상·공지·주차/영업시간 정리",
        "line": "손님이 첫 화면에서 ‘오늘 열었나, 차 가져가도 되나’를 다시 묻지 않아도 되게 만듭니다.",
        "before": [
            ("영업시간", "매일 10:00–22:00, 한 줄만"),
            ("주차", "안내 없음"),
            ("공지", "비어 있음"),
            ("대표 사진", "메뉴판 사진 1장"),
        ],
        "after": [
            ("영업시간", "요일별 시간 + 라스트오더 21:20"),
            ("주차", "매장 앞 3대, 발렛 없음"),
            ("공지", "이번 주 예약 마감일·신메뉴"),
            ("대표 사진", "외관 + 대표 메뉴 2장"),
        ],
    },
    {
        "tag": "02 — CONTENT SET",
        "title": "사장님이 갖고 계신 사진으로 만든 블로그·인스타·안내문 한 세트",
        "line": "촬영을 새로 잡지 않아도 됩니다. 이미 갖고 계신 사진에서 쓸 수 있는 것부터 골라 냅니다.",
        "before": [
            ("사진", "휴대폰 사진 40장, 보정 없이 그대로"),
            ("글", "3편, 말투와 가격 표기가 제각각"),
            ("안내문", "없음"),
        ],
        "after": [
            ("사진", "10장 선별, 밝기·색 통일"),
            ("글", "블로그 1편 + 인스타 3장"),
            ("안내문", "A4 1장, 매장에 바로 게시"),
            ("문구", "가격·영업시간을 한 곳에서 통일"),
        ],
    },
    {
        "tag": "03 — INQUIRY",
        "title": "손님이 묻기 전에 답하는 예약·가격·오시는 길 문구 정리",
        "line": "같은 질문에 매번 답하지 않도록, 답을 먼저 적어 둡니다. 상담 전에 확인하는 시간도 줄어듭니다.",
        "before": [
            ("단골 질문", "‘주차 되나요?’ ‘예약 돼요?’ ‘얼마예요?’"),
            ("답변", "받는 사람마다 다름"),
            ("오시는 길", "설명 없음"),
        ],
        "after": [
            ("예약", "네이버 예약·전화 중 하나로 통일"),
            ("가격", "대표 메뉴 3개 기준으로 표기"),
            ("오시는 길", "주차·대중교통을 한 문단으로"),
        ],
    },
]


def sample_html(sample: dict, index: int) -> str:
    def rows(items: list[tuple[str, str]]) -> str:
        return "".join(
            f'<div class="ba-row"><span class="ba-key">{esc(key)}</span>'
            f'<span class="ba-val">{esc(value)}</span></div>'
            for key, value in items
        )

    return f"""<article class="sample" data-reveal>
  <div class="sample-head">
    <p class="sample-no">{esc(sample['tag'])}</p>
    <h3 class="sample-title">{esc(sample['title'])}</h3>
    <p class="sample-line">{esc(sample['line'])}</p>
  </div>
  <div class="ba">
    <div class="ba-panel ba-panel--before">
      <p class="ba-label">BEFORE <span>정리 전</span></p>
      <div class="ba-rows">{rows(sample['before'])}</div>
    </div>
    <div class="ba-panel ba-panel--after">
      <p class="ba-label">AFTER <span>정리 후</span></p>
      <div class="ba-rows">{rows(sample['after'])}</div>
    </div>
  </div>
  <p class="sample-note">※ 예시 구성입니다. 실제 매장 화면 캡처가 아니며, 항목은 매장마다 달라집니다.</p>
</article>"""


HOME_FAQ = [
    (
        "무료 3가지 점검은 무엇을 보나요?",
        "플레이스의 빠진 정보(영업시간·주차·대표 사진·공지), 블로그 첫 화면(첫 문단·글 순서·플레이스와의 정보 일치), "
        "손님이 반복해서 묻는 문의(예약·가격·오시는 길)를 봅니다. 가게 이름이나 플레이스 링크만 보내 주시면 되고, "
        "영업 전화는 걸지 않습니다.",
    ),
    (
        "현장 촬영 없이 폰 사진만으로도 제작이 되나요?",
        "됩니다. 보유하신 매장 사진·메뉴판·짧은 영상으로 기획·제작하고, 밝기와 색 보정, 편집까지 한 세트로 만듭니다. "
        "현장 촬영이 꼭 필요한 경우에만 별도로 협의합니다.",
    ),
    (
        "단발 입문 작업과 월간 관리는 어떻게 다른가요?",
        "입문 첫 세팅은 신규 고객이 기준을 확인하는 1건짜리 작업입니다. 사전에 정한 범위에서 플레이스·공지·글·이미지 1세트를 정리하고 "
        "수정은 1회까지 들어갑니다(기준 5만 원~, 추가 제작은 별도 견적). "
        "월간 브랜드 관리는 기획·발행·점검을 매달 이어가는 방식으로 기본형이 월 30만 원~이고, 블로그·숏폼 통합이나 신규 브랜드 홍보, "
        "경영컨설팅은 매장 규모와 목표를 보고 진단 후 맞춤 견적을 냅니다. 처음에는 입문 세팅으로 기준을 확인하시고, "
        "필요할 때 월간으로 넓히시는 편이 일반적입니다.",
    ),
    (
        "수정 횟수와 원본 파일 제공 기준은 어떻게 되나요?",
        "작업 범위에 따라 다릅니다. 입문 첫 세팅은 수정 1회가 기준이고, 월간·패키지 작업은 사전 견적서에 수정 횟수와 원본 파일 제공 범위를 함께 적어 안내드립니다. "
        "그 범위 안에서 진행하고, 견적 밖의 추가 수정은 시작 전에 금액을 먼저 알려 드립니다.",
    ),
    (
        "세금계산서 발행이 가능한가요?",
        "가능합니다. 일반과세자 개인사업자(노티스랩, 사업자등록번호 266-76-00532)로 전자세금계산서를 발행합니다. "
        "결제 조건과 발행 시점은 견적을 확정할 때 함께 안내드립니다.",
    ),
    (
        "상위 노출이나 매출 증가를 보장해 주나요?",
        "보장하지 않습니다. 검색 순위와 매출은 저희가 통제할 수 없는 부분이 있습니다. "
        "대신 확인한 문제와 바꾼 지점, 다음 달에 확인할 지표를 근거로 남깁니다. 확인되지 않은 수치나 후기는 쓰지 않습니다.",
    ),
    (
        "용인 외 타 지역도 진행할 수 있나요?",
        "가능합니다. 용인·수원·화성·성남 등 경기 남부에서 시작해 수도권과 전국까지 진행합니다. "
        "원거리는 자료 정리와 화상 미팅으로 상담을 대신하고, 발행과 세팅은 원격으로 처리합니다.",
    ),
]


def home_faq_jsonld(config: dict) -> dict:
    """홈의 FAQ 섹션(templates/home.html)과 같은 문답을 FAQPage 스키마로 출력합니다."""
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "@id": url_for(config, "/#faq"),
        "mainEntity": [
            {
                "@type": "Question",
                "name": question,
                "acceptedAnswer": {"@type": "Answer", "text": answer},
            }
            for question, answer in HOME_FAQ
        ],
    }


def build_home(config: dict, posts: list[dict], base: dict) -> str:
    steps = [
        ("SEARCH", "검색", "손님이 실제로 입력하는 조건에서 시작합니다. 업종·지역·상황이 겹치는 검색어를 먼저 찾습니다."),
        ("CONTENT", "콘텐츠", "비교에 필요한 정보를 글로 남깁니다. 가격, 진행 과정, 전후 사진, 자주 묻는 질문까지."),
        ("PLACE", "플레이스", "영업시간·가격·사진을 글과 일치시킵니다. 여기서 어긋나면 읽던 사람이 멈춥니다."),
        ("CONVERSION", "상담·예약", "행동 지점을 하나로 좁힙니다. 카카오톡·전화·예약 중 하나만 남기고 나머지는 뒤로 뺍니다."),
    ]
    arch_items = []
    for index, (en, ko, text) in enumerate(steps, start=1):
        arch_items.append(f"""<li class="arch-step">
  <span class="arch-no" aria-hidden="true">{index:02d}</span>
  <div class="arch-head">
    <p class="arch-en">{en}</p>
    <h3 class="arch-ko">{ko}</h3>
  </div>
  <p class="arch-text">{text}</p>
</li>""")

    service_rows = []
    for index, service in enumerate(config["services"], start=1):
        points = "".join(f"<li>{esc(point)}</li>" for point in service["points"])
        en = service.get("en", "")
        service_rows.append(f"""<li class="service-row">
  <span class="service-no" aria-hidden="true">{index:02d}</span>
  <div class="service-head">
    <p class="service-en">{esc(en)}</p>
    <h3 class="service-title">{esc(service['title'])}</h3>
  </div>
  <p class="service-summary">{esc(service['summary'])}</p>
  <ul class="service-points">{points}</ul>
</li>""")

    region_items = []
    for index, region in enumerate(config["regions"], start=1):
        wide = " region-item--wide" if index > 5 else ""
        region_items.append(
            f'<li class="region-item{wide}"><span class="region-no" aria-hidden="true">{index:02d}</span>'
            f'<span class="region-name">{esc(region)}</span></li>'
        )

    latest = "".join(post_card(config, post, eager=(i == 0), heading_level="h3", excerpt=False)
                     for i, post in enumerate(posts[:3]))

    samples_html = "\n".join(sample_html(sample, index) for index, sample in enumerate(SAMPLES, start=1))

    pricing = config.get("pricing") or {}
    price_rows = []
    for item in pricing.get("items", []):
        free = " price-row--free" if item.get("free") else ""
        price_rows.append(f"""<div class="price-row{free}">
  <p class="price-name"><span class="price-en">{esc(item.get('en', ''))}</span>{esc(item['name'])}</p>
  <p class="price-scope">{esc(item.get('scope', ''))}</p>
  <p class="price-tag">{esc(item['price'])}<small>{esc(item.get('priceNote', ''))}</small></p>
</div>""")
    price_terms = "".join(f"<li>{esc(term)}</li>" for term in pricing.get("terms", []))

    sample_media = picture("/assets/images/hero-atelier.jpg",
                           "긴 자연광이 떨어지는 콘크리트 전시 공간과 유리벽",
                           cls="sample-img", sizes="100vw")
    coverage_media = picture("/assets/images/glass-light-study.jpg",
                             "유리와 강철 패널 사이로 스치는 빛의 결",
                             cls="coverage-img", sizes="(max-width: 900px) 100vw, 46vw")

    content = render_template("home.html", {
        **base,
        "structure_steps": "\n".join(arch_items),
        "services": "\n".join(service_rows),
        "regions": "\n".join(region_items),
        "latest_posts": latest,
        "samples": samples_html,
        "pricing_note": esc(pricing.get("note", "")),
        "pricing_rows": "\n".join(price_rows),
        "pricing_terms": price_terms,
        "sample_media": sample_media,
        "coverage_media": coverage_media,
        "post_count": len(posts),
    })

    jsonld = jsonld_block(
        organization_jsonld(config),
        {
            "@context": "https://schema.org",
            "@type": "WebSite",
            "@id": url_for(config, "/#website"),
            "url": url_for(config, "/"),
            "name": f"{config['siteName']} ({config['siteNameKo']})",
            "inLanguage": "ko-KR",
            "publisher": {"@id": url_for(config, "/#organization")},
        },
        {
            "@context": "https://schema.org",
            "@type": "Blog",
            "@id": url_for(config, "/insights/#blog"),
            "url": url_for(config, "/insights/"),
            "name": f"{config['siteName']} 인사이트",
            "inLanguage": "ko-KR",
            "publisher": {"@id": url_for(config, "/#organization")},
            "blogPost": [
                {
                    "@type": "BlogPosting",
                    "headline": post["title"],
                    "url": url_for(config, post["path"]),
                    "datePublished": post["date"].isoformat(),
                }
                for post in posts[:3]
            ],
        },
        home_faq_jsonld(config),
    )

    context = {
        **base,
        "page_title": f"{config['siteNameKo']} | 소상공인 네이버 플레이스·블로그 무료 3가지 점검",
        "description": ("가게 이름이나 플레이스 링크만 보내 주시면, 빠진 정보와 바로 고칠 3가지를 무료로 정리해 드립니다. "
                        "영업 전화 없이 카톡으로 24시간 내 답하고, 블로그·플레이스·숏폼 제작과 월간 운영을 경기 남부에서 전국까지 진행합니다."),
        "canonical": url_for(config, "/"),
        "og_title": f"{config['siteName']} | {config['slogan']}",
        "og_image": url_for(config, "/assets/images/og-notice-lab-blog-traffic-thumbnail.jpg"),
        "og_image_alt": "노티스랩 공식 홈페이지 대표 이미지",
        "nav": nav_html(config, "home"),
        "jsonld": jsonld,
        "body_class": "page-home",
        "content": content,
    }
    return render_template("base.html", context)


def build_insights_index(config: dict, posts: list[dict], base: dict) -> str:
    categories = config["categories"]
    filters = ['<button class="chip is-active" type="button" data-filter="all" aria-pressed="true">전체 <span class="chip-count">'
               + str(len(posts)) + "</span></button>"]
    for category in categories:
        count = sum(1 for post in posts if post["category"] == category["name"])
        filters.append(
            f'<button class="chip" type="button" data-filter="{esc(category["name"])}" '
            f'data-slug="{esc(category["slug"])}" aria-pressed="false">{esc(category["name"])} '
            f'<span class="chip-count">{count}</span></button>'
        )

    cards = [post_card(config, post, eager=index < 2, heading_level="h2") for index, post in enumerate(posts)]

    content = render_template("insights.html", {
        **base,
        "filters": "".join(filters),
        "cards": "\n".join(cards),
        "post_count": len(posts),
        "category_notes": "".join(
            f'<li><strong>{esc(c["name"])}</strong> {esc(c["description"])}</li>' for c in categories
        ),
    })

    jsonld = jsonld_block(
        organization_jsonld(config),
        {
            "@context": "https://schema.org",
            "@type": "CollectionPage",
            "url": url_for(config, "/insights/"),
            "name": f"{config['siteName']} 인사이트",
            "description": "검색 유입과 문의 전환을 다루는 노티스랩의 실무 글 모음입니다.",
            "inLanguage": "ko-KR",
            "isPartOf": {"@id": url_for(config, "/#website")},
            "mainEntity": {
                "@type": "ItemList",
                "itemListElement": [
                    {
                        "@type": "ListItem",
                        "position": index + 1,
                        "url": url_for(config, post["path"]),
                        "name": post["title"],
                    }
                    for index, post in enumerate(posts)
                ],
            },
        },
        {
            "@context": "https://schema.org",
            "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": 1, "name": "홈", "item": url_for(config, "/")},
                {"@type": "ListItem", "position": 2, "name": "인사이트", "item": url_for(config, "/insights/")},
            ],
        },
    )

    context = {
        **base,
        "page_title": f"블로그 마케팅 인사이트 | {config['siteName']} {config['siteNameKo']}",
        "description": "조회수와 매출 사이의 흐름을 다루는 노티스랩 인사이트입니다. 검색 유입, 블로그 운영, 지역 마케팅, 상담 전환을 실무 기준으로 정리합니다.",
        "canonical": url_for(config, "/insights/"),
        "og_title": f"인사이트 | {config['siteName']}",
        "og_image": url_for(config, "/assets/images/og-notice-lab-blog-traffic-thumbnail.jpg"),
        "og_image_alt": "노티스랩 인사이트 목록 대표 이미지",
        "nav": nav_html(config, "insights"),
        "jsonld": jsonld,
        "body_class": "page-insights",
        "content": content,
    }
    return render_template("base.html", context)


def build_post(config: dict, post: dict, posts: list[dict], base: dict) -> str:
    related = [other for other in posts if other["slug"] in post["related"]]
    related_cards = "".join(post_card(config, other, heading_level="h3") for other in related[:2])
    categories = {category["name"]: category for category in config["categories"]}
    category = categories.get(post["category"], {"slug": "etc", "description": ""})

    body = post["body_html"]
    # 첫 H2 앞에 상단 CTA 삽입
    marker = body.find("<h2")
    top_cta = cta_box(config, "top")
    body = (body[:marker] + top_cta + "\n" + body[marker:]) if marker != -1 else top_cta + body

    article = render_template("post.html", {
        **base,
        "post_title": esc(post["title"]),
        "post_description": esc(post["description"]),
        "post_category": esc(post["category"]),
        "post_category_slug": esc(category["slug"]),
        "post_date": post["date"].strftime("%Y년 %m월 %d일"),
        "post_date_iso": post["date"].isoformat(),
        "post_updated": post["updated"].strftime("%Y년 %m월 %d일"),
        "post_reading_time": post["reading_time"],
        "post_body": body,
        "post_toc": toc_html(post, config["consultUrl"]),
        "post_cover": ('<div class="post-media">'
                       + picture(post["cover"], post["cover_alt"], eager=True, cls="post-cover-img",
                                 sizes="100vw")
                       + "</div>") if post["cover"] else "",
        "post_cover_alt": esc(post["cover_alt"]),
        "post_cta": cta_box(config, "bottom"),
        "related_cards": related_cards,
        "faq_count": len(post["faq"]),
        "post_chars": f"{post['chars']:,}",
    })

    article_jsonld = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": post["title"][:110],
        "description": post["description"],
        "image": [url_for(config, post["og_image"] or post["cover"])],
        "datePublished": post["date"].isoformat(),
        "dateModified": post["updated"].isoformat(),
        "inLanguage": "ko-KR",
        "articleSection": post["category"],
        "keywords": ", ".join(post["keywords"]),
        "wordCount": post["chars"],
        "isAccessibleForFree": True,
        "author": {"@type": "Organization", "name": config["siteName"], "url": url_for(config, "/")},
        "publisher": {
            "@type": "Organization",
            "name": config["siteName"],
            "logo": {"@type": "ImageObject", "url": url_for(config, "/assets/images/logo.png")},
        },
        "mainEntityOfPage": {"@type": "WebPage", "@id": url_for(config, post["path"])},
        "isPartOf": {"@id": url_for(config, "/insights/#blog")},
    }

    faq_jsonld = None
    if post["faq"]:
        faq_jsonld = {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": item["q"],
                    "acceptedAnswer": {"@type": "Answer", "text": item["a"]},
                }
                for item in post["faq"]
            ],
        }

    breadcrumb_jsonld = {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": url_for(config, "/")},
            {"@type": "ListItem", "position": 2, "name": "인사이트", "item": url_for(config, "/insights/")},
            {"@type": "ListItem", "position": 3, "name": post["title"], "item": url_for(config, post["path"])},
        ],
    }

    context = {
        **base,
        "page_title": f"{post['title']} | {config['siteName']}",
        "description": post["description"],
        "canonical": url_for(config, post["path"]),
        "og_type": "article",
        "og_title": post["title"],
        "og_image": url_for(config, post["og_image"] or post["cover"]),
        "og_image_alt": post["og_image_alt"],
        "nav": nav_html(config, "insights"),
        "jsonld": jsonld_block(article_jsonld, faq_jsonld, breadcrumb_jsonld),
        "body_class": "page-post",
        "content": article,
        "published_time": post["date"].isoformat(),
        "modified_time": post["updated"].isoformat(),
        "post_section": esc(post["category"]),
        "post_keywords": esc(", ".join(post["keywords"])),
        "extra_meta": (
            f'<meta property="article:published_time" content="{post["date"].isoformat()}">\n'
            f'<meta property="article:modified_time" content="{post["updated"].isoformat()}">\n'
            f'<meta property="article:section" content="{esc(post["category"])}">\n'
            f'<meta name="keywords" content="{esc(", ".join(post["keywords"]))}">'
        ),
    }
    return render_template("base.html", context)


def build_404(config: dict, base: dict) -> str:
    content = render_template("404.html", {**base})
    context = {
        **base,
        "page_title": f"페이지를 찾을 수 없습니다 | {config['siteName']}",
        "description": "요청하신 페이지가 없습니다. 노티스랩 인사이트나 상담 채널로 이동해 주세요.",
        "canonical": url_for(config, "/404.html"),
        "og_title": "페이지를 찾을 수 없습니다",
        "og_image": url_for(config, "/assets/images/og-notice-lab-blog-traffic-thumbnail.jpg"),
        "og_image_alt": "노티스랩",
        "nav": nav_html(config, ""),
        "jsonld": "",
        "robots": "noindex,follow",
        "body_class": "page-404",
        "content": content,
    }
    return render_template("base.html", context)


# 인스타그램·스레드 프로필 링크용 멀티링크 허브 (/go/)
GO_PATH = "/go/"

# /go/ 버튼 아이콘 — 이모지 대신 쓰는 인라인 SVG. site.json 의 "icon_svg" 값으로 고릅니다.
# currentColor 로 그려서 버튼 글자색(카카오 옐로 버튼은 #191600)을 그대로 따라갑니다.
LINK_ICON_SVGS = {
    # 카카오톡 말풍선 심벌 — 가로로 넓은 둥근 말풍선 + 왼쪽 아래 짧은 꼬리
    "kakaotalk": (
        '<svg class="link-svg" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" '
        'aria-hidden="true" focusable="false">'
        '<ellipse cx="12" cy="10.4" rx="10.1" ry="7.75" fill="currentColor"/>'
        '<path fill="currentColor" d="M4.5 15.3 3 19.9l3.6-3.4Z"/>'
        '</svg>'
    ),
    # 네이버 블로그 엠블럼 — 네이버 그린(#03C75A) 타일 위에 흰 말풍선 + 그린 N
    # 타일 색은 templates/go.html 의 .link-icon--naver 가 칠하고, 이 SVG 는 흰 말풍선과
    # 타일과 같은 그린으로 뚫린 N 만 그립니다.
    "naverblog": (
        '<svg class="link-svg" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg" '
        'aria-hidden="true" focusable="false">'
        '<rect x="1.2" y="2.3" width="21.6" height="15.6" rx="4.2" fill="#fff"/>'
        '<path fill="#fff" d="M5.2 16.9h5.7L4.4 23.1Z"/>'
        '<path fill="#03C75A" d="M8 14.4V6h2.6l3 4.5V6h2.6v8.4h-2.6l-3-4.5v4.5Z"/>'
        '</svg>'
    ),
}

# 아이콘 타일 색 — SVG 이름별로 타일 배경 클래스를 붙입니다.
LINK_ICON_TILES = {
    "naverblog": "naver",
}

GO_DEFAULT_LINKS = [
    {
        "label": "카카오톡 채널 1:1 무료 상담",
        "sub": "가장 빠른 문의 · 매장 진단 요청",
        "url": "https://pf.kakao.com/_xdMIvX/chat",
        "icon_svg": "kakaotalk",
        "primary": True,
    },
    {
        "label": "노티스랩 공식 홈페이지 · 인사이트",
        "sub": "서비스 안내 · 무료 3가지 점검",
        "url": "https://noticelab.pages.dev/",
        "icon": "🌐",
    },
    {
        "label": "노티스랩 네이버 블로그",
        "sub": "네이버 블로그 바로가기",
        "url": "https://blog.naver.com/noticelab",
        "icon_svg": "naverblog",
    },
]


def go_link_rows(config: dict) -> str:
    """site.json 의 linkHub.links 를 /go/ 페이지 버튼 마크업으로 바꿉니다."""
    hub = config.get("linkHub") or {}
    links = hub.get("links") or GO_DEFAULT_LINKS
    rows = []
    for index, link in enumerate(links, start=1):
        url = str(link.get("url", "")).strip()
        if not url:
            continue
        primary = bool(link.get("primary"))
        classes = "link link--primary" if primary else "link"
        icon_name = str(link.get("icon_svg", "")).strip()
        icon_svg = LINK_ICON_SVGS.get(icon_name)
        icon_html = icon_svg if icon_svg else esc(link.get("icon", ""))
        icon_classes = "link-icon"
        tile = LINK_ICON_TILES.get(icon_name)
        if tile and not primary:
            icon_classes += f" link-icon--{tile}"
            classes += f" link--{tile}"
        rows.append(
            f'    <a class="{classes}" href="{esc(url)}" target="_blank" rel="noopener noreferrer">\n'
            f'      <span class="link-no">{index:02d}</span>\n'
            f'      <span class="{icon_classes}" aria-hidden="true">{icon_html}</span>\n'
            '      <span class="link-body">\n'
            f'        <span class="link-label">{esc(link.get("label", ""))}</span>\n'
            f'        <span class="link-sub">{esc(link.get("sub", ""))}</span>\n'
            '      </span>\n'
            '      <span class="link-arrow" aria-hidden="true">→</span>\n'
            '    </a>'
        )
    return "\n".join(rows)


def build_go(config: dict, base: dict) -> str:
    """인스타그램·스레드 프로필에 거는 모바일 우선 멀티링크 허브."""
    business = config["business"]
    hub = config.get("linkHub") or {}
    phone_digits = re.sub(r"[^0-9]", "", business["phone"])
    phone_intl = "+82" + phone_digits.lstrip("0") if phone_digits.startswith("0") else phone_digits
    organization = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": config["siteName"],
        "alternateName": config["siteNameKo"],
        "url": url_for(config, "/"),
        "email": business["email"],
        "telephone": phone_intl,
        "founder": {"@type": "Person", "name": business["ceo"]},
        "slogan": hub.get("slogan", "광고보다 결과, 조회수보다 매출을 연구합니다."),
        "sameAs": [link["url"] for link in (hub.get("links") or GO_DEFAULT_LINKS)
                   if link.get("url") and "noticelab.pages.dev" not in link["url"]],
    }
    context = {
        "page_title": "노티스랩 링크 | NOTICE LAB",
        "description": ("노티스랩 공식 링크 모음입니다. 카카오톡 채널 1:1 무료 상담, "
                        "홈페이지·인사이트, 네이버 블로그로 바로 이동할 수 있습니다."),
        "canonical": url_for(config, GO_PATH),
        "og_title": "NOTICE LAB · 노티스랩 — 링크",
        "og_image": url_for(config, "/assets/images/og-go-linkhub.jpg"),
        "og_image_alt": "NOTICE LAB 노티스랩 링크 — 광고보다 결과, 조회수보다 매출을 연구합니다",
        "jsonld": jsonld_block(organization),
        "region_line": "경기 남부 · 전국",
        "biz_tel": "tel:" + phone_intl,
        "link_rows": go_link_rows(config),
    }
    return render_template("go.html", {**base, **context})


def build_sitemap(config: dict, posts: list[dict]) -> str:
    entries = [
        (url_for(config, "/"), datetime.now(KST).date().isoformat(), "1.0", "weekly"),
        (url_for(config, "/insights/"), datetime.now(KST).date().isoformat(), "0.9", "daily"),
        (url_for(config, GO_PATH), datetime.now(KST).date().isoformat(), "0.7", "monthly"),
    ]
    for post in posts:
        entries.append((url_for(config, post["path"]), post["updated"].date().isoformat(), "0.8", "monthly"))

    rows = []
    for loc, lastmod, priority, changefreq in entries:
        rows.append(
            "  <url>\n"
            f"    <loc>{esc(loc)}</loc>\n"
            f"    <lastmod>{lastmod}</lastmod>\n"
            f"    <changefreq>{changefreq}</changefreq>\n"
            f"    <priority>{priority}</priority>\n"
            "  </url>"
        )
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            + "\n".join(rows) + "\n</urlset>\n")


def build_robots(config: dict) -> str:
    return (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /404.html\n\n"
        f"Sitemap: {url_for(config, '/sitemap.xml')}\n"
    )


def build_llms_txt(config: dict, posts: list[dict]) -> str:
    """AI 검색·요약 엔진이 사이트를 빠르게 이해하도록 만드는 llms.txt (llmstxt.org 관례)."""
    business = config["business"]
    price_bits = [f"{item['name']} {item['price']}" for item in (config.get("pricing") or {}).get("items", [])]
    lines = [
        f"# {config['siteName']} ({config['siteNameKo']})",
        "",
        f"> {config['slogan']} {config['description']}",
        "",
        "## 핵심 정보",
        f"- 대응 지역: {' · '.join(config['regions'])}",
        f"- 업종: {business['industries']}",
        f"- 서비스: {' / '.join(service['title'] for service in config['services'])}",
        "- 제작 원칙: 업체가 제공한 기존 사진·영상을 바탕으로 기획·제작하며, 별도 현장 촬영은 기본 서비스로 제공하지 않습니다.",
        "- 상위 노출, 매출, AI 검색 인용을 보장하지 않습니다.",
        "- 첫 제안: 가게 이름이나 플레이스 링크를 보내면 빠진 정보와 바로 고칠 3가지를 정리해 드립니다(무료, 카톡 전달 시 24시간 내 요약, 영업 전화 없음).",
        f"- 기준 가격: {' / '.join(price_bits)}",
        f"- 상담(카카오톡 채널): {config['consultUrl']}",
        "",
        "## 인사이트",
    ]
    for post in posts:
        lines.append(f"- [{post['title']}]({url_for(config, post['path'])}): {post['description']}")
    return "\n".join(lines) + "\n"


def build_rss(config: dict, posts: list[dict]) -> str:
    latest = max(post["date"] for post in posts) if posts else datetime.now(KST)
    items = []
    for post in posts:
        items.append(f"""    <item>
      <title>{esc(post['title'])}</title>
      <link>{esc(url_for(config, post['path']))}</link>
      <guid isPermaLink="true">{esc(url_for(config, post['path']))}</guid>
      <category>{esc(post['category'])}</category>
      <pubDate>{format_datetime(post['date'])}</pubDate>
      <description>{esc(post['description'])}</description>
    </item>""")

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom">
  <channel>
    <title>{esc(config['siteName'])} 인사이트</title>
    <link>{esc(url_for(config, '/insights/'))}</link>
    <description>{esc(config['description'])}</description>
    <language>ko-KR</language>
    <lastBuildDate>{format_datetime(latest)}</lastBuildDate>
    <atom:link href="{esc(url_for(config, '/rss.xml'))}" rel="self" type="application/rss+xml"/>
{chr(10).join(items)}
  </channel>
</rss>
"""


# --------------------------------------------------------------------------
# 메인
# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(description="NOTICE LAB 정적 사이트 빌드")
    parser.add_argument("--clean", action="store_true", help="dist/를 지우고 새로 빌드")
    parser.add_argument("--quiet", action="store_true", help="결과 요약만 출력")
    args = parser.parse_args()

    config = load_config()
    global IMAGE_INDEX
    IMAGE_INDEX = load_image_index()

    if args.clean and os.path.isdir(DIST_DIR):
        shutil.rmtree(DIST_DIR)

    posts = load_posts()
    if not posts:
        print("[warn] posts/ 에 글이 없습니다", file=sys.stderr)

    base = build_base_context(config)

    # 자산 복사
    if os.path.isdir(ASSETS_DIR):
        for root_dir, _, files in os.walk(ASSETS_DIR):
            for name in files:
                src = os.path.join(root_dir, name)
                rel = os.path.relpath(src, ASSETS_DIR)
                dest = os.path.join(DIST_DIR, "assets", rel)
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                shutil.copy2(src, dest)

    pages: list[tuple[str, str]] = []
    pages.append((os.path.join(DIST_DIR, "index.html"), build_home(config, posts, base)))
    pages.append((os.path.join(DIST_DIR, "insights", "index.html"), build_insights_index(config, posts, base)))
    for post in posts:
        pages.append((os.path.join(DIST_DIR, "insights", post["slug"], "index.html"),
                      build_post(config, post, posts, base)))
    pages.append((os.path.join(DIST_DIR, "404.html"), build_404(config, base)))
    pages.append((os.path.join(DIST_DIR, "go", "index.html"), build_go(config, base)))

    depths = {
        os.path.join(DIST_DIR, "index.html"): 0,
        os.path.join(DIST_DIR, "insights", "index.html"): 1,
        os.path.join(DIST_DIR, "go", "index.html"): 1,
    }
    not_found = os.path.join(DIST_DIR, "404.html")
    for path, content in pages:
        if path == not_found:
            write(path, content, root_absolute=True)
            continue
        depth = depths.get(path, 2)
        write(path, content, depth)

    write(os.path.join(DIST_DIR, "sitemap.xml"), build_sitemap(config, posts))
    write(os.path.join(DIST_DIR, "robots.txt"), build_robots(config))
    write(os.path.join(DIST_DIR, "rss.xml"), build_rss(config, posts))
    write(os.path.join(DIST_DIR, "llms.txt"), build_llms_txt(config, posts))
    write(os.path.join(DIST_DIR, ".nojekyll"), "")

    if not args.quiet:
        print(f"[build] 글 {len(posts)}편, 페이지 {len(pages)}개 -> dist/")
        for post in posts:
            print(f"        {post['slug']}  ({post['category']}, {post['chars']:,}자, FAQ {len(post['faq'])})")
    if "example.com" in config["baseUrl"]:
        print("[warn] site.json 의 baseUrl 이 예시 도메인입니다. 배포 도메인으로 바꾼 뒤 다시 빌드하세요.",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
