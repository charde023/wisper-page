# 핸드오프 — YouTube 숏츠 제외 (2026-08-01)

> 상태: **완료·머지·배포됨**. 이 문서는 다음 세션이 맥락 없이 이어받기 위한 것.

## 목표

YouTube Shorts를 파이프라인에서 완전히 배제하고, 이미 만들어진 숏츠 학습노트·발행 페이지를 제거한다. 롱폼만 다룬다.

## 결정과 근거

### 판정 기준 — `duration ≤ 180s AND 0 < aspect < 1.0`

단일 출처는 `workflow/youtube/yt_lib.py`의 `is_short()`. 두 조건의 **AND**인 이유는 실측이다.

| video | duration | aspect | 판정 | 시사점 |
|---|---|---|---|---|
| `TMd5rvh9fCU` | 35s | 0.56 | 숏츠 | — |
| `Gn30anFa_2U` | 55s | 0.56 | 숏츠 | 노트 제목에 `#Shorts` 마커 **없음** → 제목 매칭은 못 믿는다 |
| `s-L0F92HCkg` | 156s | 1.78 | **정상 영상** | 길이 단독 판정은 이걸 오탐한다 |

180초는 YouTube Shorts 길이 상한(2024-10 이후 3분).

**메타 미상이면 `False`(정상 영상 취급).** 조회 실패 한 번으로 진짜 강연을 조용히 버리는 쪽이, 숏츠 한 편 전사보다 나쁘다고 판단했다.

### 삭제 범위 — 볼트 노트 + 발행 페이지 둘 다 (차드 결정)

발행은 볼트 미러라서, 볼트 노트를 남기면 다음 밤 `--all` 발행 때 페이지가 되살아난다. 그래서 둘 다 지웠다.

## 변경 파일

| 파일 | 내용 |
|---|---|
| `workflow/youtube/yt_lib.py` | `is_short()` · `SHORTS_MAX_SEC = 180.0` |
| `workflow/youtube/mac/nightly.py` | `fetch_duration` → `fetch_meta`(길이+화면비) · 숏츠 스킵 · `n_short` 집계 |
| `workflow/youtube/mac/run_youtube.py` | `resolve_id` → `resolve_meta` + 수동 실행 가드 |
| `tests/test_shorts_filter.py` | 신규 18케이스 |
| `tests/test_channel_isolation.py` | `fetch_duration` → `fetch_meta` 스텁 갱신 |
| `workflow/youtube/youtube_MAP.md` | 함정 6-a·6-b |
| `docs/CHARTER.md` | 불변식 1항 |
| `.gitattributes` | 신규 — 줄바꿈 LF 고정 |

## 검증 명령과 결과

```bash
~/.venvs/whisper-mlx/bin/python -m pytest tests/ -q
# → 68 passed, 1 failed
```

실패 1건은 `tests/test_update_pages_index.py`로 **이 영역과 무관한 기존 실패**다(다른 작업의 미완성 변경, MAP에도 기록됨). 손대지 않았다.

```bash
# 라이브
curl -s https://charde023.github.io/page/study-notes/ | grep -o '총 [0-9]*개'   # → 총 137개
curl -so /dev/null -w '%{http_code}' https://charde023.github.io/page/study-notes/20260709-TMd5rvh9fCU/  # → 404 (숏츠)
curl -so /dev/null -w '%{http_code}' https://charde023.github.io/page/study-notes/20260731-KIiAs4V-YTs/  # → 200 (정상)
```

## 커밋

| 리포 | 커밋 |
|---|---|
| 볼트 | `c588bc8` 노트 18편 제거 · `a943844` 목차 재생성 (TechBridge 132편) |
| wisper-page | `34af2b5` 줄바꿈 정규화 · `951ce85` 숏츠 기능 · `4bbc9aa` 게이트 기록 |
| 머지 | PR #3 → main `e8b9195` (CI 없음 → 로컬 게이트로 대체) |

## 이 세션에서 발견한 함정

### 볼트 git에 NFD/NFC 이중 인덱스 엔트리

노트 18편을 `git rm` 했는데 git은 **26경로**를 지웠다. 8편이 정규화가 다른 두 경로로 인덱스에 동시 등록돼 있었다(파일시스템에는 하나로 보인다). 삭제 후 반드시 삭제된 경로 전수를 눈으로 확인할 것 — 이번엔 26경로 전부 `#Shorts`라 정상 노트 유실 0이었다.

### 작업트리 CRLF 잔재 ≠ 리포 오염

`yt_lib.py`만 커밋된 blob이 CRLF였고, 나머지 19파일은 **리포는 LF인데 로컬 작업트리만 CRLF**였다(mtime 2026-06-07/06-22 = 시그마 시절 체크아웃 그대로). 후자는 커밋할 게 아니라 HEAD 복원 대상이다. 방향을 재지 않고 `tr -d '\r'` 후 커밋했으면 리포에 없던 변경을 새로 만들어 넣을 뻔했다. `.gitattributes`로 재발 차단함.

### `git status`의 ` M`은 stat 캐시일 수 있다

파일을 대량 재작성하면 mtime이 바뀌어 `git status --porcelain`이 내용이 같아도 ` M`을 낸다. `git update-index --refresh` 후 `git diff --numstat`로 재확인할 것. 이번에 두 번 헷갈렸다.

## 남은 것 / 열린 결정

1. **야간 자동화 유지 여부 — 차드 답변 대기.** 차드가 "자동화도 안 해도 돼"라고 했는데 ① 숏츠용 자동화를 만들지 말라 ② 야간 파이프라인 자체를 끄라 로 읽힌다. ①로 보고 **끄지 않았다**. 23시 `youtube-study` cron은 롱폼만 대상으로 계속 돈다. ②였으면 launchd 잡을 내려야 한다.
2. **TechBridge `minDurationMin: 0`** — 숏츠는 아니지만 4~7분짜리 짧은 영상이 들어온다(YC·Sequoia는 8분 하한). 롱폼 하한을 올릴지는 미정.
3. `4bbc9aa`(게이트 기록)가 브랜치에만 있고 main 미머지 — 직전 페이즈의 `4be9122`도 같은 상태라 관행상 문제는 아니다.
4. 워킹트리에 **다른 작업의 untracked 5개** 잔존: `INDEX.md` · `workflow/pages_catalog.json` · `tests/test_update_pages_index.py` · `docs/plans/2026-06-04-youtube-download-and-pages-batch.md` · `workflow/youtube/config.json.bak-20260801-090843`. 내 것이 아니라 손대지 않았다. 위 테스트 실패 1건이 여기서 나온다.

## 다음 세션 진입점

```
wisper-page 유튜브 학습노트 파이프라인. 영역 MAP = workflow/youtube/youtube_MAP.md 를 먼저 읽어라.
숏츠 제외는 2026-08-01 완료·머지됨(main e8b9195) — docs/handoff/2026-08-01_youtube-shorts-exclusion.md 참고.
열린 결정 2건: ① 야간 자동화 유지 여부(차드 답변 대기) ② TechBridge 롱폼 하한(minDurationMin 현재 0).
실행 인터프리터는 ~/.venvs/whisper-mlx/bin/python 다.
```
