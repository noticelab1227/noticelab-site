#!/usr/bin/env bash
# 노티스랩 홈페이지 재빌드 + GitHub Pages 배포
#
#   ./deploy.sh                # 빌드 → 검증 → main(소스) + gh-pages(빌드 결과물) 푸시
#   ./deploy.sh --no-push      # 빌드·검증만 (푸시 생략)
#
# 처음 한 번만: 이 폴더의 원격 저장소(origin)를 실제 Pages 저장소로 설정해 두면 됩니다.
set -euo pipefail
cd "$(dirname "$0")"

PUSH=1
[[ "${1:-}" == "--no-push" ]] && PUSH=0

GIT_NAME="${GIT_NAME:-NOTICE LAB}"
GIT_EMAIL="${GIT_EMAIL:-noticelab@naver.com}"
REMOTE="${REMOTE:-origin}"
PAGES_BRANCH="${PAGES_BRANCH:-gh-pages}"

echo "[1/4] 빌드"
python3 build.py --clean

echo "[2/4] 검증"
python3 verify.py

if [[ "$PUSH" == "0" ]]; then
  echo "[3/4] --no-push: 푸시 생략"; echo "[4/4] 완료 (dist/ 만 갱신)"; exit 0
fi

ORIGIN_URL="$(git remote get-url "$REMOTE")"

echo "[3/4] 소스(main) 푸시"
git add -A
if git diff --cached --quiet; then
  echo "      변경 없음 — 소스 커밋 생략"
else
  git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -m "content: $(date '+%Y-%m-%d') 사이트 갱신"
fi
git push "$REMOTE" main

echo "[4/4] 빌드 결과물($PAGES_BRANCH) 푸시"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -a dist/. "$tmp"/
(
  cd "$tmp"
  git init -q -b "$PAGES_BRANCH"
  git add -A
  git -c user.name="$GIT_NAME" -c user.email="$GIT_EMAIL" commit -q -m "deploy: $(date '+%Y-%m-%d %H:%M')"
  git push -f "$ORIGIN_URL" "$PAGES_BRANCH"
)
echo "완료: site.json 의 baseUrl 도메인에서 확인하세요 (반영까지 1~2분)"
