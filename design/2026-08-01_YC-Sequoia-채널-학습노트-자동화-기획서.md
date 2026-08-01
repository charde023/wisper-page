---
title: YC·Sequoia 채널 학습노트 자동화 기획서
date: 2026-08-01
project: wisper-page
area: workflow/youtube
status: 기획완료(구현 대기)
---

# YC·Sequoia 채널 학습노트 자동화 기획서

> 대상: `https://www.youtube.com/@ycombinator/videos`, `https://www.youtube.com/@sequoiacapital/videos`
> 산출: `https://charde023.github.io/page/study-notes/` 에 TechBridge-KR과 **같은 리포트로 합류** + 야간 무인 자동화 편입

---

## 1. 결론 (TL;DR)

| 항목 | 결정 |
|---|---|
| **기존 파이프라인 재사용** | 새로 안 만든다. `workflow/youtube/`의 감시→큐레이션→전사→교정→노트→발행 라인을 **다채널화**해서 채널 2개를 얹는다 |
| **가장 큰 구조 변경** | 단일 채널 하드코딩(`config.json` 1세트·`seen_videos.json` 1개·볼트폴더 1개)을 **`channels[]` 배열**로 전환. 하위호환 어댑터로 TechBridge-KR은 무손상 |
| **전사 방식** | YC·Sequoia는 **YouTube 자동자막(en) 우선**, 실패·품질미달 시 Whisper 폴백. TechBridge-KR은 지금처럼 Whisper 고정 |
| **왜 자막 우선인가** | 실측: YC 영상 31~76분, Sequoia 45~70분. 주 5~8편이면 Whisper 전사만 매일 10~20분. 두 채널은 **영어 원어민 + `en`/`en-orig` 자동자막 실재**(오늘 yt-dlp로 확인) → 전사 단계를 초 단위로 압축 |
| **큐레이션** | 채널별 키워드·임계·**길이 하한(8분)** 분리. YC/Sequoia는 창업·성장·제품·조직 축을 추가하지 않으면 현 AI/코딩 키워드로는 대부분 스킵된다 |
| **발행 페이지** | `study-notes/` 그룹 **유지**(URL 안 바뀜). 랜딩에 채널 배지 + 필터 칩 추가, 카드 slug는 이미 `업로드일-영상ID`라 채널 간 충돌 없음 |
| **볼트 저장** | `학습노트/Y-Combinator/` 신설 + **`학습노트/Sequoia Capital/` 는 기존 폴더 재사용**(2026-07-02부터 노트 3편 존재 — 구현 중 발견). 채널별 `_목차.md`·`_원작채널.md` |
| **야간 배선** | 기존 `techbridge-nightly`(차미 cron 23시) 잡을 **`youtube-study`로 개명·확장**. 채널 루프 + 채널별 실패 격리 + 채널별 일일 상한 |
| **기본 볼륨** | 신규 채널 **하루 2편**·TechBridge 현행 **3편** 유지 = 합산 최대 **7편/일**(폭주 방지). 과거 영상 백필은 **기본 안 함** — 원하면 별도 1회성 실행 |

**한 줄**: 파이프라인을 새로 짓는 게 아니라 "채널 1개용"으로 굳어 있는 곳 6군데를 배열로 풀고, 두 채널은 자막 경로를 태워 붙인다.

### 1-1. 영향 범위 (누가·무엇이 영향받나)

| 대상 | 무엇이 바뀌나 | 나쁘게 흘러가면 |
|---|---|---|
| **차드**(유일 소비자) | 볼트 학습노트 폴더 3개, 웹 학습노트에 채널 필터 등장, 밤마다 노트 1~3편 증가(상한 7) | 노트 홍수로 읽지 않게 됨 → `dailyMax`·임계로 통제 |
| **`study-notes` 웹페이지 독자** | 랜딩 헤더 문구·카드 배지 변경. **기존 URL 151개는 전부 그대로** | 프루닝 사고 시 기존 페이지 404 → P5 하드게이트 |
| **볼트 야간 파이프라인**(`obsidian-organize-nightly`, 22시) | 학습노트 폴더가 3개로 늘어 링커·커밋 대상 증가 | 23시 youtube-study와 커밋 충돌 → 볼트 커밋은 `fetch`+`reset --soft origin/main` 현행 방식 유지 |
| **차미 cron / 슬랙 보고** | 잡 이름 `techbridge-nightly` → `youtube-study`, summary JSON에 채널별 집계 추가 | 개명 누락 시 잡이 사라진 채로 조용히 안 돎 → P7에서 구잡 삭제 전 신잡 1회 성공 확인 |
| **관제탑**(Monitoring-dashboard) | 카드 라벨 `kr.techbridge.nightly` → `kr.apom.youtube-study` | heartbeat 경로 불일치 시 "죽은 잡"으로 표시 → 앵커 plist·heartbeat 동시 교체 |
| **코덱스 프록시**(:18080) | LLM 호출량 증가(교정+노트, 하루 최대 7편 = 3+2+2) | 큐 지연 → `dailyMax` 상한이 1차 방어 |

운영 책임자 = 차드 단독(1인 운영, 별도 온콜 없음). 장애 시 통지 경로 = 기존 그대로(맥 데스크톱 알림 + 차미 슬랙 보고).

### 1-2. Out of Scope (이번에 **안 하는** 것)

- **과거 영상 백필** — 신규 업로드부터. 소급은 별도 1회성 실행(§6-①).
- **새 URL·별도 랜딩 신설** — `study-notes/` 한 그룹 유지.
- **기존 TechBridge 노트 151개의 본문 재생성·재교정** — 손대지 않는다(발행 HTML만 새 템플릿으로 재빌드).
- **Whisper 모델·전사 파라미터 변경** — TechBridge 경로는 무손상.
- **야간 실행 시각 변경**(23시 유지)·볼트 야간(22시) 파이프라인 수정.
- **채널 3개 초과 확장·채널 자동 발견**(YAGNI. `channels[]`가 배열이라 나중에 항목만 추가).
- **원작자 추적·크리에이터 채널 역방향 수집**(현행 정책 유지 — 크레딧 기록만).
- **노트 품질 자동 평가·재작성 루프**.

---

## 2. 배경 — 지금 파이프라인이 어떻게 생겼나

### 2-1. 현행 흐름 (TechBridge-KR, 정상 가동 중)

```
차미 cron 'techbridge-nightly' (매일 23:00)
  └ mac/nightly.py
      ① rss_watch.fetch_feed(cfg["rssUrl"])        신규 영상 감지 (seen_videos.json)
      ② curate.score_video()                        제목 점수 ≥ TB_CURATE_MIN(1.0)만 통과
      ③ mac/run_youtube.py --url                    yt-dlp 오디오 → transcribe_mlx (Whisper large-v3-turbo/mlx)
      ④ mac/transcript_clean.py                     교정 (코덱스 프록시 :18080, gpt-5.4-mini, 종량 0)
      ⑤ mac/author_note.py                          한국어 학습노트 MD (gpt-5.5) → 볼트
      ⑥ rebuild_index.py + 볼트 git commit·push
      ⑦ mac/publish_study_notes.py --all            charde023/page 의 study-notes/ 전체 재빌드·push
      ⑧ /tmp/…summary.json 기록 → 차미가 읽어 슬랙 보고
```

- 실측 상태: 볼트 `학습노트/TechBridge-KR/` **노트 151개**, 코덱스 프록시 `:18080` 응답 200, `yt-dlp 2026.06.09` 정상.
- 맥 launchd `kr.techbridge.nightly.plist`는 `Disabled=true` **모니터링 앵커**(관제탑이 주기 메타를 읽는 용도). 실제 실행은 차미 cron.

### 2-2. 단일 채널로 굳어 있는 지점 (= 이번 작업 대상)

| # | 파일 | 굳어 있는 것 |
|---|---|---|
| 1 | `workflow/youtube/config.json` | `vaultNoteDir`·`rssUrl`·`channelId`·`topicKeywords`가 **각 1개** |
| 2 | `yt_lib.load_config()` | 평면 dict 반환(`DEFAULTS` → example → local 3중 머지) |
| 3 | `mac/nightly.py` | `cfg["rssUrl"]` 하나, `seen_videos.json` **하나**, `vault_commit(cfg)`가 단일 폴더 |
| 4 | `mac/author_note.py` | 프롬프트 RULES에 `channel(TechBridge-KR)` **문자열 박힘**, 저장 경로 = `vaultNoteDir` 단일 |
| 5 | `rebuild_index.py` | 인덱스 헤더 "TechBridge-KR 학습노트 목차" 하드코딩, `--dir` 1개 |
| 6 | `mac/publish_study_notes.py` | 랜딩 템플릿에 "TechBridge-KR" 브랜딩, `vault.glob("*.md")` 단일 폴더, `--all` 프루닝이 **다른 채널 폴더를 유령으로 오인해 삭제할 위험** |

> ⚠ 6번이 이번 작업의 최대 함정. 지금 `--all`은 "볼트 폴더에 없는 slug 폴더는 전부 rmtree"다. 채널을 늘리면서 이 로직을 안 고치면 **첫 실행에 다른 채널 노트가 통째로 지워진다.**

### 2-3. 두 신규 채널 실측 (2026-08-01, yt-dlp 직접 조회)

| 채널 | channel_id | 최근 영상 길이 | 자동자막 |
|---|---|---|---|
| Y Combinator | `UCcefcZRL2oaA_uBNeo5UOWg` | 31·38·39·40·50·57·65·76분 | `en`, `en-orig` 실재 |
| Sequoia Capital | `UCWrF0oN6unbXrWsTN7RctTw` | 45·49·51·52·55·56·63·70분 | 동일 계열(원어민 채널) |

최근 YC 8편 제목 예: *Sam Altman: "Never a Better Time to Do a Startup"* / *Jensen Huang: The Mindset That Built NVIDIA* / *Boris Cherny: We Cut 80% of Claude Code's Prompt* / *Patrick Collison: Is AI Breaking the Lean Startup Playbook?*
최근 Sequoia 8편 예: *Clay Co-Founder Kareem Amin's Contrarian CEO Playbook* / *Anthropic's Katelyn Lesse & Angela Jiang* / *Kalshi's Tarek Mansour: Chaos by Design* / *Inside Zipline's Autonomous System*.

→ **차드에게 실제로 쓸모 있는 축**: AI/에이전트뿐 아니라 **창업·성장전략·GTM·가격·제품·조직·자동화 운영**. 현 `topicKeywords`(AI·코딩 전용)로 점수를 매기면 위 목록 중 상당수가 임계 미만으로 버려진다.

---

## 3. 설계

### 3-1. 설정 스키마 — `channels[]`

`workflow/youtube/config.json` (머신 로컬, gitignored):

```json
{
  "vaultRoot": "/Users/charde023/workspace/obsidian/charde_n/학습노트",
  "channels": [
    {
      "key": "techbridge",
      "name": "TechBridge-KR",
      "channelId": "UC895rbZX2iXLTDfji7W4PfA",
      "noteDir": "TechBridge-KR",
      "transcriptSource": "whisper",
      "whisperLanguage": "en",
      "titlePrefixStrip": "[한글자막]",
      "minScore": 1.0,
      "minDurationMin": 0,
      "dailyMax": 3,
      "keywordSet": "ai"
    },
    {
      "key": "yc",
      "name": "Y Combinator",
      "channelId": "UCcefcZRL2oaA_uBNeo5UOWg",
      "noteDir": "Y-Combinator",
      "transcriptSource": "caption",
      "captionLangs": ["en", "en-orig"],
      "minScore": 1.0,
      "minDurationMin": 8,
      "dailyMax": 2,
      "keywordSet": "ai+startup"
    },
    {
      "key": "sequoia",
      "name": "Sequoia Capital",
      "channelId": "UCWrF0oN6unbXrWsTN7RctTw",
      "noteDir": "Sequoia",
      "transcriptSource": "caption",
      "captionLangs": ["en", "en-orig"],
      "minScore": 1.0,
      "minDurationMin": 8,
      "dailyMax": 2,
      "keywordSet": "ai+startup"
    }
  ]
}
```

**최상위 `vaultRoot` 계약**: **필수**. 절대경로만(`~`는 확장, 상대경로면 `ValueError`). 없는 폴더면 **생성**한다.
구 설정에서 변환할 때는 `vaultNoteDir`를 쪼개 `vaultRoot = parent`, `noteDir = name`으로 삼는다
(예: `…/학습노트/TechBridge-KR` → `vaultRoot=…/학습노트`, `noteDir=TechBridge-KR`).
`channels`가 있는데 `vaultRoot`가 없으면 에러 — 볼트 위치를 추측하지 않는다.

**필드 계약** (로더 `load_channels()`가 강제):

| 필드 | 필수 | 타입·허용값 | 기본값 | 위반 시 |
|---|---|---|---|---|
| `key` | ✔ | `^[a-z0-9_-]{2,20}$` | — | 즉시 `ValueError`, 전체 실행 중단 |
| `name` | ✔ | 비어있지 않은 문자열 | — | 동일 |
| `channelId` | ✔ | `^UC[A-Za-z0-9_-]{22}$` | — | 동일 |
| `noteDir` | — | 경로 조각(`/`·`..` 금지) | `name` | `..`·절대경로면 `ValueError` |
| `transcriptSource` | — | enum `caption`\|`whisper` | `whisper` | 미지원 값 = `ValueError` |
| `captionLangs` | — | 문자열 배열 | `["en","en-orig"]` | — |
| `whisperLanguage` | — | 문자열 | `en` | — |
| `titlePrefixStrip` | — | 문자열 | `""` | — |
| `keywordSet` | — | `keywords.json`의 키를 `+`로 결합 | `ai` | **미지원 키 = `ValueError`**(조용히 빈 세트로 떨어지면 전부 스킵되어 "도는데 노트 0"이 된다) |
| `minScore` | — | float ≥ 0 | `1.0` | — |
| `minDurationMin` | — | int ≥ 0 | `0` | — |
| `dailyMax` | — | int ≥ 1 | `2` | `0` 이하 = `ValueError` |
| `enabled` | — | bool | `true` | — |

교차 검증(로더가 채널 목록 전체에 대해):
- `key` **중복** → `ValueError`(상태 파일이 덮어써져 seen이 섞인다).
- `noteDir` **중복** → `ValueError`(두 채널 노트가 한 폴더에 섞인다).
- `channelId` 중복 → 경고 로그 후 첫 항목만 사용.
- `channels`가 비었거나 `enabled` 채널이 0개 → 경고 + 정상 종료(0건). 예외 아님.

**구·신 설정 병존 우선순위** (명문화 — 심사 지적):
1. `channels`가 **있으면 그것만** 쓴다. 옛 평면 키(`rssUrl`·`vaultNoteDir`·`topicKeywords`)는 **무시하고 그 사실을 로그로 남긴다**(조용한 무시 금지).
2. `channels`가 **없고** 옛 평면 키가 있으면 → TechBridge 채널 1개로 변환(`key="techbridge"`, `transcriptSource="whisper"`, `keywordSet="ai"`).
3. 둘 다 없으면 → 명시적 에러(`config.json 없음/빈 설정`)로 종료. 기본 채널을 상상해 만들지 않는다.

`rssUrl`은 항상 `channelId`에서 파생(`https://www.youtube.com/feeds/videos.xml?channel_id=<id>`) — 두 곳에 적어 어긋나는 사고를 원천 차단. 설정에 `rssUrl`이 있으면 무시하고 경고.

**키워드 세트** `workflow/youtube/keywords.json` — `{"ai": [...], "startup": [...]}` 평면 맵:
- `ai` — 현행 `topicKeywords` 그대로 이전(값 변경 없음).
- `startup` — 신설: founder, cofounder, fundraising, seed, series a, valuation, pmf, product-market fit, go-to-market, gtm, pricing, growth, retention, churn, distribution, marketplace, supply chain, logistics, ops, hiring, culture, moat, unit economics, margin, b2b, b2c, scaling, enterprise sales, customer, revenue, startup, founder mode.
- `keywordSet: "ai+startup"` = `+`로 분리해 합집합(중복 제거, 소문자 정규화).

### 3-1b. 큐레이션 순서와 영상 길이 취득 (RSS엔 duration이 없다)

`rss_watch.fetch_feed`가 주는 필드는 `id·title·published·url` **뿐이다**. `minDurationMin`을 적용하려면 길이를 따로 얻어야 하므로 순서를 고정한다:

```
① RSS 신규 목록                      (외부 1회)
② 제목 점수 필터  score >= minScore   (호출 0 — 여기서 대부분 떨어진다)
③ ②를 통과한 것만 메타 조회
     yt-dlp --skip-download --no-warnings --print "%(duration)s|%(view_count)s" <url>
   → state/meta_cache_<key>.json 에 {video_id: {duration, view_count, fetched_at}} 캐시
④ 길이 필터  duration/60 >= minDurationMin
⑤ published 최신순 정렬 → 상위 dailyMax 절단 → 처리 큐
```

- **③은 점수 통과분에만** 돈다(영상당 약 1초, 다운로드 없음). 전량 조회하면 신규가 몰린 날 수십 번 호출된다.
- 캐시가 있으면 재조회하지 않는다 — 실패 후 다음 밤 재시도 시 중복 호출 방지.
- **조회 실패 또는 `duration`이 `NA`/null이면 `duration=None`으로 두고 길이 필터를 통과시킨다**(보수적). 뒤의 자막 품질 게이트가 `duration_unknown` 경로로 받는다. 길이를 못 얻었다는 이유로 영상을 버리지 않는다.
- ⑤에서 잘린 초과분은 **seen 마킹하지 않는다** — 다음 밤 다시 후보가 된다.

### 3-2. 전사 소스 — 자막 우선 + Whisper 폴백

신규 `mac/caption_fetch.py`:

```
yt-dlp --skip-download --write-subs --write-auto-subs --sub-langs "en,en-orig" --sub-format vtt
  → VTT 파싱(타임스탬프·중복 롤업 라인 제거) → transcript.txt
  → caption.done 스탬프 + youtube.json 에 transcript_source: "caption" 기록
```

**트랙 선택 우선순위** (첫 번째로 존재하는 것 하나만):
1. 수동 자막 `en` → 2. 수동 자막 `en-*`(en-US 등) → 3. 자동 자막 `en-orig`(원어 트랙) → 4. 자동 자막 `en`.
`en` 계열이 하나도 없으면 자막 경로 실패 → Whisper 폴백. **번역 자동자막(`ko` 등)은 쓰지 않는다** — 기계번역 중역이라 원문 손실.

**VTT 파싱 규칙** (자동자막은 롤업 자막이라 같은 문장이 여러 큐에 반복된다):
1. `WEBVTT` 헤더·`NOTE` 블록·빈 줄 제거. **`Kind:`·`Language:` 메타 헤더도 제거**(yt-dlp 자동자막이 WEBVTT 뒤에 붙인다 — 2026-08-01 실측에서 본문에 새어나온 것을 잡음).
2. `-->` 타임스탬프 줄과 `align:`·`position:` 큐 설정 제거.
3. 인라인 태그 제거: `<c>`·`</c>`·`<00:00:12.480>` 시간 태그·`<v Speaker>` 화자 태그(화자명은 `Speaker: ` 접두로 보존).
4. HTML 엔티티 디코드(`&amp;`·`&#39;`).
5. **롤업 중복 제거**: 직전에 출력한 마지막 줄과 동일하면 버린다. 부분 중복(직전 줄이 현재 줄의 접두사)이면 **증분분만** 이어붙인다.
6. 결과를 문단 없이 한 줄씩 이어 `transcript.txt`로 저장. **`>>` 화자 전환 마커는 지우지 않는다** — 자동자막의 유일한 화자 구분 신호이고, 교정 단계가 이를 문단 경계로 바꾼다(실측 확인).

**품질 게이트** — 자막이 나왔다고 무조건 쓰지 않는다. 아래 판정을 순서대로:

| 검사 | 조건 | 실패 시 |
|---|---|---|
| 트랙 존재 | `en` 계열 트랙 1개 이상 | Whisper 폴백 |
| 다운로드 | yt-dlp exit 0 + VTT 파일 존재 | Whisper 폴백 |
| 비어있지 않음 | 파싱 후 단어 수 ≥ 200 | Whisper 폴백 |
| 밀도 | `wpm = 단어수 / 영상분` **≥ 80**(경계 포함 — 정확히 80은 **통과**) | Whisper 폴백 |

- `단어수` = 공백 분리 토큰 수. `영상분` = `youtube.json.duration / 60`(yt-dlp `%(duration)s`, 초).
- **`duration`이 0·없음·비수치**면 밀도 검사를 수행할 수 없으므로 **밀도 검사를 건너뛰고 "단어 수 ≥ 200"만으로 판정**한다(길이 미상을 이유로 무조건 폴백시키면 라이브 아카이브류가 전부 Whisper로 몰린다). 이 경우 `caption_quality: "duration_unknown"` 기록.
- 임계 80의 근거: 원어민 강연 실측 130~170 wpm. 절반 이하면 트랙 일부 누락으로 본다.

**두 경로 모두 실패하면** — 그 영상은 `failed`로 기록하고 **seen 마킹하지 않는다**(다음 밤 재시도).

연속 실패 상태는 `state/failures_<key>.json`이 소유한다:
```json
{ "<video_id>": {"count": 2, "last_error": "no_track", "last_at": "2026-08-01T23:14:02"} }
```
- 실패할 때마다 `count += 1`. **성공하면 그 영상 항목을 삭제**(카운터 초기화).
- `count >= 3`이 되면 그 영상을 격리: seen에 마킹해 재시도를 멈추고 summary의 `quarantined[]`에 `{id, title, last_error}`로 올려 차드가 보게 한다. 조용히 사라지지 않는다.
- 격리 해제 = 해당 항목을 파일에서 지우고 seen에서 제거(수동).

`youtube.json`에 남기는 추적 필드(전후 스키마):
```json
{ "id": "...", "title": "...", "duration": 2341, "channel_key": "yc",
  "transcript_source": "caption" | "whisper" | "whisper(fallback)",
  "caption_lang": "en-orig" | null,
  "caption_quality": "ok" | "duration_unknown" | "low_wpm:62" | "no_track" | null }
```
폴백은 조용히 넘어가지 않는다 — 위 필드가 사후 추적의 진실이고, summary JSON에도 채널별 `n_fallback`을 집계한다.

교정 단계(`transcript_clean.py`)는 그대로 재사용하되, 자막 입력일 때 프롬프트에 **"자동자막이라 문장부호·대소문자·화자 구분이 없다. 문장 경계를 복원하고 고유명사를 교정하라"** 지시를 추가한다.

### 3-3. 상태 파일 — 채널별 분리

| 파일 | 변경 |
|---|---|
| `state/seen_videos.json` | → `state/seen_<key>.json` (`seen_techbridge.json` 등). **기존 파일은 마이그레이션으로 techbridge용으로 이전** — 지우면 151편이 전부 "신규"로 재감지되어 밤새 재처리 폭주 |
| `state/channel_index.json` | → `state/channel_index_<key>.json` |
| summary JSON | 채널별 집계 추가(스키마는 아래 고정) |

**summary JSON 계약 (단일 명명 — `ChannelResult` 필드명을 그대로 직렬화)**:

```json
{
  "generated_at": "2026-08-01T23:41:07",
  "page_url": "https://charde023.github.io/page/study-notes/",
  "n_note": 4, "n_skip": 5, "n_fail": 0,
  "per_channel": {
    "techbridge": {"n_note":2,"n_skip":1,"n_fail":0,"n_fallback":0,"channel_error":null,"quarantined":[]},
    "yc":         {"n_note":2,"n_skip":3,"n_fail":0,"n_fallback":1,"channel_error":null,"quarantined":[]},
    "sequoia":    {"n_note":0,"n_skip":0,"n_fail":0,"n_fallback":0,"channel_error":"HTTPError 404","quarantined":[]}
  },
  "new_notes": [{"title":"…","url":"…","channel":"Y Combinator"}]
}
```
최상위 `n_note`·`n_skip`·`n_fail`은 채널 합계(기존 소비자 호환). 채널 자체 실패는 `n_fail`이 아니라 `channel_error`에만 잡힌다. **다른 명명(`note`·`fail` 등)을 쓰지 않는다.**

**마이그레이션 절차 (멱등 — 몇 번 돌려도 같은 결과)** `mac/migrate_state.py`:

```
1. seen_techbridge.json 이 이미 있고 유효 JSON:
     - seen_videos.json 이 없거나 seen 집합이 **동일** → 아무것도 안 함, "이미 이전됨" 로그 후 exit 0 (멱등)
     - seen_videos.json 이 있고 집합이 **다르면** → 4번(충돌)으로 간다
2. seen_videos.json 없음 + seen_techbridge.json 없음 → 신규 설치로 보고 빈 상태 생성, exit 0
3. seen_videos.json 있음:
     a. JSON 파싱 → 실패하면 중단(exit 2). 손상 파일을 덮지 않는다.
     b. seen 배열이 리스트가 아니거나 비어 있으면 중단(exit 2) — 빈 상태로 덮으면 151편 재처리
     c. seen_videos.json.bak-<YYYYMMDD-HHMMSS> 로 백업 (원본 보존)
     d. seen_techbridge.json 으로 copy (rename 아님 — 구 코드가 남아 있어도 안 깨지게)
     e. 검증: 새 파일 파싱 성공 + len(seen) == 원본 len  → 불일치면 새 파일 삭제 후 exit 2
4. 두 파일이 동시에 존재하고 내용이 다르면 → 병합하지 않고 중단(exit 3) + 양쪽 개수를 출력.
   차드 판단 사항(어느 쪽이 진실인지 자동 추측 금지).
```

롤백 = `.bak-*`를 `seen_videos.json`으로 되돌리고 `seen_techbridge.json` 삭제. 구 파일은 이전 후에도 **삭제하지 않는다**(2주 관찰 후 수동 정리).

### 3-4. 야간 오케스트레이터 — 채널 루프

`mac/nightly.py` 재구성:

```
for ch in channels:
    try:
        feed  = rss(ch)                       # 채널별 seen
        todo  = curate(feed, ch.keywordSet, ch.minScore, ch.minDurationMin)[: ch.dailyMax]
        for v in todo:
            transcript = caption(v) if ch.transcriptSource=="caption" else whisper(v)
            if not transcript: whisper(v)     # 폴백
            clean → note(ch) 
    except Exception:
        기록만 하고 다음 채널로 (채널 단위 실패 격리)
볼트 커밋 1회(전 채널 묶음) → publish_study_notes --all → summary 기록
```

불변식:
- **채널 하나가 죽어도 나머지 채널은 완주**한다.
- `seen` 마킹은 **완주분·저가치 스킵분만**. 실패분은 남겨 다음 밤 재시도(현행 규칙 유지).
- 볼트 커밋·발행은 채널별이 아니라 **끝에 1회** — push 레이스와 커밋 파편화 방지.
- 채널별 `dailyMax`로 상한. 초과분은 seen 마킹하지 않고 다음 밤으로 이월.

### 3-5. 노트 작성 — 채널 파라미터화

`author_note.py`:
- RULES의 `channel(TechBridge-KR)` → `channel({ch.name})` 주입.
- 저장 경로 = `vaultRoot / ch.noteDir / <제목>.md`.
- YC/Sequoia용 프롬프트 보강: **원작자·소속·직함**(대담 형식이라 화자가 핵심), 그리고 마지막에 **"에이폼 적용 관점" 3줄**(차드가 이커머스/물류 운영자라 창업·성장 콘텐츠는 자기 사업에 어떻게 꽂히는지가 핵심 가치) 섹션 추가.
- 파일명 충돌: 채널 폴더가 다르므로 동일 제목이라도 안전. 금지문자 치환은 현행 유지.

### 3-6. 발행 — study-notes 그룹 다채널화

`publish_study_notes.py`:
- 입력을 **채널 폴더 전부** 순회로 확장(`vaultRoot/<noteDir>/*.md`), `--channel <key>`로 단일 채널 실행 가능.
- `meta.json` 전후 스키마:

```json
// 전 (현행)
{"slug","title","summary","upload_date","original_creator","url"}
// 후 (추가 2필드 — 기존 필드 유지, 기존 파일은 재빌드 시 자동 보강)
{"slug","title","summary","upload_date","original_creator","url",
 "channel": "Y Combinator", "channel_key": "yc"}
```
`channel_key`가 없는 기존 meta.json은 **`"techbridge"`로 간주**(마이그레이션 불필요 — `--all` 재빌드가 덮어쓴다).

- **필터 구현 = 순수 CSS 단일 방식으로 확정**(JS 없음): 숨은 라디오 `input` + `label` 칩 + `:has()`/형제 선택자로 카드 표시 제어. 이유 — GitHub Pages 정적 파일이고 JS를 넣으면 캐시·CSP·디버깅 표면이 늘어난다. 필터 상태는 URL에 남지 않아도 무방(랜딩은 진입점일 뿐).
- 랜딩 헤더 문구: "TechBridge-KR 학습노트" → **"AI·창업 유튜브 학습노트"**. eyebrow는 `{채널명}`으로 동적화(개별 노트 페이지도 동일).
- 칩 구성: `전체` / `TechBridge-KR` / `Y Combinator` / `Sequoia` — **채널 목록을 하드코딩하지 않고** 빌드 시 `meta.json`들의 `channel` 유니크 값에서 생성.
- ⚠ **프루닝 안전장치 (2중)**:
  1. `--channel` 지정 실행에서는 프루닝 **완전 잠금**.
  2. `--all`에서도 삭제 전 **부분집합 검사**: 빌드 전 기존 slug 집합 `BEFORE`, 빌드 후 desired 집합 `AFTER`를 비교해 `BEFORE ⊄ AFTER`(= 사라지는 slug가 있음)이면 **삭제하지 않고 중단**하고 사라지는 slug를 전부 출력한다. 진짜 삭제가 의도된 경우에만 `--prune-confirm`으로 통과.

### 3-6b. 기존 볼트 폴더 확인 (구현 중 발견 — 2026-08-01)

`noteDir`을 정하기 전에 **`학습노트/` 아래 그 채널 폴더가 이미 있는지 반드시 확인한다.**
Sequoia는 `Sequoia Capital/`에 노트 3편(Jensen Huang·Logan Kilpatrick·David Senra)이 2026-07-02부터 있었는데, 설정에 `noteDir: "Sequoia"`를 적어 폴더가 둘로 갈렸다. 기존 폴더로 합류시켜 해결했고, 그 결과 **기존 3편이 발행 대상에 자동 편입**됐다(154편).
→ 규칙: `noteDir`은 신설보다 **기존 폴더명 일치가 우선**. 채널 합류 시 `ls 학습노트/`를 먼저 본다.

### 3-7. 인덱스

`rebuild_index.py`에 `--channel` / 전체 순회 추가. 헤더 문구를 채널명으로 동적화. 채널별 `_목차.md`·`_원작채널.md` 생성.

### 3-8. 자동화 등록 (관제탑)

- 차미 cron `techbridge-nightly` → **`youtube-study`**로 개명(호출 스크립트 동일, 인자만 확장).
- 맥 앵커 plist `kr.techbridge.nightly.plist` → `kr.apom.youtube-study.plist`(동일하게 `Disabled=true` 모니터링 앵커, 23:00 유지). 구 plist는 `.retired-2026-08-01`로 보존.
- heartbeat: 실행 성공 시 `~/.gbrain/.heartbeat/kr.apom.youtube-study` touch → 관제탑 registrar가 자동 발견.
- `cha-automation-register` 스킬 절차를 따른다. **관제탑에 안 보이면 만든 게 아니다.**

---

## 4. 구현 단계

| 페이즈 | 내용 | 게이트(통과 조건) |
|---|---|---|
| **P0 기준선** | 현행 TechBridge 파이프라인 `--dry` 실행 스냅샷 + `seen_videos.json`·볼트 노트수(151) 기록 | dry 실행 정상 종료, 기준 수치 문서화 |
| **P1 설정 다채널화** | `channels[]` 스키마 + `yt_lib.load_channels()` + 하위호환 어댑터 + `keywords.json` | 옛 config로도 채널 1개 반환, 새 config로 3개 반환(단위 테스트) |
| **P2 상태 마이그레이션** | `seen_videos.json` → `seen_techbridge.json` **copy(구 파일 보존)**, 채널별 상태 경로 | 마이그레이션 후 TechBridge `--dry`에서 **신규 0건**(재처리 폭주 없음) — 하드 게이트 |
| **P3 자막 경로** | `caption_fetch.py` + 품질 게이트 + Whisper 폴백 + `transcript_source` 기록 | YC 1편·Sequoia 1편 자막 추출 성공, wpm 게이트 동작, 강제 실패 주입 시 폴백 확인 |
| **P4 노트·인덱스** | `author_note.py`·`rebuild_index.py` 채널 파라미터화 + 에이폼 적용 관점 섹션 | 채널당 노트 1개 생성, 볼트 규칙(이모지 금지·강조 2종·frontmatter) 준수 |
| **P5 발행** | `publish_study_notes.py` 다채널 + 랜딩 필터·배지 + **프루닝 가드** | `--no-push` 로컬 빌드에서 3채널 카드 모두 노출 + **빌드 전 slug 집합 ⊆ 빌드 후 집합**(사라지는 slug 0개) — 하드 게이트 |
| **P6 파일럿** | 채널별 1편 end-to-end 수동 실행 → 라이브 URL 검증 | `https://charde023.github.io/page/study-notes/` 에서 신규 노트 3개 확인 |
| **P7 야간 배선** | nightly 채널 루프 + cron 개명 + plist 앵명 교체 + heartbeat + 관제탑 등록 + AGENTS.md·MAP 갱신 | 다음 날 아침 summary JSON에 채널별 집계, 관제탑 카드에 `youtube-study` 노출 |

병렬 가능: P3(자막)과 P4(노트)는 독립 트랙. P5는 P4 완료 후.

### 4-1. 파일별 변경 명세 (구현자가 열어야 할 것 전부)

| 파일 | 종류 | 변경 내용 | 페이즈 |
|---|---|---|---|
| `workflow/youtube/yt_lib.py` | 변경 | `Channel` dataclass + `load_channels()`·`load_keywords()`·`state_name()` 추가. 기존 `load_config()`·`read_state()`·`write_state()`·`run_ytdlp()`·`strip_title_prefix()`는 **시그니처 불변**(구 코드 호환) | P1 |
| `workflow/youtube/keywords.json` | 신규 | `{"ai":[...], "startup":[...]}` | P1 |
| `workflow/youtube/config.example.json` | 변경 | `channels[]` 3개 예시로 교체(구 평면 키 제거) | P1 |
| `workflow/youtube/mac/migrate_state.py` | 신규 | seen 상태 이관(§3-3 절차) | P2 |
| `workflow/youtube/mac/caption_fetch.py` | 신규 | 자막 트랙 선택·VTT 파싱·품질 게이트 | P3 |
| `workflow/youtube/mac/run_youtube.py` | 변경 | `--channel <key>` 수용, `transcript_source`가 `caption`이면 `caption_fetch` 먼저 시도 후 실패 시 기존 whisper 경로 | P3 |
| `workflow/youtube/mac/transcript_clean.py` | 변경 | 입력이 자막이면 프롬프트에 "문장부호·화자 복원" 지시 추가(분기 1개) | P3 |
| `workflow/youtube/mac/author_note.py` | 변경 | `--channel <key>` 수용, RULES의 채널명·저장경로 동적화, 창업 콘텐츠용 지시 추가 | P4 |
| `workflow/youtube/rebuild_index.py` | 변경 | `--channel` / 전체 순회, 헤더 문구 동적화 | P4 |
| `workflow/youtube/mac/publish_study_notes.py` | 변경 | 다채널 수집·`channel` meta·랜딩 칩·**프루닝 가드** | P5 |
| `workflow/youtube/mac/nightly.py` | 변경 | 채널 루프·실패 격리·채널별 집계 | P6·P7 |
| `~/Library/LaunchAgents/kr.apom.youtube-study.plist` | 신규 | 모니터링 앵커(`Disabled=true`, 23:00) | P7 |
| 차미 cron `techbridge-nightly` | 개명 | → `youtube-study` | P7 |
| `AGENTS.md` §YouTube 채널 지식화 | 변경 | 다채널 서술로 갱신 + `workflow/youtube_MAP.md` 신설·인덱스 등록 | P7 |

**신규·변경 인터페이스** (구현자가 추측하지 않게 시그니처 고정):

```python
# yt_lib.py
@dataclass(frozen=True)
class Channel:
    key: str; name: str; channel_id: str; note_dir: str
    transcript_source: str          # "caption" | "whisper"
    caption_langs: tuple[str, ...]; whisper_language: str; title_prefix_strip: str   # frozen → tuple
    keyword_set: str; min_score: float; min_duration_min: int
    daily_max: int; enabled: bool
    @property
    def rss_url(self) -> str: ...              # channel_id에서 파생
    def note_path(self, vault_root: Path) -> Path: ...

def load_channels() -> tuple[Path, list[Channel]]: ...   # (vault_root, enabled 채널만)
def load_keywords(keyword_set: str) -> list[str]: ...    # "ai+startup" → 합집합(소문자·중복제거)
def state_name(base: str, key: str) -> str: ...          # ("seen","yc") → "seen_yc.json"

# mac/caption_fetch.py
@dataclass(frozen=True)
class Track: lang: str; is_manual: bool      # 같은 lang의 수동·자동이 공존할 수 있다
def list_tracks(url: str, js: str) -> list[Track]: ...
def pick_track(tracks: list[Track], prefer: list[str]) -> Track | None: ...
def download_vtt(url: str, track: Track, ws: Path, js: str) -> Path | None: ...   # 수동=--write-subs, 자동=--write-auto-subs
def parse_vtt(path: Path) -> str: ...
def quality_check(text: str, duration_sec: float | None) -> tuple[bool, str]: ...  # (ok, reason)
def fetch_caption(url: str, ws: Path, ch: Channel) -> str | None: ...  # 성공 시 transcript.txt 기록

# mac/publish_study_notes.py
def collect_notes(vault_root: Path, channels: list[Channel],
                  only: str | None = None) -> list[tuple[Channel, Path]]: ...
def existing_slugs(group_dir: Path) -> set[str]: ...
def prune_guard(before: set[str], after: set[str], confirm: bool) -> None: ...  # 위반 시 SystemExit(3)

# mac/nightly.py
@dataclass
class ChannelResult:
    key: str; n_note: int; n_skip: int; n_fail: int; n_fallback: int
    quarantined: list[dict]; done_info: list[dict]; error: str | None
    # 의미 고정: n_fail = "처리를 시도했으나 실패한 영상 수"(0 이상).
    # 채널 자체가 죽은 경우(RSS 실패·설정 오류)는 n_fail=0 + error≠None 이며,
    # summary에서는 per_channel[key].channel_error 로 별도 집계한다(영상 실패와 섞지 않는다).
def run_channel(ch: Channel, vault_root: Path, limit: int = 0) -> ChannelResult: ...
    # limit = nightly --limit (디버그용 채널별 추가 상한). 0 = 무제한.
    # 실효 상한 = min(ch.daily_max, limit) if limit else ch.daily_max
```

**nightly 본체 의사코드** (불변식이 코드 순서에 드러나게):

```python
limit = args.limit                                 # nightly --limit (0=무제한, 기본 0)
cfg_root, channels = load_channels()
if not llm.healthy(): notify("코덱스 프록시 응답 없음 — 중단"); return 2   # 현행 유지
results = []
for ch in channels:
    try:
        results.append(run_channel(ch, cfg_root, limit))   # 실효상한 = min(ch.daily_max, limit or ∞)
        # run_channel 내부 전사 분기 (중복 호출 없음):
        #   if ch.transcript_source == "caption":
        #       text = fetch_caption(...)          # 트랙없음·품질미달이면 None
        #       if text is None: text = whisper(...)      # 폴백은 caption 채널에서만
        #   else:
        #       text = whisper(...)                # whisper 고정 채널은 1회만 시도
        #   if text is None: 실패 기록 (재시도는 다음 밤)
    except Exception as exc:                       # 채널 단위 격리
        results.append(ChannelResult(ch.key, 0,0,0,0, [], [], repr(exc)))
if any(r.n_note for r in results):                 # 커밋·발행은 끝에 1회
    vault_commit(cfg_root)                         # fetch + reset --soft origin/main (현행)
    publish(["--all"])
write_summary(results)                             # 항상 기록 (stale 재보고 방지)
```

**종료 코드·신선도 계약** (전 채널이 죽은 밤에도 조용하지 않게):

| 상황 | exit | heartbeat touch | 슬랙 보고 |
|---|---|---|---|
| 정상(노트 0편 포함) | 0 | ✔ | 신규 0건도 보고 |
| 일부 채널만 실패 | 0 | ✔ | 실패 채널명 + 사유 |
| **전 채널 실패**(`channel_error` 전부 non-null) | **1** | ✘ **touch 안 함** | "전 채널 실패" 명시 |
| 코덱스 프록시 다운(진입 전 중단) | 2 | ✘ | 중단 사유 |

heartbeat를 건너뛰면 관제탑이 신선도 만료로 잡아준다 — exit 코드만 믿지 않는다.

**★래퍼 경유 주의(2026-08-01 발각)**: cron은 nightly.py를 직접 부르지 않고 zsh 래퍼 `~/.hermes/scripts/techbridge_nightly.sh`를 경유한다. 그 래퍼가 종료코드와 무관하게 구 이름 heartbeat를 touch하고 있어 위 계약이 무력화돼 있었다. **heartbeat 계약을 바꾸면 래퍼도 함께 고친다**(래퍼는 차미 소유 — 슬랙 지시).

**격리 카운터에 세는 실패의 범위**: `state/failures_<key>.json`의 `count`는 **그 영상 고유의 실패만** 센다 — 트랙 없음·자막 파싱 실패·전사 실패·LLM 응답 불가(교정/노트). 반대로 **채널·환경 차원의 실패**(RSS 오류, 코덱스 프록시 다운, 설정 오류, 볼트 커밋·발행 실패)는 세지 않는다. 프록시가 사흘 죽었다고 멀쩡한 영상이 격리되면 안 된다.

**`captionLangs`와 트랙 우선순위의 관계**: `captionLangs`는 **후보 언어 집합**(기본 `["en","en-orig"]`)이고, §3-2의 4단계 순서는 그 집합 안에서 적용되는 **선택 규칙**이다. 즉 `captionLangs`에 없는 언어는 수동 자막이어도 쓰지 않고, 집합 안에서는 `수동 > 자동`·`en > en-orig` 순으로 고른다. `captionLangs`를 비우면 자막 경로를 끄는 것과 같다(즉시 Whisper).

**author_note 프롬프트 변경 (전 → 후)**:

| | 현행 | 변경 후 |
|---|---|---|
| 채널명 | `channel(TechBridge-KR)` 고정 | `channel({ch.name})` 주입 |
| 저장 | `Path(cfg["vaultNoteDir"])` | `ch.note_path(vault_root)` |
| 섹션 | …종합 체크리스트 → 출처 → 접기식 전사 | 동일 + **`ch.keyword_set`에 `startup`이 포함된 채널일 때만** 종합 체크리스트 앞에 `## 에이폼 적용 관점`(3줄: 이 얘기가 이커머스/물류 운영에 꽂히는 지점 / 지금 당장 시험할 것 하나 / 우리 상황과 다른 전제 하나) |
| 전사 성격 | 언급 없음 | 자막 입력이면 "자동자막이라 문장부호·화자 구분이 없다. 문장 경계 복원, 고유명사 교정" 한 줄 추가 |

강조 2종·이모지 금지·`[?원문]`·IPA 등 나머지 규칙은 **변경 없음**.

**랜딩 CSS 필터 구조** (JS 0):

```html
<input type="radio" name="ch" id="f-all" checked><label for="f-all">전체</label>
<input type="radio" name="ch" id="f-yc"><label for="f-yc">Y Combinator</label>
...
<ul class="card-list"><li data-ch="yc">…</li></ul>
```
```css
#f-yc:checked ~ .card-list li:not([data-ch="yc"]) { display: none }
```
칩 목록은 빌드 시 `meta.json`의 `channel_key` 유니크 값에서 생성(하드코딩 금지). `id`는 `f-<channel_key>`.

### 4-2. 테스트 벡터 (구현 전 고정 — 이 표가 곧 테스트)

**VTT 파싱** (`parse_vtt`)

| # | 입력 큐 | 기대 출력 |
|---|---|---|
| 1 | `never been a better` / `never been a better time` (롤업 부분중복) | `never been a better time` 한 줄 |
| 2 | 동일 문장 3연속 | 한 줄만 |
| 3 | `<c>hello</c> <00:00:12.480>world` | `hello world` |
| 4 | `&amp;` `&#39;` | `&` `'` |
| 5 | `<v Sam>we shipped` | `Sam: we shipped` |
| 6 | `NOTE ...` 블록·`align:start position:0%` | 제거 |

**품질 게이트** (`quality_check`)

| # | 단어수 | duration(초) | wpm | 판정 |
|---|---|---|---|---|
| 1 | 1600 | 1200 | 80.0 | **통과**(경계 포함) |
| 2 | 1599 | 1200 | 79.95 | 폴백 `low_wpm:79` |
| 3 | 199 | 1200 | — | 폴백 `too_short` (단어수 검사가 먼저) |
| 4 | 500 | `None`/`0` | — | **통과**, `duration_unknown` |
| 5 | 0 | 1200 | — | 폴백 `too_short` |

**로더** (`load_channels`)

| # | 설정 | 기대 |
|---|---|---|
| 1 | `key` 중복 2개 | `ValueError` |
| 2 | `noteDir` 중복 2개 | `ValueError` |
| 3 | `keywordSet: "ai+bogus"` | `ValueError`(빈 세트로 떨어지지 않는다) |
| 4 | `channelId: "XX..."` | `ValueError` |
| 5 | `channels` + 옛 평면 키 병존 | `channels` 사용 + "옛 키 무시" 경고 로그 |
| 6 | 옛 평면 키만 | 채널 1개(`key="techbridge"`, whisper, ai) |
| 7 | 둘 다 없음 | 명시적 에러 종료(기본 채널 상상 금지) |
| 8 | `enabled:false` 채널 포함 | 반환 목록에서 제외 |
| 9 | `channels: []` | 빈 목록 + 경고, 예외 아님 |

**마이그레이션** (`migrate_state`)

| # | 상태 | 기대 |
|---|---|---|
| 1 | 신 파일만 존재 | exit 0, 무변경(멱등) |
| 2 | 둘 다 없음 | 빈 상태 생성, exit 0 |
| 3 | 구 파일만(정상 151개) | 백업 생성 + copy + 개수 검증 통과, exit 0 |
| 4 | 구 파일 JSON 손상 | exit 2, **덮어쓰지 않음** |
| 5 | 구 파일 `seen: []` | exit 2 (빈 상태로 덮으면 재처리 폭주) |
| 6 | 둘 다 존재·내용 동일 | exit 0, 무변경 |
| 7 | 둘 다 존재·내용 상이 | exit 3 + 양쪽 개수 출력, 자동 병합 금지 |

**프루닝 가드** (`prune_guard`)

| # | BEFORE | AFTER | `--channel` | 기대 |
|---|---|---|---|---|
| 1 | {a,b,c} | {a,b,c,d} | 없음 | 통과, 삭제 0 |
| 2 | {a,b,c} | {a,b} | 없음 | **중단**(exit 3) + 사라지는 `c` 출력 |
| 3 | {a,b,c} | {a,b} | `--prune-confirm` | 삭제 진행 |
| 4 | {a,b,c} | {a} | `--channel yc` | 프루닝 **완전 스킵** |

### 4-3. 롤백 절차 (페이즈별)

| 페이즈 | 되돌리기 |
|---|---|
| P1 설정 | `config.json`을 백업본으로 복원. 코드는 하위호환이라 구 설정으로 즉시 정상 동작 |
| P2 상태 | `seen_videos.json.bak-*` → 원위치, `seen_techbridge.json` 삭제 |
| P3 자막 | 해당 채널 `transcriptSource: "whisper"`로 전환(코드 되돌릴 필요 없음) |
| P4 노트 | 잘못 생성된 노트 파일 삭제 + `rebuild_index` 재실행. 볼트는 git이라 `git revert` 가능 |
| P5 발행 | `charde023/page`에서 직전 커밋 `git revert` → 페이지 원복(1~2분) |
| P6·P7 | 차미 cron을 구 `techbridge-nightly`로 되돌리고 신규 채널 `enabled:false` |

가장 위험한 P5는 **push 전에 `--no-push`로 로컬 빌드해 slug 집합을 확인**하므로 실제 롤백까지 갈 일이 없어야 정상이다.

---

## 5. 위험과 대응

| 위험 | 실현되면 | 대응 |
|---|---|---|
| **발행 프루닝이 기존 노트 삭제** | study-notes 151개 페이지 증발 | P5 하드 게이트: `--no-push` 빌드 후 slug 개수 diff 확인. 전 채널 빌드 시에만 프루닝 |
| **seen 상태 유실 → 151편 재처리** | 밤새 폭주, LLM 큐 마비 | P2 하드 게이트: **copy**(구 파일 보존) + 개수 검증 + dry에서 신규 0건 확인 |
| **자동자막 품질 미달** | 노트가 헛소리 | wpm 게이트 + Whisper 폴백 + `transcript_source` 추적 기록 |
| **볼륨 폭주** (YC 업로드 빈도 높음) | 매일 밤 4~6편 처리, 노트 홍수 | 채널별 `dailyMax`(기본 2) + 길이 하한 8분 + 점수 임계 |
| **키워드 미스매치로 전부 스킵** | 자동화는 도는데 노트가 0 | `startup` 키워드 세트 + 파일럿에서 최근 20편 점수 분포 확인 후 임계 보정 |
| **YouTube RSS 간헐 404** | 파이프라인 중단 | 이미 `rss_watch.fetch_feed`에 재시도 4회 구현됨(2026-07-08) — 그대로 상속 |
| **코덱스 프록시 다운** | 교정·노트 단계 실패 | `llm.healthy()` 선체크 존재 — 채널 루프 진입 전 1회 확인 후 중단(현행 유지) |

---

## 6. 결정 사항 (확정 — 구현은 이 값으로 진행)

구현자가 다시 물을 필요 없이 아래 값으로 착수한다. 차드가 뒤집으면 그때 설정값만 바꾼다(전부 `config.json` 한 곳에서 조정 가능하도록 설계했다).

| # | 항목 | **확정값** | 뒤집을 때 드는 비용 |
|---|---|---|---|
| 1 | 백필 | **안 함**. 신규 업로드부터 | 없음. 나중에 `--backfill --months N` 1회성 실행(채널당 20~40편, 하룻밤) |
| 2 | 볼륨 | 신규 채널 **하루 2편**, TechBridge는 **현행 3편 유지**(`dailyMax`) — 3채널 합산 최대 **7편/일** | 없음. 설정 숫자 하나 |
| 3 | 전사 | YC·Sequoia **자막 우선**, Whisper 폴백 / TechBridge는 Whisper 고정 | 없음. `transcriptSource: "whisper"`로 변경 |
| 4 | 노트 톤 | 창업·투자 콘텐츠에 **"에이폼 적용 관점" 3줄 포함** | 프롬프트 한 줄 |
| 5 | 페이지 | `study-notes` **한 그룹 합류** + CSS 필터 | 분리하면 랜딩 3개 관리 — 재작업 발생 |

---

## 7. 완료 기준 (DoD) — 판정값과 검증 명령

| # | 조건 | 검증 방법 | 통과값 |
|---|---|---|---|
| 1 | **기존 노트 무손실** (최우선) | 발행 전후 slug 집합 비교: `BEFORE ⊆ AFTER` | 사라진 slug **0개**. 개수 비교가 아니라 **집합 포함 관계**로 판정(신규 증가가 유실을 가리지 못하게) |
| 2 | 3채널 감시·집계 | `cat $TB_SUMMARY_PATH \| jq '.per_channel \| keys'` | `["sequoia","techbridge","yc"]` 3키 존재 |
| 3 | 랜딩 필터 동작 | `python3 mac/publish_study_notes.py --all --no-push` 후 생성된 `study-notes/index.html`을 브라우저(Chrome)로 열어 칩 4개 클릭 | 칩별로 해당 채널 카드만 표시, 콘솔 에러 0 |
| 4 | 볼트 채널 폴더 | `ls 학습노트/Y-Combinator/_목차.md 학습노트/Sequoia/_목차.md` | 두 파일 존재 + 각 목차 표에 노트 행 ≥ 1 |
| 5 | 노트 규칙 준수 | 신규 노트 3편에 대해: frontmatter 필수키(`title·channel·video_id·url·upload_date·summary·aliases`) 존재, 이모지 0개, `==하이라이트==` 0개 | 3편 모두 통과 |
| 6 | 채널 실패 격리 | **외부 의존 없는 단위 테스트** `tests/test_channel_isolation.py`: `rss_watch.fetch_feed`를 채널별 고정 피드(각 2편)를 돌려주는 스텁으로 교체하고, `sequoia` 호출에서만 예외를 던진다. 전사·LLM·발행도 스텁 | `per_channel.sequoia.channel_error` 기록 + `n_note=0`, **yc·techbridge는 각 2편 노트 생성**, 프로세스 exit 0. 외부 네트워크·신규 영상에 의존하지 않아 언제 돌려도 같은 결과 |
| 7 | 마이그레이션 안전 | 마이그레이션 후 `python3 mac/nightly.py --dry` | TechBridge **신규 0건**(151편 재감지 없음) |
| 8 | 자막 경로 | YC 1편 처리 후 `youtube.json` | `transcript_source: "caption"`, `caption_quality: "ok"`, 단어수/분 ≥ 80 |
| 9 | 관제탑 가시성 | 관제탑 대시보드에서 `kr.apom.youtube-study` 카드 확인 + `ls -la ~/.gbrain/.heartbeat/kr.apom.youtube-study` | 카드 존재 + heartbeat mtime이 당일 |
| 10 | 라이브 검증 | 발행 1~2분 후 라이브 랜딩(`?v=N`)에서 카드 `href` slug를 전부 추출해 집합 `LIVE`를 만들고, 발행 직전 로컬 `AFTER` 집합과 비교 | `LIVE == AFTER`(양방향 일치). 개수가 아니라 집합으로 판정하며, 불일치 slug를 전부 출력 |

1·7번은 **하드 게이트** — 실패 시 다음 페이즈로 넘어가지 않고 되돌린다.

---

## 8. 다음 진입점

구현은 `cha-dev-phase`로 넘긴다 — SSOT(`docs/CHARTER.md`) 확인 → Align → Spec → 티켓(P0~P7) → Build → Gate → Commit → Handoff(+ `workflow/youtube` MAP 신설).
