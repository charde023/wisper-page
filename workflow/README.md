# Workflow Scripts

지피터스 스터디 영상 mp4를 모바일 최적화된 GitHub Pages 보고서로 변환하는 도구.

## 사용 흐름 (7단계)

```powershell
# 0. 새 작업 폴더 준비 (영상은 어디 있든 OK, 절대 경로 권장)
.\workflow\new_workspace.ps1 -VideoFile "C:\path\to\지피터스-YYYY-MM-DD-주제.mp4"

# 1. 오디오 추출 (workspace 경로만 알려주면 됨, 영상 경로는 .video-path에 저장됨)
.\workflow\extract_audio.ps1 -Workspace ".\workspaces\지피터스-YYYY-MM-DD-주제"

# 2. Whisper 전사 (GPU 우선, ~5분/시간; CPU fallback, ~30분/시간)
python ".\workspaces\지피터스-YYYY-MM-DD-주제\transcribe.py"

# 3~4. Claude 대화로:
#   - transcript.txt → transcript_clean.md (어휘·문장 교정)
#   - transcript_clean.md → guide.md (frontmatter + 보고서 구조)

# 5. HTML 생성
python ".\workspaces\지피터스-YYYY-MM-DD-주제\make_html.py"

# 6. publish 폴더 구성
python .\workflow\stage_publish.py ".\workspaces\지피터스-YYYY-MM-DD-주제" --slug YYYY-MM-DD-topic

# 7. page 리포로 복사 + 인덱스 갱신 + 푸시
cp -r ".\workspaces\지피터스-YYYY-MM-DD-주제\publish\YYYY-MM-DD-topic" "<page-repo>\"
python .\workflow\update_pages_index.py "<page-repo>"
cd "<page-repo>"; git add -A; git commit -m "add YYYY-MM-DD <topic>"; git push
```

## 폴더 구조

```
wisper-page/
├── workflow/                  # 이 도구 모음
│   ├── _template/             # new_workspace.ps1가 새 작업 폴더에 복사
│   │   ├── transcribe.py
│   │   └── make_html.py
│   ├── extract_audio.ps1
│   ├── new_workspace.ps1
│   ├── stage_publish.py
│   └── update_pages_index.py
└── workspaces/                # 영상별 작업 폴더 (자동 생성)
    └── 지피터스-YYYY-MM-DD-주제/
        ├── .video-path        # 원본 영상 절대 경로 (new_workspace가 기록)
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
- **frontmatter 유지**: `stage_publish.py`가 frontmatter를 **제거하지 않음** — `update_pages_index.py`가 카드 메타데이터를 읽어야 하기 때문
- **page-repo 위치**: 어디에 clone하든 `update_pages_index.py`에 절대 경로로 넘김
