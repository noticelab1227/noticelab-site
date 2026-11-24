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


NAV_ITEMS = [
    ("home", "/", "01", "HOME", "홈"),
    ("works", "/portfolio/", "02", "SELECTED WORKS", "작업 사례"),
    ("free-check", "/#free-check", "03", "FREE CHECK", "무료 점검"),
    ("services", "/#services", "04", "WHAT WE DO", "서비스"),
    ("pricing", "/#pricing", "05", "PRICING", "기준 가격"),
    ("experience", "/about/", "06", "OUR EXPERIENCE", "대표 경험"),
    ("insight", "/insights/", "07", "INSIGHT & PROCESS", "연구 노트"),
    ("contact", "/contact/", "08", "LET'S TALK", "상담"),
]

NAV_SERVICE_LINKS = [
    ("/marketing/", "광고·마케팅"),
    ("/consulting/", "경영컨설팅"),
    ("/studio/", "콘텐츠·디자인"),
]

NAV_PAGE_LINKS = [
    ("/portfolio/", "작업 사례"),
    ("/about/", "기업 소개"),
    ("/contact/", "상담 안내"),
    ("/privacy/", "개인정보처리방침"),
    ("/rss.xml", "RSS 구독"),
]


def nav_html(config: dict, active: str) -> str:
    """상단 메뉴. 번호는 홈 섹션 번호(01~08)와 1:1로 맞춥니다."""
    rows = []
    for key, href, number, label, ko in NAV_ITEMS:
        current = ' aria-current="page"' if key == active else ""
        rows.append(
            f'<li class="nav-item"><a class="nav-link" href="{href}"{current}>'
            f'<span class="nav-no">{number}</span>'
            f'<span class="nav-en">{esc(label)}</span>'
            f'<span class="nav-ko">{esc(ko)}</span>'
            f'<span class="nav-arrow" aria-hidden="true">→</span></a></li>'
        )
        if key == "services":
            sub = "".join(
                f'<li><a href="{sub_href}">{esc(sub_ko)}</a></li>'
                for sub_href, sub_ko in NAV_SERVICE_LINKS
            )
            rows.append(f'<li class="nav-sub-item"><ul class="nav-sub">{sub}</ul></li>')

    business = config["business"]
    pages = "".join(
        f'<a href="{href}">{esc(ko)}</a>' for href, ko in NAV_PAGE_LINKS
    )
    return (
        '<div class="nav-overlay" id="site-nav">\n'
        f'  <p class="nav-topline"><span>INDEX</span><span>{esc(config["siteName"])} — {esc(config["siteNameKo"])}</span></p>\n'
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
        '        <p class="nav-meta-label">PAGES</p>\n'
        f'        {pages}\n'
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
        "@type": ["Organization", "ProfessionalService"],
        "@id": url_for(config, "/#organization"),
        "name": config["siteName"],
        "alternateName": config["siteNameKo"],
        "slogan": config["slogan"],
        "url": url_for(config, "/"),
        "logo": url_for(config, "/assets/images/logo.png"),
        "image": url_for(config, "/assets/images/logo.png"),
        "description": config["description"],
        "founder": {"@type": "Person", "name": business["ceo"]},
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
        "priceRange": "무료 점검 0원 · 입문 첫 세팅 5만 원~(VAT 별도) · 월간 브랜드 관리 월 30만 원~(VAT 별도)",
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
    return f"""<aside class="cta-box cta-box--{variant}" aria-label="무료 점검·견적 문의">
  <div class="cta-box-text">
    <p class="cta-box-kicker">FREE CHECK <span aria-hidden="true">/</span> 무료 3가지 점검</p>
    <p class="cta-box-title">가게 이름이나 채널 링크만 보내 주시면, 빠진 정보와 바로 고칠 3가지를 정리해 드립니다.</p>
    <p class="cta-box-sub">0원 · 카톡으로 전달하면 24시간 내 요약 · 영업 전화 없음</p>
  </div>
  <div class="cta-box-actions">
    <a class="btn btn--solid" href="{esc(config['consultUrl'])}" target="_blank" rel="noopener noreferrer">
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
        "매장·브랜드 정보(영업시간·주차·대표 사진·공지), 블로그·콘텐츠(첫 문단·글 순서·채널 간 정보 일치), "
        "문의·예약 동선(예약 방법·가격·오시는 길)을 봅니다. 가게 이름이나 채널 링크만 보내 주시면 되고, 영업 전화는 걸지 않습니다.",
    ),
    (
        "무료 점검만 받고 계약하지 않아도 되나요?",
        "네. 무료 점검은 현재 온라인 홍보 상태를 확인하는 서비스입니다. 유료 작업은 별도로 협의하고, "
        "점검만 받으셔도 계약 의무는 없습니다.",
    ),
    (
        "경영컨설팅만 받을 수 있나요?",
        "네. 경영컨설팅과 광고·마케팅은 각각 상담할 수 있습니다. 컨설팅을 광고·마케팅과 묶어서 구매하도록 강제하지 않습니다.",
    ),
    (
        "단발 작업도 가능한가요?",
        "가능합니다. 필요한 작업 한 건부터 상담합니다. 입문 첫 세팅은 신규 고객 1건·사전 확정 범위·수정 1회 기준으로 "
        "5만 원~(VAT 별도)이고, 범위 밖 추가 제작은 별도 견적입니다.",
    ),
    (
        "월간 관리는 어떻게 운영되나요?",
        "기획·발행·점검을 매달 이어가는 방식입니다. 기본형이 월 30만 원~(VAT 별도)이고, "
        "블로그·숏폼 통합(풀 패키지)·신규 브랜드 홍보·경영컨설팅은 매장 규모와 목표를 보고 진단 후 맞춤 견적을 냅니다.",
    ),
    (
        "세금계산서 발행이 가능한가요?",
        "가능합니다. 일반과세자 개인사업자(노티스랩, 사업자등록번호 266-76-00532)로 전자세금계산서를 발행합니다. "
        "가격표의 금액은 부가가치세(VAT) 별도 기준이라 세금계산서에는 부가세가 함께 기재됩니다.",
    ),
    (
        "상위 노출이나 매출 증가를 보장해 주나요?",
        "보장하지 않습니다. 검색 순위와 매출은 여러 요인의 영향을 받습니다. "
        "대신 확인 가능한 문제와 개선 방향, 바꾼 지점을 근거로 남깁니다. 확인되지 않은 수치나 후기는 쓰지 않습니다.",
    ),
    (
        "기존 매장 사진으로 제작할 수 있나요? 현장 촬영도 되나요?",
        "보유하신 사진과 영상으로 기획·제작합니다. 현장 촬영은 기본 서비스에 포함되지 않고, "
        "꼭 필요한 경우에만 별도로 협의합니다.",
    ),
    (
        "용인 외 타 지역도 진행할 수 있나요?",
        "가능합니다. 용인·수원·화성·성남·경기 광주 등 경기 남부에서 시작해 수도권과 전국까지 진행합니다. "
        "원거리는 자료 정리와 화상 미팅으로 상담을 대신하고, 발행과 세팅은 원격으로 처리합니다.",
    ),
]


def faq_html(items: list[tuple[str, str]], start: int = 1) -> str:
    rows = []
    for index, (question, answer) in enumerate(items, start=start):
        rows.append(f"""<details class="faq-item">
  <summary>
    <span class="faq-no" aria-hidden="true">{index:02d}</span>
    <h3 class="faq-q">{esc(question)}</h3>
    <span class="faq-icon" aria-hidden="true"></span>
  </summary>
  <div class="faq-a">
    <p>{esc(answer)}</p>
  </div>
</details>""")
    return "\n".join(rows)


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


def service_area_html(service: dict, index: int) -> str:
    points = "".join(f"<li>{esc(point)}</li>" for point in service["points"])
    return f"""<li class="area">
  <span class="area-no" aria-hidden="true">{index:02d}</span>
  <div class="area-head">
    <p class="area-en">{esc(service['en'])}</p>
    <h3 class="area-ko">{esc(service['title'])}</h3>
    <p class="area-role">{esc(service['role'])} · {esc(service['ratio'])}%</p>
  </div>
  <div class="area-body">
    <p class="area-text">{esc(service['summary'])}</p>
    <ul class="area-list">{points}</ul>
  </div>
  <a class="area-link" href="{esc(service['href'])}">자세히<span aria-hidden="true"> →</span><span class="sr-only"> ({esc(service['title'])})</span></a>
</li>"""


def mix_html(services: list[dict]) -> str:
    return "\n".join(
        f'<span class="mix-seg" style="--w:{esc(service["ratio"])}%">'
        f'<b>{esc(service["ratio"])}</b><span>{esc(service["title"])}</span></span>'
        for service in services
    )


def build_home(config: dict, posts: list[dict], base: dict) -> str:
    services = config["services"]
    service_rows = "\n".join(service_area_html(service, index) for index, service in enumerate(services, start=1))

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

    content = render_template("home.html", {
        **base,
        "services": service_rows,
        "mix": mix_html(services),
        "latest_posts": latest,
        "samples": samples_html,
        "pricing_note": esc(pricing.get("note", "")),
        "pricing_rows": "\n".join(price_rows),
        "pricing_terms": price_terms,
        "faq_items": faq_html(HOME_FAQ),
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
        "page_title": f"{config['siteNameKo']} | 용인 광고·마케팅·경영컨설팅",
        "description": config["description"],
        "canonical": url_for(config, "/"),
        "og_title": f"{config['siteName']} — {config['slogan']}",
        "og_image": url_for(config, "/assets/images/og-notice-lab-blog-traffic-thumbnail.jpg"),
        "og_image_alt": "노티스랩 — 조회수가 아닌 매출을 연구합니다",
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


# --------------------------------------------------------------------------
# 서브페이지 — MARKETING · CONSULTING · STUDIO · PORTFOLIO · ABOUT · CONTACT · PRIVACY
# --------------------------------------------------------------------------
def sp_list(items: list[str], cls: str = "sp-list") -> str:
    return f'<ul class="{cls}">' + "".join(f"<li>{esc(item)}</li>" for item in items) + "</ul>"


def sp_paras(items: list[str]) -> str:
    return "".join(f"<p>{esc(item)}</p>" for item in items)


def sp_steps(items: list[tuple[str, str, str]]) -> str:
    rows = "".join(
        f'<li class="sp-step"><span class="sp-step-no" aria-hidden="true">{index:02d}</span>'
        f'<div class="sp-step-body"><p class="sp-step-en">{esc(en)}</p>'
        f'<h3 class="sp-step-ko">{esc(ko)}</h3><p class="sp-step-text">{esc(text)}</p></div></li>'
        for index, (en, ko, text) in enumerate(items, start=1)
    )
    return f'<ol class="sp-steps">{rows}</ol>'


def sp_cards(items: list[tuple[str, str, str, list[str]]]) -> str:
    rows = []
    for en, ko, text, points in items:
        rows.append(
            f'<article class="sp-card"><p class="sp-card-en">{esc(en)}</p>'
            f'<h3 class="sp-card-ko">{esc(ko)}</h3><p class="sp-card-text">{esc(text)}</p>'
            f'{sp_list(points, "sp-list sp-list--tight")}</article>'
        )
    return f'<div class="sp-cards">{"".join(rows)}</div>'


def sp_table(rows: list[tuple[str, str]]) -> str:
    body = "".join(f"<div><dt>{esc(key)}</dt><dd>{esc(value)}</dd></div>" for key, value in rows)
    return f'<dl class="sp-table">{body}</dl>'


def sp_block(no: str, label: str, title: str, body: str) -> str:
    return f"""<section class="sp-block">
  <div class="sp-block-head">
    <p class="sp-block-no">{no}</p>
    <p class="sp-block-label">{esc(label)}</p>
    <h2 class="sp-block-title">{title}</h2>
  </div>
  <div class="sp-block-body">{body}</div>
</section>"""


def sp_price(config: dict) -> str:
    items = (config.get("pricing") or {}).get("items", [])
    rows = "".join(
        f'<li><span class="sp-price-en">{esc(item.get("en", ""))}</span>'
        f'<span class="sp-price-name">{esc(item["name"])}</span>'
        f'<span class="sp-price-value">{esc(item["price"])}</span>'
        f'<span class="sp-price-note">{esc(item.get("priceNote", ""))}</span></li>'
        for item in items
    )
    return (
        f'<ol class="sp-price">{rows}</ol>'
        '<p class="sp-note">표시 금액은 부가가치세(VAT) 별도 기준입니다. 작업 기간·수정 횟수·원본 제공 범위는 상품마다 달라 견적서에 함께 적습니다.</p>'
        '<p><a class="sp-link" href="/#pricing">기준 가격과 조건 자세히 보기 →</a></p>'
    )


def page_specs(config: dict) -> list[dict]:
    business = config["business"]
    regions_line = "용인 · 수원 · 화성 · 성남 · 경기 광주 → 수도권 · 전국"

    marketing_faq = [
        ("광고만, 또는 블로그만 맡길 수 있나요?",
         "가능합니다. 블로그·플레이스·콘텐츠·디자인 중 필요한 영역만 골라 상담하실 수 있습니다. "
         "전부 손대는 제안보다 지금 문의가 끊기는 지점 한 곳을 먼저 고치는 편을 택합니다."),
        ("광고비도 대신 집행하나요?",
         "매체 광고 집행은 실제 집행 역량과 계약 조건이 확인된 범위에서만 진행합니다. "
         "광고비는 작업비와 분리해 안내하고, 확인되지 않은 매체나 단가를 약속하지 않습니다."),
        ("최소 계약 기간이 있나요?",
         "단발 작업은 1건부터, 월간 관리는 월 단위로 시작합니다. 해지 조건과 범위는 견적서에 함께 적어 확정합니다."),
        ("결과를 보장해 주나요?",
         "보장하지 않습니다. 검색 순위와 매출은 여러 요인의 영향을 받습니다. "
         "대신 확인 가능한 문제와 바꾼 지점, 다음에 확인할 지표를 근거로 남깁니다."),
        ("용인 외 지역도 진행하나요?",
         "가능합니다. 용인을 시작으로 수원·화성·성남·경기 광주 등 경기 남부, 수도권과 전국까지 진행합니다. "
         "원거리는 자료 정리와 화상 미팅으로 상담을 대신합니다."),
    ]

    consulting_faq = [
        ("경영컨설팅만 받을 수 있나요?",
         "네. 경영컨설팅과 광고·마케팅은 각각 상담할 수 있습니다. 컨설팅을 광고·마케팅과 묶어 구매하도록 강제하지 않습니다."),
        ("무엇을 준비해야 하나요?",
         "사업 현황을 알 수 있는 자료(메뉴·가격표, 운영 채널 링크, 비용 구조 메모)가 있으면 좋습니다. "
         "정리되지 않았어도 상담에서 함께 확인합니다."),
        ("세무·법률 상담도 되나요?",
         "직접 수행하지 않습니다. 세무·법률·회계처럼 별도 자격이 필요한 업무는 해당 전문가를 안내합니다."),
        ("비용은 어떻게 되나요?",
         "진단 범위에 따라 별도 견적을 냅니다. 무료 3가지 점검(0원)은 공개된 온라인 정보를 확인하는 범위이고, "
         "컨설팅은 사업 현황과 수익구조까지 다루므로 범위가 다릅니다."),
    ]

    studio_faq = [
        ("촬영 없이도 제작이 되나요?",
         "됩니다. 보유하신 매장 사진·메뉴판·짧은 영상으로 기획·제작합니다. 현장 촬영은 기본 서비스에 포함되지 않고, "
         "꼭 필요한 경우에만 별도로 협의합니다."),
        ("원본 파일을 받을 수 있나요?",
         "상품별 계약 조건에 적어 안내합니다. 원본 제공 여부와 사용 범위(온라인·인쇄, 기간)를 견적서에 함께 명시합니다."),
        ("수정은 몇 번까지 되나요?",
         "작업 범위에 따라 다릅니다. 입문 첫 세팅은 수정 1회가 기준이고, 그 밖의 작업은 견적서에 횟수를 적습니다. "
         "범위 밖 추가 수정은 시작 전에 금액을 먼저 알려 드립니다."),
        ("어떤 파일을 보내면 되나요?",
         "휴대폰 사진 원본, 짧은 영상, 로고·메뉴판·기존 홍보물이면 충분합니다. 정리되지 않은 상태로 보내셔도 됩니다."),
    ]

    portfolio_faq = [
        ("실제 고객 사례가 없나요?",
         "지금 공개된 작업은 서비스 설명용 예시(D)입니다. 실제 프로젝트가 진행되면 유형·목적·결과물 기준으로 추가하고, "
         "성과는 확인된 경우에만 표시합니다."),
        ("성과 수치는 왜 없나요?",
         "확인되지 않은 매출 상승률·검색 순위·예약 증가율을 표시하지 않습니다. 대신 무엇을 왜 바꿨는지 적습니다."),
        ("제 업종 사례를 볼 수 있나요?",
         "같은 업종의 공개 사례가 없으면, 비슷한 구조의 점검 예시로 설명드립니다. 상담에서 업종을 알려 주세요."),
    ]

    contact_faq = [
        ("상담에 비용이 있나요?",
         "무료 3가지 점검은 0원입니다. 유료 작업은 범위를 확인한 뒤 견적을 내고, 견적 전에는 비용이 발생하지 않습니다."),
        ("전화 상담은 안 하나요?",
         "영업 전화는 걸지 않습니다. 필요하시면 원하실 때 통화나 화상 미팅으로 진행합니다."),
        ("얼마나 걸리나요?",
         "링크를 보내 주시면 24시간 안에 요약을 드립니다. 실제 작업 일정은 견적서에 적어 확정합니다."),
        ("어떤 정보를 보내야 하나요?",
         "업체명과 온라인 채널 링크면 됩니다. 지금 가장 고민되는 부분을 함께 적어 주시면 더 정확하게 봅니다."),
    ]

    marketing_blocks = [
        sp_block("01", "WHAT WE RUN", "맡을 수 있는 일", sp_list([
            "광고대행과 채널별 마케팅 전략",
            "네이버 블로그·카페 운영",
            "네이버 플레이스 정보 정리와 홍보",
            "SNS 콘텐츠 기획·운영",
            "지역 상권 마케팅",
            "SEO·GEO 콘텐츠 전략",
            "고객 유입·전환 동선 개선",
            "브랜드 홍보 캠페인 구성",
        ])),
        sp_block("02", "THE FOUR STEPS", "네 칸으로 봅니다", sp_steps([
            ("SEARCH", "검색",
             "고객이 실제로 입력하는 업종·지역·상황의 말을 먼저 찾습니다. 예쁜 키워드보다 손님이 쓰는 말이 기준입니다."),
            ("CONTENT", "콘텐츠",
             "비교에 필요한 정보를 글로 남깁니다. 가격, 진행 과정, 사진, 자주 묻는 질문까지. 읽는 사람이 결정할 수 있게 씁니다."),
            ("CHANNEL", "플레이스·채널",
             "매장이면 플레이스, 온라인 사업자면 쇼핑몰·홈페이지·SNS. 채널마다 정보가 어긋나지 않게 맞춥니다."),
            ("CONVERSION", "문의·예약",
             "행동 지점을 하나로 좁힙니다. 문의·예약·구매 중 무엇을 남길지 정하고 나머지는 뒤로 뺍니다."),
        ])),
        sp_block("03", "HOW IT RUNS", "일하는 방식",
                 sp_paras([
                     "작업은 필요한 한 건부터 시작합니다. 네 칸을 모두 손대는 제안보다, 지금 문의가 끊기는 지점 한 곳을 먼저 고치는 편을 택합니다.",
                     "범위와 금액은 말이 아니라 견적서에 적어 남깁니다.",
                 ]) + sp_list([
                     "범위를 먼저 적습니다 — 결과물, 수량, 수정 횟수, 일정, VAT 별도 여부",
                     "광고비는 따로 — 매체에 지출되는 비용은 작업비와 분리해 안내",
                     "확인 가능한 지표만 — 노출·유입·문의처럼 확인되는 것만 보고",
                     "채널은 하나로 — 문의 창구를 여러 개 두면 새는 곳이 생깁니다",
                 ])),
        sp_block("04", "WHO IT'S FOR", "이런 분들과 일합니다", sp_list([
            "소상공인·자영업자", "음식점·카페", "숙박·관광 사업자", "뷰티·미용업체",
            "신규 창업자", "온라인 판매 사업자", "개인 브랜드 운영자", "전문 서비스 사업자", "중소기업",
        ], cls="sp-chips")),
        sp_block("05", "PRICE", "기준 가격", sp_price(config)),
    ]

    consulting_blocks = [
        sp_block("01", "WHAT WE LOOK AT", "다루는 것", sp_list([
            "사업 현황과 문제 진단",
            "시장·경쟁업체 분석",
            "고객층과 상품 구성 검토",
            "가격 전략",
            "마케팅 비용과 채널 검토",
            "수익구조 검토",
            "브랜드 포지셔닝",
            "디지털 전환 방향",
        ])),
        sp_block("02", "WHO IT'S FOR", "이런 경우에 찾습니다", sp_list([
            "새로 시작하는 사업의 방향을 정해야 할 때",
            "매출은 있는데 남는 수익이 부족할 때",
            "상품 구성과 가격을 다시 정리해야 할 때",
            "광고비를 어디에 써야 할지 모르겠을 때",
            "우리 브랜드만의 차별화 요소를 찾기 어려울 때",
            "광고·마케팅과 별개로 사업 구조를 점검하고 싶을 때",
        ])),
        sp_block("03", "HOW IT RUNS", "진행 방식", sp_steps([
            ("DIAGNOSIS", "현황 확인",
             "지금의 상품·가격·채널·비용 구조를 확인합니다. 자료가 정리되어 있지 않아도 상담에서 함께 정리합니다."),
            ("ANALYSIS", "문제와 원인 정리",
             "보이는 증상과 원인을 나눠 적습니다. 우선순위를 정해 지금 손댈 것과 나중에 볼 것을 구분합니다."),
            ("PROPOSAL", "개선 방향과 실행 순서",
             "분석 정리, 개선 제안, 실행 순서를 문서로 전달합니다. 실행까지 필요하면 광고·마케팅·제작 범위에서 따로 견적합니다."),
        ])),
        sp_block("04", "SCOPE", "범위와 경계",
                 sp_paras([
                     "세무·법률·회계처럼 별도 자격이 필요한 업무는 직접 수행하지 않습니다. 필요한 경우 해당 전문가를 안내합니다.",
                     "확인되지 않은 자격·실적·인증을 내세우지 않습니다. 컨설팅을 광고·마케팅과 묶어 구매하도록 강제하지도 않습니다.",
                 ])),
        sp_block("05", "FEE", "비용", sp_paras([
            "컨설팅 비용은 진단 범위에 따라 별도 견적을 냅니다. 무료 3가지 점검(0원)은 공개된 온라인 정보를 확인하는 범위이고, "
            "컨설팅은 사업 현황과 수익구조까지 다루므로 범위가 다릅니다.",
            "견적 전에 무엇을 받게 되는지(분석 정리·개선 제안·실행 순서)를 먼저 적어 안내합니다.",
        ])),
    ]

    studio_blocks = [
        sp_block("01", "WHAT WE MAKE", "만드는 것", sp_cards([
            ("TEXT", "글",
             "브랜드 소개, 상품·서비스 설명, 블로그 콘텐츠, 스토리텔링.",
             ["블로그 글·브랜드 소개문", "상품·서비스 설명", "자주 묻는 질문 정리"]),
            ("IMAGE & DESIGN", "이미지·디자인",
             "매장에서 바로 쓰는 홍보물부터 온라인 이미지까지.",
             ["로고·브랜드 디자인", "포스터·메뉴판·배너", "상세페이지·SNS 이미지"]),
            ("VIDEO", "영상",
             "짧은 영상과 브랜드 영상. 보유하신 소재로 기획·편집합니다.",
             ["릴스·클립·쇼츠", "브랜드 홍보 영상", "숏폼 편집"]),
        ])),
        sp_block("02", "HOW WE MAKE", "제작 방식", sp_steps([
            ("ASSETS", "소재 확인", "가지고 계신 사진·영상·기존 홍보물을 먼저 봅니다. 쓸 수 있는 것부터 골라 냅니다."),
            ("PLAN", "기획", "누가 어디서 보게 될 콘텐츠인지 정하고, 목적에 맞춰 구성과 문장을 잡습니다."),
            ("BUILD", "제작", "원고·이미지·영상을 만들고 브랜드 톤에 맞춰 다듬습니다."),
            ("REVIEW", "검수", "가격·영업시간·채널 정보가 서로 어긋나지 않는지 확인합니다."),
            ("DELIVER", "전달", "채널에 바로 쓸 수 있는 형태로 전달하고, 쓰는 방법을 함께 안내합니다."),
        ])),
        sp_block("03", "RIGHTS", "원본과 사용권", sp_paras([
            "원본 파일 제공 여부와 사용 범위(온라인·인쇄, 사용 기간)는 상품별 계약 조건에 적어 안내합니다.",
            "폰트·이미지·음원은 사용 권한이 확인된 것만 씁니다. 별도 구매가 필요한 소재는 시작 전에 알려 드립니다.",
        ])),
        sp_block("04", "PRICE", "기준 가격", sp_price(config)),
    ]

    portfolio_blocks = [
        sp_block("01", "TYPES", "네 가지로 구분합니다", sp_list([
            "A — 노티스랩 공식 프로젝트",
            "B — 대표 블로그·브랜드 협업 콘텐츠",
            "C — 자체 제작 시안",
            "D — 서비스 설명용 작업 예시",
        ])),
        sp_block("02", "CURRENT", "지금 공개된 작업",
                 "<div class=\"samples samples--page\">" + "\n".join(
                     sample_html(sample, index) for index, sample in enumerate(SAMPLES, start=1)
                 ) + "</div>"
                 + '<p class="sp-note">위 세 건은 D — 서비스 설명용 예시입니다. 실제 고객 화면 캡처가 아니며, 항목은 매장마다 달라집니다.</p>'),
        sp_block("03", "HOW TO READ", "읽는 방법", sp_paras([
            "이 페이지는 결과 숫자보다 무엇을 왜 바꿨는지를 먼저 적습니다. 확인되지 않은 매출 상승률·검색 순위·예약 증가율은 표시하지 않습니다.",
            "실제 프로젝트가 진행되면 프로젝트명, 작업 목적, 대상 업종, 제작 방향, 결과물, 확인 가능한 성과를 기준으로 추가합니다.",
        ])),
    ]

    about_blocks = [
        sp_block("01", "STORY", "왜 이 일을 하는가", sp_paras([
            "친구들이 쿠폰을 챙겨 다니지 않던 시절, 저는 따로 쿠폰 주머니를 들고 다니던 사람이었습니다.",
            "같은 제품이라도 어디에서 구매하는 것이 합리적인지, 어떤 혜택을 받을 수 있는지 알아보는 일이 즐거웠습니다.",
            "2007년부터 블로그를 운영하며 다양한 매장과 제품을 경험하고 여러 브랜드와 협업했습니다. 소비자가 어떤 정보를 찾고, 무엇을 비교하며, 어떤 이유로 지갑을 여는지 살펴왔습니다.",
            "하지만 사업자의 입장에서는 또 다른 고민이 있습니다. 매출이 발생한다고 해서 반드시 충분한 마진이 남는 것은 아니고, 좋은 제품과 서비스가 있어도 필요한 정보가 전달되지 않으면 선택받기 어렵습니다.",
            "광고를 더 많이 하는 것보다, 고객이 선택할 이유를 제대로 전달할 수는 없을까. 노티스랩은 그 질문에서 출발했습니다.",
            "광고와 마케팅으로 브랜드를 알리고, 경영컨설팅으로 사업의 방향을 고민하며, 글과 이미지, 영상으로 실행합니다. 소비자의 시선으로 발견하고, 사업자의 입장에서 연구합니다.",
        ])),
        sp_block("02", "SINCE 2007", "블로그 경험은 2007년부터",
                 '<p class="sp-display">BLOG EXPERIENCE<br><b>SINCE 2007.</b></p>'
                 + sp_paras([
                     "2007년부터 축적한 블로그 운영 경험, 소비자의 선택을 연구해 온 콘텐츠 제작 경험이 노티스랩의 출발점입니다.",
                     "SINCE 2007은 대표자의 블로그 운영 경험을 뜻합니다. 노티스랩의 설립연도나 광고대행 시작 연도가 아닙니다.",
                 ])),
        sp_block("03", "ORGANIZATION", "하는 일", sp_list([
            "광고·브랜드 마케팅 (주력, 홈페이지 콘텐츠 비중 50%)",
            "경영컨설팅 (전략, 20%)",
            "콘텐츠·영상 제작 (실행, 15%)",
            "브랜드·시각디자인 (실행, 15%)",
        ]) + '<p class="sp-note">비중은 홈페이지 콘텐츠 구성 기준이며 실제 매출 비중이 아닙니다.</p>'),
        sp_block("04", "IMPACT", "우리의 성장이 누군가의 시작이 되도록",
                 sp_paras([
                     "노티스랩은 소상공인·기업 프로젝트(Track A)로 수익을 만듭니다. 그 수익과 일정의 일부를 신진 예술가, 청년 초기 창업자, 자립준비청년의 첫 홍보물을 만드는 데 쓰는 것을 목표로 합니다(Track B).",
                     "전체 사업의 10% 환원을 목표로 두고 있습니다. 다만 매출·순이익·작업시간 중 어떤 기준으로 산정할지는 확정 전이라, 구체적인 지원 실적이나 확정된 배정으로 표현하지 않습니다.",
                     "처음 일을 시작할 때 필요한 건 거창한 캠페인이 아닙니다. 내 일을 설명하는 소개서 한 장, 검색했을 때 걸리는 최소한의 구조입니다.",
                 ])),
        sp_block("05", "VISION", "장기 목표", sp_paras([
            "기업 비전은 지속 가능한 동반 성장입니다. 일회성 홍보 지원을 넘어, 마케팅·브랜드 디자인·영상 제작 역량을 직접 배우고 활용할 수 있는 실무 교육 기반을 만드는 것을 장기 목표로 둡니다.",
            "고객의 성장이 노티스랩의 성장으로, 노티스랩의 성장이 새로운 도전자의 기회로 이어지게 하는 것이 목표입니다.",
        ])),
        sp_block("06", "COMPANY", "기업 정보", sp_table([
            ("상호", business["name"]),
            ("대표", business["ceo"]),
            ("사업자등록번호", business["registrationNumber"]),
            ("주소", business["address"]),
            ("이메일", business["email"]),
            ("전화", business["phone"]),
            ("업종", business["industries"]),
            ("서비스 지역", regions_line),
        ])),
    ]

    contact_blocks = [
        sp_block("01", "TYPES", "상담 유형", sp_list([
            "무료 온라인 홍보 3가지 점검",
            "광고·마케팅 상담",
            "경영컨설팅 상담",
            "블로그·카페 운영 문의",
            "영상·디자인 제작 문의",
            "기타 브랜드 프로젝트",
        ])),
        sp_block("02", "HOW", "접수 방식", sp_steps([
            ("SEND", "카카오톡으로 보내기",
             "업체명과 채널 링크를 1:1 채팅으로 보내 주세요. 회원가입이나 긴 신청서는 없습니다."),
            ("REPLY", "24시간 내 요약",
             "공개된 정보에서 확인한 것과 바로 고칠 순서를 정리해 답합니다. 영업 전화는 걸지 않습니다."),
            ("TALK", "필요하면 통화·화상",
             "원하실 때만 통화나 화상으로 이어갑니다. 견적과 범위는 문서로 남깁니다."),
        ])),
        sp_block("03", "PREPARE", "미리 준비하면 좋은 것 (선택)", sp_list([
            "업체명 또는 브랜드명",
            "플레이스·블로그·쇼핑몰 등 운영 중인 채널 링크",
            "지금 가장 고민되는 부분",
            "가지고 계신 사진·영상(있으면)",
        ])),
        sp_block("04", "NOT", "하지 않는 것", sp_list([
            "방문 영업·전화 영업",
            "확인되지 않은 실적이나 보장 문구",
            "반복 연락",
            "상담을 위한 회원가입 요구",
        ])),
        sp_block("05", "INFO", "사업자 정보", sp_table([
            ("상호", business["name"]),
            ("대표", business["ceo"]),
            ("사업자등록번호", business["registrationNumber"]),
            ("이메일", business["email"]),
            ("전화", business["phone"]),
            ("주소", business["address"]),
        ])),
    ]

    privacy_blocks = [
        sp_block("01", "COLLECT", "수집하는 정보",
                 sp_paras([
                     "홈페이지는 회원가입이나 신청 폼을 운영하지 않습니다. 상담은 카카오톡 채널에서 진행되며, 이용자가 직접 보내는 정보만 받습니다.",
                 ]) + sp_list([
                     "업체명 또는 브랜드명",
                     "온라인 채널 링크",
                     "상담 내용",
                     "이용자가 알려준 연락처",
                 ])),
        sp_block("02", "PURPOSE", "이용 목적", sp_list([
            "상담 회신과 무료 점검 결과 안내",
            "견적·작업 범위 안내",
            "계약 이후 작업 진행과 결과 전달",
        ])),
        sp_block("03", "RETENTION", "보유 기간", sp_paras([
            "상담이 끝나면 목적이 달성된 정보는 지체 없이 파기합니다. 계약이 진행되면 계약·세무 관련 법령이 정한 기간 동안 보관합니다.",
        ])),
        sp_block("04", "THIRD PARTY", "제3자 제공", sp_paras([
            "상담에서 받은 정보를 제3자에게 제공하지 않습니다. 법령에 따라 요구되는 경우를 제외합니다.",
        ])),
        sp_block("05", "PROCESSOR", "처리 위탁과 국외 이전", sp_paras([
            "상담은 카카오톡 채널에서 진행되어 카카오의 서비스 정책이 함께 적용됩니다. 홈페이지는 Cloudflare의 호스팅과 접속 통계를 사용하며, 페이지 요청 처리 과정에서 접속 정보가 국외 서버로 전송될 수 있습니다.",
        ])),
        sp_block("06", "ANALYTICS", "분석 도구", sp_paras([
            "Cloudflare Web Analytics를 사용합니다. 쿠키를 쓰지 않고 개인을 식별하지 않는 방식의 접속 통계입니다. Google Analytics 4와 Google Tag Manager는 설치하지 않았습니다.",
        ])),
        sp_block("07", "RIGHTS", "이용자의 권리", sp_paras([
            "본인이 제공한 정보의 열람·정정·삭제를 요청할 수 있습니다. 아래 문의처로 알려 주시면 확인 후 처리합니다.",
        ])),
        sp_block("08", "CONTACT", "문의", sp_table([
            ("이메일", business["email"]),
            ("전화", business["phone"]),
            ("상호", business["name"]),
            ("대표", business["ceo"]),
        ]) + '<p class="sp-note">시행일 2026년 11월 25일</p>'),
    ]

    return [
        {
            "key": "marketing",
            "path": "/marketing/",
            "label": "광고·마케팅",
            "mark": "BRAND MARKETING — 01",
            "title": "고객에게 보이는 것에서,<br>고객에게 선택받는 것으로.",
            "lede": "광고·마케팅은 노티스랩의 중심 사업입니다. 검색에서 시작해 문의·예약·구매까지, 브랜드가 고객과 만나는 접점을 정리합니다.",
            "action": "광고·마케팅 상담",
            "secondary": ("/#pricing", "기준 가격 보기"),
            "meta_title": "광고·마케팅 | 노티스랩 — 플레이스·블로그·SEO·GEO",
            "meta_desc": "네이버 플레이스·블로그·카페 운영, SNS 콘텐츠, 지역 상권 마케팅, SEO·GEO, 전환 동선 개선까지. 검색에서 문의까지 이어지는 구조를 설계합니다.",
            "blocks": marketing_blocks,
            "faq": marketing_faq,
            "faq_no": "06",
            "next": [("/consulting/", "BUSINESS CONSULTING", "경영컨설팅"),
                     ("/studio/", "CONTENT STUDIO", "콘텐츠·디자인"),
                     ("/portfolio/", "SELECTED WORKS", "작업 사례")],
            "cta": ("FREE CHECK", "광고비를 더 쓰기 전에,<br>끊긴 지점부터.",
                    "가게 이름이나 채널 링크만 보내 주세요. 공개된 정보에서 개선할 세 가지를 정리해 드립니다."),
            "service": {"name": "광고·브랜드 마케팅", "serviceType": "광고대행 및 브랜드 마케팅"},
        },
        {
            "key": "consulting",
            "path": "/consulting/",
            "label": "경영컨설팅",
            "mark": "BUSINESS CONSULTING — 02",
            "title": "사업의 고민을 분석하고,<br>성장의 방향을 설계합니다.",
            "lede": "경영컨설팅은 광고·마케팅과 별도로 상담할 수 있는 서비스입니다. 사업 현황과 수익구조를 함께 봅니다.",
            "action": "경영컨설팅 상담",
            "secondary": ("/#free-check", "무료 점검 안내"),
            "meta_title": "경영컨설팅 | 노티스랩 — 사업 현황·수익구조·가격 전략",
            "meta_desc": "사업 현황과 문제 진단, 시장·경쟁 분석, 고객층과 상품 구성, 가격과 수익구조 검토. 광고·마케팅과 별도로 상담할 수 있는 경영컨설팅입니다.",
            "blocks": consulting_blocks,
            "faq": consulting_faq,
            "faq_no": "06",
            "next": [("/marketing/", "BRAND MARKETING", "광고·마케팅"),
                     ("/about/", "ABOUT NOTICE LAB", "기업 소개"),
                     ("/contact/", "CONTACT", "상담 안내")],
            "cta": ("BUSINESS CONSULTING", "사업의 고민부터<br>정리해 보겠습니다.",
                    "지금 상황을 알 수 있는 자료가 없어도 됩니다. 확인한 것부터 순서대로 정리합니다."),
            "service": {"name": "경영컨설팅", "serviceType": "경영컨설팅"},
        },
        {
            "key": "studio",
            "path": "/studio/",
            "label": "콘텐츠·디자인",
            "mark": "CONTENT STUDIO — 03",
            "title": "브랜드의 이야기를,<br>고객이 기억하는 콘텐츠로.",
            "lede": "글, 이미지, 영상. 가지고 계신 사진과 영상으로 시작합니다. 현장 촬영은 기본 제공하지 않고, 필요한 경우에만 따로 협의합니다.",
            "action": "콘텐츠 제작 견적 문의",
            "secondary": ("/portfolio/", "작업 사례 보기"),
            "meta_title": "콘텐츠·디자인 | 노티스랩 — 블로그·릴스·포스터·상세페이지",
            "meta_desc": "블로그 콘텐츠, 브랜드 소개, 릴스·클립·쇼츠, 포스터·메뉴판·상세페이지 제작. 보유하신 사진과 영상으로 기획·제작합니다.",
            "blocks": studio_blocks,
            "faq": studio_faq,
            "faq_no": "05",
            "next": [("/portfolio/", "SELECTED WORKS", "작업 사례"),
                     ("/marketing/", "BRAND MARKETING", "광고·마케팅"),
                     ("/contact/", "CONTACT", "상담 안내")],
            "cta": ("CONTENT STUDIO", "가지고 계신 사진으로<br>시작할 수 있습니다.",
                    "매장 사진·메뉴판·짧은 영상만 있으면 첫 세트를 만들 수 있습니다."),
            "service": {"name": "콘텐츠·영상·시각디자인 제작", "serviceType": "콘텐츠 제작 및 시각디자인"},
        },
        {
            "key": "portfolio",
            "path": "/portfolio/",
            "label": "작업 사례",
            "mark": "SELECTED WORKS — 04",
            "title": "SELECTED<br>WORKS.",
            "lede": "작업 유형을 네 가지로 구분해 표시합니다. 확인되지 않은 성과 수치나 실제 고객 화면처럼 보이는 조작은 하지 않습니다.",
            "action": "제작 견적 문의",
            "secondary": ("/#free-check", "무료 점검 안내"),
            "meta_title": "작업 사례 | 노티스랩 — 플레이스·콘텐츠·문의 동선",
            "meta_desc": "노티스랩의 작업 유형과 공개된 작업 예시입니다. 플레이스 정보 정리, 콘텐츠 세트, 문의 동선 개선을 전후 구성으로 보여 드립니다.",
            "blocks": portfolio_blocks,
            "faq": portfolio_faq,
            "faq_no": "04",
            "next": [("/marketing/", "BRAND MARKETING", "광고·마케팅"),
                     ("/studio/", "CONTENT STUDIO", "콘텐츠·디자인"),
                     ("/about/", "ABOUT NOTICE LAB", "기업 소개")],
            "cta": ("PROJECT", "같은 방식으로<br>정리해 보겠습니다.",
                    "업종과 상황이 다르면 바꾸는 항목도 달라집니다. 링크를 보내 주시면 확인한 것부터 정리합니다."),
            "service": {"name": "브랜드 작업 사례", "serviceType": "브랜드 마케팅 제작"},
        },
        {
            "key": "about",
            "path": "/about/",
            "label": "기업 소개",
            "mark": "ABOUT NOTICE LAB — 05",
            "title": "쿠폰 주머니에서 시작된<br>소비자의 시선.",
            "lede": "노티스랩은 소비자의 시선과 사업자의 수익성을 함께 보는 회사입니다. 광고·마케팅을 중심으로 경영컨설팅과 콘텐츠 제작을 연결합니다.",
            "action": "노티스랩에 문의",
            "secondary": ("/insights/", "연구 노트 보기"),
            "meta_title": "기업 소개 | 노티스랩 — 2007년부터 쌓은 소비자의 시선",
            "meta_desc": "쿠폰 주머니에서 시작된 소비자의 시선, 2007년부터 이어온 블로그 경험, 노티스랩의 사회적 가치와 장기 목표를 소개합니다.",
            "blocks": about_blocks,
            "faq": [],
            "next": [("/portfolio/", "SELECTED WORKS", "작업 사례"),
                     ("/marketing/", "BRAND MARKETING", "광고·마케팅"),
                     ("/contact/", "CONTACT", "상담 안내")],
            "cta": ("NOTICE LAB", "브랜드의 이야기를<br>고객이 선택할 이유로.",
                    "소상공인부터 기업까지. 필요한 이야기를 함께 찾아보겠습니다."),
            "page_type": "AboutPage",
        },
        {
            "key": "contact",
            "path": "/contact/",
            "label": "상담 안내",
            "mark": "CONTACT — 06",
            "title": "상담은 카카오톡 채널<br>하나로 받습니다.",
            "lede": "업체명과 온라인 채널 링크만 보내 주세요. 영업 전화는 걸지 않고, 확인한 내용만 정리해 답합니다.",
            "action": "카카오톡 채널 열기",
            "secondary": ("/#free-check", "무료 점검 안내"),
            "meta_title": "상담 안내 | 노티스랩 — 카카오톡 채널 1:1",
            "meta_desc": "업체명과 채널 링크만 보내 주세요. 24시간 내 요약, 영업 전화 없음, 계약 의무 없음. 광고·마케팅과 경영컨설팅 상담을 함께 받습니다.",
            "blocks": contact_blocks,
            "faq": contact_faq,
            "faq_no": "06",
            "next": [("/marketing/", "BRAND MARKETING", "광고·마케팅"),
                     ("/consulting/", "BUSINESS CONSULTING", "경영컨설팅"),
                     ("/about/", "ABOUT NOTICE LAB", "기업 소개")],
            "cta": None,
            "page_type": "ContactPage",
        },
        {
            "key": "privacy",
            "path": "/privacy/",
            "label": "개인정보처리방침",
            "mark": "PRIVACY — 07",
            "title": "개인정보<br>처리방침.",
            "lede": "노티스랩은 상담에 필요한 최소한의 정보만 받습니다. 이 페이지는 실제 운영 방식만 적습니다.",
            "action": "이메일로 문의",
            "secondary": ("/contact/", "상담 안내"),
            "meta_title": "개인정보처리방침 | 노티스랩",
            "meta_desc": "노티스랩 홈페이지와 카카오톡 상담에서 받는 정보의 항목, 이용 목적, 보유 기간, 제3자 제공과 처리 위탁을 안내합니다.",
            "blocks": privacy_blocks,
            "faq": [],
            "next": [("/contact/", "CONTACT", "상담 안내"),
                     ("/about/", "ABOUT NOTICE LAB", "기업 소개"),
                     ("/", "HOME", "홈")],
            "cta": None,
            "page_type": "WebPage",
            "robots": "index,follow",
            "action_href": f'mailto:{business["email"]}',
        },
    ]


def build_page(config: dict, spec: dict, base: dict) -> str:
    faq = spec.get("faq") or []
    blocks = list(spec["blocks"])
    if faq:
        blocks.append(sp_block(spec["faq_no"], "FAQ", "자주 묻는 질문", faq_html(faq)))

    next_html = "".join(
        f'<a href="{href}"><span class="sp-next-en">{esc(en)}</span>'
        f'<span class="sp-next-ko">{esc(ko)}</span>'
        '<span class="sp-next-arrow" aria-hidden="true">→</span></a>'
        for href, en, ko in spec["next"]
    )

    action_href = spec.get("action_href") or config["consultUrl"]
    blank = "" if action_href.startswith("mailto:") else ' target="_blank" rel="noopener noreferrer"'
    sr = "" if action_href.startswith("mailto:") else '<span class="sr-only"> (카카오톡 채널, 새 탭에서 열림)</span>'
    actions = (
        f'<a class="btn btn--solid" href="{esc(action_href)}"{blank}>'
        f'{esc(spec["action"])}<span class="btn-arrow" aria-hidden="true">→</span>{sr}</a>'
        f'<a class="btn btn--line" href="{spec["secondary"][0]}">{esc(spec["secondary"][1])}'
        '<span class="btn-arrow" aria-hidden="true">→</span></a>'
    )

    cta = spec.get("cta")
    if cta:
        closing = f"""<section class="closing closing--page" aria-labelledby="sp-closing-title">
  <div class="wrap closing-inner">
    <p class="closing-label">{esc(cta[0])}</p>
    <h2 class="closing-title" id="sp-closing-title">{cta[1]}</h2>
    <p class="closing-lede">{esc(cta[2])}</p>
    <div class="closing-actions">
      <a class="btn btn--light btn--lg" href="{esc(config['consultUrl'])}" target="_blank" rel="noopener noreferrer">
        카카오톡으로 견적 문의<span class="btn-arrow" aria-hidden="true">→</span><span class="sr-only"> (카카오톡 채널, 새 탭에서 열림)</span>
      </a>
      <a class="btn btn--ghost-light btn--lg" href="{esc(config['consultUrl'])}" target="_blank" rel="noopener noreferrer">
        내 가게 3가지 무료 점검<span class="btn-arrow" aria-hidden="true">→</span><span class="sr-only"> (카카오톡 채널, 새 탭에서 열림)</span>
      </a>
    </div>
    <p class="closing-notes">계약 의무 없음 · 영업 전화 없음 · 24시간 내 요약</p>
  </div>
</section>"""
    else:
        closing = ""

    content = render_template("page.html", {
        **base,
        "sp_label": esc(spec["label"]),
        "sp_mark": esc(spec["mark"]),
        "sp_title": spec["title"],
        "sp_lede": esc(spec["lede"]),
        "sp_actions": actions,
        "sp_blocks": "\n".join(blocks),
        "sp_next": next_html,
        "sp_closing": closing,
    })

    page_type = spec.get("page_type") or "WebPage"
    page_jsonld: dict = {
        "@context": "https://schema.org",
        "@type": page_type,
        "@id": url_for(config, spec["path"]),
        "url": url_for(config, spec["path"]),
        "name": re.sub(r"<br>", " ", spec["meta_title"]),
        "description": spec["meta_desc"],
        "inLanguage": "ko-KR",
        "isPartOf": {"@id": url_for(config, "/#website")},
        "about": {"@id": url_for(config, "/#organization")},
    }
    blocks_jsonld = [organization_jsonld(config), page_jsonld]
    if spec.get("service"):
        blocks_jsonld.append({
            "@context": "https://schema.org",
            "@type": "Service",
            "name": spec["service"]["name"],
            "serviceType": spec["service"]["serviceType"],
            "description": spec["meta_desc"],
            "provider": {"@id": url_for(config, "/#organization")},
            "areaServed": [{"@type": "AdministrativeArea", "name": region} for region in config["regions"]],
            "url": url_for(config, spec["path"]),
        })
    if faq:
        blocks_jsonld.append({
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {"@type": "Question", "name": question,
                 "acceptedAnswer": {"@type": "Answer", "text": answer}}
                for question, answer in faq
            ],
        })
    blocks_jsonld.append({
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "홈", "item": url_for(config, "/")},
            {"@type": "ListItem", "position": 2, "name": spec["label"], "item": url_for(config, spec["path"])},
        ],
    })

    context = {
        **base,
        "page_title": spec["meta_title"],
        "description": spec["meta_desc"],
        "canonical": url_for(config, spec["path"]),
        "og_title": re.sub(r"<br>", " ", spec["title"]),
        "og_image": url_for(config, spec.get("og") or "/assets/images/og-go-linkhub.jpg"),
        "og_image_alt": f"노티스랩 — {spec['label']}",
        "nav": nav_html(config, spec["key"]),
        "jsonld": jsonld_block(*blocks_jsonld),
        "body_class": f"page-sub page-{spec['key']}",
        "robots": spec.get("robots", "index,follow,max-image-preview:large"),
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
        "label": "제작 · 세팅 견적 문의",
        "sub": "필요한 작업 1건(5만 원~)부터 · 카카오톡 1:1",
        "url": "https://pf.kakao.com/_xdMIvX/chat",
        "icon_svg": "kakaotalk",
        "primary": True,
    },
    {
        "label": "내 가게 3가지 무료 점검",
        "sub": "0원 · 링크만 보내면 24시간 내 요약 · 영업 전화 없음",
        "url": "https://pf.kakao.com/_xdMIvX/chat",
        "icon_svg": "kakaotalk",
    },
    {
        "label": "노티스랩 공식 홈페이지",
        "sub": "서비스 · 기준 가격 · 작업 사례 · 연구 노트",
        "url": "https://noticelab.pages.dev/",
        "icon": "🌐",
    },
    {
        "label": "노티스랩 네이버 블로그",
        "sub": "현장 기록과 연구 노트",
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
        "slogan": hub.get("slogan", "조회수가 아닌 매출을 연구합니다."),
        "sameAs": [link["url"] for link in (hub.get("links") or GO_DEFAULT_LINKS)
                   if link.get("url") and "noticelab.pages.dev" not in link["url"]],
    }
    context = {
        "page_title": "노티스랩 링크 | NOTICE LAB",
        "description": ("노티스랩 공식 링크입니다. 제작·세팅 견적 문의와 무료 3가지 점검, "
                        "홈페이지·인사이트, 네이버 블로그로 바로 이동할 수 있습니다."),
        "canonical": url_for(config, GO_PATH),
        "og_title": "NOTICE LAB · 노티스랩 — 링크",
        "og_image": url_for(config, "/assets/images/og-go-linkhub.jpg"),
        "og_image_alt": "NOTICE LAB 노티스랩 링크 — 조회수가 아닌 매출을 연구합니다",
        "jsonld": jsonld_block(organization),
        "region_line": "경기 남부 · 전국",
        "biz_tel": "tel:" + phone_intl,
        "link_rows": go_link_rows(config),
    }
    return render_template("go.html", {**base, **context})


def build_sitemap(config: dict, posts: list[dict]) -> str:
    today = datetime.now(KST).date().isoformat()
    entries = [
        (url_for(config, "/"), today, "1.0", "weekly"),
        (url_for(config, "/marketing/"), today, "0.9", "monthly"),
        (url_for(config, "/consulting/"), today, "0.9", "monthly"),
        (url_for(config, "/studio/"), today, "0.8", "monthly"),
        (url_for(config, "/portfolio/"), today, "0.8", "monthly"),
        (url_for(config, "/about/"), today, "0.7", "monthly"),
        (url_for(config, "/contact/"), today, "0.8", "monthly"),
        (url_for(config, "/insights/"), today, "0.9", "daily"),
        (url_for(config, "/privacy/"), today, "0.3", "yearly"),
        (url_for(config, GO_PATH), today, "0.5", "monthly"),
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
        f"- 영문 포지셔닝: {config.get('positioning', 'BRAND MARKETING & BUSINESS CONSULTING')}",
        f"- 대표 지역: {' · '.join(config['regions'])}",
        f"- 업종: {business['industries']}",
        f"- 서비스: {' / '.join(service['title'] for service in config['services'])}",
        "- 제작 원칙: 업체가 제공한 기존 사진·영상을 바탕으로 기획·제작하며, 별도 현장 촬영은 기본 서비스로 제공하지 않습니다.",
        "- 상위 노출, 매출, AI 검색 인용을 보장하지 않습니다.",
        "- 첫 제안: 가게 이름이나 채널 링크를 보내면 빠진 정보와 바로 고칠 3가지를 정리해 드립니다(무료, 카톡 전달 시 24시간 내 요약, 영업 전화 없음).",
        "- 기준 가격(모든 금액 VAT 별도): " + " / ".join(price_bits),
        "- 입문 첫 세팅: 신규 고객 1건 · 사전 확정 범위 · 수정 1회 기준, 추가 제작은 별도 견적",
        "- 월간 브랜드 관리: 기본형 시작가, 풀 패키지·신규 브랜드 홍보·경영컨설팅은 진단 후 맞춤 견적",
        f"- 상담(카카오톡 채널): {config['consultUrl']}",
        f"- 사업자: {business['name']} / 대표 {business['ceo']} / 사업자등록번호 {business['registrationNumber']}",
        "",
        "## 페이지",
        f"- [홈]({url_for(config, '/')}): 조회수가 아닌 매출을 연구합니다.",
        f"- [광고·마케팅]({url_for(config, '/marketing/')}): 플레이스·블로그·SNS·SEO/GEO·전환 동선",
        f"- [경영컨설팅]({url_for(config, '/consulting/')}): 사업 현황·수익구조·가격 전략 진단",
        f"- [콘텐츠·디자인]({url_for(config, '/studio/')}): 글·이미지·영상 제작",
        f"- [작업 사례]({url_for(config, '/portfolio/')}): 작업 유형과 설명용 예시",
        f"- [기업 소개]({url_for(config, '/about/')}): 2007년부터 이어온 블로그 경험과 사회적 가치",
        f"- [상담]({url_for(config, '/contact/')}): 카카오톡 채널 1:1 접수",
        f"- [개인정보처리방침]({url_for(config, '/privacy/')})",
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
    for spec in page_specs(config):
        slug = spec["path"].strip("/")
        pages.append((os.path.join(DIST_DIR, slug, "index.html"), build_page(config, spec, base)))
    pages.append((os.path.join(DIST_DIR, "insights", "index.html"), build_insights_index(config, posts, base)))
    for post in posts:
        pages.append((os.path.join(DIST_DIR, "insights", post["slug"], "index.html"),
                      build_post(config, post, posts, base)))
    pages.append((os.path.join(DIST_DIR, "404.html"), build_404(config, base)))
    pages.append((os.path.join(DIST_DIR, "go", "index.html"), build_go(config, base)))

    not_found = os.path.join(DIST_DIR, "404.html")
    for path, content in pages:
        if path == not_found:
            write(path, content, root_absolute=True)
            continue
        rel = os.path.relpath(path, DIST_DIR).replace(os.sep, "/")
        write(path, content, rel.count("/"))

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
