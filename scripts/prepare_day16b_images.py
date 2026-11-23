#!/usr/bin/env python3
"""2026-11-24 08:00 회차(글 49~51) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day16_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "theme-slots-thumbnail.png": (1600, ("맛집 검색에 두 칸이 생겼습니다", "테마 칸은 메뉴로 뽑힙니다")),
    "tiktok-first-second-thumbnail.png": (1600, ("광고 705개를 세어보니", "15초 공식은 없었습니다")),
    "auto-ad-counter-thumbnail.png": (1600, ("자동 광고는", "예산을 다 씁니다")),
    "theme-slots-body.png": (1400, None),
    "tiktok-first-second-body.png": (1400, None),
    "auto-ad-counter-body.png": (1400, None),
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
