#!/usr/bin/env python3
"""2026-11-28 08:00 회차(글 81~83) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day26_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

DERIVATIVES = {
    "reservation-rookie-thumbnail.png": (1600, ("예약을 안 켠 가게에", "15만 원이 걸렸습니다")),
    "card-credit-thumbnail.png": (1600, ("카드 매출 4억 1,667만 원", "이 선을 넘는 가게만")),
    "free-support-thumbnail.png": (1600, ("무료 신청을", "30만 원에 해 준다면")),
    "reservation-rookie-body.png": (1400, None),
    "card-credit-body.png": (1400, None),
    "free-support-body.png": (1400, None),
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
