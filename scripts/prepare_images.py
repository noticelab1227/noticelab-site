#!/usr/bin/env python3
"""이미지 파생본 생성 스크립트 (선택 실행).

빌드(build.py)는 표준 라이브러리만 쓰기 때문에 이미지 변환을 하지 않습니다.
이 스크립트는 Pillow가 설치된 환경에서 한 번만 실행해 아래 파일을 만듭니다.

  assets/images/*-1600.webp   본문·썸네일용 경량 WebP (원본 PNG는 폴백으로 유지)
  assets/images/og-*.jpg      1200x630 Open Graph 카드
  assets/images/logo.png      512x512 조직 로고 (JSON-LD publisher.logo)

사용:
    python3 scripts/prepare_images.py
"""

from __future__ import annotations

import json
import os
import sys

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "images")
FONT_BOLD = "/usr/share/fonts/pickle-hwp/NotoSansCJKkr-Regular.otf"
FONT_ALT = "/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf"

NAVY = (15, 23, 42)
CORAL = (249, 115, 98)
BLUE = (37, 99, 235)
WHITE = (255, 255, 255)
MUTED = (203, 213, 225)

# 원본 → (경량본 최대 폭, OG 카드 문구). OG 문구가 None 이면 카드를 만들지 않습니다.
# OG 카드는 글 대표 이미지(썸네일)에만 붙입니다.
DERIVATIVES = {
    "notice-lab-blog-traffic-thumbnail.png": (
        1600,
        ("조회수는 올랐는데", "문의가 없다면"),
    ),
    "yongin-local-marketing-thumbnail.png": (
        1600,
        ("용인 블로그 마케팅", "생활권 단위로 키워드 나누기"),
    ),
    "year-end-store-sales-thumbnail.png": (
        1200,
        ("카드 결제는 역대 두 번째로 늘었는데", "매장은 왜 조용할까"),
    ),
    "search-content-map-consultation-funnel.png": (1400, None),
    "local-keyword-three-layers.png": (1400, None),
    "year-end-action-checklist-calendar.png": (1400, None),
}


def load_font(size: int) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if os.path.exists(FONT_BOLD) else FONT_ALT
    return ImageFont.truetype(path, size)


def webp_name(name: str, width: int) -> str:
    stem = os.path.splitext(name)[0]
    return f"{stem}-{width}.webp"


def make_webp(name: str, max_width: int) -> str:
    src = os.path.join(IMG, name)
    im = Image.open(src).convert("RGB")
    if im.width > max_width:
        height = round(im.height * max_width / im.width)
        im = im.resize((max_width, height), Image.LANCZOS)
    out = webp_name(name, im.width)
    im.save(os.path.join(IMG, out), "WEBP", quality=82, method=6)
    return out


def wrap_text(draw: ImageDraw.ImageDraw, text: str, font, max_width: int):
    """공백 단위로 줄바꿈하되 한 단어가 넘치면 글자 단위로 자른다."""
    lines, current = [], ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=font) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while draw.textlength(current, font=font) > max_width and len(current) > 1:
            cut = len(current)
            while cut > 1 and draw.textlength(current[:cut], font=font) > max_width:
                cut -= 1
            lines.append(current[:cut])
            current = current[cut:]
    if current:
        lines.append(current)
    return lines


def make_og(name: str, headline) -> str:
    """원본 이미지를 왼쪽 46%에, 네이비 패널에 문구를 얹은 1200x630 카드."""
    base = Image.open(os.path.join(IMG, name)).convert("RGB")
    card = Image.new("RGB", (1200, 630), NAVY)

    # 오른쪽에 원본 이미지를 630 높이에 맞춰 크롭 배치
    target_w = 520
    ratio = max(target_w / base.width, 630 / base.height)
    resized = base.resize((round(base.width * ratio), round(base.height * ratio)), Image.LANCZOS)
    left = (resized.width - target_w) // 2
    top = (resized.height - 630) // 2
    card.paste(resized.crop((left, top, left + target_w, top + 630)), (680, 0))

    # 왼쪽 패널 위 그라데이션 느낌의 사각형
    overlay = Image.new("RGBA", (700, 630), (15, 23, 42, 255))
    card.paste(Image.alpha_composite(card.crop((0, 0, 700, 630)).convert("RGBA"), overlay).convert("RGB"), (0, 0))

    draw = ImageDraw.Draw(card)
    label_font = load_font(24)
    title_font = load_font(52)

    # 브랜드 라인
    draw.text((72, 84), "NOTICE LAB", font=load_font(28), fill=WHITE)
    draw.rounded_rectangle((72, 132, 132, 140), radius=4, fill=CORAL)

    # 문구는 패널 안쪽 폭(560px)에 맞춰 자동 줄바꿈
    wrapped = []
    for chunk in headline:
        wrapped.extend(wrap_text(draw, chunk, title_font, 560))
    block_h = len(wrapped) * (title_font.size + 16) - 16
    y = 340 - block_h // 2
    for line in wrapped:
        draw.text((72, y), line, font=title_font, fill=WHITE)
        y += title_font.size + 16

    draw.text((72, 540), "조회수가 아닌 매출을 연구합니다", font=label_font, fill=MUTED)

    stem = os.path.splitext(name)[0]
    out = f"og-{stem}.jpg"
    card.save(os.path.join(IMG, out), "JPEG", quality=88, optimize=True, progressive=True)
    return out


def make_logo() -> str:
    size = 512
    card = Image.new("RGB", (size, size), NAVY)
    draw = ImageDraw.Draw(card)
    # 공지(notice) 라인 마크: 흰 막대 3개 + 코랄 점
    for i, (x0, x1) in enumerate(((128, 336), (128, 296), (128, 256))):
        y = 170 + i * 66
        draw.rounded_rectangle((x0, y, x1, y + 34), radius=17, fill=WHITE)
    draw.ellipse((330, 330, 386, 386), fill=CORAL)
    out = "logo.png"
    card.save(os.path.join(IMG, out), "PNG", optimize=True)
    return out


def main() -> int:
    manifest = {}
    for name, (max_width, headline) in DERIVATIVES.items():
        src = os.path.join(IMG, name)
        if not os.path.exists(src):
            print(f"[skip] {name} 없음")
            continue
        webp = make_webp(name, max_width)
        og = make_og(name, headline) if headline else None
        manifest[name] = {"webp": webp, "og": og}
        print(f"[ok] {name} -> {webp}" + (f", {og}" if og else ""))
    logo = make_logo()
    print(f"[ok] logo -> {logo}")

    with open(os.path.join(IMG, "derivatives.json"), "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
