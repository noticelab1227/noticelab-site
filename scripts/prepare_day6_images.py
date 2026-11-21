#!/usr/bin/env python3
"""2026-11-22 08:00 회차(글 28~30) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

기존 derivatives.json 항목은 그대로 두고 새 항목만 병합합니다.
    python3 scripts/prepare_day6_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "radius-first-thumbnail.png": (1600, ("키워드보다", "반경이 먼저입니다")),
    "margin-budget-thumbnail.png": (1600, ("지출 3.2% 줄였는데", "이익은 8.3% 줄었습니다")),
    "place-ad-slots-thumbnail.png": (1600, ("광고 자리는 6개에서 9개로", "클릭이 늘어도 손님은 따로")),
    "radius-three-bands.png": (1400, None),
    "margin-three-blocks.png": (1400, None),
    "place-ad-slots-grid.png": (1400, None),
}


def main() -> int:
    manifest_path = os.path.join(IMG, "derivatives.json")
    manifest = {}
    if os.path.exists(manifest_path):
        with open(manifest_path, encoding="utf-8") as fh:
            manifest = json.load(fh)

    for name, (max_width, headline) in DERIVATIVES.items():
        src = os.path.join(IMG, name)
        if not os.path.exists(src):
            print(f"[skip] {name} 없음")
            continue
        webp = make_webp(name, max_width)
        og = make_og(name, headline) if headline else None
        manifest[name] = {"webp": webp, "og": og}
        print(f"[ok] {name} -> {webp}" + (f", {og}" if og else ""))

    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, ensure_ascii=False, indent=2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
