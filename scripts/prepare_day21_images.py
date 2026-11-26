#!/usr/bin/env python3
"""2026-11-26 12:00 회차(글 67~69) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

    python3 scripts/prepare_day21_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "ai-local-recommend-thumbnail.png": (1600, ("3km 떨어진 두 동네에서", "챗GPT가 고른 맛집은 겹치지 않았습니다")),
    "five-employee-labor-law-thumbnail.png": (1600, ("알바 2명 가게에도", "연차휴가가 생길 수 있습니다")),
    "storepro-agency-benchmark-thumbnail.png": (1600, ("카페24가 동네 가게", "대행을 시작했습니다")),
    "ai-local-recommend-body.png": (1400, None),
    "five-employee-labor-law-body.png": (1400, None),
    "storepro-agency-benchmark-body.png": (1400, None),
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
