# Workflow Scripts

지피터스 스터디 영상 mp4를 모바일 최적화된 GitHub Pages 보고서로 변환하는 도구.

## 사용 흐름 (7단계)

```powershell
# 원클릭 오케스트레이터 (Steps 0-2를 한 번에)
.\workflow\run.ps1 -VideoFile "C:\path\to\지피터스-YYYY-MM-DD-주제.mp4"
# 전사만 필요한 경우 (미팅/통화 등)
.\workflow\run.ps1 -VideoFile "C:\path\to\recording.mp4" -TranscribeOnly

# --- 또는 단계별 수동 실행 ---

# 0. 새 작업 폴더 준비 (pipeline.json 스테이지 매니페스트 자동 생성)
.\workflow\new_workspace.ps1 -VideoFile "C:\path\to\지피터스-YYYY-MM-DD-주제.mp4"

# 1. 오디오 추출
.\workflow\extract_audio.ps1 -Workspace ".\workspaces\지피터스-YYYY-MM-DD-주제"

# 2. Whisper 전사 (산출물 존재 여부로 성공 판정 — exit code 무시)
.\workflow\transcribe.ps1 -Workspace ".\workspaces\지피터스-YYYY-MM-DD-주제"
# 또는 중앙 정본 직접 호출:
python .\workflow\_template\transcribe.py --workspace ".\workspaces\지피터스-YYYY-MM-DD-주제"

# 3~4. Claude 대화로:
#   - transcript.txt → transcript_clean.md (어휘·문장 교정)
#   - transcript_clean.md → guide.md (frontmatter + 보고서 구조)
#   - 푸시 전: python .\workflow\lint_guide.py .\workspaces\...\guide.md

# 5. HTML 생성 (중앙 정본 호출)
python .\workflow\_template\make_html.py --workspace ".\workspaces\지피터스-YYYY-MM-DD-주제"

# 6. publish 폴더 구성
python .\workflow\stage_publish.py ".\workspaces\지피터스-YYYY-MM-DD-주제" --slug YYYY-MM-DD-topic

# 7. page 리포로 복사 + 인덱스 갱신 + 푸시
# 원클릭:
.\workflow\deploy.ps1 -Workspace ".\workspaces\지피터스-YYYY-MM-DD-주제" -Slug YYYY-MM-DD-topic
# 또는 수동:
Copy-Item -Recurse -Force ".\workspaces\지피터스-YYYY-MM-DD-주제\publish\YYYY-MM-DD-topic" "<page-repo>\"
python .\workflow\update_pages_index.py "<page-repo>"
git -C "<page-repo>" add -A; git -C "<page-repo>" commit -m "add YYYY-MM-DD <topic>"; git -C "<page-repo>" push
```

> 머신별 경로(`pageRepoPath` 등)는 `workflow/config.json`(gitignored)에 보관.
> 없으면 `workflow/config.example.json`을 복사해 값을 채울 것.

## 폴더 구조

```
wisper-page/
├── workflow/                  # 이 도구 모음
│   ├── _template/             # 중앙 정본 (--workspace 플래그로 직접 호출, 복사 X)
│   │   ├── transcribe.py
│   │   ├── make_html.py
│   │   └── guide-template.md  # guide.md 작성 골격
│   ├── lib/
│   │   ├── config.py          # load_config() — config.json 우선, 없으면 config.example.json
│   │   ├── frontmatter.py     # split_frontmatter()
│   │   └── manifest.py        # pipeline.json 스테이지 매니페스트
│   ├── config.example.json    # 머신별 경로 예시 (커밋됨)
│   ├── config.json            # 실제 값 (gitignored)
│   ├── run.ps1                # 오케스트레이터 (Steps 0-2)
│   ├── deploy.ps1             # 배포 원클릭 (Steps 5-7)
│   ├── transcribe.ps1         # Whisper 래퍼 (exit code 무시, 산출물 확인)
│   ├── extract_audio.ps1
│   ├── new_workspace.ps1
│   ├── lint_guide.py          # guide.md 사전 검증
│   ├── stage_publish.py
│   └── update_pages_index.py
└── workspaces/                # 영상별 작업 폴더 (자동 생성, gitignored)
    └── 지피터스-YYYY-MM-DD-주제/
        ├── .video-path        # 원본 영상 절대 경로
        ├── pipeline.json      # 스테이지 타임스탬프 매니페스트
        ├── audio.wav
        ├── transcript.{txt,srt}, segments.json
        ├── transcript_clean.md
        ├── guide.md
        ├── index.html
        └── publish/<slug>/{index.html, guide.md, README.md}
```

## 의존성

- Python 3.11+ — `pip install faster-whisper markdown`
- ffmpeg (시스템 PATH)
- PowerShell 7+ (Windows)
- Git (page 리포 푸시용)

## guide.md frontmatter (필수)

```yaml
---
title: <h1과 동일하게>
eyebrow: 지피터스 22기 · 끌림 영상 스터디
subtitle: YYYY-MM-DD 라이브 강의 정리본
source: <원본 영상 파일명>.mp4
description: <og:description, meta description>
date: YYYY-MM-DD
---
```

## guide.md 표준 구조

위에서 아래로 갈수록 상세도 깊어짐. 모바일에서 위쪽만 읽어도 핵심 전달.

1. `# 제목` (h1) + 메타 인용구
2. `## 결론 (TL;DR)` — 한 줄 요약 + **표/구조화** + 핵심 포인트
3. `## 강의는 어떤 내용이었나` — 1~2문단 개요
4. `## 0. 한눈에 보는 [주제]` — 번호 매긴 단계
5. `## 1. ~ ## N.` — 상세 본문
6. (선택) 부록·검증 체크리스트·자주 막히는 곳

## 알려진 함정

- **cuBLAS DLL 못 찾음**: `transcribe.py` 안에 `os.environ["PATH"]` prepend 패치 이미 적용됨
- **exit code 127**: `transcribe.ps1`이 산출물 존재 여부로 성공 판정 — exit code 무시
- **frontmatter 유지**: `stage_publish.py`가 frontmatter를 **제거하지 않음** — `update_pages_index.py`가 카드 메타데이터를 읽어야 하기 때문
- **page-repo 위치**: `workflow/config.json`의 `pageRepoPath`에 저장. 없으면 `config.example.json` 복사 후 수정
- **이모지**: guide.md에 이모지 쓰지 말 것. `lint_guide.py`가 경고함
