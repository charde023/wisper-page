"""Convert a report MD file into a self-contained index.html for GitHub Pages.

Usage:
    python make_report_html.py --input report.md
    python make_report_html.py --input report.md --output path/to/index.html

Differences from make_html.py:
  - Takes --input (direct MD path) instead of --workspace/--src
  - Header shows type badge (WEEKLY / INTERIM) + title + date
  - TOC enabled by default
  - Report-specific footer (no transcript note)
  - Type-specific badge colour
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from pathlib import Path


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

import markdown  # noqa: E402

PRETENDARD_LINK = (
    '<link rel="stylesheet" '
    'href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">'
)

CSS = """
:root {
  --bg: #f4fbf6;
  --surface: #ffffff;
  --surface-soft: #edfaf2;
  --text: #1a2e22;
  --text-soft: #4a6657;
  --text-muted: #7a9e8a;
  --border: #c8e6d4;
  --border-soft: #ddf0e6;
  --accent: #16a34a;
  --accent-soft: #dcfce7;
  --accent-deep: #15803d;
  --badge-weekly-bg: #dcfce7;
  --badge-weekly-text: #15803d;
  --badge-interim-bg: #fef3c7;
  --badge-interim-text: #92400e;
  --badge-project-bg: #e0f2fe;
  --badge-project-text: #0369a1;
  --status-ok: #16a34a;
  --status-warn: #d97706;
  --status-bad: #dc2626;
  --shadow: 0 1px 2px rgba(22,58,34,.04), 0 8px 24px rgba(22,58,34,.07);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: 'Pretendard Variable', 'Pretendard', -apple-system, BlinkMacSystemFont,
               'Segoe UI', 'Apple SD Gothic Neo', 'Noto Sans KR', Roboto, sans-serif;
  font-feature-settings: 'tnum', 'ss03';
  line-height: 1.75;
  max-width: 860px;
  margin: 0 auto;
  padding: 32px 24px 96px;
  color: var(--text);
  background: var(--bg);
  font-size: 17px;
  -webkit-font-smoothing: antialiased;
  word-break: keep-all;
  overflow-wrap: anywhere;
}
h1,h2,h3,h4 {
  line-height: 1.35;
  margin-top: 2em;
  margin-bottom: 0.65em;
  font-weight: 700;
  letter-spacing: -.01em;
  color: var(--text);
}
h1 { font-size: 2rem; margin-top: 0; }
h2 { font-size: 1.45rem; padding-bottom: .35em; border-bottom: 1px solid var(--border); }
h3 { font-size: 1.15rem; color: var(--accent-deep); }
h4 { font-size: 1.02rem; }
p { margin: .85em 0; }
a { color: var(--accent); text-decoration: none; font-weight: 500; }
a:hover { text-decoration: underline; text-underline-offset: 3px; }
strong { color: var(--accent-deep); font-weight: 700; }
em { color: var(--text-soft); }
blockquote {
  margin: 1.2em 0;
  padding: .9em 1.2em;
  background: var(--accent-soft);
  border-left: 4px solid var(--accent);
  border-radius: 10px;
  font-size: .97em;
}
blockquote p { margin: .35em 0; }
blockquote strong { color: var(--accent-deep); }
ol,ul { padding-left: 1.5em; }
li { margin: .4em 0; }
code {
  font-family: 'JetBrains Mono','SF Mono',Consolas,'Liberation Mono',monospace;
  font-size: .88em;
  background: var(--surface-soft);
  color: var(--accent-deep);
  padding: .15em .45em;
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
pre code { background: transparent; border: 0; padding: 0; font-size: .92em; color: var(--text); }
table {
  border-collapse: separate;
  border-spacing: 0;
  width: 100%;
  margin: 1.2em 0;
  font-size: .96em;
  background: var(--surface);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
  box-shadow: var(--shadow);
}
th,td { padding: 11px 14px; text-align: left; vertical-align: top; border-bottom: 1px solid var(--border-soft); }
tr:last-child td { border-bottom: 0; }
th { background: var(--surface-soft); font-weight: 600; color: var(--accent-deep); border-bottom: 1px solid var(--border); }
hr { border: 0; border-top: 1px solid var(--border); margin: 2.6em 0; }

/* ── Header banner ── */
.header-banner {
  margin: -32px -24px 36px;
  padding: 32px 28px 26px;
  background: linear-gradient(160deg, #bbf7d0 0%, #dcfce7 50%, #f0fdf4 100%);
  border-bottom: 1px solid var(--border);
}
.badge {
  display: inline-block;
  font-size: .72rem;
  font-weight: 700;
  letter-spacing: .1em;
  text-transform: uppercase;
  padding: 4px 11px;
  border-radius: 999px;
  margin-bottom: 12px;
  border: 1px solid transparent;
}
.badge-weekly  { background: var(--badge-weekly-bg);  color: var(--badge-weekly-text);  border-color: #bfdbfe; }
.badge-interim { background: var(--badge-interim-bg); color: var(--badge-interim-text); border-color: #fde68a; }
.badge-project { background: var(--badge-project-bg); color: var(--badge-project-text); border-color: #bae6fd; margin-left: 6px; }
.header-banner h1 { margin: 0; font-size: 1.85rem; color: var(--text); line-height: 1.3; }
.header-banner .meta { margin-top: 10px; color: var(--text-soft); font-size: .94rem; }

/* ── TOC ── */
.toc {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 18px 24px;
  margin: 1.5em 0 2.4em;
  box-shadow: var(--shadow);
}
.toc h3 { margin: 0 0 10px; font-size: .88rem; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; color: var(--accent); }
.toc ol { margin: 0; padding-left: 1.4em; color: var(--text-soft); }
.toc li { margin: .3em 0; }
.toc a { color: var(--text); font-weight: 500; }
.toc a:hover { color: var(--accent); }

/* ── Back button ── */
.back-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 999px;
  font-size: .88rem;
  font-weight: 600;
  color: var(--text-soft);
  text-decoration: none;
  box-shadow: var(--shadow);
  transition: background .15s, border-color .15s, color .15s;
}
.back-btn:hover { background: var(--accent-soft); border-color: var(--accent); color: var(--accent); text-decoration: none; }
.back-btn-top { margin: 0 0 1.8em; }
.back-btn-bottom { margin: 3em 0 0; }
/* ── Footer ── */
.footer { margin-top: 2em; padding-top: 1.4em; border-top: 1px solid var(--border); font-size: .88em; color: var(--text-muted); text-align: center; }

/* ── Mobile ── */
@media (max-width: 640px) {
  body { padding: 20px 18px 72px; font-size: 16px; }
  .header-banner { margin: -20px -18px 24px; padding: 24px 20px 20px; }
  .header-banner h1 { font-size: 1.5rem; }
  h2 { font-size: 1.25rem; }
  h3 { font-size: 1.08rem; }
  table { font-size: .9em; }
  th,td { padding: 9px 10px; }
}
@media (max-width: 380px) {
  body { font-size: 15.5px; padding: 18px 16px 64px; }
  table { font-size: .86em; }
  th,td { padding: 7px 8px; }
}
"""


TYPE_LABELS = {
    "weekly": "Weekly",
    "interim": "Interim",
}


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s가-힣-]", "", text, flags=re.UNICODE).strip()
    text = re.sub(r"\s+", "-", text)
    return text.lower() or "section"


def inject_h2_ids(html_str: str) -> tuple[str, list[tuple[str, str]]]:
    entries: list[tuple[str, str]] = []
    used: dict[str, int] = {}

    def add_id(match: re.Match[str]) -> str:
        inner = match.group(1)
        title = re.sub(r"<.*?>", "", inner).strip()
        base = slugify(title)
        slug = base
        if base in used:
            used[base] += 1
            slug = f"{base}-{used[base]}"
        else:
            used[base] = 1
        entries.append((slug, title))
        return f'<h2 id="{slug}">{inner}</h2>'

    new_html = re.sub(r"<h2>(.*?)</h2>", add_id, html_str, flags=re.DOTALL)
    return new_html, entries


def build_toc(entries: list[tuple[str, str]]) -> str:
    if not entries:
        return ""
    items = "\n".join(f'    <li><a href="#{s}">{t}</a></li>' for s, t in entries)
    return (
        '<nav class="toc" aria-label="목차">\n'
        '  <h3>목차</h3>\n  <ol>\n'
        f'{items}\n'
        '  </ol>\n</nav>\n'
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Render a report MD into index.html.")
    parser.add_argument("--input", type=Path, required=True, help="Source report.md path")
    parser.add_argument("--output", type=Path, default=None, help="Output index.html path (default: same dir as input)")
    parser.add_argument("--base-url", default="https://charde023.github.io/page", help="Site base URL for back-link")
    args = parser.parse_args()

    src: Path = args.input.resolve()
    if not src.exists():
        print(f"ERROR: input not found: {src}", file=sys.stderr)
        return 1

    dest: Path = args.output.resolve() if args.output else src.parent / "index.html"
    dest.parent.mkdir(parents=True, exist_ok=True)

    md_text = src.read_text(encoding="utf-8")
    meta, md_body = split_frontmatter(md_text)

    report_type = str(meta.get("type", "weekly")).lower()
    type_label = TYPE_LABELS.get(report_type, report_type.upper())
    badge_class = f"badge-{report_type}" if report_type in TYPE_LABELS else "badge-weekly"

    project = html.escape(str(meta.get("project", "APOM")))
    date_str = html.escape(str(meta.get("date", "")))
    week_str = html.escape(str(meta.get("week", "")))
    period_str = html.escape(str(meta.get("period", "")))
    milestone_str = html.escape(str(meta.get("milestone", "")))
    description_raw = meta.get("description", "")
    owner = html.escape(str(meta.get("owner", "")))

    # Build subtitle line
    meta_parts = []
    if date_str:
        meta_parts.append(date_str)
    if week_str:
        meta_parts.append(week_str)
    if period_str:
        meta_parts.append(f"기간: {period_str}")
    if milestone_str:
        meta_parts.append(f"마일스톤: {milestone_str}")
    if owner:
        meta_parts.append(f"보고자: {owner}")
    meta_line = " · ".join(meta_parts)

    body = markdown.markdown(
        md_body,
        extensions=["extra", "tables", "fenced_code", "sane_lists"],
        output_format="html5",
    )

    title_match = re.search(r"<h1>(.*?)</h1>", body, re.DOTALL)
    title_text = html.escape(
        re.sub(r"<.*?>", "", title_match.group(1)).strip()
        if title_match
        else meta.get("title", "보고서")
    )

    if not description_raw:
        description_raw = f"APOM {type_label} 보고서 — {title_text}"
    description = html.escape(str(description_raw))

    body = re.sub(r"<h1>.*?</h1>\s*", "", body, count=1, flags=re.DOTALL)
    body, entries = inject_h2_ids(body)
    toc = build_toc(entries)

    back_url = f"{args.base_url}/reports/{report_type}/"
    back_btn = f'<a class="back-btn" href="{back_url}">← {TYPE_LABELS.get(report_type, "보고서")} 목록</a>'

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
<meta name="theme-color" content="#16a34a">
{PRETENDARD_LINK}
<style>{CSS}</style>
</head>
<body>
<header class="header-banner">
  <div>
    <span class="badge {badge_class}">{type_label}</span>
    <span class="badge badge-project">{project}</span>
  </div>
  <h1>{title_text}</h1>
  <div class="meta">{meta_line}</div>
</header>
<div class="back-btn-top">{back_btn}</div>
{toc}
{body}
<div class="back-btn-bottom">{back_btn}</div>
<footer class="footer">
  APOM · {project} 보고서 · {date_str}
</footer>
</body>
</html>
"""

    dest.write_text(html_doc, encoding="utf-8")
    print(f"wrote {dest} ({dest.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
