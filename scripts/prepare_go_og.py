#!/usr/bin/env python3
"""링크 허브(/go/) 공유 카드(OG 이미지)를 만듭니다.

    python3 scripts/prepare_go_og.py

결과: assets/images/og-go-linkhub.jpg (1200x630)
"""

from __future__ import annotations

import os

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "images", "og-go-linkhub.jpg")

W, H = 1200, 630
WHITE = (255, 255, 255)
PAPER = (247, 247, 245)
INK = (17, 17, 17)
CORAL = (255, 59, 48)
CORAL_INK = (196, 41, 31)
MUTED = (95, 95, 93)
DIM = (132, 132, 127)
HAIR = (229, 229, 227)

FONT_REG = "/usr/share/fonts/pickle-hwp/NotoSansCJKkr-Regular.otf"
FONT_MONO = "/usr/share/fonts/pickle-hwp/NotoSansMonoCJKkr-Regular.otf"


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size)


def text(draw: ImageDraw.ImageDraw, xy, value: str, f: ImageFont.FreeTypeFont,
         fill, spacing: int = 0, bold: int = 0, anchor=None) -> None:
    """자간(spacing)과 가짜 굵기(stroke)를 지원하는 텍스트 그리기."""
    if not spacing and not bold:
        draw.text(xy, value, font=f, fill=fill, anchor=anchor)
        return
    x, y = xy
    for ch in value:
        draw.text((x, y), ch, font=f, fill=fill,
                  stroke_width=bold, stroke_fill=fill, anchor=anchor)
        x += draw.textlength(ch, font=f) + spacing


def line(draw: ImageDraw.ImageDraw, xy, segments, f: ImageFont.FreeTypeFont, bold: int = 0) -> None:
    """색이 섞인 한 줄을 이어서 그립니다: [(글자, 색), ...]."""
    x, y = xy
    for value, color in segments:
        draw.text((x, y), value, font=f, fill=color, stroke_width=bold, stroke_fill=color)
        x += draw.textlength(value, font=f)
    return x


def main() -> int:
    img = Image.new("RGB", (W, H), WHITE)
    draw = ImageDraw.Draw(img)

    # 왼쪽 위 아주 옅은 웜 그레이 (밝은 지면의 여백)
    glow = Image.new("RGB", (W, H), WHITE)
    gdraw = ImageDraw.Draw(glow)
    gdraw.ellipse([-420, -520, 700, 240], fill=(250, 240, 238))
    glow = glow.filter(ImageFilter.GaussianBlur(150))
    img = Image.blend(img, glow, 0.9)
    draw = ImageDraw.Draw(img)

    # 상단 헤어라인 + 라벨
    draw.line([(80, 66), (W - 80, 66)], fill=HAIR, width=1)
    text(draw, (80, 88), "NL. LINK", font(FONT_MONO, 20), CORAL_INK, spacing=4, bold=0)
    right = "경기 남부 · 전국"
    rf = font(FONT_REG, 19)
    text(draw, (W - 80 - draw.textlength(right, font=rf), 88), right, rf, DIM, spacing=1)

    # 브랜드
    text(draw, (78, 150), "NL.", font(FONT_MONO, 40), CORAL_INK, bold=1)
    text(draw, (178, 158), "NOTICE LAB", font(FONT_REG, 30), INK, spacing=10, bold=1)
    text(draw, (470, 160), "·  노티스랩", font(FONT_REG, 26), MUTED, spacing=3)

    # 슬로건
    f1 = font(FONT_REG, 62)
    line(draw, (78, 246), [("광고보다 ", INK), ("결과", CORAL_INK), (",", INK)], f1, bold=1)
    line(draw, (78, 330), [("조회수보다 ", INK), ("매출", CORAL_INK), ("을 연구합니다.", INK)],
         font(FONT_REG, 50), bold=1)

    # 하단 링크 요약
    draw.line([(80, 470), (W - 80, 470)], fill=HAIR, width=1)
    text(draw, (80, 500), "카카오톡 1:1 무료 상담   ·   홈페이지 · 인사이트   ·   네이버 블로그",
         font(FONT_REG, 23), MUTED, spacing=1)

    # 우하단 주소
    addr = "noticelab.pages.dev/go"
    af = font(FONT_MONO, 19)
    text(draw, (W - 80 - draw.textlength(addr, font=af), 500), addr, af, DIM)

    # 코랄 사각 마크
    draw.rectangle([78, 434, 118, 446], fill=CORAL)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, "JPEG", quality=90, optimize=True, progressive=True)
    print(f"[ok] {os.path.relpath(OUT, ROOT)} ({W}x{H})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
