# wisper-page — Claude Code 작업 가이드

지피터스 스터디 라이브 강의 mp4를 모바일 최적화된 GitHub Pages 보고서로 변환하는 워크플로우.
새 영상이 들어오면 이 가이드를 따라 7단계 자동 진행한다.

---

## 1. 트리거 — 사용자가 이렇게 말하면

> *"지피터스-YYYY-MM-DD-주제.mp4 처리해줘"*
> *"이 영상도 진행해줘"* + (영상 경로)
> *"새 강의 가이드 만들어줘"*

→ 즉시 7단계 워크플로우 시작. 영상 경로가 모호하면 사용자에게 절대 경로 한 번만 확인.

---

## 2. 7단계 워크플로우

### Step 1. 영상 메타 확인
```bash
ffprobe -i "<video.mp4>" -show_entries format=duration -v quiet -of csv="p=0"
```
영상 길이 보고 (분 단위) → 전사 예상 시간 안내 (GPU ~5분/시간, CPU ~30분/시간).

### Step 2. 작업 폴더 생성
```powershell
.\workflow\new_workspace.ps1 -VideoFile "<영상 절대 경로>"
```
→ `workspaces/<영상-basename>/` 생성, `.video-path`에 영상 경로 저장, `transcribe.py`+`make_html.py` 복사.

### Step 3. 오디오 추출
```powershell
.\workflow\extract_audio.ps1 -Workspace ".\workspaces\<영상-basename>"
```
→ `audio.wav` (16kHz mono).

### Step 4. Whisper 전사 (**백그라운드 권장**)
```bash
python "workspaces/<영상-basename>/transcribe.py"
```
- **반드시 `run_in_background: true`로 실행** (5분~30분 이상 소요)
- exit code 127로 떨어져도 산출물(transcript.txt 등) 확인 후 정상이면 진행
- 산출물: `transcript.txt`, `transcript.srt`, `segments.json`, `progress.log`

### Step 5. transcript_clean.md 작성 (Claude가 직접)
**정책**:
- 명백한 음성인식 오류·맞춤법·고유명사 대소문자만 수정
- 의미 변경 없음, 요약·재배열 없음
- 의심 단어는 `[?원문]` 표기 (예: `Cline [?Crawl]`)
- 강의 흐름 그대로 따라가되 같은 표현의 중복·말더듬·진행 잡담은 압축 가능
- 파일 상단에 헤더 (원본 파일명, segments 수, 영상 길이, 정책 명시)

영상이 1시간 넘으면 transcript.txt를 청크로 읽고(`offset/limit`) 점진적 정리.

### Step 6. guide.md 작성 (Claude가 직접) — **가장 중요**

**frontmatter 필수**:
```yaml
---
title: <h1과 동일하게>
eyebrow: 지피터스 22기 · 끌림 영상 스터디
subtitle: YYYY-MM-DD 라이브 강의 정리본
source: 지피터스-YYYY-MM-DD-주제.mp4
description: <og·meta description, 한 줄>
date: YYYY-MM-DD
---
```

**표준 구조** (위에서 아래로 갈수록 상세도 깊어짐 — 모바일에서 위쪽만 읽어도 핵심 전달):

1. `# 제목` (h1)
2. 메타 인용구 (`> 스터디명 · 날짜 / 원본 파일명·길이`)
3. `## 결론 (TL;DR)` — **표·구조화 필수**, 줄글 금지
   - 한 줄 요약 (인용구)
   - 핵심 비교 표 (강사가 여러 명이면 강사별 비교 표 권장)
   - "챙겨야 할 N가지" 표 (`#` / `메시지` / `한 줄` 컬럼)
4. `## 강의는 어떤 내용이었나` — 1~2문단 개요 + 구성 표
5. `## 0. 한눈에 보는 [주제]` — 번호 매긴 단계 목록
6. `## 1. ~ ## N.` — 상세 본문 (강사·섹션별)
7. (선택) `## 부록 — 명대사`, `## 검증 체크리스트`, `## 자주 막히는 곳`

**Slug 명명**: `YYYY-MM-DD-<짧은-주제>` (예: `2026-05-18-installation`, `2026-05-18-week1-lecture`)

### Step 7. HTML 생성 + publish + 배포

```bash
# HTML 생성
python "workspaces/<영상-basename>/make_html.py"

# publish 폴더 구성
python workflow/stage_publish.py "workspaces/<영상-basename>" --slug <slug>

# page 리포로 복사
cp -r "workspaces/<영상-basename>/publish/<slug>" "<page-repo>/"

# 루트 인덱스 갱신
python workflow/update_pages_index.py "<page-repo>"

# git commit + push
cd "<page-repo>"
git add -A
git commit -m "add YYYY-MM-DD <topic>"
git push origin main
```

배포 후 1~2분 대기 → `WebFetch`로 `https://charde023.github.io/page/<slug>/` 검증.

---

## 3. 디렉토리 컨벤션

| 위치 | 용도 |
|---|---|
| `C:\workspace\wisper-page\` | **이 프로젝트 루트** |
| `workflow/` | 도구 스크립트 (수정 시 다음 영상에도 반영됨) |
| `workspaces/<basename>/` | 영상별 작업물 (자동 생성, gitignore) |
| `docs/specs/`, `docs/plans/` | 설계·계획 문서 |
| `C:\Users\inwon\Documents\page-repo\` | **GitHub Pages 리포 clone** |
| 원본 영상 mp4 | 보통 `C:\Users\inwon\Documents\Bandicam\` (위치는 매번 다를 수 있음, 절대 경로로 처리) |

---

## 4. 페이지 리포 구조 (`charde023/page`)

```
page/
├── index.html              # 루트 카드 인덱스 (update_pages_index.py가 자동 생성)
├── YYYY-MM-DD-topic/
│   ├── index.html
│   ├── guide.md            # frontmatter 포함 (인덱스가 메타 읽음)
│   └── README.md
└── ...
```

- 라이브 URL: `https://charde023.github.io/page/`
- 가이드 URL: `https://charde023.github.io/page/<slug>/`

---

## 5. 푸시 정책 (중요)

**두 개의 리포가 있고 역할이 다르다.** 헷갈리지 말 것.

| 리포 | 용도 | 푸시 정책 |
|---|---|---|
| `charde023/wisper-page` (이 프로젝트) | 도구·문서·CLAUDE.md 보관 | **작업 결과물(워크스페이스·가이드) 푸시 X.** 도구·CLAUDE.md·docs 변경 시에만, 사용자 명시 승인 후 푸시 |
| `charde023/page` → `https://charde023.github.io/page/` | **강의 정리본 전용** 게시 | 가이드 결과물 푸시 대상 (기본값). 단, **매번 사용자에게 어디에 올릴지 확인** |

### 워크플로우 적용

- **Step 7 (배포) 시작 전**: *"이번 가이드를 `charde023/page`에 올릴까? 다른 리포에 올릴까?"* 한 번 확인.
  - 사용자가 "응 / page에 올려" → 기존 페이지 리포로 진행
  - 사용자가 다른 리포 지정 → 그쪽으로 (필요시 clone + 인덱스 갱신 스크립트 적용)
- **이 프로젝트(wisper-page) 자체 변경**: 도구 수정·CLAUDE.md 갱신·docs 추가 등은 commit까지만. push는 사용자 승인 후 별도로.
- **workspaces/는 .gitignore됨** → 실수로라도 wisper-page에 결과물 안 올라감.

### 다른 컨텐츠는 올리지 말 것

`charde023/page`는 강의 정리본 전용. 다른 종류의 컨텐츠(블로그, 메모, 실험 페이지)는 별도 리포로.

---

## 6. 알려진 함정

| 상황 | 대응 |
|---|---|
| **`cublas64_12.dll` not found** | `transcribe.py`에 이미 `os.environ["PATH"]` prepend 패치 적용됨. `_template/`의 최신 버전 사용 |
| **Whisper exit code 127** | 산출물(transcript.txt) 확인 후 정상이면 무시하고 진행 |
| **인덱스 카드에 slug만 표시** | publish 폴더 guide.md에 frontmatter가 있는지 확인. `stage_publish.py`는 frontmatter를 **유지**하도록 수정됨 (제거 X) |
| **2시간 넘는 영상 transcript** | 한 번에 못 읽음. `Read offset/limit`로 청크 단위 정리, 의미 보존하되 압축 |
| **새 폴더 인덱스 누락** | `update_pages_index.py`가 `YYYY-MM-DD-` 접두 폴더만 스캔. slug 규칙 지켜야 함 |
| **GitHub Pages 빌드 캐시** | WebFetch 결과가 옛 버전이면 query string (`?v=2`)로 캐시 우회 |

---

## 7. 사용자 톤·선호 (반드시 따를 것)

- **답변 짧고 핵심만.** 불필요한 요약·반복 금지. 진행 중 1줄 업데이트로 충분.
- **표·구조화 선호.** TL;DR을 줄글로 쓰지 말 것 — 표·비교·번호 매기기 우선.
- **모바일 가독성이 1순위.** 화면 위쪽에 가장 중요한 게 와야 함.
- **자동화 신뢰.** "쭉 진행해줘" 라고 하면 막힘 없이 7단계 끝까지. 사용자 결정이 꼭 필요한 지점만 멈춰서 확인.
- **caveman 모드 사용 X** (명시적으로 요청 없는 한).
- **백그라운드 작업 시 알림 기다림.** 폴링 금지.

---

## 8. 신규 진행 시 체크리스트 (Claude용)

영상 처리 요청 받으면:

- [ ] `ffprobe`로 길이 확인 → 사용자에게 예상 소요 시간 안내
- [ ] `new_workspace.ps1`로 작업 폴더 생성
- [ ] `extract_audio.ps1`로 오디오 추출
- [ ] `transcribe.py` 백그라운드 실행 (run_in_background: true) → 완료 알림 대기
- [ ] `transcript.txt` 읽고 영상 주제 파악 (긴 영상은 청크)
- [ ] `transcript_clean.md` 작성 (의미 보존 + 교정)
- [ ] `guide.md` 작성 (frontmatter + 구조화된 TL;DR + 본문)
- [ ] slug 결정 (`YYYY-MM-DD-<topic>`, 같은 날짜에 여러 영상이면 토픽 구분)
- [ ] `make_html.py` 실행
- [ ] `stage_publish.py` 실행
- [ ] **사용자에게 푸시 리포 확인** ("page에 올릴까? 다른 리포?")
- [ ] page-repo로 복사 (또는 사용자 지정 리포)
- [ ] `update_pages_index.py` 실행
- [ ] git commit + push (commit message에 한 줄 + 변경 사항)
- [ ] 1~2분 후 WebFetch로 라이브 URL 검증 (캐시 우회 위해 `?v=N` 권장)
- [ ] 사용자에게 라이브 URL + commit hash 보고

---

## 9. 의사결정 히스토리

이 프로젝트의 구조가 왜 이렇게 됐는지 알고 싶으면:

- `docs/specs/2026-05-19-video-to-pages-workflow-design.md` — 설계서
- `docs/plans/2026-05-19-video-to-pages-workflow.md` — 실행 계획서

기존 작업 결과 (Bandicam 폴더에 남아있는 5/17, 5/18 가이드 작업물)도 참고 가능.
