#!/usr/bin/env python3
"""히어로·섹션용 에디토리얼 비주얼 파생본 생성.

원본 PNG(생성 이미지)를 다크 에디토리얼 톤으로 가볍게 그레이딩한 뒤
JPEG 폴백과 여러 폭의 WebP 소스를 만듭니다. (derivatives.json 갱신)

    python3 scripts/prepare_hero_images.py
"""

from __future__ import annotations

import json
import os

from PIL import Image, ImageEnhance

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMG = os.path.join(ROOT, "assets", "images")
DERIVATIVES = os.path.join(IMG, "derivatives.json")

# 원본 PNG -> (출력 베이스 이름, 자르기 비율(w/h) or None, 폭 목록)
JOBS = [
    ("hero-atelier.png", "hero-atelier", None, [1402, 1000, 720]),
    ("glass-light-study.png", "glass-light-study", None, [1122, 760, 520]),
]


def grade(image: Image.Image) -> Image.Image:
    """딥 옵시디언 톤에 맞춰 채도를 살짝 낮추고 대비를 올립니다."""
    image = image.convert("RGB")
    image = ImageEnhance.Color(image).enhance(0.88)
    image = ImageEnhance.Contrast(image).enhance(1.08)
    image = ImageEnhance.Brightness(image).enhance(0.97)
    # 그림자에 아주 옅은 쿨톤을 얹어 브랜드 블랙(#0A0A0C)과 이어지게 합니다.
    overlay = Image.new("RGB", image.size, (10, 12, 20))
    image = Image.blend(image, overlay, 0.06)
    return image


def main() -> int:
    with open(DERIVATIVES, encoding="utf-8") as fh:
        derivatives = json.load(fh)

    for source, base, crop_ratio, widths in JOBS:
        src_path = os.path.join(IMG, source)
        if not os.path.exists(src_path):
            print(f"[skip] {source} 없음")
            continue
        image = grade(Image.open(src_path))
        width, height = image.size
        if crop_ratio:
            target_h = int(round(width / crop_ratio))
            if target_h < height:
                top = (height - target_h) // 2
                image = image.crop((0, top, width, top + target_h))
                width, height = image.size

        jpg_name = f"{base}.jpg"
        image.save(os.path.join(IMG, jpg_name), "JPEG", quality=88, optimize=True,
                   progressive=True)

        entries = []
        for target_w in widths:
            target_w = min(target_w, width)
            target_h = int(round(height * target_w / width))
            resized = image.resize((target_w, target_h), Image.LANCZOS)
            webp_name = f"{base}-{target_w}.webp"
            resized.save(os.path.join(IMG, webp_name), "WEBP", quality=79, method=6)
            entries.append((webp_name, target_w))

        derivatives[jpg_name] = {
            "webp": entries[0][0],
            "webp_srcset": ", ".join(f"{name} {w}w" for name, w in entries),
            "og": None,
        }
        print(f"[ok] {jpg_name} {width}x{height}, webp {len(entries)}개")

    with open(DERIVATIVES, "w", encoding="utf-8") as fh:
        json.dump(derivatives, fh, ensure_ascii=False, indent=2)
        fh.write("\n")

    for source, *_ in JOBS:
        path = os.path.join(IMG, source)
        if os.path.exists(path):
            os.remove(path)
            print(f"[clean] {source} 삭제 (파생본만 배포)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
