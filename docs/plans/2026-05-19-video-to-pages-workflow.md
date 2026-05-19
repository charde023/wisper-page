# 영상 → GitHub Pages 보고서 워크플로우 실행 계획서

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 지피터스 라이브 강의 mp4를 모바일 최적화된 GitHub Pages 보고서로 변환하는 재사용 가능한 워크플로우를 구축하고 `지피터스-2026-05-18-설치법.mp4`로 검증한다.

**Architecture:** 7단계 파이프라인 (mp4 → audio → transcript → clean transcript → guide.md → index.html → publish 폴더 → page 리포). 도움 스크립트는 `workflow/`에 모아두고, 작업물은 영상별 폴더에 격리. GitHub Pages 리포는 날짜별 하위 폴더 + 루트 인덱스 구조.

**Tech Stack:** Python 3.11+ (faster-whisper, python-markdown), PowerShell 7 (Windows), ffmpeg, Git (page 리포 푸시용)

**Spec:** `docs/superpowers/specs/2026-05-19-video-to-pages-workflow-design.md`

---

## 파일 구조 (작업 전체에서 변경되는 모든 파일)

### 생성 (Phase A — 도구)
- `workflow/_template/transcribe.py` — 기존 antigravity-guide/transcribe.py 복사
- `workflow/_template/make_html.py` — frontmatter 지원 추가 버전
- `workflow/extract_audio.ps1` — mp4 → audio.wav
- `workflow/new_workspace.ps1` — 영상명 → 작업 폴더 생성 + 템플릿 복사
- `workflow/stage_publish.py` — 작업 폴더 → publish/<slug>/
- `workflow/update_pages_index.py` — page 리포 루트 index.html 생성
- `workflow/README.md` — 사용법 안내

### 수정 (Phase A — 17일자 마이그레이션 준비)
- `antigravity-guide/guide.md` — frontmatter 추가
- `antigravity-guide/index.html` — 새 make_html.py로 재생성

### 생성 (Phase B — 5/18 처리)
- `지피터스-2026-05-18-설치법/audio.wav`
- `지피터스-2026-05-18-설치법/transcript.{txt,srt}`, `segments.json`
- `지피터스-2026-05-18-설치법/transcript_clean.md`
- `지피터스-2026-05-18-설치법/guide.md`
- `지피터스-2026-05-18-설치법/index.html`
- `지피터스-2026-05-18-설치법/publish/2026-05-18-installation/{index.html,guide.md,README.md}`

### 수정 (Phase C — page 리포)
- `<page-clone>/index.html` — 루트 인덱스 (신규 또는 갱신)
- `<page-clone>/2026-05-17-antigravity/` — 17일자 마이그레이션 (폴더 신설)
- `<page-clone>/2026-05-18-installation/` — 18일자 (폴더 신설)

---

## Phase A — 워크플로우 도구 준비

### Task 1: workflow 디렉토리 구조 만들기

**Files:**
- Create: `workflow/_template/` (디렉토리)
- Create: `workflow/README.md`

- [ ] **Step 1: 디렉토리 생성**

```powershell
New-Item -ItemType Directory -Force -Path "workflow\_template" | Out-Null
```

- [ ] **Step 2: README.md 작성**

Create `workflow/README.md`:

```markdown
# Video → GitHub Pages 워크플로우

지피터스 라이브 강의 mp4를 보고서 형태 웹 페이지로 변환하는 도구 모음.

## 사용 흐름

```powershell
# 0. 새 작업 폴더 준비
.\workflow\new_workspace.ps1 "지피터스-YYYY-MM-DD-주제.mp4"

# 1. 오디오 추출
.\workflow\extract_audio.ps1 "지피터스-YYYY-MM-DD-주제.mp4"

# 2. 전사
python "지피터스-YYYY-MM-DD-주제\transcribe.py"

# 3~4. Claude 대화로: transcript.txt → transcript_clean.md → guide.md

# 5. HTML 생성
python "지피터스-YYYY-MM-DD-주제\make_html.py"

# 6. publish 폴더 구성
python .\workflow\stage_publish.py "지피터스-YYYY-MM-DD-주제" --slug YYYY-MM-DD-topic

# 7. page 리포 푸시
#    - publish/<slug>/를 page 리포로 복사
#    - python .\workflow\update_pages_index.py <page-clone-path>
#    - git add . && git commit && git push
```
```

- [ ] **Step 3: 검증**

```powershell
Test-Path "workflow\_template"
Test-Path "workflow\README.md"
```
Expected: 둘 다 `True`

---

### Task 2: _template에 transcribe.py·make_html.py 복사

**Files:**
- Create: `workflow/_template/transcribe.py` (antigravity-guide/transcribe.py 그대로)
- Create: `workflow/_template/make_html.py` (frontmatter 지원 추가 — Task 3에서 수정)

- [ ] **Step 1: transcribe.py 복사**

```powershell
Copy-Item "antigravity-guide\transcribe.py" "workflow\_template\transcribe.py"
```

- [ ] **Step 2: make_html.py 복사 (Task 3에서 수정함)**

```powershell
Copy-Item "antigravity-guide\make_html.py" "workflow\_template\make_html.py"
```

- [ ] **Step 3: 검증**

```powershell
Get-Item "workflow\_template\transcribe.py", "workflow\_template\make_html.py" | Select-Object Name, Length
```
Expected: 두 파일 모두 존재, 0바이트 아님

---

### Task 3: make_html.py에 frontmatter 지원 추가

**Files:**
- Modify: `workflow/_template/make_html.py`

기존 코드의 하드코딩된 `eyebrow`, `subtitle`, `description`, `source`를 guide.md frontmatter에서 읽도록 변경. frontmatter 없으면 기본값 사용해서 기존 동작 유지.

- [ ] **Step 1: 파일 상단에 frontmatter 파서 추가**

`workflow/_template/make_html.py` 상단 import 직후, `PRETENDARD_LINK` 정의 위에 추가:

```python
def split_frontmatter(text: str) -> tuple[dict, str]:
    """Parse YAML-ish frontmatter (key: value lines) from markdown.

    Returns (meta_dict, body_text). If no frontmatter, returns ({}, text).
    """
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in fm_text.splitlines():
        if ':' in line and not line.lstrip().startswith('#'):
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
    return meta, body
```

- [ ] **Step 2: main() 함수에서 frontmatter 사용하도록 변경**

`workflow/_template/make_html.py`의 `def main()` 본문을 다음과 같이 변경:

```python
def main() -> int:
    md_text = SRC.read_text(encoding="utf-8")
    meta, md_body = split_frontmatter(md_text)

    eyebrow = meta.get("eyebrow", "지피터스 22기 · 끌림 영상 스터디")
    subtitle = meta.get("subtitle", "라이브 강의 정리본")
    description = meta.get("description", f"{eyebrow} — {subtitle}")
    source = meta.get("source", "원본 영상")

    body = markdown.markdown(
        md_body,
        extensions=["extra", "tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )

    title_match = re.search(r"<h1>(.*?)</h1>", body, re.DOTALL)
    title_text = (
        re.sub(r"<.*?>", "", title_match.group(1)).strip()
        if title_match
        else meta.get("title", "가이드")
    )
    body = re.sub(r"<h1>.*?</h1>\s*", "", body, count=1, flags=re.DOTALL)
    body, _entries = inject_h2_ids(body)
    toc = ""

    html_doc = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_text}</title>
<meta name="description" content="{description}">
<meta property="og:title" content="{title_text}">
<meta property="og:description" content="{description}">
<meta property="og:type" content="article">
<meta name="theme-color" content="#2563eb">
{PRETENDARD_LINK}
<style>{CSS}</style>
</head>
<body>
<header class="header-banner">
  <span class="eyebrow">{eyebrow}</span>
  <h1>{title_text}</h1>
  <div class="sub">{subtitle}</div>
</header>
{toc}
{body}
<footer class="footer">
  이 문서는 원본 강의 녹화본(<code>{source}</code>)을 Whisper로 전사한 뒤
  주제별로 정리한 것입니다. 정확한 발화 흐름이 필요하면 원본 영상을 참조하세요.
</footer>
</body>
</html>
"""

    DEST.write_text(html_doc, encoding="utf-8")
    print(f"wrote {DEST} ({DEST.stat().st_size} bytes)")
    return 0
```

- [ ] **Step 3: 파서 단위 테스트**

작은 검증 스크립트를 ad-hoc으로 실행 (저장하지 않음):

```powershell
python -c "import sys; sys.path.insert(0, 'workflow/_template'); from make_html import split_frontmatter; meta, body = split_frontmatter('---\ntitle: 테스트\neyebrow: 스터디\n---\n# 본문\n'); print('meta=', meta); print('body=', repr(body))"
```
Expected: `meta= {'title': '테스트', 'eyebrow': '스터디'}` 그리고 `body= '# 본문\n'`

---

### Task 4: extract_audio.ps1 작성 + ffmpeg 확인

**Files:**
- Create: `workflow/extract_audio.ps1`

- [ ] **Step 1: ffmpeg 설치 확인**

```powershell
ffmpeg -version 2>&1 | Select-Object -First 1
```
Expected: `ffmpeg version ...` 출력. 없으면 `winget install Gyan.FFmpeg` 또는 `choco install ffmpeg`로 설치 후 PowerShell 재시작.

- [ ] **Step 2: extract_audio.ps1 작성**

Create `workflow/extract_audio.ps1`:

```powershell
# Extract 16kHz mono WAV from a video file into a workspace folder.
# Usage: .\workflow\extract_audio.ps1 "video-name.mp4"
param(
    [Parameter(Mandatory)][string]$VideoFile
)
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$rootDir = Split-Path -Parent $scriptDir
$base = [System.IO.Path]::GetFileNameWithoutExtension($VideoFile)
$workspace = Join-Path $rootDir $base
$audio = Join-Path $workspace "audio.wav"

if (-not (Test-Path $workspace)) {
    New-Item -ItemType Directory -Path $workspace | Out-Null
    Write-Host "created workspace: $workspace"
}

if (Test-Path $audio) {
    Write-Host "audio.wav already exists, skipping: $audio"
    exit 0
}

$videoPath = Join-Path $rootDir $VideoFile
if (-not (Test-Path $videoPath)) {
    Write-Error "video file not found: $videoPath"
    exit 1
}

Write-Host "extracting: $videoPath -> $audio"
ffmpeg -i $videoPath -ar 16000 -ac 1 $audio
if ($LASTEXITCODE -ne 0) {
    Write-Error "ffmpeg failed with exit code $LASTEXITCODE"
    exit $LASTEXITCODE
}
Write-Host "done: $audio"
```

- [ ] **Step 3: 검증 (syntax 체크만)**

```powershell
powershell -NoProfile -Command "& { . '.\workflow\extract_audio.ps1' -VideoFile 'nonexistent.mp4' }" 2>&1 | Select-Object -First 5
```
Expected: "video file not found" 에러로 종료 (syntax 자체는 OK 확인용)

---

### Task 5: new_workspace.ps1 작성

**Files:**
- Create: `workflow/new_workspace.ps1`

- [ ] **Step 1: new_workspace.ps1 작성**

Create `workflow/new_workspace.ps1`:

```powershell
# Create a new workspace folder for a video, seeded with _template scripts.
# Usage: .\workflow\new_workspace.ps1 "video-name.mp4"
param(
    [Parameter(Mandatory)][string]$VideoFile
)
$ErrorActionPreference = "Stop"

$scriptDir = $PSScriptRoot
$rootDir = Split-Path -Parent $scriptDir
$base = [System.IO.Path]::GetFileNameWithoutExtension($VideoFile)
$workspace = Join-Path $rootDir $base
$template = Join-Path $scriptDir "_template"

if (Test-Path $workspace) {
    Write-Warning "workspace already exists, leaving as-is: $workspace"
    exit 0
}

New-Item -ItemType Directory -Path $workspace | Out-Null
Write-Host "created workspace: $workspace"

foreach ($file in @("transcribe.py", "make_html.py")) {
    $src = Join-Path $template $file
    $dest = Join-Path $workspace $file
    Copy-Item $src $dest
    Write-Host "copied: $file"
}

Write-Host ""
Write-Host "next: .\workflow\extract_audio.ps1 `"$VideoFile`""
```

- [ ] **Step 2: 가짜 입력으로 검증**

```powershell
.\workflow\new_workspace.ps1 "fake-test-video.mp4"
Test-Path "fake-test-video\transcribe.py"
Test-Path "fake-test-video\make_html.py"
Remove-Item -Recurse "fake-test-video"
```
Expected: 두 `Test-Path` 모두 `True`, 그 후 폴더 삭제

---

### Task 6: stage_publish.py 작성

**Files:**
- Create: `workflow/stage_publish.py`

- [ ] **Step 1: 파일 작성**

Create `workflow/stage_publish.py`:

```python
"""Stage workspace artifacts into publish/<slug>/ folder.

Usage:
    python workflow/stage_publish.py <workspace-dir> --slug <slug>
"""
from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.DOTALL)
    if not m:
        return {}, text
    fm_text, body = m.group(1), m.group(2)
    meta: dict = {}
    for line in fm_text.splitlines():
        if ':' in line and not line.lstrip().startswith('#'):
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
    return meta, body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("workspace", type=Path)
    parser.add_argument("--slug", required=True)
    args = parser.parse_args()

    ws = args.workspace.resolve()
    guide = ws / "guide.md"
    html = ws / "index.html"
    if not guide.exists():
        print(f"missing guide.md in {ws}")
        return 1
    if not html.exists():
        print(f"missing index.html in {ws} (run make_html.py first)")
        return 1

    dest = ws / "publish" / args.slug
    dest.mkdir(parents=True, exist_ok=True)

    md_text = guide.read_text(encoding="utf-8")
    meta, body = split_frontmatter(md_text)

    shutil.copy(html, dest / "index.html")
    (dest / "guide.md").write_text(body, encoding="utf-8")

    title = meta.get("title", "가이드")
    subtitle = meta.get("subtitle", "")
    source = meta.get("source", "")

    readme = f"""# {title}

{subtitle}

웹 페이지로 보기: <https://charde023.github.io/page/{args.slug}/>

## 포함된 파일

- [`index.html`](./index.html) — GitHub Pages가 서빙하는 단일 웹 페이지
- [`guide.md`](./guide.md) — 원본 마크다운

## 생성 방법

원본 녹화본 (`{source}`)을 Whisper로 전사 → 어휘·문장 교정 → 보고서 구조로 정리 → 모바일 최적화 HTML.
"""
    (dest / "README.md").write_text(readme, encoding="utf-8")
    print(f"staged at {dest}")
    print(f"  - index.html ({(dest / 'index.html').stat().st_size} bytes)")
    print(f"  - guide.md   ({(dest / 'guide.md').stat().st_size} bytes)")
    print(f"  - README.md  ({(dest / 'README.md').stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 가짜 데이터로 검증**

```powershell
New-Item -ItemType Directory -Force -Path "fake-ws" | Out-Null
Set-Content -Path "fake-ws\guide.md" -Encoding utf8 -Value @"
---
title: 테스트 가이드
subtitle: 부제
source: test.mp4
---

# 테스트 가이드

본문입니다.
"@
Set-Content -Path "fake-ws\index.html" -Encoding utf8 -Value "<html><body>test</body></html>"
python .\workflow\stage_publish.py "fake-ws" --slug test-slug
Test-Path "fake-ws\publish\test-slug\index.html"
Test-Path "fake-ws\publish\test-slug\guide.md"
Test-Path "fake-ws\publish\test-slug\README.md"
Get-Content "fake-ws\publish\test-slug\guide.md" -TotalCount 3
Remove-Item -Recurse "fake-ws"
```
Expected: 세 `Test-Path` 모두 `True`. guide.md 첫 3줄에는 frontmatter 없이 `# 테스트 가이드`부터 보임.

---

### Task 7: update_pages_index.py 작성

**Files:**
- Create: `workflow/update_pages_index.py`

- [ ] **Step 1: 파일 작성**

Create `workflow/update_pages_index.py`:

```python
"""Generate root index.html for charde023/page from date-prefixed subfolders.

Scans each folder matching YYYY-MM-DD-*, reads guide.md frontmatter, and
builds a card list sorted by date desc.

Usage:
    python workflow/update_pages_index.py <page-repo-path>
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

CSS = """
:root {
  --bg: #f7f9fc; --surface: #ffffff; --text: #1f2a44; --text-soft: #5a6b87;
  --border: #e3e9f3; --accent: #2563eb; --accent-soft: #dbeafe;
  --accent-deep: #1d4ed8;
  --shadow: 0 1px 2px rgba(31,42,68,0.04), 0 8px 24px rgba(31,42,68,0.06);
}
* { box-sizing: border-box; }
body {
  font-family: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont,
               'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', Roboto, sans-serif;
  line-height: 1.6; max-width: 820px; margin: 0 auto; padding: 32px 24px 96px;
  color: var(--text); background: var(--bg); font-size: 17px;
  -webkit-font-smoothing: antialiased; word-break: keep-all;
}
.header {
  margin: -32px -24px 36px; padding: 34px 28px 28px;
  background: linear-gradient(160deg, #e0ecff 0%, #f1f6ff 55%, #ffffff 100%);
  border-bottom: 1px solid var(--border);
}
.header .eyebrow {
  display: inline-block; font-size: 0.78rem; font-weight: 600;
  letter-spacing: 0.08em; text-transform: uppercase; color: var(--accent);
  background: var(--surface); padding: 4px 10px; border-radius: 999px;
  border: 1px solid var(--accent-soft); margin-bottom: 14px;
}
.header h1 { margin: 0; font-size: 1.9rem; line-height: 1.3; }
.header .sub { margin-top: 10px; color: var(--text-soft); font-size: 0.97rem; }
.card-list {
  list-style: none; padding: 0; margin: 0;
  display: flex; flex-direction: column; gap: 14px;
}
.card {
  display: block; padding: 18px 22px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px;
  text-decoration: none; color: var(--text); box-shadow: var(--shadow);
  transition: border-color 0.15s, transform 0.15s;
}
.card:hover { border-color: var(--accent); transform: translateY(-1px); }
.card .date {
  font-size: 0.85rem; color: var(--accent); font-weight: 600;
  letter-spacing: 0.04em;
}
.card h2 { margin: 6px 0 4px; font-size: 1.2rem; color: var(--text); }
.card .sub { color: var(--text-soft); font-size: 0.95rem; }
.empty {
  text-align: center; color: var(--text-soft); padding: 40px 20px;
  background: var(--surface); border: 1px dashed var(--border); border-radius: 12px;
}
.footer {
  margin-top: 4em; padding-top: 1.4em; border-top: 1px solid var(--border);
  font-size: 0.88em; color: var(--text-soft); text-align: center;
}
@media (max-width: 640px) {
  body { padding: 20px 18px 72px; font-size: 16px; }
  .header { margin: -20px -18px 24px; padding: 24px 20px 20px; }
  .header h1 { font-size: 1.5rem; }
  .card { padding: 16px 18px; }
}
"""


def split_frontmatter(text: str) -> tuple[dict, str]:
    m = re.match(r'^---\n(.*?)\n---\n(.*)$', text, re.DOTALL)
    if not m:
        return {}, text
    fm_text = m.group(1)
    meta: dict = {}
    for line in fm_text.splitlines():
        if ':' in line and not line.lstrip().startswith('#'):
            key, value = line.split(':', 1)
            meta[key.strip()] = value.strip()
    return meta, m.group(2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, help="path to charde023/page checkout")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}")
        return 1

    cards: list[dict] = []
    for folder in sorted(repo.iterdir()):
        if not folder.is_dir():
            continue
        if not re.match(r'^\d{4}-\d{2}-\d{2}-', folder.name):
            continue
        guide = folder / "guide.md"
        if not guide.exists():
            continue
        meta, _ = split_frontmatter(guide.read_text(encoding="utf-8"))
        cards.append({
            "slug": folder.name,
            "title": meta.get("title", folder.name),
            "date": meta.get("date", folder.name[:10]),
            "subtitle": meta.get("subtitle", ""),
        })

    cards.sort(key=lambda c: c["date"], reverse=True)

    if cards:
        items_html = "\n".join(
            f'    <li><a class="card" href="./{c["slug"]}/">\n'
            f'      <div class="date">{c["date"]}</div>\n'
            f'      <h2>{c["title"]}</h2>\n'
            f'      <div class="sub">{c["subtitle"]}</div>\n'
            f'    </a></li>'
            for c in cards
        )
        list_html = f'<ul class="card-list">\n{items_html}\n</ul>'
    else:
        list_html = '<div class="empty">아직 등록된 가이드가 없습니다.</div>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>지피터스 스터디 가이드 모음</title>
<meta name="description" content="지피터스 22기 끌림 영상 스터디 라이브 강의 정리본 모음">
<meta name="theme-color" content="#2563eb">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>{CSS}</style>
</head>
<body>
<header class="header">
  <span class="eyebrow">지피터스 22기 · 끌림 영상 스터디</span>
  <h1>스터디 가이드 모음</h1>
  <div class="sub">라이브 강의 녹화본을 보고서 형태로 정리한 모음입니다.</div>
</header>
{list_html}
<footer class="footer">
  charde023 · 자동 생성 인덱스 ({len(cards)}개 가이드)
</footer>
</body>
</html>
"""

    dest = repo / "index.html"
    dest.write_text(html, encoding="utf-8")
    print(f"wrote {dest} ({len(cards)} cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: 가짜 리포로 검증**

```powershell
New-Item -ItemType Directory -Force -Path "fake-repo\2026-05-17-test" | Out-Null
Set-Content -Path "fake-repo\2026-05-17-test\guide.md" -Encoding utf8 -Value @"
---
title: 가짜 가이드
date: 2026-05-17
subtitle: 부제
---
# 본문
"@
python .\workflow\update_pages_index.py fake-repo
Test-Path "fake-repo\index.html"
Get-Content "fake-repo\index.html" | Select-String "가짜 가이드"
Remove-Item -Recurse "fake-repo"
```
Expected: `Test-Path = True`, 출력에 "가짜 가이드"가 한 번 이상 등장.

---

### Task 8: 17일자 가이드에 frontmatter 추가 + HTML 재생성

**Files:**
- Modify: `antigravity-guide/guide.md` (frontmatter 추가)
- Modify: `antigravity-guide/index.html` (재생성)
- Modify: `antigravity-guide/make_html.py` (workflow/_template/ 버전으로 교체)

기존 17일자 가이드를 새 시스템에 맞춰 마이그레이션 준비. publish 폴더는 Phase C에서 다시 만듦.

- [ ] **Step 1: antigravity-guide/make_html.py를 새 버전으로 교체**

```powershell
Copy-Item "workflow\_template\make_html.py" "antigravity-guide\make_html.py" -Force
```

- [ ] **Step 2: guide.md 상단에 frontmatter 추가**

`antigravity-guide/guide.md` 맨 윗줄(`# Antigravity 설치 가이드`) **위에** 다음을 삽입:

```yaml
---
title: Antigravity 설치 가이드
eyebrow: 지피터스 22기 · 끌림 영상 스터디
subtitle: 2026-05-17 라이브 강의 정리본
source: 지피터스-2026-05-17-안티그래비티-설치방법.mp4
description: 지피터스 22기 끌림 영상 스터디 — Antigravity 설치 가이드 (2026-05-17 라이브 정리본)
date: 2026-05-17
---

```

(빈 줄 한 줄 후에 기존 `# Antigravity 설치 가이드`가 이어짐)

- [ ] **Step 3: HTML 재생성**

```powershell
python "antigravity-guide\make_html.py"
```
Expected: `wrote ...\antigravity-guide\index.html (NNNN bytes)` 출력, byte 수가 0보다 큼

- [ ] **Step 4: 시각 확인**

```powershell
Start-Process "antigravity-guide\index.html"
```
브라우저에서 확인: 헤더에 "지피터스 22기 · 끌림 영상 스터디" eyebrow, "Antigravity 설치 가이드" 제목, "2026-05-17 라이브 강의 정리본" 부제가 보여야 함. 본문은 변경 없음.

---

## Phase B — 5/18 영상으로 워크플로우 실행

### Task 9: 작업 폴더 생성 + 오디오 추출

**Files:**
- Create: `지피터스-2026-05-18-설치법/` 작업 폴더
- Create: `지피터스-2026-05-18-설치법/audio.wav`
- Create: `지피터스-2026-05-18-설치법/{transcribe.py, make_html.py}` (템플릿 복사)

- [ ] **Step 1: 작업 폴더 생성**

```powershell
.\workflow\new_workspace.ps1 "지피터스-2026-05-18-설치법.mp4"
```
Expected: `created workspace: ...\지피터스-2026-05-18-설치법`, `copied: transcribe.py`, `copied: make_html.py`

- [ ] **Step 2: 영상 길이 사전 확인**

```powershell
ffprobe -i "지피터스-2026-05-18-설치법.mp4" -show_entries format=duration -v quiet -of csv="p=0"
```
Expected: 초 단위 숫자 출력. 60분 영상 ≈ 3600. 30분 이상이면 다음 단계가 길어질 거라 마음의 준비.

- [ ] **Step 3: 오디오 추출**

```powershell
.\workflow\extract_audio.ps1 "지피터스-2026-05-18-설치법.mp4"
```
Expected: `ffmpeg` 로그 후 `done: ...\audio.wav`

- [ ] **Step 4: 검증**

```powershell
Get-Item "지피터스-2026-05-18-설치법\audio.wav" | Select-Object Name, Length
```
Expected: `Length`가 영상 분당 약 2MB 수준 (예: 60분 → ~120MB). 0바이트면 실패.

---

### Task 10: Whisper 전사 실행

**Files:**
- Create: `지피터스-2026-05-18-설치법/transcript.txt`
- Create: `지피터스-2026-05-18-설치법/transcript.srt`
- Create: `지피터스-2026-05-18-설치법/segments.json`
- Create: `지피터스-2026-05-18-설치법/progress.log`

- [ ] **Step 1: faster-whisper 설치 확인**

```powershell
python -c "import faster_whisper; print(faster_whisper.__version__)"
```
Expected: 버전 출력. 없으면 `pip install faster-whisper`로 설치.

- [ ] **Step 2: 전사 실행 (백그라운드 권장)**

```powershell
python "지피터스-2026-05-18-설치법\transcribe.py"
```
첫 실행이면 모델 다운로드 (large-v3 ≈ 3GB) 발생. GPU 가용 시 5분/시간, CPU 시 30분/시간 이상 소요. 진행률은 같은 폴더 `progress.log`에 30초마다 기록됨.

별도 창에서 진행 보기:
```powershell
Get-Content "지피터스-2026-05-18-설치법\progress.log" -Wait -Tail 20
```

- [ ] **Step 3: 결과 검증**

```powershell
Get-Item "지피터스-2026-05-18-설치법\transcript.txt", "지피터스-2026-05-18-설치법\transcript.srt", "지피터스-2026-05-18-설치법\segments.json" | Select-Object Name, Length
Get-Content "지피터스-2026-05-18-설치법\transcript.txt" -TotalCount 5
```
Expected: 세 파일 모두 0바이트 아님. 첫 5줄에 강의 첫 발화가 한국어로 보임.

---

### Task 11: transcript_clean.md 생성 (Claude 교정)

**Files:**
- Create: `지피터스-2026-05-18-설치법/transcript_clean.md`

Whisper 원문은 그대로 두고, 어휘·문장 교정본을 별도 파일로 만든다. 강의 맥락에 맞춰 명백한 오인식만 수정 (예: 잘못 인식된 영어 단어, 고유명사, 띄어쓰기). 의미를 바꾸거나 요약하지는 않음.

- [ ] **Step 1: 원본 읽기**

Claude 도구로 `지피터스-2026-05-18-설치법/transcript.txt` 전체 읽기. 영상이 길면 segments.json도 참조해 타임라인 확인.

- [ ] **Step 2: 교정 원칙**

다음만 수정한다:
- 명백한 음성인식 오류 (예: "Anti gravity" → "Antigravity")
- 한국어 띄어쓰기·맞춤법
- 영어 고유명사 대소문자 (Node.js, Python, VS Code, Antigravity 등)
- 문장이 끊긴 곳에 마침표·줄바꿈
- 의심스러운 단어는 `[?원문]` 형태로 주석 (예: `Cline [?Crawl]`)

다음은 절대 하지 않는다:
- 의미 추가/삭제
- 문장 합치기·재배열
- 요약·생략

- [ ] **Step 3: transcript_clean.md 작성**

`지피터스-2026-05-18-설치법/transcript_clean.md`에 교정본 저장. 파일 상단에 간단한 헤더 추가:

```markdown
# Transcript (교정본)

> 원본: `transcript.txt` (Whisper 전사본)
> 교정 정책: 명백한 오인식·맞춤법만 수정. 의미 변경 없음. 의심 단어는 `[?원문]` 표기.

---

<교정된 본문>
```

- [ ] **Step 4: 검증**

```powershell
Get-Item "지피터스-2026-05-18-설치법\transcript_clean.md" | Select-Object Name, Length
Select-String -Path "지피터스-2026-05-18-설치법\transcript_clean.md" -Pattern "\[\?" | Measure-Object | Select-Object Count
```
Expected: 파일 존재. `[?` 마크가 너무 많지 않음 (예상: 한 자리 수). 너무 많으면 다음 단계에서 사용자 확인 필요.

---

### Task 12: guide.md 작성 (Claude, frontmatter 포함, 보고서 구조)

**Files:**
- Create: `지피터스-2026-05-18-설치법/guide.md`

5/17 가이드(`antigravity-guide/guide.md`)와 동일한 구조를 따른다.

- [ ] **Step 1: 표준 구조 확인**

`antigravity-guide/guide.md`를 참고 구조로 다시 한번 확인:

1. `# 제목` (h1)
2. 메타 인용구 (`> 스터디명 · 날짜 / 원본 파일명·길이`)
3. `## 결론 (TL;DR)` — 한 줄 요약 + 핵심 포인트 3~5개
4. `## 강의는 어떤 내용이었나` — 1~2문단 개요
5. `## 0. 한눈에 보는 [주제]` — 번호 목록
6. `## 1. ~ ## N.` — 상세 본문
7. (선택) 부록

- [ ] **Step 2: guide.md 작성**

`지피터스-2026-05-18-설치법/guide.md`에 다음 골격으로 작성:

```markdown
---
title: <강의 주제에 맞춰>
eyebrow: 지피터스 22기 · 끌림 영상 스터디
subtitle: 2026-05-18 라이브 강의 정리본
source: 지피터스-2026-05-18-설치법.mp4
description: 지피터스 22기 끌림 영상 스터디 — 2026-05-18 정리본
date: 2026-05-18
---

# <강의 주제>

> 지피터스 22기 끌림 영상 스터디 · 2026-05-18 라이브 강의 정리본
> 원본: `지피터스-2026-05-18-설치법.mp4` (<길이>)

---

## 결론 (TL;DR)

**<한 줄 요약>**

- 핵심 포인트 1
- 핵심 포인트 2
- 핵심 포인트 3

## 강의는 어떤 내용이었나

<1~2문단 개요>

---

## 0. 한눈에 보는 <주제>

1. 단계 1
2. 단계 2
...

---

## 1. <첫 번째 섹션>

<상세 내용>

## 2. <두 번째 섹션>

...
```

내용은 `transcript_clean.md`를 토대로 작성. 의미를 빠뜨리지 않으면서 보고서 톤으로 재구성.

- [ ] **Step 3: 검증**

```powershell
Get-Content "지피터스-2026-05-18-설치법\guide.md" -TotalCount 8
Select-String -Path "지피터스-2026-05-18-설치법\guide.md" -Pattern "^## " | Measure-Object | Select-Object Count
```
Expected: 처음 8줄에 frontmatter 보임. `## ` 헤더가 최소 5개 이상 (TL;DR, 강의 개요, 0번, 1~N).

---

### Task 13: HTML 생성 + 모바일 시각 검증

**Files:**
- Create: `지피터스-2026-05-18-설치법/index.html`

- [ ] **Step 1: HTML 생성**

```powershell
python "지피터스-2026-05-18-설치법\make_html.py"
```
Expected: `wrote ...\index.html (NNNN bytes)`. NNNN > 5000 (대략적인 하한)

- [ ] **Step 2: 데스크탑 시각 확인**

```powershell
Start-Process "지피터스-2026-05-18-설치법\index.html"
```

체크리스트:
- [ ] 헤더 eyebrow ("지피터스 22기 · 끌림 영상 스터디")
- [ ] h1 제목이 guide.md의 `# ...`과 일치
- [ ] 부제 ("2026-05-18 라이브 강의 정리본")
- [ ] TL;DR 인용구 박스
- [ ] 본문이 위에서 아래로 흐름
- [ ] footer 원본 파일명 표시

- [ ] **Step 3: 모바일 시뮬레이션**

Chrome / Edge → DevTools (F12) → Toggle device toolbar (Ctrl+Shift+M) → "iPhone 12 Pro" 또는 "Pixel 7" 선택. 다음 확인:
- [ ] 좌우 스크롤 없음
- [ ] 폰트 가독성 OK (16px 이상)
- [ ] 헤더가 양옆 끝까지 닿음
- [ ] 표가 가로로 넘치지 않음 (필요 시 스크롤)
- [ ] TL;DR 박스의 padding이 답답하지 않음

---

## Phase C — GitHub Pages 배포

### Task 14: page 리포 clone (또는 위치 확인)

**Files:**
- 작업 디렉토리 외부 (예: `C:\Users\inwon\Documents\page-repo\`)

- [ ] **Step 1: 리포 위치 결정**

이미 clone돼 있으면 그 경로를 사용. 없으면:

```powershell
git clone https://github.com/charde023/page.git "C:\Users\inwon\Documents\page-repo"
```
또는 SSH:
```powershell
git clone git@github.com:charde023/page.git "C:\Users\inwon\Documents\page-repo"
```

- [ ] **Step 2: 현재 리포 상태 확인**

```powershell
$repo = "C:\Users\inwon\Documents\page-repo"
Get-ChildItem $repo
```
Expected: 17일자 가이드 파일들이 루트에 있음 (`index.html`, `guide.md`, `README.md` 등). 이게 Phase 16에서 이동 대상.

```powershell
git -C $repo status
git -C $repo log --oneline -5
```
Expected: working tree clean.

---

### Task 15: 5/18 publish 폴더 구성

**Files:**
- Create: `지피터스-2026-05-18-설치법/publish/2026-05-18-installation/{index.html,guide.md,README.md}`

- [ ] **Step 1: stage_publish 실행**

```powershell
python .\workflow\stage_publish.py "지피터스-2026-05-18-설치법" --slug 2026-05-18-installation
```
Expected: `staged at ...\publish\2026-05-18-installation`, 세 파일 byte 수 출력

- [ ] **Step 2: 검증**

```powershell
$pub = "지피터스-2026-05-18-설치법\publish\2026-05-18-installation"
Get-ChildItem $pub
Get-Content "$pub\guide.md" -TotalCount 3
Get-Content "$pub\README.md" -TotalCount 5
```
Expected:
- 3개 파일 모두 존재
- guide.md 첫 줄이 `# ...` (frontmatter 없이)
- README.md에 웹 페이지 링크 보임

---

### Task 16: 17일자 마이그레이션 + 18일자 폴더 복사

**Files (page-repo 내부):**
- Move: 루트 `*.html`, `guide.md`, `README.md` → `2026-05-17-antigravity/`
- Create: `2026-05-18-installation/` (5/18 publish에서 복사)

- [ ] **Step 1: page 리포에 5/17 폴더 만들고 이동**

```powershell
$repo = "C:\Users\inwon\Documents\page-repo"
$dir17 = Join-Path $repo "2026-05-17-antigravity"
New-Item -ItemType Directory -Force -Path $dir17 | Out-Null

# 루트 파일들을 17일자 폴더로 이동
Get-ChildItem $repo -File | Where-Object {
    $_.Name -in @("index.html", "guide.md", "README.md")
} | Move-Item -Destination $dir17

# 결과 확인
Get-ChildItem $dir17
```
Expected: `index.html`, `guide.md`, `README.md`가 `2026-05-17-antigravity/` 안에 보임

- [ ] **Step 2: 17일자 guide.md가 frontmatter 포함되어 있는지 확인**

```powershell
Get-Content "$dir17\guide.md" -TotalCount 8
```
Expected: 첫 8줄에 `---`로 시작하는 frontmatter 보임 (Task 8에서 이미 추가). 없으면 Task 8을 먼저 수행했는지 확인 후 `antigravity-guide/publish/guide.md` 대신 `antigravity-guide/guide.md`에서 다시 복사:

```powershell
Copy-Item "antigravity-guide\guide.md" "$dir17\guide.md" -Force
Copy-Item "antigravity-guide\index.html" "$dir17\index.html" -Force
```

- [ ] **Step 3: 18일자 publish 폴더 통째로 복사**

```powershell
$pubSrc = Join-Path (Get-Location) "지피터스-2026-05-18-설치법\publish\2026-05-18-installation"
$pubDest = Join-Path $repo "2026-05-18-installation"
Copy-Item -Recurse -Force $pubSrc $pubDest
Get-ChildItem $pubDest
```
Expected: `index.html`, `guide.md`, `README.md`

---

### Task 17: 루트 인덱스 생성

**Files:**
- Create: `<page-repo>/index.html` (루트 가이드 목록)

- [ ] **Step 1: update_pages_index.py 실행**

```powershell
$repo = "C:\Users\inwon\Documents\page-repo"
python .\workflow\update_pages_index.py $repo
```
Expected: `wrote ...\page-repo\index.html (2 cards)`

- [ ] **Step 2: 시각 확인**

```powershell
Start-Process "$repo\index.html"
```
체크리스트:
- [ ] 헤더 "스터디 가이드 모음"
- [ ] 카드 2개 (2026-05-18이 위, 2026-05-17이 아래)
- [ ] 각 카드 클릭 시 해당 폴더 (`./2026-05-17-antigravity/`, `./2026-05-18-installation/`)로 이동
- [ ] 모바일 시뮬레이션에서도 카드가 세로로 정렬, 좌우 스크롤 없음

- [ ] **Step 3: 링크 작동 검증 (로컬 파일 한정 — 폴더 슬래시는 실제 호스팅에서만 동작)**

로컬에서는 `file:///` 프로토콜이라 `./2026-05-18-installation/`이 자동으로 `index.html`을 찾지 못할 수 있음. 그래도 URL 자체는 올바르게 생성됐는지 HTML 소스로 확인:

```powershell
Select-String -Path "$repo\index.html" -Pattern 'href="\./2026-'
```
Expected: 2개 href 라인 출력 (17일자, 18일자)

---

### Task 18: 푸시 + 라이브 검증

**Files:** (커밋)
- Modified: 17일자 파일 이동 + 18일자 추가 + 루트 인덱스

- [ ] **Step 1: 변경 사항 확인**

```powershell
$repo = "C:\Users\inwon\Documents\page-repo"
git -C $repo status
```
Expected:
- 루트 `index.html`, `guide.md`, `README.md` 삭제됨
- `2026-05-17-antigravity/` 폴더 추가됨
- `2026-05-18-installation/` 폴더 추가됨
- 새 루트 `index.html` 추가됨

- [ ] **Step 2: 스테이지 + 커밋**

```powershell
git -C $repo add -A
git -C $repo commit -m @'
restructure: per-date subfolders + root index

- migrate 2026-05-17 antigravity guide into /2026-05-17-antigravity/
- add 2026-05-18 installation guide at /2026-05-18-installation/
- add root index.html listing all guides
'@
```
Expected: commit 성공

- [ ] **Step 3: 푸시**

```powershell
git -C $repo push origin main
```
Expected: 푸시 성공 (브랜치 이름이 `master`면 적절히 교체)

- [ ] **Step 4: 5분 대기 후 라이브 확인**

5분 후 다음 URL을 PC + 모바일에서 확인:

1. `https://charde023.github.io/page/` — 카드 2개 보이는 인덱스
2. `https://charde023.github.io/page/2026-05-17-antigravity/` — 17일자 가이드
3. `https://charde023.github.io/page/2026-05-18-installation/` — 18일자 가이드

체크리스트 (각 URL마다):
- [ ] HTTP 200 (404 없음)
- [ ] 모바일에서 좌우 스크롤 없음
- [ ] 헤더·본문·푸터 정상

- [ ] **Step 5: 완료 보고**

작업 완료를 사용자에게 보고:
- 3개 URL 접속 결과
- 작업 폴더 위치 (`workflow/`, `지피터스-2026-05-18-설치법/`)
- 다음 영상 처리 시 사용할 명령 한 줄 요약

---

## 작업 완료 정의 (Done)

- [ ] `workflow/` 안의 5개 스크립트가 모두 실행 가능
- [ ] `https://charde023.github.io/page/` 에서 17·18일자 카드가 보이는 목록 페이지가 로드됨
- [ ] `https://charde023.github.io/page/2026-05-17-antigravity/` 와 `…/2026-05-18-installation/` 두 가이드 모두 모바일에서 정상 표시
- [ ] 다음 영상(예: 5/19)은 7단계만 차례로 실행하면 끝 — 별도 구현 없이
