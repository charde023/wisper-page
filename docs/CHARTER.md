---
title: wisper-page — 개발운영헌장 (CHARTER)
type: charter
created: 2026-07-03
---
# wisper-page 헌장

> `cha-dev-phase` Phase 0의 기준문서. 페이즈 착수 전 항상 여기부터 재확인한다(기억으로 짜지 않는다).
> 전문 워크플로우 절차는 `AGENTS.md`(SSOT)가 담당 — 이 문서는 불변식·로드맵·게이트·열린결정만.

## 불변식 (깨면 안 되는 것)

- **두 리포 역할 분리**: `charde023/wisper-page`(이 프로젝트) = 도구·문서·AGENTS.md 보관소. **작업 결과물(워크스페이스·가이드·전사)은 이 리포에 푸시 금지.** `charde023/page` = 강의/학습노트 정리본 전용 게시처.
- **push는 항상 사용자 승인 후**: wisper-page 리포(도구·AGENTS.md·docs) 변경 푸시, `charde023/page` 배포(Step 7) 모두 매번 차드에게 어디에 올릴지 확인 후 진행. 예외 없음.
- **`workspaces/`·`영상자료/`·`결과물/`는 `.gitignore` 대상** — 대용량·개인 산출물이 실수로도 원격에 올라가지 않게 유지한다.
- **`charde023/page`는 정리본 전용** — 블로그·메모·실험 페이지 등 다른 성격 콘텐츠를 얹지 않는다.
- **guide.md는 lint 통과 없이 배포하지 않는다** — `workflow/lint_guide.py` 게이트 필수.
- **전사 산출물 계약 고정**: `transcript.txt`·`segments.json`·`transcript.srt`·완료 센티넬(`transcribe.done`/`pipeline.json` 스탬프)의 형식·경로는 엔진(faster-whisper/mlx-whisper 등)이 바뀌어도 동일하게 유지한다 — 다운스트림(노트화·인덱스 재구성)이 무수정으로 재사용 가능해야 한다.
- **YouTube Shorts는 감지·전사·발행 대상이 아니다** — 판정은 `yt_lib.is_short()` 단일 출처(`duration ≤ 180s AND 0 < aspect < 1.0`). 길이 단독·제목 `#Shorts` 단독은 오탐하므로 쓰지 않는다. 야간(`nightly.py`)과 수동(`run_youtube.py`) 두 경로 모두에서 막는다.
- **YouTube 지식화 서브워크플로우는 전사 인프라만 공유**하고 발행 목적(Obsidian 학습노트 vs GitHub Pages 가이드)은 분리 유지한다.

## 로드맵 (페이즈 상태)

| 페이즈 | 내용 | 상태 |
|---|---|---|
| P0 — 로컬 mp4 → Pages 7단계 워크플로우 | ffprobe→workspace→전사→요약→HTML→배포 | ✅ 완료(운영 중) |
| P1 — YouTube 채널 지식화(TechBridge-KR → Obsidian) | 채널 스캔·큐레이션·전사·노트화·인덱스 | ✅ 완료(운영 중, 수동 노트화) |
| P2 — 맥(M4 Max) 로컬 전사 이식 | `faster-whisper(CUDA)` → `mlx-whisper`(Metal GPU), `.ps1` 3종 → 파이썬 이식 | ✅ 완료(운영 중, 2026-08-01 실측 확인) — 설계: `design/2026-07-02_맥-로컬-전사-파이프라인-기획서.md` |
| P3 — 학습노트 자동화(무인 파이프라인) | 감시→전사→코덱스 프록시 교정/노트화→발행→알림, 차미 cron 야간 23시 | ✅ 완료(운영 중, 노트 149편) — 설계: `design/2026-07-02_학습노트-자동화-파이프라인-기획서.md` |
| P4 — 채널 다채널화(YC·Sequoia 합류) | `channels[]` 설정·자막 우선 전사·채널별 상태/노트폴더·발행 랜딩 필터 | 🔷 구현 중(2026-08-01, P1~P7 중 P1~P6 완료) — 설계: `design/2026-08-01_YC-Sequoia-채널-학습노트-자동화-기획서.md` |

- ✅ = 운영 중(회귀 시 즉시 보수). 🔷 = 구현 진행 중. 🔶 = 설계 완료·구현 미착수(Align/Spec까지 끝, Plan/Build 대기).
- 페이즈 착수 순서는 차드 지정에 따른다(고정 순번 아님) — 이 표는 "무엇이 결정됐고 무엇이 대기 중인가"의 스냅샷.

## 게이트 정의 (통과 기준)

- **7단계 워크플로우(P0)**: `python workflow/lint_guide.py <guide.md>` 통과 → 배포 → 1~2분 대기 후 WebFetch로 `https://charde023.github.io/page/<slug>/` 라이브 검증(캐시 우회 `?v=N`) → 라이브 URL + commit hash 보고.
- **전사 전용 모드**: `결과물/<제목>.md` 존재 + 화자구분/요지표 포함 여부로 검증.
- **테스트**: `tests/`(예: `test_update_pages_index.py`) 통과. 신규 스크립트 추가 시 대응 테스트 권장.
- **엔진 교체(P2 등)**: 기존 산출물 계약(위 불변식) 그대로 유지되는지 대조 검증 — 기존 시그마(Windows/CUDA) 산출물과 신규 엔진 산출물을 같은 샘플로 비교.

## 열린 결정 (미결 — 차드 판단 대기)

- P2 기획서 D1~D6 (기본 모델·파이썬 환경·시그마 GPU 은퇴 여부·자막 우선 탐침·노트 자동초안·VAD 전처리) — `design/2026-07-02_맥-로컬-전사-파이프라인-기획서.md` §6.
- P3 기획서 E1~E3 (큐레이션 바닥임계값·발행 공개성·알림 채널) — `design/2026-07-02_학습노트-자동화-파이프라인-기획서.md` §6.
- P2·P3 착수 순서/시점 자체도 미결(차드 지정 대기).
