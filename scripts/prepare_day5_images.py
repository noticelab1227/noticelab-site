#!/usr/bin/env python3
"""Day 5 신규 이미지의 파생본(WebP 경량본·OG 카드)만 추가로 만듭니다.

기존 derivatives.json 의 항목은 그대로 두고 새 항목만 병합합니다.
    python3 scripts/prepare_day5_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "group-booking-calendar-thumbnail.png": (1600, ("단체 예약은", "'송년회'로 검색되지 않습니다")),
    "senior-owner-dawn-store-thumbnail.png": (1600, ("가게는 줄었는데", "60대 사장님은 210만 명")),
    "review-stars-five-tiles-thumbnail.png": (1600, ("별점 이벤트가", "리뷰 탭을 지웁니다")),
    "group-booking-private-room.png": (1400, None),
    "senior-owner-ten-prints.png": (1400, None),
    "review-receipt-counter.png": (1400, None),
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
