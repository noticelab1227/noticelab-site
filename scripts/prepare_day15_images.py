#!/usr/bin/env python3
"""2026-11-24 회차(글 46~48) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day15_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "winter-entrance-thumbnail.png": (1600, ("손님은 가게 앞 골목에서", "돌아섭니다")),
    "december-booking-thumbnail.png": (1600, ("12월 약속은", "11월 마지막 주에 정해집니다")),
    "agency-baseline-thumbnail.png": (1600, ("12월에 시작하면", "성과를 잘못 봅니다")),
    "winter-entrance-body.png": (1400, None),
    "december-booking-body.png": (1400, None),
    "agency-baseline-body.png": (1400, None),
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
