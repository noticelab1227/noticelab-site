#!/usr/bin/env python3
"""Day 7 (2026-11-21 08:00 회차) 신규 이미지의 파생본(WebP 경량본·OG 카드)을 만듭니다.

기존 derivatives.json 의 항목은 그대로 두고 새 항목만 병합합니다.
    python3 scripts/prepare_day7_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "ai-answer-thumbnail.png": (1600, ("AI는 소개글이 아니라", "리뷰 문장을 읽습니다")),
    "support-fund-thumbnail.png": (1600, ("지원금 3,604억은 다 나갔는데", "10명 중 7명은 몰라서 못 받았습니다")),
    "gift-card-thumbnail.png": (1600, ("상품권 판매대금은", "아직 매출이 아닙니다")),
    "ai-answer-slips.png": (1400, None),
    "support-four-forms.png": (1400, None),
    "gift-card-ledger.png": (1400, None),
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
