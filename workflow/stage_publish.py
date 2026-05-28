"""Stage workspace artifacts into publish/<slug>/ folder.

Usage:
    python workflow/stage_publish.py <workspace-dir> --slug <slug> [--page-url <url>]
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Shared lib bootstrap (resolves whether called from workflow/, _template/, or
# a legacy workspaces/<ws>/ copy)
# ---------------------------------------------------------------------------
def _ensure_lib_on_path() -> None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        for cand in (parent / "lib", parent / "workflow" / "lib"):
            if (cand / "frontmatter.py").exists():
                if str(cand) not in sys.path:
                    sys.path.insert(0, str(cand))
                return


_ensure_lib_on_path()

from frontmatter import split_frontmatter  # noqa: E402
from config import load_config  # noqa: E402
from manifest import set_stage  # noqa: E402

# ---------------------------------------------------------------------------
# Slug validation
# ---------------------------------------------------------------------------
_SLUG_RE = re.compile(r"^\d{4}-\d{2}-\d{2}-")


def _validate_slug(slug: str) -> None:
    if not _SLUG_RE.match(slug):
        print(
            f"WARNING: slug '{slug}' does not match YYYY-MM-DD-<topic> pattern. "
            "update_pages_index.py only scans folders starting with YYYY-MM-DD- and will skip this one.",
            file=sys.stderr,
        )


def main() -> int:
    cfg = load_config()

    parser = argparse.ArgumentParser(
        description="Stage workspace artifacts into publish/<slug>/ folder.",
    )
    parser.add_argument("workspace", type=Path, help="Workspace directory")
    parser.add_argument("--slug", required=True, help="URL slug (YYYY-MM-DD-<topic>)")
    parser.add_argument(
        "--page-url",
        default=cfg.get("pageBaseUrl", "https://charde023.github.io/page"),
        help="Base URL for the GitHub Pages site (default: from config pageBaseUrl)",
    )
    args = parser.parse_args()

    ws = args.workspace.resolve()
    slug: str = args.slug
    page_url: str = args.page_url.rstrip("/")

    # Slug validation — warn only, don't hard-fail
    _validate_slug(slug)

    guide = ws / "guide.md"
    html = ws / "index.html"

    if not guide.exists():
        print(f"ERROR: missing guide.md in {ws}", file=sys.stderr)
        return 1
    if not html.exists():
        print(f"ERROR: missing index.html in {ws} — run make_html.py first", file=sys.stderr)
        return 1

    # Warn if HTML is stale compared to guide.md
    if html.stat().st_mtime < guide.stat().st_mtime:
        print(
            "WARNING: index.html is older than guide.md — consider re-running make_html.py "
            "to pick up the latest guide content.",
            file=sys.stderr,
        )

    dest = ws / "publish" / slug
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

    guide_url = f"{page_url}/{slug}/"
    readme = f"""# {title}

{subtitle}

웹 페이지로 보기: <{guide_url}>

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

    # Best-effort manifest stamp
    set_stage(ws, "staged")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
