# workflow/youtube — TechBridge-KR 지식 파이프라인

YouTube 채널(영어 강연 + 한글자막 큐레이션) → Whisper 전사 → Claude 한국어 학습노트 → Obsidian.
`wisper-page`의 전사 인프라(`_template/transcribe.py`·`transcribe.ps1`·`lib/manifest.py`)를 재사용한다.

> 설계서: `docs/specs/2026-06-06-techbridge-knowledge-pipeline-design.md`
> 계획서: `docs/plans/2026-06-06-techbridge-knowledge-pipeline.md`

## 전제

- `yt-dlp`(`--js-runtimes node` 사용), `ffmpeg`, `python`, `faster-whisper`, NVIDIA GPU.
- `config.json`(gitignored) — `config.example.json` 복사 후 `vaultNoteDir` 등 머신별 값 확인.

## 스크립트

| 파일 | 역할 |
|---|---|
| `yt_lib.py` | 공통 헬퍼(설정 병합·상태파일·yt-dlp 실행) |
| `yt_channel_scan.py` | 채널 최근 N개월 영상 메타 → `state/channel_index.json` |
| `curate.py` | 토픽·조회수 점수 → `state/curated_queue.json` (+ 표 출력) |
| `yt_fetch.ps1` | URL → 워크스페이스(음성 16k wav + `youtube.json` + manifest) |
| `extract_provenance.py` | `audio.info.json` → `youtube.json`(메타 + 원작자 추정) |
| `run_youtube.ps1` | 오케스트레이터: 큐 → (fetch→transcribe) 직렬 배치 |
| `rebuild_index.py` | 볼트 `_목차.md` · `_원작채널.md` 재생성 |
| `rss_watch.py` | RSS diff → 신규 영상 (scheduled-task가 호출, 푸시 알림만) |
| `note_template.md` | 학습노트 골격(에이전트가 채움) |

## 사용 흐름

```powershell
# 1. 채널 스캔 (최근 3개월)
python workflow\youtube\yt_channel_scan.py --months 3

# 2. 큐레이션 (상위 50) → 차드 확인
python workflow\youtube\curate.py --top 50

# 3. 배치 전사 (확정 큐)
.\workflow\youtube\run_youtube.ps1 -Queue workflow\youtube\state\curated_queue.json

# 4. (Claude) 영상별 transcript.txt + youtube.json → 학습노트 작성 (벌트에 Write)

# 5. 인덱스 갱신
python workflow\youtube\rebuild_index.py

# 신규 영상 감시 (수동 1회 확인)
python workflow\youtube\rss_watch.py
```

## 노트 정책 (요약)

- 영상 1개 = 노트 1개. 상단에 **학습 헤더**(핵심 학습 포인트 / 내가 모를 것 / 화자의 디테일), 하단에 접기식 교정 전사.
- 한국어로 교정·번역, 핵심 영어 용어 괄호 병기, 음성인식 의심 단어 `[?원문]`.
- 이모지 금지. 강조 스팬 2종(주황 `#ef6c00` / 일반 볼드 1.1em)만. 볼트 학습노트 표준 준수.
- 재사용 용어는 `학습노트\` 루트에 용어노트 스필오버 + `[[wikilink]]`.

## 주의

- `--flat-playlist`는 `upload_date`=NA → 스캔에 쓰지 말 것(비-flat `/videos` + `--break-on-reject`).
- yt-dlp throttle 시 `--remote-components ejs:github` 폴백.
- 전사 종료코드는 무시(산출물 검증이 진실) — `transcribe.ps1`가 처리.
- `state/`·`config.json`은 gitignored(머신별).
