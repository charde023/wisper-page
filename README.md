# wisper-page

지피터스 스터디 라이브 강의 mp4를 **모바일 최적화된 GitHub Pages 보고서**로 변환하는 워크플로우.

라이브 결과물 → <https://charde023.github.io/page/>

## 빠른 시작

새 영상이 들어오면 Claude Code 세션에서 다음 한 줄:

> *"지피터스-2026-MM-DD-주제.mp4 처리해줘"*
>
> *(영상 절대 경로: `C:\...\지피터스-2026-MM-DD-주제.mp4`)*

Claude가 `CLAUDE.md`를 읽고 7단계 워크플로우를 자동 진행한다.

## 수동으로 돌리는 방법

`workflow/README.md` 참조.

## 디렉토리

```
wisper-page/
├── CLAUDE.md              # Claude Code가 자동으로 읽는 프로젝트 가이드
├── README.md              # (이 파일)
├── workflow/              # 7단계 변환 도구 (PowerShell + Python)
│   ├── README.md
│   ├── _template/
│   ├── new_workspace.ps1
│   ├── extract_audio.ps1
│   ├── stage_publish.py
│   └── update_pages_index.py
├── workspaces/            # 영상별 작업 폴더 (자동 생성, .gitignore됨)
└── docs/
    ├── specs/             # 의사결정 기록 (설계서)
    └── plans/             # 실행 계획서
```

## 의존성

- Python 3.11+ (`faster-whisper`, `markdown`)
- ffmpeg (PATH)
- PowerShell 7+
- Git
- (전사용) NVIDIA GPU 권장 — 없으면 CPU fallback 자동

## 출력 페이지 리포

- `https://github.com/charde023/page` → `https://charde023.github.io/page/`
- 로컬 clone 위치 (현재): `C:\Users\inwon\Documents\page-repo`
- 가이드는 날짜별 하위 폴더 (`/YYYY-MM-DD-topic/`) + 루트에 카드 인덱스
