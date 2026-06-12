# TechBridge-KR 지식 파이프라인 설계서

> **작성일**: 2026-06-06
> **대상 채널**: [TechBridge-KR](https://www.youtube.com/@TechBridge-KR) (`channel_id = UC895rbZX2iXLTDfji7W4PfA`)
> **산출 대상**: Obsidian 볼트 `C:\workspace\obsidian\charde_n\학습노트\TechBridge-KR\`
> **기반**: `wisper-page` 전사 파이프라인(faster-whisper + ffmpeg + manifest) 재사용
> **목적 한 줄**: 양질의 큐레이션 채널을 발판 삼아 AI/개발 지식을 체계적으로 학습하고, 원작 소스 채널까지 확장한다.

---

## 0. 목적

차드는 TechBridge-KR 채널의 콘텐츠를 **자기 지식으로 만들고 싶다**. 이 채널은 해외(주로 영어) AI/개발 강연을 한글자막 입혀 재업로드하는 큐레이션 채널로, 주제가 거의 전부 AI 코딩·에이전트·하네스(Claude Code, Codex, MCP, Opus 4.8)에 집중되어 차드의 현재 관심사와 정확히 일치한다.

이 파이프라인은 4가지를 한다:

1. **전사 + LLM 교정**: 영상 오디오를 Whisper로 받아쓰고, Claude가 한국어 학습노트로 교정·번역해 Obsidian에 보관.
2. **학습 헤더**: 노트 상단에 "차드가 배워야 할 것 + 화자의 세세한 디테일"을 캐치해 적는다.
3. **신규 알림**: 백필 후, 새 영상이 올라오면 알림 → (승인 시) 동일 패턴으로 노트화.
4. **원작 확장**: 영상이 크레딧하는 원작자·소스를 기록해 누적 인덱스를 만들고, 학습을 원작 채널로 확장하는 발판으로 삼는다.

---

## 1. 결정 사항 요약

| 영역 | 결정 | 근거 |
|---|---|---|
| **백필 범위** | 큐레이션 ~40-60개 먼저, 나머지는 차후 백필 | 3개월 ≈ 170개라 비용·시간 과다. 핵심 토픽 우선 |
| **전사 방식** | yt-dlp로 **음성만** 다운로드 → 로컬 Whisper `large-v3` | 한글 자동자막은 기술용어·고유명사 정확도 낮음 |
| **언어** | Whisper `language=auto` (대부분 영어 원본) | 채널 오디오는 영어. 원본 단어 손실 없이 캡처 |
| **노트 구성** | 영상 1개 = 노트 1개 (학습 헤더 + 접기식 교정 전사) | 기존 '에이전트 강의 정리' 패턴 + 자동 상호링크 대상 |
| **노트 위치** | `학습노트\TechBridge-KR\` | 학습노트 산하 → `study_notes_link.py` 자동 링크 대상 |
| **원작 확장** | 1단계 = 출처 기록만 + 누적 `_원작채널.md` 인덱스 | 채널이 원본 영상 링크는 안 검(화자 이름+SNS만) |
| **신규 알림** | 로컬 scheduled-task로 매일 RSS 체크 → **푸시 알림만**(처리는 승인 후) | 로컬만 GPU·볼트 접근 가능. 원격 cron 부적합 |

---

## 2. 채널 실태 (실측)

| 항목 | 값 |
|---|---|
| 핸들 / 표시명 | `@TechBridge-KR` / "Tech Bridge" |
| channel_id | `UC895rbZX2iXLTDfji7W4PfA` |
| RSS | `https://www.youtube.com/feeds/videos.xml?channel_id=UC895rbZX2iXLTDfji7W4PfA` |
| 규모 | 구독 ~4,120 · 영상 237개 · 개설 2026-01-31 · 하루 ~2개 |
| 콘텐츠 | 영어 강연 + **한글자막 구워박음(burned-in, 소프트자막 없음)**. 모든 제목 `[한글자막]` 접두 |
| 오디오 언어 | 영어 (`en-orig` 자동자막 = 원본 언어 표식) |
| 주제 | Claude Code, Codex, MCP, 에이전트, 하네스, Opus 4.8, agentic engineering |
| 원작자 예 | Nate Herkelman, Philipp Schmid(DeepMind), Charlie Holtz(Conductor), Nick Nisi(WorkOS), Prasenjit Sarkar(Sonar), Andrew Ng |

**핵심 함의**: 채널의 한글 번역은 픽셀에 박혀 텍스트로 추출 불가. 오디오는 영어. → Whisper로 영어 원본을 받아쓰는 것이 **품질상 최선**(화자의 정확한 용어·수치·명령어 보존). 교정·번역은 Claude가 한국어 노트 작성 시 수행.

---

## 3. 아키텍처

### 3-1. 데이터 흐름

```
[신규] yt_fetch.ps1            [재사용] transcribe.ps1        [신규] 노트작성 에이전트        Obsidian
  yt-dlp 음성→16k wav    →     Whisper large-v3 (auto)   →    transcript 읽고 한국어 노트  →   학습노트\TechBridge-KR\
  + youtube.json 메타          transcript.txt/segments       학습헤더 + 교정전사 + 출처        NN_주제.md + _목차 + _원작채널
```

### 3-2. 재사용 vs 신규

| 구분 | 자산 |
|---|---|
| **재사용 그대로** | `_template/transcribe.py`(cublas 패치)·`transcribe.ps1`(산출물 검증)·`lib/manifest.py`·`workspaces/<name>/` 레이아웃 |
| **버림** | GitHub Pages 경로 전체(`make_html.py`·`stage_publish.py`·`update_pages_index.py`·`deploy.ps1`·`config.pageRepoPath`) — Obsidian 목적엔 불필요 |
| **신규** | `workflow/youtube/` 하위 스크립트군(아래 §5) + Obsidian 노트 템플릿 + scheduled-task + CLAUDE 지침 |

### 3-3. 디렉토리 구조

```
wisper-page/
├── workflow/
│   ├── youtube/                       ← 신규 toolset
│   │   ├── yt_channel_scan.py         최근 N개월 영상 목록+메타 → channel_index.json
│   │   ├── curate.py                  토픽·조회수 점수 → curated_queue.json
│   │   ├── yt_fetch.ps1               URL → 워크스페이스(음성 wav + youtube.json + manifest)
│   │   ├── extract_provenance.py      설명 파싱 → 원작자·링크 → provenance
│   │   ├── rebuild_index.py           _목차.md · _원작채널.md 재생성
│   │   ├── rss_watch.py               RSS diff → 새 영상 목록 (scheduled-task용)
│   │   ├── run_youtube.ps1            오케스트레이터: 큐 → (fetch→transcribe) 직렬 배치
│   │   ├── note_template.md           노트 골격(에이전트가 채움)
│   │   └── config.example.json        볼트 경로·channel_id·폴더·모델
│   ├── _template/transcribe.py        ← 재사용 (language auto)
│   └── transcribe.ps1                 ← 재사용
├── workspaces/yt-<videoId>/           ← 영상별 작업물 (gitignore)
│   ├── audio.wav · transcript.txt · segments.json · transcribe.done
│   ├── youtube.json                   메타(url·title·creator·links·date·views·duration)
│   └── .source-url                    YouTube URL
└── docs/specs · docs/plans            이 설계서 + 실행 계획서

C:\workspace\obsidian\charde_n\학습노트\TechBridge-KR\   ← 산출 대상 (별도 볼트)
├── _목차.md                            카드 인덱스 (rebuild_index.py 생성)
├── _원작채널.md                        누적 원작자/소스 인덱스
└── NN_<주제>.md                        영상별 학습노트
```

---

## 4. 노트 포맷 표준 (핵심)

영상 1개 = `학습노트\TechBridge-KR\NN_<주제>.md` 1개. 기존 볼트 '에이전트 강의 정리' 포맷에 **학습 헤더**를 얹는다. 위에서 아래로 갈수록 상세해진다(모바일 가독성 1순위).

### 4-1. frontmatter

```yaml
---
title: <한글자막 접두 제거한 제목>
channel: TechBridge-KR
original_creator: <화자/원작자>
original_affiliation: <소속, 있으면>
original_links: [<화자 SNS/제품 링크>]
video_id: <11자 ID>
url: https://youtu.be/<id>
upload_date: YYYY-MM-DD
duration_min: <분>
status: 정리완료        # 전사완료 | 정리완료
created: YYYY-MM-DD
tags: [학습노트, techbridge-kr, 정리노트, <토픽태그>]
aliases: [<영문 원제 등>]
related: [[...]]
---
```

### 4-2. 본문 골격

```markdown
# <제목>

> [!summary] 한 줄 요약
> (영상 핵심을 한 문장으로)

> [!info] 영상 정보
> 원작자 <이름> · <소속> · 추정 출처 <링크> · 업로드 YYYY-MM-DD · <길이>분 · 전사 Whisper large-v3

---

## 핵심 학습 포인트 (내가 배워야 할 것)
표: | 개념 | 왜 중요한가 | 한 줄 |
(차드가 새로 알거나 익혀야 할 것 3-7개)

## 내가 모를 만한 것 / 처음 보는 것
용어·도구·기법 목록. 재사용 가능한 개념은 [[용어노트]]로 스필오버.

## 화자의 디테일 (놓치기 쉬운 포인트)
화자가 흘리듯 말한 구체 수치·설정값·명령어·뉘앙스를 번호목록으로.
원어 용어는 괄호 병기. "왜 그렇게 말했는지"의 맥락까지.

## 한눈에 보기
표: 섹션별 요지 (영상 흐름 순)

## 1. ~ ## N.
본문 요지 (영상 흐름대로, 상세). 화자 주장·예시·반론 포함.

## 종합 체크리스트
- [ ] 적용/실험해볼 것

> [!cite] 출처
> TechBridge-KR [한글자막] <원제> · <url> · 전사: Whisper large-v3 (auto)

---

## 교정 전사 (한국어)
> [!note]- 전체 전사 펼치기
> (영어 원문을 한국어로 교정·번역. 핵심 영어 용어는 괄호 병기. 말더듬·중복 압축, 의미 보존, 의심 단어 `[?원문]`)
```

### 4-3. 스타일 규칙 (볼트 표준 준수)

- **이모지 금지** (전역 CLAUDE.md).
- 강조 스팬 2종만: 1차 `<span style="color:#ef6c00; font-size:1.1em">**...**</span>`, 2차 `<span style="font-size:1.1em">**...**</span>`. `==하이라이트==` 금지.
- 코드/명령어는 백틱.
- 영어 용어는 한국어 병기, 실제 사전 단어에만 IPA(용어노트 스필오버 시).

### 4-4. 용어노트 스필오버

영상이 재사용 가능한 용어/개념을 소개하면 `학습노트\` 루트에 `English-한국어.md` 형식(study-notes 스킬 양식: 헤드워드+IPA / 1줄 / 3줄 / 설명)으로 별도 노트를 만들고 영상노트에서 `[[wikilink]]`. 영상노트를 용어 사전으로 부풀리지 않는다.

---

## 5. 스크립트별 책임

### 5-1. `yt_channel_scan.py` (신규)
- **입력**: 채널 URL, `--months 3` (또는 `--after YYYYMMDD`), `--all`
- **동작**: `yt-dlp "<채널>/videos" --dateafter "today-3months" --break-on-reject --skip-download` + 영상별 `--print`(id·title·upload_date·view_count·duration·channel) 및 `--write-info-json`(description)
- **출력**: `workflow/youtube/state/channel_index.json` — 영상 메타 배열
- **주의**: `--flat-playlist`는 `upload_date`가 NA → 사용 금지. `--break-on-reject`로 3개월 경계에서 조기 종료(videos 탭은 최신순).

### 5-2. `curate.py` (신규)
- **입력**: `channel_index.json`, `--top 50`
- **동작**: 영상별 점수 = 토픽 키워드 매칭(claude code·agent·harness·mcp·codex·opus·rag·eval·context·prompt·tool use·agentic 등) + 조회수 백분위
- **출력**: `curated_queue.json` — 선정 영상 + 점수 + 선정이유. 차드가 눈으로 가감.

### 5-3. `yt_fetch.ps1` (신규)
- **입력**: `-Url <youtube>` (또는 큐 항목), `-Workspace`(기본 `workspaces/yt-<id>`)
- **동작**:
  1. yt-dlp로 메타 조회 → `video_id`, title, upload_date, view_count, duration, description
  2. `workspaces/yt-<id>/` 생성, `.source-url` 기록
  3. `yt-dlp --js-runtimes node -x --audio-format wav --postprocessor-args "-ar 16000 -ac 1" -o "<ws>/audio.%(ext)s" <URL>` → **audio.wav 직접 생성**
  4. `youtube.json`(메타 + provenance) 기록
  5. `manifest.py init --mode transcribe-only --language auto --video <URL>` + `set audio`
- **비고**: `extract_audio.ps1` 불필요(yt-dlp가 16k wav 직접 산출). `--js-runtimes node` 필수.

### 5-4. `extract_provenance.py` (신규)
- **입력**: `youtube.json`(또는 info.json description)
- **동작**: 설명에서 원작자 이름·SNS(x.com/linkedin/github)·제품 도메인 추출. "관련 링크" 블록 파싱.
- **출력**: `youtube.json`에 `provenance` 병합 + `_원작채널.md` 누적 인덱스 갱신 입력.

### 5-5. `rebuild_index.py` (신규)
- **동작**: `학습노트\TechBridge-KR\*.md` frontmatter 스캔 → `_목차.md`(`| 노트 | 한 줄 요약 |` 표, DB지식/APOM `_목차` 양식) + 모든 노트 provenance 집계 → `_원작채널.md`(원작자별 → 참조 영상 목록).

### 5-6. `rss_watch.py` (신규)
- **입력**: channel_id, `state/seen_videos.json`
- **동작**: RSS fetch → 신규 video_id diff → 신규 목록 반환(JSON/표) + `seen_videos.json` 갱신(옵션). scheduled-task가 호출해 **푸시 알림만**.

### 5-7. `run_youtube.ps1` (신규 오케스트레이터)
- **입력**: `-Queue curated_queue.json` 또는 `-Url <list>`
- **동작**: 각 영상 직렬(GPU VRAM 경합 방지): `yt_fetch.ps1` → `transcribe.ps1 -Language auto -Model large-v3 -Device cuda`. 산출물 검증 후 다음. 노트작성은 별도(에이전트 배치).

### 5-8. 노트작성 (스크립트 아님 — 에이전트 배치)
- **주체**: Claude / Sonnet 실행자 N개 병렬(Workflow). 영상별 `transcript.txt` + `youtube.json` 읽고 §4 포맷대로 노트 작성 → 볼트에 Write.
- **고정**: `note_template.md` + CLAUDE 지침(+선택적 `techbridge-note` 스킬)으로 포맷 일관성 보장.

---

## 6. 신규 영상 자동화 설계

| 요소 | 내용 |
|---|---|
| **메커니즘** | 로컬 `scheduled-tasks` MCP `create_scheduled_task` (이 PC에서만 GPU·볼트 접근 가능) |
| **주기** | 매일 1회 (정시·30분 회피, 예: 09:37). 채널 ~2개/일이라 충분 |
| **동작** | `rss_watch.py`로 RSS diff → 신규 있으면 **PushNotification(proactive)으로 차드에게 알림만**. 제목·URL·길이 보고 |
| **처리** | 차드 승인 후 `run_youtube.ps1` + 노트작성 (자동 전사 X — 차드 선택) |
| **상태** | `state/seen_videos.json` + yt-dlp `--download-archive`로 중복 방지 |

---

## 7. 원작 채널 확장 (1단계 = 기록만)

- 채널은 원본 영상 링크를 **안 검**. 설명에 화자 이름 + 개인 SNS만 크레딧.
- **1단계(이번)**: 노트마다 `original_creator`·`original_links`를 provenance로 기록 → `_원작채널.md`에 "원작자 → 참조 영상" 누적.
- **차후 단계(범위 밖, 인덱스가 쌓이면)**: 원작 채널을 찾아 워치리스트화 / 원본 영상 직접 전사. 지금은 YAGNI.

---

## 8. 위험과 완화

| # | 위험 | 영향 | 완화 |
|---|---|---|---|
| 1 | yt-dlp JS 런타임 경고 (nsig 미해독 → 다운로드 throttle/실패) | 다운로드 블로킹 | `--js-runtimes node`(node v24 설치됨) 명시. 첫 영상 스모크테스트로 검증 |
| 2 | 영어 오디오 → 한글 노트 번역 부담 | 노트작성 토큰·시간 증가 | 큐레이션으로 범위 축소. Sonnet 실행자 병렬. 원문 영어 transcript 보존 |
| 3 | 3개월 ≈ 170개 과다 | 비용·시간 폭증 | 큐레이션 40-60개로 게이트. 나머지 차후 배치 |
| 4 | Whisper 고유명사·코드명 오인식 | 노트 정확도 | 교정 단계에서 맥락 보정, 의심 단어 `[?원문]` |
| 5 | 워크스페이스가 worktree에 생성되면 정리 시 소실 | 전사 재실행 필요 | 산출물(노트)은 볼트에 영구 저장. 워크스페이스는 중간물(gitignore). 실제 런은 메인 체크아웃 `workspaces/`에서 |
| 6 | yt-dlp 추출기 변경으로 메타/포맷 실패 | 스캔·다운로드 깨짐 | `yt-dlp -U` 최신 유지. 실패 시 단건 재시도 |
| 7 | scheduled-task가 앱 꺼져 있으면 미실행 | 알림 지연 | 다음 실행 시 보충. 누적 diff라 누락 없음(seen 상태 기준) |
| 8 | 자동 상호링크가 영상노트까지 과링크 | 노트 노이즈 | `study_notes_link.py`는 학습노트 전용 — 동작 확인 후 필요시 영상노트 제외 규칙 |

---

## 9. 비범위 (Out of Scope)

- 원본(영어) 영상 직접 추적·전사 (2단계 이후)
- 자동 전사 + 무인 노트작성 (차드는 "승인 후 처리" 선택)
- GitHub Pages 발행 (이 파이프라인은 Obsidian 전용)
- 영상 임베드·자막 burn 추출(OCR)
- 전체 237개 일괄 백필 (큐레이션 후 차후)

---

## 10. 다음 단계

이 설계서 → 실행 계획서(`docs/plans/2026-06-06-techbridge-knowledge-pipeline.md`) → 하네스 구축(Phase 0) → 채널 스캔·큐레이션(Phase 1, **차드 확인 게이트**) → 배치 전사·노트작성(Phase 2-4) → 신규 알림(Phase 5) → CLAUDE 지침·스킬(Phase 6).
