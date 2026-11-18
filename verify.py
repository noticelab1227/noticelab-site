#!/usr/bin/env python3
"""dist/ 결과물 검증 스크립트 (표준 라이브러리만 사용).

    python3 verify.py            # 전체 검사, 실패 시 종료 코드 1
    python3 verify.py --verbose  # 경고와 세부 수치까지 출력

검사 항목
  1. HTML 태그 구조(열고 닫힘)와 필수 속성
  2. 내부 링크·이미지 경로가 실제 파일로 존재하는지, 앵커 대상이 있는지
  3. <img> 대체 텍스트, width/height, WebP 소스
  4. title/description/canonical/OG/H1 개수 등 메타데이터
  5. JSON-LD 문법과 Article·FAQPage 스키마, 본문 FAQ와의 일치
  6. sitemap.xml·rss.xml·robots.txt 정합성
  7. 템플릿 변수 잔여물, placeholder, 미사용 이미지
  8. day1 원고 및 글 간 중복도(리라이팅 확인)
"""

from __future__ import annotations

import argparse
import difflib
import json
import os
import posixpath
import re
import sys
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from urllib.parse import unquote, urlparse

ROOT = os.path.dirname(os.path.abspath(__file__))
DIST = os.path.join(ROOT, "dist")
POSTS = os.path.join(ROOT, "posts")
CONFIG = os.path.join(ROOT, "site.json")
DAY1 = os.path.normpath(os.path.join(ROOT, "..", "day1"))
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link",
        "meta", "param", "source", "track", "wbr"}

FAILS: list[str] = []
WARNS: list[str] = []
INFO: list[str] = []


def fail(msg: str) -> None:
    FAILS.append(msg)


def warn(msg: str) -> None:
    WARNS.append(msg)


class PageParser(HTMLParser):
    def __init__(self, path: str):
        super().__init__(convert_charrefs=True)
        self.path = path
        self.stack: list[tuple[str, tuple[int, int]]] = []
        self.ids: set[str] = set()
        self.links: list[tuple[str, tuple[int, int]]] = []
        self.images: list[dict] = []
        self.sources: list[str] = []
        self.meta: dict[str, str] = {}
        self.canonical = ""
        self.title = ""
        self.h1 = 0
        self.h2_ids: list[str] = []
        self.jsonld_texts: list[str] = []
        self._in_title = False
        self._in_script = False
        self._script_type = ""
        self._buffer: list[str] = []
        self.errors: list[str] = []
        self.html_lang = ""

    def handle_starttag(self, tag, attrs):
        attrs_d = {key: (value or "") for key, value in attrs}
        pos = self.getpos()
        if tag == "html":
            self.html_lang = attrs_d.get("lang", "")
        if tag == "title":
            self._in_title = True
        if tag == "script":
            self._in_script = True
            self._script_type = attrs_d.get("type", "")
            self._buffer = []
        if "id" in attrs_d:
            if attrs_d["id"] in self.ids:
                self.errors.append(f"{pos} 중복 id '{attrs_d['id']}'")
            self.ids.add(attrs_d["id"])
        if tag == "h1":
            self.h1 += 1
        if tag == "h2" and attrs_d.get("id"):
            self.h2_ids.append(attrs_d["id"])
        if tag in {"a", "link"} and attrs_d.get("href"):
            self.links.append((attrs_d["href"], pos))
            if tag == "link" and "canonical" in attrs_d.get("rel", ""):
                self.canonical = attrs_d["href"]
        if tag == "img":
            self.images.append({"src": attrs_d.get("src", ""), "alt": attrs_d.get("alt"),
                                "width": attrs_d.get("width"), "height": attrs_d.get("height"),
                                "pos": pos})
        if tag == "source" and attrs_d.get("srcset"):
            self.sources.extend(part.strip().split(" ")[0] for part in attrs_d["srcset"].split(",") if part.strip())
        if tag == "meta":
            key = attrs_d.get("property") or attrs_d.get("name")
            if key:
                self.meta[key] = attrs_d.get("content", "")
        if tag not in VOID:
            self.stack.append((tag, pos))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID and self.stack and self.stack[-1][0] == tag:
            self.stack.pop()

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        if tag == "script":
            self._in_script = False
            if "ld+json" in self._script_type:
                self.jsonld_texts.append("".join(self._buffer))
        if tag in VOID:
            self.errors.append(f"{self.getpos()} 닫는 태그 </{tag}> 가 있으면 안 됨")
            return
        if not self.stack:
            self.errors.append(f"{self.getpos()} 짝 없는 닫는 태그 </{tag}>")
            return
        open_tag, pos = self.stack.pop()
        if open_tag != tag:
            self.errors.append(f"{self.getpos()} </{tag}> 가 <{open_tag}> ({pos}) 를 닫음")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_script:
            self._buffer.append(data)


def walk_pages() -> list[str]:
    pages = []
    for root_dir, _, files in os.walk(DIST):
        for name in files:
            if name.endswith(".html"):
                pages.append(os.path.join(root_dir, name))
    return sorted(pages)


def dist_rel(path: str) -> str:
    return "/" + os.path.relpath(path, DIST).replace(os.sep, "/")


def resolve_target(url: str, page_path: str) -> str | None:
    """내부 링크를 dist 안의 실제 경로로 변환합니다. 외부 링크면 None."""
    if url.startswith(("mailto:", "tel:", "javascript:")):
        return None
    parsed = urlparse(url)
    if parsed.scheme in ("http", "https"):
        with open(CONFIG, encoding="utf-8") as fh:
            base = json.load(fh)["baseUrl"].rstrip("/")
        if not url.startswith(base):
            return None
        path = parsed.path or "/"
    else:
        path = parsed.path

    if not path:
        target = dist_rel(page_path)
    elif path.startswith("/"):
        target = posixpath.normpath(path)
        if path.endswith("/") and not target.endswith("/"):
            target += "/"
    else:
        base_dir = posixpath.dirname(dist_rel(page_path))
        target = posixpath.normpath(posixpath.join(base_dir, path))
        if path.endswith("/") and not target.endswith("/"):
            target += "/"

    if target == "/" or target.endswith("/"):
        target = target.rstrip("/") + "/index.html"
    return unquote(target)


def normalize(text: str) -> str:
    text = re.sub(r"https?://\S+", " ", text)
    return re.sub(r"[^0-9a-zA-Z가-힣]", "", text)


def shingles(text: str, size: int = 8) -> set[str]:
    return {text[i:i + size] for i in range(len(text) - size + 1)}


def source_texts() -> dict[str, str]:
    texts = {}
    if not os.path.isdir(DAY1):
        return texts
    for name in sorted(os.listdir(DAY1)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(DAY1, name), encoding="utf-8") as fh:
            body = fh.read()
        body = re.sub(r"^---.*?---", "", body, flags=re.S)
        # 발행용 원고(4번 항목)만 비교 대상으로 사용
        match = re.search(r"## 4\..*?(?=\n## 5\.)", body, flags=re.S)
        texts[name] = normalize(match.group(0) if match else body)
    return texts


def check_page(path: str, pages_index: dict[str, PageParser]) -> PageParser:
    parser = PageParser(path)
    with open(path, encoding="utf-8") as fh:
        parser.feed(fh.read())
    parser.close()
    rel = dist_rel(path)

    for error in parser.errors:
        fail(f"{rel}: HTML 구조 오류 — {error}")
    if parser.stack:
        remaining = ", ".join(f"<{tag}>@{pos}" for tag, pos in parser.stack)
        fail(f"{rel}: 닫히지 않은 태그 — {remaining}")

    if parser.html_lang != "ko":
        fail(f"{rel}: html lang 이 'ko' 가 아님 ('{parser.html_lang}')")
    if parser.title.count("|") > 1:
        warn(f"{rel}: title 에 구분자(|)가 여러 개")
    if not parser.title.strip():
        fail(f"{rel}: <title> 없음")
    description = parser.meta.get("description", "")
    if not description:
        fail(f"{rel}: meta description 없음")
    elif not 40 <= len(description) <= 160:
        warn(f"{rel}: meta description 길이 {len(description)}자 (권장 40~120자)")
    if parser.meta.get("robots") in (None, ""):
        fail(f"{rel}: robots 메타 없음")
    if not parser.canonical:
        fail(f"{rel}: rel=canonical 링크 없음")
    elif not parser.canonical.startswith("https://"):
        fail(f"{rel}: canonical 이 https 절대 URL 이 아님 ('{parser.canonical}')")

    required_og = ["og:type", "og:title", "og:description", "og:url", "og:image", "og:image:alt"]
    for key in required_og:
        if key not in parser.meta:
            fail(f"{rel}: {key} 메타 없음")

    if parser.h1 != 1:
        fail(f"{rel}: <h1> 개수가 {parser.h1}개 (정확히 1개여야 함)")

    # 링크
    for href, pos in parser.links:
        if href.startswith("#"):
            if href[1:] and href[1:] not in parser.ids:
                fail(f"{rel}:{pos[0]} 앵커 대상 없음 '{href}'")
            continue
        target = resolve_target(href, path)
        if target is None:
            continue
        fs = os.path.join(DIST, target.lstrip("/"))
        if not os.path.isfile(fs):
            fail(f"{rel}:{pos[0]} 깨진 내부 링크 '{href}' → {target}")

    # 이미지
    for image in parser.images:
        src = image["src"]
        if not src:
            fail(f"{rel}:{image['pos'][0]} src 없는 img")
            continue
        if image["alt"] is None:
            fail(f"{rel}:{image['pos'][0]} alt 없는 img ({src})")
        elif not image["alt"].strip():
            fail(f"{rel}:{image['pos'][0]} alt 가 빈 img ({src})")
        if not image["width"] or not image["height"]:
            warn(f"{rel}:{image['pos'][0]} width/height 없는 img ({src})")
        target = resolve_target(src, path)
        if target and not os.path.isfile(os.path.join(DIST, target.lstrip("/"))):
            fail(f"{rel}:{image['pos'][0]} 이미지 파일 없음 '{src}'")

    for src in parser.sources:
        target = resolve_target(src, path)
        if target and not os.path.isfile(os.path.join(DIST, target.lstrip("/"))):
            fail(f"{rel}: WebP 소스 파일 없음 '{src}'")

    for og_image in [parser.meta.get("og:image", "")]:
        if og_image:
            target = resolve_target(og_image, path)
            if target and not os.path.isfile(os.path.join(DIST, target.lstrip("/"))):
                fail(f"{rel}: og:image 파일 없음 '{og_image}'")

    # 템플릿 잔여물
    with open(path, encoding="utf-8") as fh:
        raw = fh.read()
    if "{{" in raw:
        fail(f"{rel}: 렌더링되지 않은 템플릿 변수가 남아 있음")
    if re.search(r"\b(TODO|FIXME|Lorem ipsum)\b", raw):
        fail(f"{rel}: 임시 문구(TODO/FIXME/Lorem)가 남아 있음")

    # JSON-LD
    for index, text in enumerate(parser.jsonld_texts):
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            fail(f"{rel}: JSON-LD #{index + 1} 문법 오류 — {exc}")
            continue
        if "@context" not in data or "@type" not in data:
            fail(f"{rel}: JSON-LD #{index + 1} 에 @context/@type 누락")
        INFO.append(f"{rel} JSON-LD: {data.get('@type')}")

    return parser


def check_anchor_links(parsed: dict[str, PageParser]) -> None:
    """모든 페이지를 파싱한 뒤, 앵커(#id) 대상이 실제로 있는지 확인합니다."""
    for rel, page in parsed.items():
        for href, pos in page.links:
            if not href.startswith("#"):
                path = os.path.join(DIST, rel.lstrip("/"))
                target = resolve_target(href, path)
                if target is None:
                    continue
                fragment = urlparse(href).fragment
                if not fragment:
                    continue
                target_page = parsed.get(target)
                if target_page and fragment not in target_page.ids:
                    fail(f"{rel}:{pos[0]} 앵커 대상 없음 '{href}'")
                continue
            if href[1:] and href[1:] not in page.ids:
                fail(f"{rel}:{pos[0]} 같은 문서에 앵커 대상 없음 '{href}'")


def check_schema(pages: dict[str, PageParser]) -> None:
    post_files = sorted(os.path.join(POSTS, name) for name in os.listdir(POSTS) if name.endswith(".md"))
    for post_path in post_files:
        with open(post_path, encoding="utf-8") as fh:
            text = fh.read()
        meta_block = text.split("---")[1] if text.startswith("---") else ""
        slug = re.search(r"^slug:\s*(.+)$", meta_block, flags=re.M).group(1).strip()
        rel = f"/insights/{slug}/index.html"
        page = pages.get(rel)
        if not page:
            fail(f"글 페이지가 없습니다: {rel}")
            continue

        types = []
        faq_questions: list[str] = []
        article = None
        for text_block in page.jsonld_texts:
            try:
                data = json.loads(text_block)
            except json.JSONDecodeError:
                continue
            types.append(data.get("@type"))
            if data.get("@type") == "Article":
                article = data
            if data.get("@type") == "FAQPage":
                faq_questions = [item.get("name", "") for item in data.get("mainEntity", [])]

        if "Article" not in types:
            fail(f"{rel}: Article 스키마 없음")
        if "FAQPage" not in types:
            fail(f"{rel}: FAQPage 스키마 없음")
        if "BreadcrumbList" not in types:
            warn(f"{rel}: BreadcrumbList 스키마 없음")
        if article:
            for field in ("headline", "description", "image", "datePublished", "dateModified", "author", "publisher"):
                if not article.get(field):
                    fail(f"{rel}: Article.{field} 누락")
            if len(article.get("headline", "")) > 110:
                warn(f"{rel}: Article.headline 이 110자를 넘음")
        if not faq_questions:
            fail(f"{rel}: FAQPage 문항이 없음")
        elif len(faq_questions) < 3:
            warn(f"{rel}: FAQ 문항이 {len(faq_questions)}개 (3개 권장)")
        # 본문 FAQ 소제목과 스키마 문항 일치 여부
        html = page_text(page=rel)
        body_questions = re.findall(r"<h3 id=\"[^\"]*\">(.*?)<a class=\"anchor\"", html, flags=re.S)
        body_questions = [re.sub(r"<[^>]+>", "", item) for item in body_questions]
        joined = normalize(" ".join(body_questions))
        for question in faq_questions:
            if normalize(question) not in joined:
                fail(f"{rel}: FAQ 스키마 문항이 본문 소제목에 없음 — '{question}'")


def page_text(page: str) -> str:
    path = os.path.join(DIST, page.lstrip("/"))
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def check_sitemap(pages: list[str]) -> None:
    path = os.path.join(DIST, "sitemap.xml")
    if not os.path.exists(path):
        fail("sitemap.xml 없음")
        return
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        fail(f"sitemap.xml XML 문법 오류 — {exc}")
        return
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [loc.text or "" for loc in tree.getroot().findall(".//sm:loc", ns)]
    if not locs:
        fail("sitemap.xml 에 URL 이 없음")
    lastmods = [el.text or "" for el in tree.getroot().findall(".//sm:lastmod", ns)]
    for value in lastmods:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            fail(f"sitemap.xml lastmod 형식 오류 '{value}'")

    with open(CONFIG, encoding="utf-8") as fh:
        base = json.load(fh)["baseUrl"].rstrip("/")
    available = {dist_rel(page) for page in pages}
    for loc in locs:
        if not loc.startswith(base):
            fail(f"sitemap.xml URL 이 baseUrl 과 다름 '{loc}'")
            continue
        path_part = urlparse(loc).path
        target = path_part if path_part.endswith("index.html") else (
            path_part + "index.html" if path_part.endswith("/") else path_part)
        if target not in available:
            fail(f"sitemap.xml 에 실제 페이지가 없는 URL '{loc}'")
    INFO.append(f"sitemap URL {len(locs)}개")


def check_rss() -> None:
    path = os.path.join(DIST, "rss.xml")
    if not os.path.exists(path):
        fail("rss.xml 없음")
        return
    try:
        tree = ET.parse(path)
    except ET.ParseError as exc:
        fail(f"rss.xml XML 문법 오류 — {exc}")
        return
    items = tree.getroot().findall("./channel/item")
    post_files = [name for name in os.listdir(POSTS) if name.endswith(".md")]
    if len(items) != len(post_files):
        fail(f"rss.xml 항목 {len(items)}개 ≠ 글 {len(post_files)}편")
    for item in items:
        title = item.findtext("title") or ""
        link = item.findtext("link") or ""
        if not title or not link:
            fail("rss.xml 항목에 title/link 누락")
        if not item.findtext("pubDate"):
            fail(f"rss.xml '{title}' pubDate 누락")
    INFO.append(f"RSS 항목 {len(items)}개")


def check_robots() -> None:
    path = os.path.join(DIST, "robots.txt")
    if not os.path.exists(path):
        fail("robots.txt 없음")
        return
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    if "Sitemap:" not in text:
        fail("robots.txt 에 Sitemap 지시문 없음")


def check_css_js() -> None:
    css = os.path.join(DIST, "assets", "css", "style.css")
    if not os.path.isfile(css):
        fail("style.css 없음")
        return
    with open(css, encoding="utf-8") as fh:
        text = fh.read()
    if text.count("{") != text.count("}"):
        fail(f"style.css 중괄호 불일치 ({{ {text.count('{')} / }} {text.count('}')})")
    INFO.append(f"CSS {len(text):,}자")

    js = os.path.join(DIST, "assets", "js", "site.js")
    if not os.path.isfile(js):
        fail("site.js 없음")


def check_assets_used(pages: list[str]) -> None:
    """HTML 이 실제로 참조하는 자산과 dist 안의 파일을 대조합니다."""
    referenced: set[str] = set()
    for page in pages:
        html = page_text(dist_rel(page))
        for url in re.findall(r'(?:src|href|srcset)="([^"]+)"', html):
            for part in url.split(","):
                candidate = part.strip().split(" ")[0]
                if not candidate or candidate.startswith("#"):
                    continue
                target = resolve_target(candidate, page)
                if target:
                    referenced.add(target)
        referenced.update(re.findall(r"/assets/images/og-[^\s\"']+?\.jpg", html))

    for root_dir, _, files in os.walk(os.path.join(DIST, "assets")):
        for name in files:
            rel = "/" + os.path.relpath(os.path.join(root_dir, name), DIST).replace(os.sep, "/")
            if rel in {"/assets/css/style.css", "/assets/js/site.js", "/assets/images/derivatives.json"}:
                continue
            if rel not in referenced:
                warn(f"참조되지 않는 자산: {rel}")


def check_duplicates() -> None:
    sources = source_texts()
    posts = []
    for name in sorted(os.listdir(POSTS)):
        if not name.endswith(".md"):
            continue
        with open(os.path.join(POSTS, name), encoding="utf-8") as fh:
            text = fh.read()
        body = text.split("---", 2)[2] if text.startswith("---") else text
        posts.append((name, normalize(body)))

    # 원고별 가장 비슷한 day1 문서와 겹침 비율
    for name, body in posts:
        body_sh = shingles(body)
        worst = (0.0, "")
        for source_name, source in sources.items():
            if not source:
                continue
            source_sh = shingles(source)
            if not source_sh:
                continue
            overlap = len(body_sh & source_sh) / len(source_sh)
            if overlap > worst[0]:
                worst = (overlap, source_name)
        longest = 0
        for source_name, source in sources.items():
            matcher = difflib.SequenceMatcher(None, body, source, autojunk=False)
            block = matcher.find_longest_match(0, len(body), 0, len(source))
            longest = max(longest, block.size)
        INFO.append(f"{name}: day1 최대 8-gram 겹침 {worst[0]:.1%} ({worst[1]}), 최장 일치 {longest}자")
        if worst[0] > 0.20:
            fail(f"{name}: day1 원고와 8-gram 겹침이 {worst[0]:.1%} — 리라이팅이 충분하지 않음")
        elif worst[0] > 0.12:
            warn(f"{name}: day1 원고와 8-gram 겹침 {worst[0]:.1%}")
        if longest > 60:
            fail(f"{name}: day1 원고와 {longest}자가 그대로 일치하는 구간이 있음")

    # 글 사이 중복
    for i in range(len(posts)):
        for j in range(i + 1, len(posts)):
            a, b = shingles(posts[i][1]), shingles(posts[j][1])
            if not a or not b:
                continue
            jaccard = len(a & b) / len(a | b)
            INFO.append(f"{posts[i][0]} ↔ {posts[j][0]} 8-gram 유사도 {jaccard:.1%}")
            if jaccard > 0.08:
                warn(f"{posts[i][0]} ↔ {posts[j][0]} 유사도 {jaccard:.1%}")


def check_placeholders() -> None:
    found: set[str] = set()
    for root_dir, _, files in os.walk(DIST):
        for name in files:
            if not name.endswith(".html"):
                continue
            with open(os.path.join(root_dir, name), encoding="utf-8") as fh:
                html = fh.read()
            found.update(re.findall(r"<span class=\"ph\">([^<]+)</span>", html))
    INFO.append("입력 대기 placeholder: " + (", ".join(sorted(found)) if found else "없음"))
    if found:
        fail("입력 대기 placeholder 가 남아 있습니다: " + ", ".join(sorted(found)))


def check_business_info() -> None:
    """site.json 의 사업자 정보가 푸터에 실제 값으로 들어갔는지 확인합니다."""
    with open(CONFIG, encoding="utf-8") as fh:
        config = json.load(fh)
    business = config["business"]
    with open(os.path.join(DIST, "index.html"), encoding="utf-8") as fh:
        html = fh.read()
    for key, label in (("ceo", "대표"), ("registrationNumber", "사업자등록번호"),
                       ("address", "주소"), ("email", "이메일"), ("phone", "전화")):
        value = str(business.get(key, "")).strip()
        if not value:
            fail(f"사업자 정보 {label}({key}) 가 site.json 에서 비어 있음")
        elif value not in html:
            fail(f"사업자 정보 {label} 값이 홈페이지 푸터에 없음: {value}")
        else:
            INFO.append(f"사업자 정보 {label}: {value}")
    if re.search(r"<dd>\s*</dd>", html):
        fail("푸터에 값이 빈 <dd> 가 있음")
    if "example.com" in html:
        warn("예시 도메인(example.com)이 빌드 결과물에 남아 있음 — 배포 전 site.json 의 baseUrl 확정 필요")


def main() -> int:
    parser = argparse.ArgumentParser(description="NOTICE LAB dist 검증")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    if not os.path.isdir(DIST):
        print("dist/ 가 없습니다. 먼저 python3 build.py 를 실행하세요.", file=sys.stderr)
        return 2

    pages = walk_pages()
    if not pages:
        print("dist/ 에 HTML 이 없습니다.", file=sys.stderr)
        return 2

    parsed: dict[str, PageParser] = {}
    for page in pages:
        parsed[dist_rel(page)] = check_page(page, parsed)

    check_anchor_links(parsed)
    check_schema(parsed)
    check_sitemap(pages)
    check_rss()
    check_robots()
    check_css_js()
    check_assets_used(pages)
    check_duplicates()
    check_placeholders()
    check_business_info()

    print(f"검사한 HTML {len(pages)}개")
    for page in pages:
        print(f"  - {dist_rel(page)}")
    if args.verbose:
        print("\n[정보]")
        for line in INFO:
            print(f"  · {line}")
    if WARNS:
        print(f"\n[경고] {len(WARNS)}건")
        for line in WARNS:
            print(f"  ! {line}")
    if FAILS:
        print(f"\n[실패] {len(FAILS)}건")
        for line in FAILS:
            print(f"  ✗ {line}")
        return 1
    print("\n[통과] 실패 0건" + (f", 경고 {len(WARNS)}건" if WARNS else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
