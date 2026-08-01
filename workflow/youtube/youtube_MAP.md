# workflow/youtube — 영역 MAP (에이전트 항법도)

> YouTube 채널 → Obsidian 학습노트 → GitHub Pages 발행. 이 영역 작업 착수 전에 먼저 읽는다.
> 최종 갱신 2026-08-01(다채널화 P1~P7). 설계 SSOT = `design/2026-08-01_YC-Sequoia-채널-학습노트-자동화-기획서.md`

## 진입점

| 하고 싶은 것 | 명령 |
|---|---|
| 야간 전체(모든 채널) | `python mac/nightly.py` — 차미 cron `youtube-nightly` 23시가 호출 |
| 감지·점수만 보기 | `python mac/nightly.py --dry` |
| 한 채널만 | `python mac/nightly.py --channel yc --limit 1` |
| 영상 1편 전사 | `python mac/run_youtube.py --channel yc --url <URL>` |
| 자막만 뽑기 | `python mac/caption_fetch.py --url <URL> --workspace <ws>` |
| 노트 1편 작성 | `python mac/author_note.py <ws> --channel yc` |
| 인덱스 재생성 | `python rebuild_index.py` (전 채널) |
| 발행(로컬 검증) | `python mac/publish_study_notes.py --all --no-push` |
| 상태 이관 | `python mac/migrate_state.py` (멱등) |

실행 인터프리터는 **`~/.venvs/whisper-mlx/bin/python`** — mlx-whisper·yaml·markdown·pytest가 여기 있다. 시스템 python3에는 `markdown`이 없어 발행이 죽는다.

## 구성

```
config.json          channels[] (머신 로컬·gitignored) + 구 평면 키 병존
keywords.json        {"ai":[...], "startup":[...]} — keywordSet은 "ai+startup" 처럼 합집합
yt_lib.py            Channel dataclass · load_channels() · load_keywords() · state_name()
rss_watch.py         채널 RSS 폴링(404 재시도 4회 — YouTube가 간헐적으로 뱉는다)
curate.py            제목 점수(topic·concept·speaker·view)
rebuild_index.py     채널별 _목차.md · _원작채널.md
mac/
  nightly.py         오케스트레이터: 채널 루프 · 실패 격리 · summary
  run_youtube.py     페치+전사 (caption 우선 → whisper 폴백)
  caption_fetch.py   자막 트랙 선택 · VTT 파싱 · 품질 게이트
  yt_fetch.py        오디오 다운로드(whisper 경로)
  transcribe_mlx.py  Whisper(mlx)
  transcript_clean.py 교정(gpt-5.4-mini) — 자막 입력이면 문장부호 복원 지시 추가
  author_note.py     노트 작성(gpt-5.5) — 채널명·저장폴더·에이폼 섹션 주입
  publish_study_notes.py 발행 + 랜딩(채널 칩) + 프루닝 가드
  migrate_state.py   seen 상태 채널별 이관
state/               seen_<key>.json · meta_cache_<key>.json · failures_<key>.json (gitignored)
```

## ★ 음성지식 (안 한 것·왜·함정)

**함정 1 — 발행 프루닝이 노트를 지운다.** `publish_study_notes.py --all`은 "볼트에 없는 slug 폴더는 삭제"다. 채널을 늘리면서 일부 채널만 수집하면 나머지가 유령으로 판정돼 **통째로 삭제**된다. 그래서 ① `--channel` 지정 시 프루닝 완전 잠금 ② `--all`에서도 `prune_guard()`가 `BEFORE ⊆ AFTER`를 검사해 사라지는 slug가 있으면 `exit 3`으로 중단한다. **개수 비교가 아니라 집합 포함**으로 판정 — 신규 증가가 유실을 가리기 때문이다.

**함정 2 — seen 상태를 지우면 밤새 폭주한다.** `seen_<key>.json`이 비면 과거 영상 전부가 "신규"로 재감지된다(TechBridge 152편). `migrate_state.py`는 그래서 빈 seen·손상 JSON·신구 충돌을 **덮지 않고 중단**하고, rename이 아니라 **copy + 백업**을 한다.

**함정 3 — RSS에는 영상 길이가 없다.** 피드는 `id·title·published·url`뿐이다. `minDurationMin`을 쓰려면 yt-dlp를 따로 불러야 해서, **제목 점수를 통과한 것만** duration을 조회하고 `meta_cache_<key>.json`에 캐시한다. 전량 조회하면 신규가 몰린 날 호출이 폭증한다.

**함정 4 — 자동자막에 메타 헤더가 섞인다.** yt-dlp 자동자막은 `WEBVTT` 뒤에 `Kind: captions` / `Language: en`을 붙인다. 안 걸러내면 본문 첫 두 줄로 새어나온다(2026-08-01 실측으로 잡음). `>>` 화자 전환 마커는 **일부러 남긴다** — 자동자막의 유일한 화자 신호이고 교정 단계가 문단으로 바꾼다.

**함정 5 — 채널 자체 실패와 영상 실패를 섞지 마라.** `ChannelResult.n_fail`은 "처리를 시도했으나 실패한 영상 수"다. RSS가 죽거나 설정이 틀린 경우는 `channel_error`에만 잡힌다. 섞으면 summary가 거짓말을 한다. 마찬가지로 격리 카운터(`failures_<key>.json`)는 **영상 고유 실패만** 센다 — 프록시가 사흘 죽었다고 멀쩡한 영상이 격리되면 안 된다.

**함정 6 — 채널 폴더가 이미 있을 수 있다.** Sequoia는 `학습노트/Sequoia Capital/`에 노트 3편이 2026-07-02부터 있었는데 `noteDir: "Sequoia"`로 적어 폴더가 둘로 갈렸다(2026-08-01 발견·합류). 채널을 추가할 때는 `ls 학습노트/`로 **기존 폴더명을 먼저 확인**하고 `noteDir`을 거기 맞춘다. 새로 만드는 것보다 합류가 이득이다 — 기존 노트가 발행 대상에 자동 편입된다.

**안 한 것 1 — 백필.** 두 신규 채널의 과거 영상은 소급하지 않는다(신규 업로드부터). 필요하면 별도 1회성 실행.

**안 한 것 2 — nightly의 구 평면 키 제거.** `config.json`에 `vaultNoteDir` 등 구 키를 **일부러 남겼다**. 이관 도중 구 코드가 돌아도 안 깨지게 하기 위함이고, `load_channels()`는 `channels[]`를 쓰며 구 키 무시를 로그로 알린다. 안정화되면 제거 가능.

**안 한 것 3 — 채널 자동 발견·4번째 채널.** `channels[]`가 배열이라 항목만 추가하면 된다. 코드에 채널을 박지 않는다.

**안 한 것 4 — 랜딩 필터의 JS.** 순수 CSS(숨은 radio + `:has()`)로 구현했다. GitHub Pages 정적 파일에 JS를 넣으면 캐시·CSP·디버깅 표면이 는다.

**신선도 계약** — `nightly.py`는 성공 시에만 `~/.gbrain/.heartbeat/kr.apom.youtube-nightly`를 touch한다. 전 채널 실패면 touch하지 않고 `exit 1` — 관제탑이 신선도 만료로 잡는다. exit 코드만 믿지 않는다.

## SSOT 조회 경로

| 알고 싶은 것 | 어디 |
|---|---|
| 불변식·로드맵·게이트 | `docs/CHARTER.md` |
| 워크플로우 절차 | `AGENTS.md` §YouTube 채널 지식화 |
| 다채널 설계 근거·테스트 벡터 | `design/2026-08-01_YC-Sequoia-채널-학습노트-자동화-기획서.md` |
| 페이즈 진행 상태 | `design/phase-state.json` · `design/scoreboard.json` |
| 노트 양식 | `workflow/youtube/note_template.md` + 스킬 `cha-study-notes` |
| 어젯밤 결과 | `/tmp/techbridge-nightly-summary.json` |

## 테스트

```bash
~/.venvs/whisper-mlx/bin/python -m pytest tests/test_channels_config.py \
  tests/test_migrate_state.py tests/test_caption_fetch.py tests/test_channel_isolation.py -q
```
`tests/test_update_pages_index.py`는 이 영역과 무관하며 2026-08-01 현재 실패 상태다(다른 작업의 미완성 변경).
