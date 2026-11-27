#!/usr/bin/env python3
"""2026-11-28 08:00 회차(글 78~80) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day25_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

DERIVATIVES = {
    "tax-audit-deferral-thumbnail.png": (1600, ("12월 31일, 유예가 끝납니다", "조사가 아니라 서류입니다")),
    "rate-325-thumbnail.png": (1600, ("금리 3.25%", "이자와 손님 지갑이 같이")),
    "beer-tax-menu-thumbnail.png": (1600, ("생맥주 한 잔에 127원", "메뉴판 고치는 순서")),
    "tax-audit-deferral-body.png": (1400, None),
    "rate-325-body.png": (1400, None),
    "beer-tax-menu-body.png": (1400, None),
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
