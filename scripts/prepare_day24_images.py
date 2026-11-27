#!/usr/bin/env python3
"""2026-11-27 12:00 회차(글 75~77) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day24_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

DERIVATIVES = {
    "reservation-lead-time-thumbnail.png": (1600, ("겨울 예약은", "검색보다 열흘 빠릅니다")),
    "voucher-25-deadline-thumbnail.png": (1600, ("25만원, 신청은 18일", "사용은 31일까지")),
    "black-friday-discount-rate-thumbnail.png": (1600, ("반값의 기준은", "20일 중 최저가입니다")),
    "reservation-lead-time-body.png": (1400, None),
    "voucher-25-deadline-body.png": (1400, None),
    "black-friday-discount-rate-body.png": (1400, None),
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
