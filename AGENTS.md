# AGENTS.md
> 이 레포의 문서·주석·커밋은 한국어. 같은 톤으로 작업한다.
> 지침 SSOT는 이 파일(에이전트 공용 — Claude·Codex). `CLAUDE.md`는 `@AGENTS.md` 한 줄. 표준 → 스킬 `cha-proj-init`.

## 무엇인가
지피터스 스터디 라이브 강의 mp4를 모바일 최적화 GitHub Pages 보고서로 변환하는 워크플로우. 새 영상이 들어오면 아래 7단계를 자동 진행한다. 별개 서브워크플로우로 YouTube 채널(TechBridge-KR) 전사 → Obsidian 학습노트화도 지원(§YouTube 지식화).

- 리포 레이아웃: `workflow/`(도구 스크립트, 수정 시 다음 영상에도 반영) · `workspaces/<basename>/`(영상별 작업물, gitignore) · `결과물/`(전사 정리본 모음, gitignore) · `docs/specs/`·`docs/plans/`(설계·계획) · `workflow/youtube/`(YouTube 서브워크플로우)
- 산출 리포는 별도: `charde023/page`(강의 정리본 게시, `https://charde023.github.io/page/`)

## 트리거
- *"지피터스-YYYY-MM-DD-주제.mp4 처리해줘"* / *"이 영상도 진행해줘"* + 영상 경로 / *"새 강의 가이드 만들어줘"* → 즉시 7단계 시작. 영상 경로가 모호하면 절대 경로 한 번만 확인.
- *"TechBridge 새 영상 처리해줘"* / *"이 유튜브 영상 전사해서 노트로"* + URL / *"채널 백필 더 돌려줘"* → §YouTube 지식화.

## 명령어 (7단계 워크플로우)

1. **영상 메타 확인**: `ffprobe -i "<video.mp4>" -show_entries format=duration -v quiet -of csv="p=0"` → 길이 보고 + 전사 예상시간 안내(GPU ~5분/시간, CPU ~30분/시간).
2. **작업 폴더 생성**: `.\workflow\new_workspace.ps1 -VideoFile "<영상 절대 경로>"` → `workspaces/<basename>/` 생성, `.video-path`·`pipeline.json` 초기화. `transcribe.py`·`make_html.py`는 워크스페이스에 복사되지 않음 — `workflow/_template/`의 정본을 `--workspace` 플래그로 직접 호출.
   - 원클릭: `.\workflow\run.ps1 -VideoFile "<영상 절대 경로>"` → Step1-4 자동(`new_workspace`→`extract_audio`→`transcribe.ps1`). 전사만 필요하면 `-TranscribeOnly` (→ 전사 전용 모드 참고).
3. **오디오 추출**: `.\workflow\extract_audio.ps1 -Workspace ".\workspaces\<basename>"` → `audio.wav`(16kHz mono), `pipeline.json`의 `audio` 스테이지 스탬프.
4. **Whisper 전사** (반드시 `run_in_background: true`, 5~30분+): `.\workflow\transcribe.ps1 -Workspace ".\workspaces\<basename>"` (권장 — exit code 127을 내부 처리, 산출물 존재 여부로 성공 판정) 또는 `python workflow/_template/transcribe.py --workspace "workspaces/<basename>"`. 산출물: `transcript.txt`·`transcript.srt`·`segments.json`·`progress.log`.
5. **transcript_clean.md 작성** (에이전트가 직접): 음성인식 오류·맞춤법·고유명사만 수정, 의미변경·요약·재배열 없음, 의심 단어는 `[?원문]`(예: `Cline [?Crawl]`), 같은 표현 중복·말더듬·잡담은 압축 가능, 파일 상단 헤더(원본 파일명·segments 수·영상 길이·정책 명시). 1시간 넘으면 `transcript.txt`를 청크로(`offset/limit`) 점진 정리.
6. **guide.md 작성** (에이전트가 직접, 가장 중요):
   - frontmatter 필수: `title`(h1과 동일)·`eyebrow`(지피터스 22기 · 끌림 영상 스터디)·`subtitle`(YYYY-MM-DD 라이브 강의 정리본)·`source`(mp4 파일명)·`description`(og 한 줄)·`date`
   - 구조(위→아래 상세도 심화, 모바일에서 위쪽만 읽어도 핵심 전달): `# 제목` → 메타 인용구 → `## 결론(TL;DR)`(표·구조화 필수, 줄글 금지 — 한 줄 요약 인용구 + 강사별 비교 표 + "챙겨야 할 N가지" 표) → `## 강의는 어떤 내용이었나`(1-2문단 + 구성 표) → `## 0. 한눈에 보는 [주제]`(번호 단계) → `## 1.~N.`(상세 본문) → (선택) 부록/체크리스트/함정
   - 이모지 금지(명시 요청 없는 한). 강조는 **볼드** 또는 `> 인용구`. 골격은 `workflow/_template/guide-template.md`. 푸시 전 `python workflow/lint_guide.py <guide.md>`.
   - Slug: `YYYY-MM-DD-<짧은-주제>`
7. **HTML 생성 + publish + 배포**: 원클릭 `.\workflow\deploy.ps1 -Workspace ".\workspaces\<basename>" -Slug <slug>` (HTML생성→stage→page-repo 복사→인덱스 갱신→git push). 수동 단계는 `make_html.py`→`stage_publish.py`→`Copy-Item`→`update_pages_index.py`→git commit/push 순. `pageRepoPath` 등 머신별 경로는 `workflow/config.json`(gitignored, 없으면 `config.example.json` 복사). 배포 후 1~2분 대기 → WebFetch로 `https://charde023.github.io/page/<slug>/` 검증(캐시 우회 `?v=N`).

### 전사 전용 모드 (TranscribeOnly)
미팅·통화·비강의 녹화 등 guide.md/HTML/배포가 불필요한 경우. `.\workflow\run.ps1 -VideoFile "<녹화 절대 경로>" -TranscribeOnly` → Step1-4만 실행.
- **산출물 저장 위치 = 프로젝트 루트 `결과물/` 폴더로 통일**(워크스페이스에 흩어두지 않음). **파일명 = 영상·녹화 제목**(`transcript_clean.md` 같은 고정명 금지 — 여러 건 구분 불가). 윈도우 금지문자 `\ / : * ? " < > |`는 제거 또는 ` - ` 치환.
- 일반 미팅/통화: 화자 구분(`**홍길동**: …`) + 파일 상단 요지 표. 여러 건은 하나의 md로 병합(시간순, 파일명 헤더 구분). 어휘·문장은 맞춤법·오인식만 교정, 타임스탬프 미기록, 요약·재배열 없음.

### YouTube 다운로드 워크플로우
권한 있는 YouTube URL을 받으면 먼저 `C:\workspace\wisper-page\영상자료`에 다운로드(파일명 `YYYY-MM-DD 제목.mp4`, 날짜는 제목 내 `YYYY-MM-DD` 우선 없으면 `upload_date`). 배치는 `workflow/pages_catalog.json`에 URL·로컬파일명·slug·상태·정렬순서 기록. 중복 판단: 같은 영상ID/같은 날짜·제목 파일/이미 배포된 `page-repo/<slug>/guide.md`.
```powershell
yt-dlp --no-playlist --no-progress -f "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/best" --merge-output-format mp4 -P "C:\workspace\wisper-page\영상자료" -o "%(upload_date>%Y-%m-%d)s %(title).180B [%(id)s].%(ext)s" "<YouTube URL>"
```
다운로드 후: 제목 앞 `YYYY-MM-DD |`/`｜`는 최종 파일명 날짜로 사용, `[VIDEO_ID]` 제거, `ffprobe`로 duration·size 검증. 기존 페이지 있으면 재전사하지 않고 카탈로그에서 `published` 계열 상태로 연결.

### YouTube 채널 지식화 — 다채널 → Obsidian (별개 워크플로우)
로컬 mp4→Pages와는 별개: YouTube 채널 영상을 전사해 **Obsidian 학습노트**로 만든다(Pages 배포 없음). 도구는 `workflow/youtube/`(README 참고), 전사 인프라(`transcribe.ps1`·`_template/transcribe.py`·manifest)는 위 파이프라인과 공유. **대상 채널 3개**(설정 `workflow/youtube/config.json` 의 `channels[]` — 코드에 채널을 박지 않는다): TechBridge-KR(`UC895rbZX2iXLTDfji7W4PfA`, 한글자막 큐레이션, **Whisper 전사**) · Y Combinator(`UCcefcZRL2oaA_uBNeo5UOWg`) · Sequoia Capital(`UCWrF0oN6unbXrWsTN7RctTw`) — 뒤 둘은 영어 원어민이라 **자막(WebVTT) 우선**, 품질 미달 시 Whisper 폴백. 산출: `~/workspace/obsidian/charde_n/학습노트/<noteDir>/` (채널별 폴더 + `_목차.md`). 설계: `docs/specs/2026-06-06-techbridge-knowledge-pipeline-design.md`, `docs/plans/2026-06-06-techbridge-knowledge-pipeline.md`.

핵심 사실: **오디오는 영어**, 한글자막은 burned-in이라 텍스트 추출 불가 → Whisper로 **영어 원본 전사**(`-Language auto`→en, 한글 자동자막 사용 금지). yt-dlp는 `--js-runtimes node` 필수, 음성만 받아 16k mono wav 직접 산출. 전사 종료코드는 무시(산출물 검증이 진실, `transcribe.ps1` 처리).

단계:
```powershell
python workflow\youtube\yt_channel_scan.py --months 3          # 채널 스캔
python workflow\youtube\curate.py --top 50                     # 큐레이션 표 → 차드 확인 게이트
.\workflow\youtube\run_youtube.ps1 -Queue workflow\youtube\state\curated_queue.json -RootDir "C:\workspace\wisper-page"   # 배치 전사(워크스페이스는 메인 체크아웃에 영구 저장)
# (에이전트) 영상별 transcript.txt + youtube.json → 학습노트 작성, 노트작성은 Sonnet 실행자 병렬 권장, 포맷 note_template.md
python workflow\youtube\rebuild_index.py                       # 인덱스 갱신
```
노트 정책: 영상 1개=노트 1개. 상단 학습헤더(`핵심 학습 포인트`/`내가 모를 만한 것`/`화자의 디테일`) + `## 교정 전사(한국어)` 접기식. 한국어 교정·번역 + 핵심 영어 용어 괄호병기 + 의심단어 `[?원문]`(예: `Cloud`→`Claude`). frontmatter에 `original_creator`·`original_links`·`summary` 채움. 이모지 금지, 강조 스팬은 주황(`#ef6c00`)/일반 볼드 1.1em 2종만. 재사용 용어는 `학습노트\` 루트 `English-한국어.md`로 스필오버 + `[[wikilink]]`.
신규 영상 알림: 로컬 `scheduled-tasks` 일일 태스크가 `rss_watch.py --json --mark`로 감지 → PushNotification 제목·URL 보고만, 차드 승인 후 처리. 원작 채널은 화자 크레딧만 기록(직접 추적은 차후, YAGNI).

## 컨벤션
- **답변 짧고 핵심만.** 표·구조화 선호(TL;DR 줄글 금지). 모바일 가독성 1순위(중요한 게 위로). "쭉 진행해줘"면 막힘없이 7단계 끝까지, 사용자 결정 필요 지점만 멈춤. caveman 모드 사용 X(명시 요청 없는 한). 백그라운드 작업은 알림 대기(폴링 금지).
- 페이지 리포 구조(`charde023/page`): `index.html`(루트 카드 인덱스, `update_pages_index.py` 자동생성) + `YYYY-MM-DD-topic/`(`index.html`·`guide.md`·`README.md`). `update_pages_index.py`는 `YYYY-MM-DD-` 접두 폴더만 스캔 — slug 규칙 필수.
- 신규 진행 체크리스트: ffprobe 길이확인 → run.ps1 백그라운드 실행+완료대기 → transcript.txt 읽고 주제파악 → transcript_clean.md 작성 → guide.md 작성 → slug 결정 → lint_guide.py 검증 → **사용자에게 푸시 리포 확인** → deploy.ps1 → 1~2분 후 WebFetch 검증 → 라이브 URL+commit hash 보고.

## 불변식·금지
- **두 리포 역할 분리, 헷갈리지 말 것**: `charde023/wisper-page`(이 프로젝트) = 도구·문서·AGENTS.md 보관, **작업 결과물(워크스페이스·가이드) 푸시 금지** — 도구·AGENTS.md·docs 변경 시에만 사용자 명시 승인 후 푸시. `charde023/page` = 강의 정리본 전용 게시(가이드 결과물 기본 푸시 대상), **매번 사용자에게 어디에 올릴지 확인**.
- Step 7(배포) 시작 전 반드시 확인: *"이번 가이드를 `charde023/page`에 올릴까? 다른 리포에 올릴까?"* 사용자가 다른 리포 지정 시 clone + 인덱스 갱신 스크립트 적용.
- `charde023/page`는 강의 정리본 전용 — 블로그·메모·실험 페이지 등 다른 컨텐츠 올리지 말 것.
- `workspaces/`는 `.gitignore` — 실수로도 wisper-page에 결과물 업로드 금지.
- Obsidian 볼트(로컬 git) 노트 적재는 일반 작업(별도 승인 불필요) — 단 wisper-page 리포 push(도구·AGENTS.md·docs)는 항상 차드 승인 후.

### 알려진 함정
| 상황 | 대응 |
|---|---|
| `cublas64_12.dll` not found | `transcribe.py`에 `os.environ["PATH"]` prepend 패치 적용됨. `_template/`의 최신 버전 사용 |
| Whisper exit code 127 | `transcribe.ps1`이 산출물 존재 여부로 성공 판정하므로 무시. 직접 py 호출 시도 transcript.txt 있으면 진행 |
| 머신별 경로(pageRepoPath 등) | `workflow/config.json`(gitignored) 보관. 없으면 `config.example.json` 복사 후 값 채움 |
| 인덱스 카드에 slug만 표시 | publish 폴더 guide.md에 frontmatter 있는지 확인. `stage_publish.py`는 frontmatter 유지(제거 X) |
| 2시간 넘는 영상 transcript | 한 번에 못 읽음. `Read offset/limit` 청크 단위, 의미 보존하며 압축 |
| 새 폴더 인덱스 누락 | `update_pages_index.py`가 `YYYY-MM-DD-` 접두만 스캔. slug 규칙 준수 |
| GitHub Pages 빌드 캐시 | WebFetch 결과가 옛 버전이면 query string(`?v=2`)로 캐시 우회 |

## 완료의 정의(DoD)·검증
- guide.md는 푸시 전 `python workflow/lint_guide.py <guide.md>` 통과 필수.
- 배포 후 1~2분 대기 → WebFetch로 `https://charde023.github.io/page/<slug>/` 라이브 검증(캐시 우회 `?v=N`) → 라이브 URL + commit hash를 사용자에게 보고해야 완료.
- 전사 전용 모드는 산출물(`결과물/<제목>.md`) 존재 + 화자구분/요지표 포함 여부로 검증.

## MAP 인덱스
- [`workflow/youtube/youtube_MAP.md`](workflow/youtube/youtube_MAP.md) — YouTube 채널 → Obsidian 학습노트 → Pages 발행. 다채널(TechBridge·YC·Sequoia) 설정·자막 우선 경로·프루닝 가드·seen 상태 함정. 이 영역 작업 착수 전 필독(2026-08-01 다채널화로 승격).

## 문서 지도
- 헌장(불변식·로드맵·게이트·열린결정): `docs/CHARTER.md` — 페이즈 착수 전 항상 먼저 읽는다(`cha-dev-phase` Phase 0).
- 의사결정 히스토리: `docs/specs/2026-05-19-video-to-pages-workflow-design.md`(설계서), `docs/plans/2026-05-19-video-to-pages-workflow.md`(실행계획), `docs/specs/2026-06-06-techbridge-knowledge-pipeline-design.md`·`docs/plans/2026-06-06-techbridge-knowledge-pipeline.md`(YouTube 지식화)
- 최신 기획서(구현 대기): `docs/design/2026-07-02_맥-로컬-전사-파이프라인-기획서.md`+`_구현계획서.md`(P2 맥 이식), `docs/design/2026-07-02_학습노트-자동화-파이프라인-기획서.md`+`_구현계획서.md`(P3 무인 자동화)
- 신규 설계·기획 산출물 저장 위치(표준): `design/`(현재 비어있음 — 기존 문서는 위 `docs/design/`에 레거시 배치, 안내는 `design/.keep` 참고)
- 기존 작업 결과: Bandicam 폴더에 남은 5/17·5/18 가이드 작업물 참고 가능
- 핸드오프: `docs/handoff/`(세션 인계 문서, 현재 비어있음)
