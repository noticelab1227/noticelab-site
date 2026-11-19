# NOTICE LAB 웹사이트 · 인사이트 (정적 사이트)

노티스랩의 공식 홈페이지와 구글 SEO/GEO 대응 블로그입니다.
Node.js나 별도 패키지 없이 **Python 표준 라이브러리만으로** 빌드되며, 결과물은 `dist/` 폴더 하나입니다.
GitHub Pages · Vercel · Cloudflare Pages 어디에나 그대로 올릴 수 있습니다.

- 슬로건: 조회수가 아닌 매출을 연구합니다.
- 상담 채널(모든 CTA): <https://pf.kakao.com/_xdMIvX/chat> — 카카오톡 채널 「노티스랩」 1:1 채팅 (새 탭)
- 대응 지역: 용인 · 수원 · 화성 · 성남 · 경기 광주 → 수도권 · 전국

## 1. 폴더 구조

```
website/
├── site.json                 사이트 설정(도메인, 브랜드, 사업자 정보, 서비스, 지역)
├── build.py                  빌드 스크립트 (posts/*.md → dist/)
├── verify.py                 결과물 검증 스크립트
├── posts/                    글 원본 (마크다운 + front matter)
│   ├── 01-blog-traffic-without-inquiries.md
│   ├── 02-yongin-blog-marketing-living-areas.md
│   ├── 03-card-spending-store-quiet.md
│   ├── 04-agency-checklist-before-hiring.md
│   ├── 05-making-blog-and-reels-from-10-photos.md
│   └── 06-yongin-pogok-vs-suji-strategy.md
├── templates/                HTML 템플릿 (base / home / insights / post / 404 / go)
├── assets/
│   ├── css/style.css         디자인 (딥 옵시디언 #0A0A0C · 오프화이트 #F4F4F2 · 코랄 #FF3B30)
│   ├── js/site.js            풀스크린 메뉴 · 히어로 패럴랙스 · 섹션 인디케이터 · 필터 · 목차
│   ├── favicon.svg
│   └── images/               히어로·커버·도식 · OG 카드 · 로고
├── scripts/prepare_images.py 이미지 경량화(WebP) · OG 카드 생성 (선택, Pillow 필요)
├── scripts/prepare_hero_images.py 히어로 비주얼 그레이딩 · WebP 다중 폭 생성 (선택)
├── scripts/prepare_go_og.py  /go/ 링크 허브 공유 카드(1200×630) 생성 (선택, Pillow 필요)
└── dist/                     빌드 결과물 (배포 대상)
```

`dist/` 구성

```
dist/
├── index.html                        홈
├── insights/index.html               인사이트 목록 (카테고리 필터)
├── insights/<slug>/index.html        개별 글 (Article + FAQPage + BreadcrumbList JSON-LD)
├── sitemap.xml · robots.txt · rss.xml · llms.txt
├── go/index.html                     링크 허브 (인스타그램·스레드 프로필 링크)
├── 404.html · .nojekyll
└── assets/...
```

## 2. 빌드와 검증

```bash
cd noticelab/website
python3 build.py --clean     # dist/ 새로 생성
python3 verify.py            # 링크 · 이미지 · HTML · 스키마 · 중복도 검사
```

`build.py`는 글을 날짜 역순으로 정렬해 목록·홈 최신 글·sitemap·RSS·목차를 모두 다시 만듭니다.
`verify.py`는 실패가 있으면 종료 코드 1을 돌려주므로, 배포 전 자동 검사에 그대로 넣을 수 있습니다.

이미지 경량본(WebP)과 OG 카드를 다시 만들 때만 Pillow가 필요합니다. 이미 생성된 파일이 있으므로 평소 빌드에는 필요하지 않습니다.

```bash
python3 -m pip install pillow
python3 scripts/prepare_images.py
```

## 3. 새 글 추가하기 (매일 하는 일)

1. `posts/` 에 `YYYY-MM-DD-슬러그.md` 파일을 만듭니다.
2. 아래 front matter를 채우고 본문을 씁니다.
3. `python3 build.py --clean && python3 verify.py` 실행.
4. `dist/` 를 커밋하거나 배포 명령을 실행합니다.

```markdown
---
title: "글 제목 (H1으로 그대로 출력됩니다)"
slug: url-에-들어갈-영문-슬러그
description: "검색 결과에 나올 80~120자 요약"
category: 지역·검색 전략     # 지역·검색 전략 | 시장·제작 방식 | 전환·대행 기준
date: 2026-11-20T09:00:00+09:00
updated: 2026-11-20T09:00:00+09:00
cover: /assets/images/파일명.png
cover_alt: "대표 이미지 설명(스크린리더·검색용)"
og_image: /assets/images/og-파일명.jpg
og_image_alt: "OG 카드 설명"
keywords: 키워드1, 키워드2, 키워드3
related: 다른-글-슬러그, 또-다른-슬러그
faq_heading: 자주 묻는 질문
---

첫 문단은 요약입니다. (검색 결과 스니펫과 GEO 인용에 함께 쓰입니다.)

## 소제목은 H2
### 소제목은 H3
```

본문 마크다운 지원 범위: `##` `###` `####` 제목, 문단, `**굵게**`, `` `코드` ``, `[링크](주소)`,
`- ` 목록, `1. ` 번호 목록, `> ` 인용, `---` 구분선, 단독 이미지 줄
`![대체텍스트](/assets/images/파일.png "캡션")`.

- `## 자주 묻는 질문` 아래의 `### 질문` + 답변 문단은 **자동으로 FAQPage 구조화 데이터**가 됩니다. 3개 이상 권장.
- `related` 는 슬러그를 쉼표로 적습니다. 비워 두면 최신 글에서 자동으로 채워집니다.
- H1은 템플릿이 제목으로 출력하므로 본문에 `#` 을 쓰지 마세요.
- 이미지 파일은 `assets/images/` 에 넣으면 `dist/assets/images/` 로 함께 복사됩니다.

## 4. 배포 (0원)

### 현재 상태 (2026-11-19)

- `site.json` 의 `business` 는 실제 정보로 채워졌습니다(대표 김지은, 사업자등록번호 266-76-00532, 주소 경기도 용인시 처인구 포곡읍, 이메일 noticelab@naver.com, 전화 010-2000-0239). 통신판매업 신고번호는 값이 없어 푸터에서 해당 줄을 출력하지 않습니다.
- `baseUrl` 은 **`https://noticelab.pages.dev`** 로 확정되었습니다(Cloudflare Pages). canonical·OG·sitemap·robots 주소가 모두 이 주소로 출력됩니다. 도메인이 바뀌면 `site.json` 의 `baseUrl` 만 고치고 다시 빌드하면 됩니다.
- 소스와 빌드 결과물(`dist/`)을 함께 GitHub `noticelab-site` 저장소(`main`)에 올려 두었습니다. `dist/` 는 `python3 build.py --clean` 로 언제든 재생성됩니다.
- 2026-11-19 Day 2: 인사이트 6편(기존 3편 보완 + 신규 3편)으로 확장했습니다. 신규 3편의 네이버 블로그 발행용 원고·이미지는 `noticelab/day2/` 에 있습니다.
- 2026-11-19 Day 3: 인사이트 9편으로 확장했습니다. 신규 3편(수원 생활권 검색 · 시즌 검색 달력 · 플레이스 전환)의 구글 SEO/GEO 버전이며, 네이버 블로그 발행용 원고·이미지는 `noticelab/day3/` 에 그대로 두었습니다. 네이버 블로그에는 자동 발행하지 않았습니다.
- 2026-11-20 Day 4: 인사이트 12편으로 확장했습니다. 신규 3편은 구글 비즈니스 프로필 점검(지역·검색 전략), 10월 소비자물가 기반 메뉴 가격 공지(시장·제작 방식), 대행 종료 시 인수인계(전환·대행 기준)이며 이미지 파생본은 `scripts/prepare_day4_images.py` 로 만듭니다. 네이버 블로그에는 발행하지 않았습니다.
- 2026-11-20 링크 허브: 인스타그램·스레드 프로필에 거는 **`https://noticelab.pages.dev/go/`** 를 `templates/go.html` + `build.py` 의 `build_go()` 로 생성합니다(`--clean` 빌드에서도 항상 함께 생성). 버튼 문구·순서·주소는 `site.json` 의 `linkHub.links` 에서 고칩니다. 공유 카드는 `python3 scripts/prepare_go_og.py` 로 재생성합니다.

### 링크 허브(`/go/`) 문구·링크 고치기

인스타그램·스레드 프로필에 거는 링크 페이지입니다. 버튼은 `site.json` 의 `linkHub.links` 배열 순서대로 출력되고, `"primary": true` 인 항목만 **카카오 옐로(`#FEE500`, 호버 `#F5DC00`) 버튼에 `#191600` 글자·카카오톡 말풍선 심벌 SVG**로 강조됩니다. 말풍선 심벌은 이모지 대신 `build.py` 의 `LINK_ICON_SVGS` 에 들어 있는 인라인 SVG 이고, `"icon_svg": "kakaotalk"` 로 지정합니다. 네이버 블로그 버튼은 `"icon_svg": "naverblog"` 로 **네이버 그린(`#03C75A`, 호버 타일 `#02B351`) 타일 위 흰 말풍선 + 그린 N 엠블럼**을 쓰고, 호버 시 버튼 테두리·화살표가 그린으로 물듭니다(`LINK_ICON_TILES`). 나머지 버튼과 페이지 전체는 옵시디언·코랄 톤 그대로입니다.

```json
"linkHub": {
  "slogan": "광고보다 결과, 조회수보다 매출을 연구합니다.",
  "links": [
    { "label": "카카오톡 채널 1:1 무료 상담", "sub": "가장 빠른 문의 · 매장 진단 요청",
      "url": "https://pf.kakao.com/_xdMIvX/chat", "icon_svg": "kakaotalk", "primary": true }
  ]
}
```

`label`·`sub`·`url`·`icon`(이모지)·`icon_svg`(인라인 SVG 이름) 을 고친 뒤 `python3 build.py --clean && python3 verify.py` → `git commit` → `git push` 만 하면 됩니다. 페이지의 레이아웃·색은 `templates/go.html` 안의 `<style>` 에 있습니다. 공유 카드 이미지는 `scripts/prepare_go_og.py` 로 다시 만들고, 사업자 정보는 `site.json` 의 `business` 값을 그대로 씁니다.

### 재빌드·배포 스크립트

`./deploy.sh` 는 빌드 → 검증(`verify.py`) → 소스 `main` 푸시 → 빌드 결과물 `gh-pages` 브랜치 루트 푸시를 순서대로 실행합니다. 검증에서 실패가 나오면 푸시 단계로 넘어가지 않습니다.

- 저장소 원격이 연결되어 있어야 합니다: `git remote add origin https://github.com/<계정>/<저장소>.git`
- GitHub Pages 설정: Settings → Pages → Source `Deploy from a branch` → 브랜치 `gh-pages`, 폴더 `/ (root)`
- `dist/.nojekyll` 이 포함되므로 `_` 로 시작하는 파일도 그대로 배포됩니다.
- 빌드만 하고 푸시하지 않으려면 `./deploy.sh --no-push`.

### GitHub Pages 일반 절차

- 저장소에 이 폴더(소스)를 올리고 Pages 소스는 `gh-pages` 브랜치 루트(빌드 결과물)로 지정합니다. 소스와 배포물을 분리하면 글이 늘어도 `dist/` 충돌 없이 재배포할 수 있습니다.
- 사이트 내부 링크와 자산 경로는 `/` 로 시작하는 **루트 절대 경로**로 출력되므로 사용자 사이트(`계정.github.io`) 루트나 커스텀 도메인 루트 배포에 맞습니다. `계정.github.io/저장소명/` 같은 하위 경로에 올리려면 `baseUrl` 에 그 경로를 넣고 경로 처리 방식을 조정해야 합니다.

### Vercel

- New Project → 저장소 선택 → Framework Preset: **Other**
- Build Command: `python3 build.py --clean`
- Output Directory: `dist`
- Root Directory: `noticelab/website`

### Cloudflare Pages (현재 사용하는 배포 경로)

저장소 루트가 이 `website` 폴더이므로 아래처럼 설정하면 빌드 없이 바로 배포됩니다.

- 저장소: `noticelab1227/noticelab-site` (`main` 브랜치)
- Framework preset: `None`
- Build command: (비움)
- Build output directory: `dist`
- Root directory: (비움 / `/`)

빌드 결과물 `dist/` 가 저장소에 함께 들어 있으니 Cloudflare가 파이썬을 실행하지 않아도 그대로 배포됩니다. 글이 늘면 로컬에서 `python3 build.py --clean` → `git commit` → `git push` 만 하면 됩니다.

세 곳 모두 무료 플랜으로 운영할 수 있고, 커스텀 도메인을 붙이면 `baseUrl` 과 같은 주소로 맞춰 주세요.

## 5. 검색 등록 (배포 직후 1회)

- **Google Search Console**: 속성 추가 → `https://도메인/sitemap.xml` 제출 → 색인 생성 요청.
- **네이버 서치어드바이저**: 사이트 등록 → 소유 확인 → `sitemap.xml`, `rss.xml` 제출.
- **IndexNow**(선택): Cloudflare Pages를 쓰면 자동 핑을 켤 수 있습니다.
- `llms.txt`: AI 검색 엔진이 사이트 구조와 글 목록을 빠르게 읽도록 빌드 시 자동 생성됩니다.

## 6. 운영 원칙 (반드시 지킬 것)

- **자동 발행 금지.** 이 사이트는 초안을 쌓는 곳이고, 실제 발행 여부는 사장님이 판단합니다.
- **네이버 블로그와 같은 원고를 쓰지 않습니다.** 네이버·구글·AI 검색에서 중복 문서로 평가받을 수 있어, 같은 소재라도 제목·소제목·문장을 다시 씁니다. `verify.py` 가 `noticelab/day1/` 원고와의 8-gram 겹침을 자동으로 검사합니다(현재 10~13%).
- **보장 문구 금지.** 상위 노출, 매출, AI 인용을 보장한다고 쓰지 않습니다. 이 사이트의 문구에도 명시되어 있습니다.
- **가짜 사례 금지.** 성공 사례·매출 수치·후기는 확인된 자료만 사용합니다.
- **제작 원칙 유지.** 업체가 제공한 기존 사진·영상을 바탕으로 기획·제작하며, 별도 현장 촬영은 기본 서비스가 아닙니다. 이 문장은 홈과 모든 글에 들어가야 합니다.
- **인용한 통계는 출처와 기준일을 함께 적습니다.** 예: 한국은행 「2026년 3/4분기 가계신용(잠정)」 보도자료(2026.11.18).

## 7. 디자인 메모

- 톤: Plus X 벤치마킹. 딥 옵시디언 `#0A0A0C` + 오프화이트 `#F4F4F2` + 화이트, 포인트는 에디토리얼 코랄 `#FF3B30`(밝은 지면에서는 `#C4291F`). 둥근 모서리·그라데이션·그림자 없이 1px 헤어라인 그리드와 직각 면으로만 구성합니다. CSS 변수는 `assets/css/style.css` 상단 `:root`.
- 타이포: 국문은 Pretendard(CDN) → 시스템 폰트, 라벨·수치는 모노스페이스. 디스플레이는 `letter-spacing: -.04em`, `line-height: 1.05` 안팎의 스위스 조판.
- 지면 리듬: 다크(01 전환 구조) → 페이퍼(02 서비스) → 다크(03 인사이트) → 다크(04 대응 지역) → 페이퍼(클로징 CTA) → 다크(푸터). 섹션은 01~04 번호와 영문 라벨로 고정됩니다.
- 헤더: NL 모노그램 + 브랜드 마키 티커 + 사각 `MENU`(풀스크린 오버레이) + `TALK` 버튼. 스크롤 시 배경이 불투명 잉크로 바뀝니다.
- 히어로: `assets/images/hero-atelier.jpg`(WebP 3폭)를 풀블리드 배경으로 쓰고 스크림·그리드·미세 패럴랙스를 겹칩니다. 비주얼은 `scripts/prepare_hero_images.py` 로 다시 만들 수 있습니다.
- 반응형: 1180px(전환 구조 2열 · 서비스 그리드 축소), 980px(티커 숨김 · 전환 구조/카드 재배치 · 목차 상단), 720px(1열 · 히어로 타이포 축소), 420px(헤더 압축).
- 접근성: 건너뛰기 링크, `aria-current`, `aria-expanded`, `aria-pressed`, `aria-live` 필터 안내, `prefers-reduced-motion`(패럴랙스·등장 모션 정지), 포커스 링.
- 이미지: `<picture>` 로 WebP를 먼저 제공하고 JPEG/PNG로 폴백합니다. 모든 `<img>` 에 `width`/`height` 와 대체 텍스트가 있습니다.
- 정적 자산 캐시: `templates/base.html` 의 `style.css?v=` · `site.js?v=` 값을 CSS/JS 수정 시 올립니다.

## 8. 검증 항목 (`verify.py`)

1. HTML 태그 구조 · 중복 id · 닫히지 않은 태그
2. 내부 링크 · 앵커 · 이미지 경로 존재 여부
3. `alt` · `width` · `height` · WebP 소스
4. title · description · canonical · OG · H1 개수
5. JSON-LD 문법과 Article · FAQPage · BreadcrumbList, 본문 FAQ와 스키마 일치
6. sitemap.xml · rss.xml · robots.txt 정합성
7. 템플릿 변수 잔여물, 미참조 자산, placeholder 목록
8. `noticelab/day1/` 원고 및 글 간 8-gram 중복도
