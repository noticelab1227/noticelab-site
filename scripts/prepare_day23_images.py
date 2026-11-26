#!/usr/bin/env python3
"""2026-11-27 08:00 회차 추가분(글 73~74) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day23_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

DERIVATIVES = {
    "place-plus-filter-thumbnail.png": (1600, ("손님이 필터를 누르면", "우리 가게만 빠집니다")),
    "ai-expert-ad-ban-thumbnail.png": (1600, ("AI로 만든 가짜 의사 추천 광고", "오늘부터 금지입니다")),
    "place-plus-filter-body.png": (1400, None),
    "ai-expert-ad-ban-body.png": (1400, None),
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
