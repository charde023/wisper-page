---
title: report 발행 도구 맥 이식 (publish_report.py) — 핸드오프
date: 2026-07-07
author: 스미스(맥) Claude
phase: cha-dev-phase / walking skeleton
status: 구현·검증 완료, 커밋 보류
---

# 핸드오프 — publish_report.ps1 → publish_report.py 맥 이식

## 무엇을 했나
`workflow/publish_report.ps1`(주간/중간보고 GitHub Pages 발행)의 **맥(darwin, pwsh 없음) 크로스플랫폼 이식본** `workflow/publish_report.py`를 작성·검증했다. 볼트 스킬 `cha-apom-report-publish`가 이 도구에 의존하는데 맥에서 대화형 발행이 안 되던 문제(2026-07-07 트랩스윕 발견) 해소.

- 로직 1:1 이식(입력검증 → report.md 복사 → make_report_html.py → update_reports_index.py → git add/commit/pull --rebase/push → live URL).
- 추가 옵션: `--no-git`(파일 생성까지, 검증용) · `--no-push`(로컬 커밋까지).
- `.ps1`은 시그마(윈도) 폴백으로 보존(맥-로컬-전사 구현계획서 롤백 원칙과 동일).

## 실행 (맥)
```bash
~/.venvs/whisper-mlx/bin/python workflow/publish_report.py \
  --report "/Users/charde023/workspace/obsidian/charde_n/APOM/보고서/주간보고/<slug>.md" \
  --type weekly --slug <slug> --page-repo /Users/charde023/workspace/page
```
- **반드시 whisper-mlx venv** — 발행이 `markdown` 의존(시스템 python엔 없음).
- `sys.executable`로 하위 `make_report_html.py`·`update_reports_index.py`를 같은 venv로 호출.

## 게이트 (통과)
기존 발행본 `page/reports/weekly/2026-W23/report.md`를 재생성해 기존 `index.html`과 대조 → **EOL(CRLF↔LF) 제외 바이트 100% 동일**. 엔진 교체 무결(CHARTER "엔진 교체 시 산출물 계약 유지" 불변식 충족). 인덱스 재생성도 정상.

## ⚠️ 발견 — 발행 도구 3종이 git untracked
`publish_report.ps1` · `_template/make_report_html.py` · `update_reports_index.py` **전부 `??`(시그마 로컬 미커밋)**. 작동은 함(2026-W22/23 실발행) 그러나 **git 백업·동기화 안 됨**. `publish_report.py`도 뒤 2개에 의존 → git 커밋이 이 3종과 강결합.

## 커밋 보류 (차드 결정 2026-07-07)
`publish_report.py`를 본체 `workflow/`에 둔 채(즉시 발행 가능) **git 커밋은 보류** — 시그마가 발행도구 3종 + EOL 정규화(`sigma/v2-표준구조` uncommitted 21파일)를 정리한 뒤 함께 커밋. 지금 `publish_report.py`는 untracked 로컬 파일(백업 전엔 이 맥에만 존재).

## 남은 작업 (대기)
1. **발행도구 3종 git 커밋**(시그마 조율) → 그 위에 `publish_report.py` 함께 커밋.
2. **로컬 전사 오케스트레이터 맥판**: `run.ps1`+`extract_audio.ps1`+`new_workspace.ps1`(로컬 m4a/mp4 → wav → 전사). 전사 코어는 `youtube/mac/transcribe_mlx.py` 재사용. meeting-report용. (전사 코어·youtube 파이프라인은 7012c98로 이미 맥 이식됨.)
3. **`deploy.ps1` 맥판**(로컬 mp4 가이드 Step7 배포).

## 브랜치 주의
본체 `sigma/v2-표준구조`에 EOL 정규화 uncommitted 21파일(시그마, `git diff --ignore-all-space` 빈결과 = 순수 정규화). `publish_report.py`는 신규파일이라 이 정규화와 파일단위로 무충돌.

## 볼트 스킬 갱신 (~/.claude, 볼트 git 백업 X)
- `cha-apom-report-publish`: "이식 미완" 경고 → **맥 발행 커맨드**(위)로 정정.
- `cha-apom-meeting-report`: "이식 미완" → **부분 이식**(전사 코어 됨, 대화형 오케스트레이터만 미이식 + 맥 수동 2스텝) 안내로 정정.
