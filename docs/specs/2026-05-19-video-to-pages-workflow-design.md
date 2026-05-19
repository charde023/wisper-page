# 영상 → GitHub Pages 보고서 워크플로우 계획서

> **작성일**: 2026-05-19
> **테스트 영상**: `지피터스-2026-05-18-설치법.mp4`
> **배포 대상**: `https://github.com/charde023/page.git` → `https://charde023.github.io/page/`
> **기반**: 5/17 안티그래비티 가이드(`antigravity-guide/`)에서 검증된 파이프라인

---

## 0. 목적

지피터스 스터디 라이브 강의 녹화본(mp4)을 매주 받아서, **모바일 최적화된 보고서 형태 웹 페이지**로 변환·게시하는 반복 가능한 워크플로우를 구축한다.

5/17 가이드 제작 때 사용한 도구·디자인을 재사용 가능한 형태로 정리하고, `지피터스-2026-05-18-설치법.mp4`로 실제 동작을 검증한다.

---

## 1. 결정 사항 요약

| 영역 | 결정 |
|---|---|
| **Pages 구조** | 날짜별 하위 폴더 + 루트 인덱스 (`/2026-05-18-installation/`) |
| **자동화 수준** | 단계별 수동 실행 + 도움 스크립트 (중간 검토 가능) |
| **보고서 틀** | 기존 17일자 형식 = TL;DR + 강의 개요 + 한눈에 보는 순서 + 상세 본문 |
| **MD 정리 주체** | Claude가 매 회 정리. 단, **교정 단계 추가**: raw transcript → clean transcript → guide |
| **작업 폴더 위치** | `C:\Users\inwon\Documents\Bandicam\<영상명>\` |
| **도움 스크립트 위치** | `C:\Users\inwon\Documents\Bandicam\workflow\` |

---

## 2. 디렉토리 구조

### 2-1. 워크스페이스 (로컬)

```
C:\Users\inwon\Documents\Bandicam\
├── 지피터스-2026-05-17-안티그래비티-설치방법.mp4    (원본 영상)
├── 지피터스-2026-05-18-설치법.mp4                    (이번 테스트용)
├── antigravity-guide\                               (5/17 작업 폴더 — 기존)
├── workflow\                                        (도움 스크립트 모음 — 신규)
│   ├── _template\                                   (작업 폴더 초기 템플릿)
│   │   ├── transcribe.py
│   │   └── make_html.py
│   ├── extract_audio.ps1                            (mp4 → audio.wav)
│   ├── new_workspace.ps1                            (영상명 → 작업 폴더 생성)
│   ├── stage_publish.py                             (작업 폴더 → publish 구조)
│   └── update_pages_index.py                        (page 리포 루트 인덱스 갱신)
├── docs\
│   └── superpowers\specs\
│       └── 2026-05-19-video-to-pages-workflow-design.md  (이 문서)
└── 지피터스-2026-05-18-설치법\                      (이번 테스트 작업 폴더 — 신규)
    ├── audio.wav                                    (1단계 산출물)
    ├── transcript.txt / .srt / segments.json        (2단계 산출물)
    ├── transcript_clean.md                          (3단계 산출물 — 신규)
    ├── guide.md                                     (4단계 산출물 — frontmatter 포함)
    ├── index.html                                   (5단계 산출물)
    └── publish\
        └── 2026-05-18-installation\
            ├── index.html
            ├── guide.md
            └── README.md
```

### 2-2. GitHub Pages 리포 (`charde023/page`)

```
page/
├── index.html                              (루트 가이드 목록 — 신규)
├── 2026-05-17-antigravity/                 (기존 17일자, 마이그레이션됨)
│   ├── index.html
│   ├── guide.md
│   └── README.md
└── 2026-05-18-installation/                (이번 테스트 산출물)
    ├── index.html
    ├── guide.md
    └── README.md
```

**최종 URL**

- `https://charde023.github.io/page/` → 루트 인덱스 (가이드 카드 목록)
- `https://charde023.github.io/page/2026-05-17-antigravity/` → 17일자
- `https://charde023.github.io/page/2026-05-18-installation/` → 18일자

---

## 3. 7단계 워크플로우

| # | 단계 | 도구 | 수동 / 자동 |
|---|---|---|---|
| 1 | mp4 → audio.wav (16kHz mono) | `extract_audio.ps1` (ffmpeg) | 스크립트 한 줄 |
| 2 | audio.wav → transcript.txt/.srt/.json | `transcribe.py` (faster-whisper) | 스크립트 (10~30분) |
| 3 | **transcript 교정** (어휘·문장 다듬기) | Claude (대화) | 수동 |
| 4 | 교정본 → **guide.md** (보고서 구조 + frontmatter) | Claude (대화) | 수동 |
| 5 | guide.md → index.html (모바일 최적화) | `make_html.py` (수정) | 스크립트 한 줄 |
| 6 | 작업 폴더 → publish 구조 | `stage_publish.py` | 스크립트 한 줄 |
| 7 | page 리포 폴더 추가 + 인덱스 갱신 + 푸시 | `update_pages_index.py` + git | 수동 + 스크립트 |

### 사용 흐름 (예시)

```powershell
# 0. 새 작업 폴더 준비 (영상명 인자)
.\workflow\new_workspace.ps1 "지피터스-2026-05-18-설치법.mp4"

# 1. 오디오 추출
.\workflow\extract_audio.ps1 "지피터스-2026-05-18-설치법.mp4"

# 2. 전사 (GPU 우선, CPU fallback)
python "지피터스-2026-05-18-설치법\transcribe.py"

# 3~4. Claude 대화로 교정 → guide.md 작성

# 5. HTML 생성
python "지피터스-2026-05-18-설치법\make_html.py"

# 6. publish 폴더 구성
python .\workflow\stage_publish.py "지피터스-2026-05-18-설치법" --slug 2026-05-18-installation

# 7. page 리포 푸시
#    - publish/2026-05-18-installation/ 복사
#    - update_pages_index.py로 루트 index.html 갱신
#    - git add . && git commit && git push
```

---

## 4. 스크립트별 책임

### 4-1. `extract_audio.ps1` (신규)

- **입력**: 영상 파일명 (인자)
- **출력**: `<영상명 기반 작업 폴더>/audio.wav` (16kHz mono)
- **본질**: `ffmpeg -i <input> -ar 16000 -ac 1 audio.wav` 한 줄. 이미 있으면 스킵.

### 4-2. `new_workspace.ps1` (신규)

- **입력**: 영상 파일명 (인자)
- **출력**: 영상명에서 `.mp4` 제거한 폴더 생성 + `workflow/_template/`의 `transcribe.py`·`make_html.py` 복사
- 이미 폴더가 있으면 덮어쓰지 않고 경고

### 4-3. `transcribe.py` (기존 재사용, 수정 없음)

- 현재 `HERE = Path(__file__).parent` 기준이라 **작업 폴더에 복사만 하면 그대로 작동**.
- GPU 우선 (large-v3 → medium → CPU fallback), VAD 필터, 진행률 로그 포함.

### 4-4. `make_html.py` (기존 수정)

- **수정 포인트** (3가지):
  1. `eyebrow`, `subtitle`, `description`을 `guide.md` frontmatter에서 읽기 (현재는 하드코딩)
  2. footer 원본 파일명도 frontmatter에서
  3. HTML 변환 시 frontmatter 제거 후 markdown 처리
- **CSS·디자인은 그대로** (이미 모바일 최적화 검증됨)

#### guide.md frontmatter 형식

```yaml
---
title: 지피터스 5/18 설치법 정리
eyebrow: 지피터스 22기 · 끌림 영상 스터디
subtitle: 2026-05-18 라이브 강의 정리본
source: 지피터스-2026-05-18-설치법.mp4
description: 지피터스 22기 끌림 영상 스터디 — 2026-05-18 설치법 정리본
date: 2026-05-18
---

# 지피터스 5/18 설치법 정리

> ...본문 시작
```

### 4-5. `stage_publish.py` (신규)

- **입력**: 작업 폴더 경로, `--slug <폴더명>`
- **출력**: `<작업폴더>/publish/<slug>/` 구조
  - `index.html` (작업 폴더에서 복사)
  - `guide.md` (frontmatter 제거 후 복사)
  - `README.md` (제목·요약·웹 링크 자동 생성)

### 4-6. `update_pages_index.py` (신규)

- **목적**: `page` 리포 루트에 `index.html`(가이드 목록) 자동 생성
- **로직**:
  1. 리포 안의 모든 날짜 폴더 스캔 (`2026-*-*` 패턴)
  2. 각 폴더의 `guide.md` frontmatter에서 `title` / `date` / `subtitle` 추출
  3. 최신순(date desc) 정렬 → 카드 목록 HTML 생성
  4. `make_html.py`와 동일한 디자인 시스템(CSS) 사용

---

## 5. 보고서 (guide.md) 표준 구조

5/17 가이드와 동일한 구조를 표준으로 채택. 모든 가이드는 다음 순서를 따른다:

1. `# 제목` (h1)
2. 메타 인용구 (`> 스터디명 · 날짜 / 원본 파일명·길이`)
3. `## 결론 (TL;DR)` — 굵게 한 줄 요약 + 핵심 포인트 불릿 3~5개
4. `## 강의는 어떤 내용이었나` — 1~2문단으로 강의 개요 설명
5. `## 0. 한눈에 보는 [주제]` — 번호 매긴 단계 요약 + 한 줄 결론
6. `## 1. ~ ## N.` — 상세 본문 (단계별·주제별)
7. (선택) `## 검증 체크리스트`, `## 자주 막히는 곳` 등 부록

**원칙**: 위에서 아래로 갈수록 상세도가 깊어진다. 모바일에서 위쪽만 읽어도 핵심이 전달돼야 한다.

---

## 6. 테스트 계획

### Phase A — 워크플로우 도구 준비

- [ ] `workflow/` 폴더 및 `_template/` 구성
- [ ] `extract_audio.ps1` 작성 + `ffmpeg -version` 확인
- [ ] `new_workspace.ps1` 작성
- [ ] `make_html.py` frontmatter 지원 추가 (기존 동작 보존)
- [ ] `stage_publish.py` 작성
- [ ] `update_pages_index.py` 작성 + 루트 인덱스 CSS

### Phase B — 5/18 영상으로 워크플로우 실행

- [ ] 작업 폴더 생성 (`new_workspace.ps1`)
- [ ] `audio.wav` 추출
- [ ] `transcribe.py` 실행 → `transcript.txt` 생성
- [ ] Claude: `transcript.txt` → `transcript_clean.md` (어휘·문장 교정)
- [ ] Claude: `transcript_clean.md` → `guide.md` (frontmatter + 보고서 구조)
- [ ] `make_html.py` → `index.html` 생성 + 모바일 시뮬레이터로 시각 확인
- [ ] `stage_publish.py` → `publish/2026-05-18-installation/` 검증

### Phase C — GitHub Pages 배포

- [ ] `page` 리포 clone 또는 pull
- [ ] **17일자 마이그레이션**: 루트 파일들 → `2026-05-17-antigravity/` 폴더로 이동 + frontmatter 추가 후 HTML 재생성
- [ ] 18일자 폴더 추가
- [ ] `update_pages_index.py` 실행 → 루트 `index.html` 생성
- [ ] 한 커밋으로 (a) 마이그레이션 + (b) 18일자 추가 + (c) 루트 인덱스
- [ ] `git push`
- [ ] 5분 후 3개 URL 모두 PC·모바일에서 확인

### 완료 정의 (Done)

1. `https://charde023.github.io/page/` → 17·18일자 카드가 보이는 목록 페이지
2. `https://charde023.github.io/page/2026-05-17-antigravity/` → 기존 가이드 정상
3. `https://charde023.github.io/page/2026-05-18-installation/` → 새 가이드 정상 (모바일 최적화 확인)
4. `workflow/` 안의 스크립트가 **다음 영상(5/19, 5/20)에도 그대로 재사용 가능**

---

## 7. 위험과 완화

| # | 위험 | 영향 | 완화 |
|---|---|---|---|
| 1 | 17일자 마이그레이션이 라이브 페이지를 잠시 깨뜨림 | 5~10분간 404 가능 | 한 커밋으로 (a) 폴더 이동 + (b) 루트 인덱스 + (c) 17일자 폴더 추가를 묶어 푸시. 푸시 직전 로컬 검증 |
| 2 | Whisper 전사 품질 (사람 이름·고유명사 오인식) | guide.md 정확도 저하 | 3단계(교정)에서 Claude가 맥락 보고 명백한 오인식 수정. 의심 단어는 `[?]` 표시 후 사용자 확인 |
| 3 | GPU 미사용 / Whisper 모델 다운로드 실패 | 전사 단계 블로킹 | `transcribe.py`에 이미 medium → CPU fallback 존재. 첫 실행 시 모델 다운(2~3GB) 시간 안내 |
| 4 | 18일자 영상 길이 미상 → 전사 시간 예측 불가 | Phase B 일정 영향 | Phase B 시작 전 영상 duration 확인. 1시간 영상 ≈ GPU 5분 / CPU 30분 기준 |
| 5 | frontmatter 추가로 기존 17일자 guide.md 호환 깨짐 | 마이그레이션 시 17일자 HTML 재생성 안 됨 | 17일자 guide.md에도 frontmatter 추가 후 `make_html.py` 재실행. 둘 다 새 시스템에 맞춤 |
| 6 | page 리포 인증 실패 | 푸시 단계 블로킹 | 첫 푸시 전 `git remote -v` + credential 상태 확인. SSH 또는 PAT 사용 권장 |
| 7 | 루트 인덱스가 가이드 늘수록 길어짐 | 장기 UX 저하 | 처음엔 단순 카드 정렬. 가이드 5개 넘으면 그때 카테고리·검색 추가 (지금은 YAGNI) |

---

## 8. 비범위 (Out of Scope)

이번 워크플로우 구축에서 **하지 않을 것**:

- 다국어 지원 (지금은 한국어만)
- 댓글·검색·인증 기능
- 영상 임베드 (개인정보·저작권 고려, 텍스트 정리본만)
- 자동 영상 감지·트리거 (수동 실행 유지)
- 검색 엔진 최적화 고도화 (기본 meta만)
- CI/CD (수동 git push 유지)

---

## 9. 다음 단계

이 계획서가 승인되면 `superpowers:writing-plans` 스킬로 단계별 실행 계획서를 작성한다. 실행 계획서는 Phase A → B → C 순서로 각 작업을 verify-able한 단위로 쪼개 두며, 각 단계마다 검증 방법을 명시한다.
