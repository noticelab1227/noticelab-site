#!/usr/bin/env python3
"""2026-11-26 08:00 회차(글 64~66) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day20_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "grant-name-thumbnail.png": (1600, ("12월 31일 마감", "이름이 세 개인 지원금")),
    "profit-gap-thumbnail.png": (1600, ("매출은 늘었는데", "이익은 줄었습니다")),
    "single-channel-thumbnail.png": (1600, ("손님이 들어오는 길이", "하나뿐이라면")),
    "grant-name-body.png": (1400, None),
    "profit-gap-body.png": (1400, None),
    "single-channel-body.png": (1400, None),
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
