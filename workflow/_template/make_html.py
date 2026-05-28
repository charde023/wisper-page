"""Render guide.md into a self-contained index.html for GitHub Pages."""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path

import markdown

# ---------------------------------------------------------------------------
# Shared frontmatter bootstrap (resolves lib/ whether this file lives in
# workflow/_template/, workflow/, or a legacy workspaces/<ws>/ copy).
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


PRETENDARD_LINK = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">'
)

CSS = """
:root {
  --bg: #f7f9fc;
  --surface: #ffffff;
  --surface-soft: #f1f6ff;
  --text: #1f2a44;
  --text-soft: #5a6b87;
  --text-muted: #8593ab;
  --border: #e3e9f3;
  --border-soft: #eef2f8;
  --accent: #2563eb;
  --accent-soft: #dbeafe;
  --accent-deep: #1d4ed8;
  --shadow: 0 1px 2px rgba(31, 42, 68, 0.04), 0 8px 24px rgba(31, 42, 68, 0.06);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont,
               'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', Roboto, sans-serif;
  font-feature-settings: 'tnum', 'ss03';
  line-height: 1.75;
  max-width: 820px;
  margin: 0 auto;
  padding: 32px 24px 96px;
  color: var(--text);
  background: var(--bg);
  font-size: 17px;
  -webkit-font-smoothing: antialiased;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
h1, h2, h3, h4 {
  line-height: 1.35;
  margin-top: 2em;
  margin-bottom: 0.65em;
  font-weight: 700;
  letter-spacing: -0.01em;
  color: var(--text);
}
h1 { font-size: 2rem; margin-top: 0; }
h2 {
  font-size: 1.5rem;
  padding-bottom: 0.35em;
  border-bottom: 1px solid var(--border);
}
h3 { font-size: 1.18rem; color: var(--accent-deep); }
h4 { font-size: 1.02rem; }
p { margin: 0.85em 0; color: var(--text); }
a { color: var(--accent); text-decoration: none; font-weight: 500; }
a:hover { text-decoration: underline; text-underline-offset: 3px; }
strong { color: var(--accent-deep); font-weight: 700; }
em { color: var(--text-soft); }
blockquote {
  margin: 1.2em 0;
  padding: 0.9em 1.2em;
  background: var(--accent-soft);
  border-left: 4px solid var(--accent);
  color: var(--text);
  border-radius: 10px;
  font-size: 0.97em;
}
blockquote p { margin: 0.35em 0; }
blockquote strong { color: var(--accent-deep); }
ol, ul { padding-left: 1.5em; }
li { margin: 0.4em 0; }
code {
  font-family: 'JetBrains Mono', 'SF Mono', Consolas, 'Liberation Mono', monospace;
  font-size: 0.88em;
  background: var(--surface-soft);
  color: var(--accent-deep);
  padding: 0.15em 0.45em;
  border-radius: 5px;
  border: 1px solid var(--border-soft);
}
pre {
  background: var(--surface);
  padding: 16px 20px;
  border-radius: 10px;
  overflow-x: auto;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
  line-height: 1.6;
  margin: 1.2em 0;
}
pre code {
  background: transparent;
  border: 0;
  padding: 0;
  font-size: 0.92em;
  color: var(--text);
}
table {
  border-collapse: separate;
  border-spacing: 0;
  width: 100%;
  margin: 1.2em 0;
  font-size: 0.96em;
  background: var(--surface);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}
th, td {
  padding: 12px 14px;
  text-align: left;
  vertical-align: top;
  border-bottom: 1px solid var(--border-soft);
}
tr:last-child td { border-bottom: 0; }
th {
  background: var(--surface-soft);
  font-weight: 600;
  color: var(--accent-deep);
  border-bottom: 1px solid var(--border);
}
hr { border: 0; border-top: 1px solid var(--border); margin: 2.6em 0; }
.header-banner {
  margin: -32px -24px 36px;
  padding: 34px 28px 28px;
  background: linear-gradient(160deg, #e0ecff 0%, #f1f6ff 55%, #ffffff 100%);
  border-bottom: 1px solid var(--border);
  text-align: left;
}
.header-banner .eyebrow {
  display: inline-block;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  background: var(--surface);
  padding: 4px 10px;
  border-radius: 999px;
  border: 1px solid var(--accent-soft);
  margin-bottom: 14px;
}
.header-banner h1 {
  margin: 0;
  font-size: 1.9rem;
  color: var(--text);
  line-height: 1.3;
}
.header-banner .sub {
  margin-top: 10px;
  color: var(--text-soft);
  font-size: 0.97rem;
}
.toc {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px 24px;
  margin: 1.5em 0 2.4em;
  box-shadow: var(--shadow);
}
.toc h3 {
  margin: 0 0 10px;
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--accent);
}
.toc ol {
  margin: 0;
  padding-left: 1.4em;
  color: var(--text-soft);
}
.toc li { margin: 0.3em 0; }
.toc a { color: var(--text); font-weight: 500; }
.toc a:hover { color: var(--accent); }
.footer {
  margin-top: 4em;
  padding-top: 1.4em;
  border-top: 1px solid var(--border);
  font-size: 0.88em;
  color: var(--text-muted);
  text-align: center;
}
.footer code { font-size: 0.92em; }
@media (max-width: 640px) {
  body {
    padding: 20px 18px 72px;
    font-size: 16px;
    line-height: 1.72;
  }
  .header-banner {
    margin: -20px -18px 24px;
    padding: 24px 20px 20px;
    border-radius: 0;
  }
  .header-banner .eyebrow { font-size: 0.72rem; }
  .header-banner h1 { font-size: 1.5rem; }
  .header-banner .sub { font-size: 0.9rem; }
  h1 { font-size: 1.7rem; }
  h2 { font-size: 1.3rem; }
  h3 { font-size: 1.08rem; }
  h4 { font-size: 1rem; }
  blockquote { padding: 0.8em 1em; font-size: 0.95em; }
  pre { padding: 14px 16px; font-size: 0.9em; }
  table { font-size: 0.92em; }
  th, td { padding: 10px 11px; }
  .toc { padding: 14px 18px; }
  ol, ul { padding-left: 1.3em; }
}
@media (max-width: 380px) {
  body { font-size: 15.5px; padding: 18px 16px 64px; }
  .header-banner h1 { font-size: 1.35rem; }
  table { font-size: 0.88em; }
  th, td { padding: 8px 9px; }
}
"""


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s가-힣-]", "", text, flags=re.UNICODE).strip()
    text = re.sub(r"\s+", "-", text)
    return text.lower() or "section"


def inject_h2_ids(html_str: str) -> tuple[str, list[tuple[str, str]]]:
    entries: list[tuple[str, str]] = []
    used: dict[str, int] = {}

    def add_id(match: re.Match[str]) -> str:
        title = re.sub(r"<.*?>", "", match.group(1)).strip()
        base = slugify(title)
        slug = base
        if base in used:
            used[base] += 1
            slug = f"{base}-{used[base]}"
        else:
            used[base] = 1
        entries.append((slug, title))
        return f'<h2 id="{slug}">{match.group(1)}</h2>'

    new_html = re.sub(r"<h2>(.*?)</h2>", add_id, html_str, flags=re.DOTALL)
    return new_html, entries


def build_toc(entries: list[tuple[str, str]]) -> str:
    if not entries:
        return ""
    items = "\n".join(
        f'    <li><a href="#{slug}">{title}</a></li>' for slug, title in entries
    )
    return (
        '<nav class="toc" aria-label="목차">\n'
        '  <h3>목차</h3>\n'
        '  <ol>\n'
        f'{items}\n'
        '  </ol>\n'
        '</nav>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render guide.md into a self-contained index.html."
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path(__file__).parent,
        help="Workspace directory (default: directory containing this script)",
    )
    parser.add_argument(
        "--src",
        type=Path,
        default=None,
        help="Override source markdown path (default: <workspace>/guide.md)",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        default=None,
        help="Override output HTML path (default: <workspace>/index.html)",
    )
    args = parser.parse_args()

    workspace: Path = args.workspace.resolve()
    src: Path = args.src.resolve() if args.src else workspace / "guide.md"
    dest: Path = args.dest.resolve() if args.dest else workspace / "index.html"

    md_text = src.read_text(encoding="utf-8")
    meta, md_body = split_frontmatter(md_text)

    eyebrow = html.escape(meta.get("eyebrow", "지피터스 22기 · 끌림 영상 스터디"))
    subtitle = html.escape(meta.get("subtitle", "라이브 강의 정리본"))
    description_raw = meta.get("description", "")
    source = html.escape(str(meta.get("source", "원본 영상")))

    body = markdown.markdown(
        md_body,
        extensions=["extra", "tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )

    title_match = re.search(r"<h1>(.*?)</h1>", body, re.DOTALL)
    title_text = html.escape(
        re.sub(r"<.*?>", "", title_match.group(1)).strip()
        if title_match
        else meta.get("title", "가이드")
    )
    if not description_raw:
        description_raw = f"{meta.get('eyebrow', '지피터스 22기 · 끌림 영상 스터디')} — {meta.get('subtitle', '라이브 강의 정리본')}"
    description = html.escape(str(description_raw))

    body = re.sub(r"<h1>.*?</h1>\s*", "", body, count=1, flags=re.DOTALL)
    body, _entries = inject_h2_ids(body)

    # TOC is gated: only render when frontmatter has 'toc: true'
    toc_flag = str(meta.get("toc", "false")).strip().lower()
    toc = build_toc(_entries) if toc_flag == "true" else ""

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

    dest.write_text(html_doc, encoding="utf-8")
    print(f"wrote {dest} ({dest.stat().st_size} bytes)")

    # Best-effort manifest stage stamp
    try:
        _ensure_lib_on_path()
        from manifest import set_stage  # noqa: E402
        set_stage(workspace, "html")
    except Exception:  # noqa: BLE001
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
