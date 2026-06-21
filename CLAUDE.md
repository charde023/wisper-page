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
→ `workspaces/<영상-basename>/` 생성, `.video-path`에 영상 경로 저장, `pipeline.json` 스테이지 매니페스트 초기화.
`transcribe.py`·`make_html.py`는 **더 이상 워크스페이스에 복사되지 않음** — `workflow/_template/`의 정본을 `--workspace` 플래그로 직접 호출.

**원클릭 오케스트레이터** (Steps 1-4를 한 번에):
```powershell
.\workflow\run.ps1 -VideoFile "<영상 절대 경로>"
```
→ `new_workspace` → `extract_audio` → `transcribe.ps1` 순으로 자동 진행. 전사만 필요할 때는 `-TranscribeOnly` 옵션 추가 (→ §2.5 참고).

### Step 3. 오디오 추출
```powershell
.\workflow\extract_audio.ps1 -Workspace ".\workspaces\<영상-basename>"
```
→ `audio.wav` (16kHz mono). `pipeline.json`의 `audio` 스테이지 스탬프.

### Step 4. Whisper 전사 (**백그라운드 권장**)
```powershell
# transcribe.ps1 권장 — exit code 대신 산출물 존재 여부로 성공 판단
.\workflow\transcribe.ps1 -Workspace ".\workspaces\<영상-basename>"
```
또는 직접 호출:
```bash
python workflow/_template/transcribe.py --workspace "workspaces/<영상-basename>"
```
- **반드시 `run_in_background: true`로 실행** (5분~30분 이상 소요)
- `transcribe.ps1`이 exit code 127 문제를 내부 처리 — 산출물(transcript.txt) 존재 여부로 성공 판정하므로 exit code 무시 가능
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

**작성 규칙 (추가)**:
- **이모지 사용 금지** (명시적 요청 없는 한). 강조는 **볼드** 또는 `> 인용구`로.
- 골격은 `workflow/_template/guide-template.md` 참고.
- 푸시 전 검증: `python workflow/lint_guide.py <guide.md>`

**Slug 명명**: `YYYY-MM-DD-<짧은-주제>` (예: `2026-05-18-installation`, `2026-05-18-week1-lecture`)

### Step 7. HTML 생성 + publish + 배포

**원클릭 배포** (권장):
```powershell
.\workflow\deploy.ps1 -Workspace ".\workspaces\<영상-basename>" -Slug <slug>
```
→ HTML 생성 → stage → page-repo 복사 → 인덱스 갱신 → git push 까지 한 번에.

또는 단계별 수동 실행:
```powershell
# HTML 생성 (중앙 정본 호출)
python workflow/_template/make_html.py --workspace "workspaces/<영상-basename>"

# publish 폴더 구성
python workflow/stage_publish.py "workspaces/<영상-basename>" --slug <slug>

# page 리포로 복사 (PowerShell)
Copy-Item -Recurse -Force "workspaces\<영상-basename>\publish\<slug>" "<page-repo>\"

# 루트 인덱스 갱신
python workflow/update_pages_index.py "<page-repo>"

# git commit + push
git -C "<page-repo>" add -A
git -C "<page-repo>" commit -m "add YYYY-MM-DD <topic>"
git -C "<page-repo>" push origin main
```

> `pageRepoPath` 등 머신별 경로는 `workflow/config.json`(gitignored)에 보관.
> 없으면 `workflow/config.example.json`을 복사해 값 채울 것.

배포 후 1~2분 대기 → `WebFetch`로 `https://charde023.github.io/page/<slug>/` 검증.

---

### 2.5 전사 전용 모드 (transcribe-only)

미팅·통화·비강의 녹화 등 guide.md/HTML/Pages 배포가 필요 없는 경우. 과거 워크스페이스 9개 중 약 4개가 이 모드였음.

```powershell
.\workflow\run.ps1 -VideoFile "<녹화 절대 경로>" -TranscribeOnly
```
→ Steps 1–4만 실행 (new_workspace → extract_audio → transcribe). guide.md·HTML·배포 없음.

**산출물**: 전사 정리본 md. **저장 위치는 프로젝트 루트 `결과물/` 폴더로 통일**(워크스페이스에 흩어두지 않음), **파일명은 영상·녹화 제목**으로 한다 — `transcript_clean.md` 같은 고정 이름은 여러 건일 때 구분이 안 되므로 금지. (윈도우 금지문자 `\ / : * ? " < > |`는 제거 또는 ` - ` 치환.)

| 상황 | 정책 |
|---|---|
| 일반 미팅/통화 | 화자 구분 (`**홍길동**: …`), 파일 상단에 **요지 표** |
| 여러 건 | 하나의 md로 병합 (시간순, 파일명 헤더로 구분) |
| 어휘·문장 교정 | 맞춤법·오인식만 교정. 타임스탬프 미기록. 요약·재배열 없음 |

---

## 3. 디렉토리 컨벤션

| 위치 | 용도 |
|---|---|
| `C:\workspace\wisper-page\` | **이 프로젝트 루트** |
| `workflow/` | 도구 스크립트 (수정 시 다음 영상에도 반영됨) |
| `workspaces/<basename>/` | 영상별 작업물 (자동 생성, gitignore). 각 워크스페이스에 `pipeline.json` 스테이지 매니페스트 자동 생성 |
| `결과물/` | **전사 정리본 결과물 모음** (gitignore). 모든 전사 산출물을 여기 한곳에, 파일명 = 영상 제목 |
| `workflow/config.json` | 머신별 경로 설정 (gitignored). `config.example.json` 복사 후 수정 |
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
| **Whisper exit code 127** | `transcribe.ps1`이 산출물 존재 여부로 성공 판정하므로 exit code 무시. 직접 py 호출 시에도 transcript.txt 있으면 진행 |
| **머신별 경로 (pageRepoPath 등)** | `workflow/config.json`(gitignored)에 보관. 없으면 `config.example.json` 복사 후 값 채울 것 |
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
- [ ] `run.ps1` (또는 `new_workspace.ps1` → `extract_audio.ps1` → `transcribe.ps1`) 실행 — 백그라운드(run_in_background: true) → 완료 알림 대기
- [ ] `transcript.txt` 읽고 영상 주제 파악 (긴 영상은 청크)
- [ ] `transcript_clean.md` 작성 (의미 보존 + 교정)
- [ ] `guide.md` 작성 (frontmatter + 구조화된 TL;DR + 본문)
- [ ] slug 결정 (`YYYY-MM-DD-<topic>`, 같은 날짜에 여러 영상이면 토픽 구분)
- [ ] `lint_guide.py`로 guide.md 검증 (`python workflow/lint_guide.py <guide.md>`)
- [ ] **사용자에게 푸시 리포 확인** ("page에 올릴까? 다른 리포?")
- [ ] `deploy.ps1` (또는 `make_html.py` → `stage_publish.py` → `Copy-Item` → `update_pages_index.py` → git push) 실행
- [ ] 1~2분 후 WebFetch로 라이브 URL 검증 (캐시 우회 위해 `?v=N` 권장)
- [ ] 사용자에게 라이브 URL + commit hash 보고

---

## 9. 의사결정 히스토리

이 프로젝트의 구조가 왜 이렇게 됐는지 알고 싶으면:

- `docs/specs/2026-05-19-video-to-pages-workflow-design.md` — 설계서
- `docs/plans/2026-05-19-video-to-pages-workflow.md` — 실행 계획서

기존 작업 결과 (Bandicam 폴더에 남아있는 5/17, 5/18 가이드 작업물)도 참고 가능.

---

## 10. YouTube 채널 지식화 — TechBridge-KR → Obsidian

위 §1-9는 **로컬 mp4 → GitHub Pages** 워크플로다. 이건 **별개 워크플로**: YouTube 채널 영상을 전사해 **Obsidian 학습노트**로 만든다. (Pages 배포 없음.)

- **도구**: `workflow/youtube/` (README 참고). 전사 인프라(`transcribe.ps1`·`_template/transcribe.py`·`manifest`)는 §1-9와 공유.
- **설계/계획**: `docs/specs/2026-06-06-techbridge-knowledge-pipeline-design.md`, `docs/plans/2026-06-06-techbridge-knowledge-pipeline.md`
- **대상 채널**: TechBridge-KR (`UC895rbZX2iXLTDfji7W4PfA`) — 해외(영어) AI/개발 강연을 한글자막 입혀 재업로드하는 큐레이션 채널.
- **산출 대상**: `C:\workspace\obsidian\charde_n\학습노트\TechBridge-KR\`

### 트리거
> *"TechBridge 새 영상 처리해줘"*, *"이 유튜브 영상 전사해서 노트로"* + URL, *"채널 백필 더 돌려줘"*

### 핵심 사실 (반드시 기억)
- **오디오는 영어**, 한글자막은 영상에 구워박혀(burned-in) 텍스트 추출 불가 → **Whisper로 영어 원본 전사**(`-Language auto` → en). 한글 자동자막 쓰지 말 것.
- yt-dlp는 **`--js-runtimes node`** 필수. 음성만 받아 16k mono wav 직접 산출.
- 전사 종료코드 무시(산출물 검증이 진실) — `transcribe.ps1`가 처리.

### 단계
```powershell
# 1. (백필) 채널 스캔 → 큐레이션 → 차드 확인
python workflow\youtube\yt_channel_scan.py --months 3
python workflow\youtube\curate.py --top 50      # 표 보여주고 가감 확정 ← 게이트

# 2. 배치 전사 (워크스페이스는 메인 체크아웃에 영구 저장)
.\workflow\youtube\run_youtube.ps1 -Queue workflow\youtube\state\curated_queue.json -RootDir "C:\workspace\wisper-page"

# 3. (Claude) 영상별 transcript.txt + youtube.json → 학습노트 작성 (벌트에 Write)
#    노트작성은 Sonnet 실행자 병렬(Workflow) 권장. 포맷은 note_template.md.

# 4. 인덱스 갱신
python workflow\youtube\rebuild_index.py
```

### 노트 정책 (Claude가 직접 작성)
- 영상 1개 = 노트 1개. **상단에 학습 헤더**: `핵심 학습 포인트(내가 배워야 할 것)` / `내가 모를 만한 것` / `화자의 디테일(흘린 수치·설정·명령어·뉘앙스)`. 그 아래 `## 교정 전사(한국어)` 접기식.
- 한국어로 교정·번역, 핵심 영어 용어 괄호 병기, 음성인식 의심 단어 `[?원문]`(예: `Cloud`→`Claude`).
- frontmatter에 `original_creator`·`original_links`(원작 출처 기록) + `summary`(목차용) 채울 것.
- **이모지 금지.** 강조 스팬 2종(주황 `#ef6c00` / 일반 볼드 1.1em)만. 볼트 학습노트 표준 준수.
- 재사용 용어는 `학습노트\` 루트에 `English-한국어.md` 용어노트로 스필오버 + `[[wikilink]]`.

### 신규 영상 알림 (푸시만, 처리는 승인 후)
- 로컬 `scheduled-tasks` 일일 태스크가 `rss_watch.py --json --mark`로 신규 감지 → **PushNotification으로 제목·URL 보고만**. 차드 "응" 하면 그때 `run_youtube.ps1` + 노트작성.

### 원작 채널 확장 (1단계 = 기록만)
- 채널은 원본 영상 링크를 안 검 — 화자 이름+SNS만 크레딧. 노트 frontmatter에 출처 기록 → `_원작채널.md`에 원작자별 누적. 원작 채널 직접 추적은 차후 단계(YAGNI).

### 푸시 정책
- **wisper-page 리포 push는 차드 승인 후.** 도구·CLAUDE.md·docs 변경만 해당. `workspaces/`·`workflow/youtube/state/`는 gitignore.
- **Obsidian 볼트(로컬 git) 노트 적재는 일반 작업** — 별도 승인 불필요.
