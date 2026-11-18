#!/usr/bin/env python3
"""Day 2 신규 이미지의 파생본(WebP 경량본·OG 카드)만 추가로 만듭니다.

기존 derivatives.json 의 항목(히어로·커버)을 건드리지 않고 새 항목만 병합합니다.
    python3 scripts/prepare_day2_images.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from prepare_images import IMG, make_og, make_webp  # noqa: E402

# 원본 → (경량본 최대 폭, OG 카드 문구). 문구가 None 이면 OG 카드를 만들지 않습니다.
DERIVATIVES = {
    "agency-checklist-thumbnail.png": (1600, ("월 관리비보다 먼저", "확인할 5가지")),
    "ten-photos-reels-thumbnail.png": (1600, ("매장 사진 10장으로", "블로그와 릴스까지")),
    "pogok-suji-thumbnail.png": (1600, ("포곡과 수지에서", "같은 전략이 안 통하는 이유")),
    "agency-five-checks-diagram.png": (1400, None),
    "ten-photos-production-flow.png": (1400, None),
    "pogok-suji-search-patterns.png": (1400, None),
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
