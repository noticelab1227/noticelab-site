#!/usr/bin/env python3
"""2026-11-21 09:00 회차(글 22~24) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

같은 날 08:00 회차(글 19~21)의 파생본은 scripts/prepare_day7_images.py 가 만들었습니다.
이 스크립트는 기존 derivatives.json 의 항목을 그대로 두고 새 항목만 병합합니다.
    python3 scripts/prepare_day8_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "gyeonggi-eight-cities-thumbnail.png": (1600, ("여덟 개 시가", "역할을 나눴습니다")),
    "online-md-meeting-thumbnail.png": (1600, ("유통 상담이", "길어지는 상품")),
    "year-end-hours-thumbnail.png": (1600, ("연말 휴무는", "2주 전에 보입니다")),
    "gyeonggi-eight-cities-spine.png": (1400, None),
    "online-md-five-checks.png": (1400, None),
    "year-end-hours-three-boards.png": (1400, None),
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
