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
    meta, _body = split_frontmatter(md_text)

    shutil.copy(html, dest / "index.html")
    # Keep frontmatter intact — update_pages_index.py reads it to build the
    # root index, and it's harmless for GitHub's markdown renderer.
    shutil.copy(guide, dest / "guide.md")

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
