#!/usr/bin/env python3
"""노티스랩 공식 로고(NL.) 자산 생성 스크립트 (선택 실행).

공식 로고 원본(검은 배경 + 흰색 굵은 기하학 `NL` + 빨간 정사각 점)의 비율을
그대로 옮겨 아래 파일을 만듭니다. Pillow만 있으면 됩니다.

  assets/favicon.svg                    브라우저 파비콘 (벡터)
  assets/images/logo.png                512x512 조직 로고 (JSON-LD publisher.logo)
  assets/images/apple-touch-icon.png    180x180 iOS 홈 화면 아이콘
  assets/images/favicon-32.png          32x32 파비콘 PNG 폴백
  assets/images/og-notice-lab-brand.jpg 1200x630 기본 공유 카드 (NOTICE LAB. + 슬로건)

공식 원본(로고 3종)은 brand/ 에 두고, 이 스크립트가 읽어 사이트용 자산을 만듭니다.

사용:
    python3 scripts/prepare_brand_assets.py
"""

from __future__ import annotations

import os
import sys

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "images")
BRAND_SRC = os.path.join(ROOT, "brand")

# 공식 로고 색: 검정 배경 / 흰 글자 / 빨간 점(사이트 포인트 레드 --coral #FF382C)
BG = (5, 5, 5)
FG = (255, 255, 255)
ACCENT = (255, 56, 44)

# 공식 NL. 심볼의 기하 비율 (원본 이미지 픽셀 측정값을 그대로 사용)
# 기준: 글자 높이 193, 전체 폭 391 (N 0~165 · L 201~327 · 점 353~391)
MARK_W = 391
MARK_H = 194
CAP = 193
STEM = 40


def _shapes() -> tuple[list[tuple[int, int, int, int]], list[list[tuple[int, int]]]]:
    """심볼을 사각형과 다각형으로 분해 (rel 좌표)."""
    rects = [
        (0, 0, STEM, CAP),          # N 왼쪽 기둥
        (125, 0, 165, CAP),         # N 오른쪽 기둥
        (201, 0, 241, CAP),         # L 기둥
        (201, 157, 327, CAP),       # L 발
    ]
    polys = [
        [(0, 0), (STEM, 0), (165, CAP), (125, CAP)],  # N 대각선
    ]
    return rects, polys


def make_icon(size: int, mark_ratio: float, *, ss: int = 4) -> Image.Image:
    canvas = Image.new("RGB", (size * ss, size * ss), BG)
    draw = ImageDraw.Draw(canvas)
    rects, polys = _shapes()

    mark_w = size * ss * mark_ratio
    s = mark_w / MARK_W
    ox = (size * ss - mark_w) / 2
    oy = (size * ss - MARK_H * s) / 2

    def X(v: float) -> float:
        return ox + v * s

    def Y(v: float) -> float:
        return oy + v * s

    for x0, y0, x1, y1 in rects:
        draw.rectangle((X(x0), Y(y0), X(x1) - 1, Y(y1) - 1), fill=FG)
    for pts in polys:
        draw.polygon([(X(x), Y(y)) for x, y in pts], fill=FG)
    # 빨간 정사각 점 (353,156)-(391,194)
    draw.rectangle((X(353), Y(156), X(391) - 1, Y(194) - 1), fill=ACCENT)
    return canvas.resize((size, size), Image.LANCZOS)


def make_favicon_svg(size: int = 64, mark_ratio: float = 0.84) -> str:
    rects, polys = _shapes()
    mark_w = size * mark_ratio
    s = mark_w / MARK_W
    ox = (size - mark_w) / 2
    oy = (size - MARK_H * s) / 2

    def r(v: float) -> str:
        return f"{v:.2f}".rstrip("0").rstrip(".")

    body = []
    for x0, y0, x1, y1 in rects:
        body.append(
            f'  <rect x="{r(ox + x0 * s)}" y="{r(oy + y0 * s)}" '
            f'width="{r((x1 - x0) * s)}" height="{r((y1 - y0) * s)}" fill="#FFFFFF"/>'
        )
    for pts in polys:
        d = " ".join(f"{r(ox + x * s)},{r(oy + y * s)}" for x, y in pts)
        body.append(f'  <polygon points="{d}" fill="#FFFFFF"/>')
    body.append(
        f'  <rect x="{r(ox + 353 * s)}" y="{r(oy + 156 * s)}" '
        f'width="{r(38 * s)}" height="{r(38 * s)}" fill="#FF382C"/>'
    )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {size} {size}" '
        'role="img" aria-label="NOTICE LAB">\n'
        f'  <rect width="{size}" height="{size}" rx="{r(size * 0.1875)}" fill="#050505"/>\n'
        + "\n".join(body)
        + "\n</svg>\n"
    )


def make_brand_og(src: str, dst: str, bg=(6, 6, 6)) -> str:
    """공식 락업(NOTICE LAB. + 슬로건)을 1200x630 공유 카드로.

    원본 JPEG의 검은 배경은 미세한 노이즈가 있어 그대로 붙이면 사각 경계가 보입니다.
    글자 획(휘도 24 이상)만 남기고 배경은 카드 배경색으로 평탄화해 이음매 없이 얹습니다.
    """
    base = Image.open(src).convert("RGB")
    # 원본 1202x800 안의 로고 덩어리(143,255)-(1074,539) + 20px 여백
    crop = base.crop((123, 235, 1095, 560))
    px = crop.load()
    w, h = crop.size
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if max(r, g, b) < 24:
                px[x, y] = bg
    canvas = Image.new("RGB", (1200, 630), bg)
    canvas.paste(crop, ((1200 - w) // 2, (630 - h) // 2))
    canvas.save(dst, "JPEG", quality=92, optimize=True, progressive=True)
    return dst


def main() -> int:
    os.makedirs(BRAND_SRC, exist_ok=True)

    logo = make_icon(512, 0.62, ss=4)
    logo.save(os.path.join(IMG, "logo.png"), "PNG", optimize=True)
    print("[ok] assets/images/logo.png 512x512")

    touch = make_icon(180, 0.62, ss=6)
    touch.save(os.path.join(IMG, "apple-touch-icon.png"), "PNG", optimize=True)
    print("[ok] assets/images/apple-touch-icon.png 180x180")

    fav = make_icon(32, 0.84, ss=8)
    fav.save(os.path.join(IMG, "favicon-32.png"), "PNG", optimize=True)
    print("[ok] assets/images/favicon-32.png 32x32")

    with open(os.path.join(ROOT, "assets", "favicon.svg"), "w", encoding="utf-8") as fh:
        fh.write(make_favicon_svg())
    print("[ok] assets/favicon.svg")

    src = os.path.join(BRAND_SRC, "notice-lab-lockup-tagline.jpg")
    if os.path.exists(src):
        make_brand_og(src, os.path.join(IMG, "og-notice-lab-brand.jpg"))
        print("[ok] assets/images/og-notice-lab-brand.jpg 1200x630")
    else:
        print(f"[skip] {src} 없음 — OG 카드 생성 건너뜀")
    return 0


if __name__ == "__main__":
    sys.exit(main())
