#!/usr/bin/env python3
"""2026-11-24 12:00 회차(글 55~57) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day17_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "megashow-neighborhood-thumbnail.png": (1600, ("12월 3일 광교, 나흘", "행사 이름으로는 안 나옵니다")),
    "year-end-ads-desk-thumbnail.png": (1600, ("연말 광고 25건을 세어보니", "동네 가게는 한 건이었습니다")),
    "booking-button-frontdesk-thumbnail.png": (1600, ("예약 버튼을", "직접 끌 수 있습니다")),
    "megashow-neighborhood-body.png": (1400, None),
    "year-end-ads-desk-body.png": (1400, None),
    "booking-button-frontdesk-body.png": (1400, None),
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
