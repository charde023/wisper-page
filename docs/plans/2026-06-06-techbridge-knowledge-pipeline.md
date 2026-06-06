# TechBridge-KR 지식 파이프라인 실행 계획서

> **작성일**: 2026-06-06
> **설계서**: `docs/specs/2026-06-06-techbridge-knowledge-pipeline-design.md`
> **원칙**: 각 Phase는 검증 가능한 단위. Phase 1 끝(큐레이션 확정)에서 **차드 확인 게이트**.

---

## 진행 요약

| Phase | 목표 | 차드 개입 |
|---|---|---|
| 0 | 하네스 구축 (스크립트 + 설정 + 스모크테스트) | 없음 |
| 1 | 채널 스캔 → 큐레이션 후보 ~40-60개 | **게이트: 큐 확정** |
| 2 | 큐 배치 전사 (yt-dlp → Whisper) | 없음 (백그라운드) |
| 3 | 노트 일괄 작성 (Sonnet 실행자 병렬) | 샘플 1개 리뷰 |
| 4 | Obsidian 인덱스 갱신 + 검증 | 없음 |
| 5 | 신규 영상 알림 scheduled-task | 푸시 동작 확인 |
| 6 | CLAUDE 지침 + (선택) 스킬 | 없음 |

---

## Phase 0 — 하네스 구축

목표: `workflow/youtube/` 스크립트군 작성 + 첫 영상 스모크테스트로 전 경로 검증.

- [x] 인프라/볼트/yt-dlp/채널/알림 리서치 (완료)
- [x] 첫 영상(ompD1oHqn7Q) 음성 다운로드 → `audio.wav` 검증 (완료, `--js-runtimes node`)
- [ ] `transcribe.ps1 -Language auto -Model large-v3 -Device cuda` 스모크테스트 → `transcript.txt` 검증
- [ ] `workflow/youtube/config.example.json` 작성 (볼트경로·channel_id·폴더·모델·토픽키워드)
- [ ] `yt_channel_scan.py` 작성
- [ ] `curate.py` 작성
- [ ] `yt_fetch.ps1` 작성
- [ ] `extract_provenance.py` 작성
- [ ] `rebuild_index.py` 작성
- [ ] `rss_watch.py` 작성
- [ ] `run_youtube.ps1` 작성
- [ ] `note_template.md` 작성
- [ ] `.gitignore`에 `workflow/youtube/state/` 추가 (channel_index·seen_videos는 머신별 상태)

**검증**: 첫 영상의 `transcript.txt`가 영어로 정상 생성되고 segments가 충분(>50). `yt_fetch.ps1`을 둘째 영상에 돌려 `audio.wav` + `youtube.json`이 나오면 글루 정상.

---

## Phase 1 — 채널 스캔 + 큐레이션 (게이트)

목표: 최근 3개월 영상 목록을 메타와 함께 확보하고, 토픽·조회수로 ~40-60개 후보를 추려 차드 확인.

```bash
# 1. 채널 스캔 (최근 3개월)
python workflow/youtube/yt_channel_scan.py "https://www.youtube.com/@TechBridge-KR" --months 3
#   → workflow/youtube/state/channel_index.json

# 2. 큐레이션
python workflow/youtube/curate.py --top 50
#   → workflow/youtube/state/curated_queue.json  (선정 + 점수 + 이유)
```

- [ ] `channel_index.json`에 최근 3개월 전 영상 메타(id·title·date·views·duration·description)
- [ ] `curated_queue.json`에 토픽·조회수 점수 상위 ~40-60개 + 선정이유
- [ ] **차드에게 큐 목록 표로 제시 → 가감 확정** ← 게이트

**검증**: 큐 항목 수가 합리적(40-60), 토픽 분포가 차드 관심사(Claude Code·에이전트·하네스) 중심. 차드 OK 전까지 Phase 2 진입 금지.

---

## Phase 2 — 배치 전사

목표: 확정 큐를 직렬 배치로 음성 다운로드 + Whisper 전사.

```powershell
.\workflow\youtube\run_youtube.ps1 -Queue workflow\youtube\state\curated_queue.json
#   각 영상: yt_fetch.ps1 → transcribe.ps1 (large-v3/auto), 직렬(GPU 경합 방지)
```

- [ ] 각 영상 `workspaces/yt-<id>/`에 `audio.wav`·`transcript.txt`·`segments.json`·`youtube.json`
- [ ] `extract_provenance.py`로 각 `youtube.json`에 provenance 병합
- [ ] 실패 영상은 SUMMARY 표에 표기, 단건 재시도

**검증**: 큐의 N개 중 전사 성공 수 ≈ N. 평균 segments/영상이 충분. 백그라운드 실행, 완료 알림 대기(폴링 금지).

---

## Phase 3 — 노트 일괄 작성

목표: 전사된 영상별로 §4 포맷의 학습노트를 Obsidian에 작성. Sonnet 실행자 병렬(Workflow).

- [ ] **샘플 1개** 먼저 작성 → 차드 리뷰 (포맷·디테일 캐치 수준 확인)
- [ ] 승인되면 나머지 일괄 (Workflow: 영상당 실행자 1개, transcript+youtube.json 읽고 노트 Write)
- [ ] 재사용 용어는 `학습노트\` 루트에 용어노트 스필오버 + `[[wikilink]]`

**검증**: 각 노트가 frontmatter + 학습헤더(핵심 학습 포인트/내가 모를 것/화자 디테일) + 교정 전사 포함. 이모지 0, 강조 스팬 규칙 준수. 샘플 리뷰에서 "화자 디테일" 품질 합격.

---

## Phase 4 — Obsidian 인덱스 + 검증

```bash
python workflow/youtube/rebuild_index.py
#   → 학습노트\TechBridge-KR\_목차.md + _원작채널.md
```

- [ ] `_목차.md` 카드 인덱스(노트별 한 줄 요약)
- [ ] `_원작채널.md` 원작자별 → 참조 영상 누적 인덱스
- [ ] Obsidian에서 그래프·링크 동작 확인. `study_notes_link.py` 일일 링크 정상

**검증**: 모든 노트가 인덱스에 등장. 원작채널 인덱스에 Nate Herkelman·Charlie Holtz 등 집계.

---

## Phase 5 — 신규 영상 알림

목표: 매일 RSS 체크 → 새 영상 푸시 알림(처리는 승인 후).

- [ ] `rss_watch.py` 단독 동작 확인 (seen 상태 diff)
- [ ] `scheduled-tasks` MCP로 일일 태스크 등록 (예: 09:37). 프롬프트는 자기완결: RSS diff → 신규 있으면 PushNotification(proactive)로 제목·URL 보고, 없으면 조용히 종료
- [ ] `state/seen_videos.json` 초기화(현재까지 본 영상 = 처리완료 + 미선정 모두 seen 처리해 알림 폭주 방지)

**검증**: 태스크 수동 트리거 시 신규 0건이면 조용, 신규 있으면 푸시 1건. 차드 "응" 하면 `run_youtube.ps1` + 노트작성.

---

## Phase 6 — CLAUDE 지침 + (선택) 스킬

- [ ] `CLAUDE.md`에 "YouTube 채널 지식화" 섹션 추가 (트리거·7단계·푸시정책·디렉토리) 또는 `docs/`에 가이드 + CLAUDE.md에서 링크
- [ ] (선택) `techbridge-note` 스킬 — 노트 포맷·학습헤더 정책을 스킬화해 세션/에이전트 일관성
- [ ] 푸시 정책 명시: wisper-page 리포 push는 승인 후. 볼트는 로컬 작업

**검증**: 새 세션에서 "TechBridge 새 영상 처리해줘" → 지침대로 7단계 무중단.

---

## 완료 정의 (Done)

1. `workflow/youtube/` 스크립트군이 다음 영상에도 그대로 재사용 가능.
2. 큐레이션 ~40-60개가 `학습노트\TechBridge-KR\`에 학습헤더 포함 노트로 적재.
3. `_목차.md`·`_원작채널.md` 인덱스 정상.
4. 일일 scheduled-task가 신규 영상을 푸시로 알림.
5. CLAUDE 지침으로 신규 영상이 동일 패턴으로 처리됨.

---

## 위험 (Phase별 핵심)

| Phase | 위험 | 완화 |
|---|---|---|
| 0 | 스크립트-기존 인터페이스 불일치 | manifest/transcribe 인터페이스 그대로 호출, 스모크테스트로 검증 |
| 1 | `--flat-playlist` upload_date NA | 비-flat `/videos` + `--break-on-reject` 사용 |
| 2 | yt-dlp throttle | `--js-runtimes node`. 실패 시 `--remote-components ejs:github` 폴백 |
| 3 | 노트 포맷 편차(실행자 병렬) | 템플릿·스킬 고정, 샘플 리뷰 게이트 |
| 5 | 알림 폭주(초기 seen 미설정) | 등록 시 현재 catalog 전부 seen 처리 |
