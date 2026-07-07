"""Scan page/reports/{weekly,interim}/ and regenerate all index pages.

Usage:
    python update_reports_index.py <page_repo_path>

Generates:
    <page_repo>/reports/index.html          (all reports, latest first)
    <page_repo>/reports/weekly/index.html   (weekly only)
    <page_repo>/reports/interim/index.html  (interim only)

Each report folder must contain a report.md with YAML frontmatter:
    title, type, date, description  (required)
    week, period, milestone, project, owner  (optional)
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from datetime import datetime

# ---------------------------------------------------------------------------
# Lib path bootstrap (same pattern as make_html.py)
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
  --bg: #f4fbf6; --surface: #fff; --surface-soft: #edfaf2;
  --text: #1a2e22; --text-soft: #4a6657; --text-muted: #7a9e8a;
  --border: #c8e6d4; --border-soft: #ddf0e6;
  --accent: #16a34a; --accent-soft: #dcfce7; --accent-deep: #15803d;
  --badge-weekly-bg: #dcfce7;  --badge-weekly-text: #15803d;
  --badge-interim-bg: #fef3c7; --badge-interim-text: #92400e;
  --shadow: 0 1px 2px rgba(22,58,34,.04), 0 8px 24px rgba(22,58,34,.07);
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  font-family: 'Pretendard Variable','Pretendard',-apple-system,BlinkMacSystemFont,
               'Segoe UI','Apple SD Gothic Neo','Noto Sans KR',Roboto,sans-serif;
  line-height: 1.7; max-width: 900px; margin: 0 auto;
  padding: 32px 24px 96px; color: var(--text); background: var(--bg);
  font-size: 17px; -webkit-font-smoothing: antialiased;
  word-break: keep-all; overflow-wrap: anywhere;
}
h1,h2,h3 { line-height:1.35; font-weight:700; letter-spacing:-.01em; color:var(--text); }
h1 { font-size:2rem; margin-top:0; }
h2 { font-size:1.3rem; margin:2em 0 .8em; padding-bottom:.35em; border-bottom:1px solid var(--border); }
a { color:var(--accent); text-decoration:none; font-weight:500; }
a:hover { text-decoration:underline; text-underline-offset:3px; }
.header-banner {
  margin:-32px -24px 36px; padding:32px 28px 26px;
  background:linear-gradient(160deg,#bbf7d0 0%,#dcfce7 50%,#f0fdf4 100%);
  border-bottom:1px solid var(--border);
}
.header-banner h1 { margin:0; }
.header-banner .sub { margin-top:8px; color:var(--text-soft); font-size:.95rem; }
.nav-tabs { display:flex; gap:8px; margin-bottom:2em; flex-wrap:wrap; }
.nav-tab {
  padding:6px 16px; border-radius:999px; font-size:.88rem; font-weight:600;
  border:1px solid var(--border); background:var(--surface); color:var(--text-soft);
  text-decoration:none; transition:all .15s;
}
.nav-tab:hover { background:var(--accent-soft); border-color:var(--accent); color:var(--accent); text-decoration:none; }
.nav-tab:hover { background:var(--accent-soft); border-color:var(--accent); color:var(--accent); text-decoration:none; }
.nav-tab.active { background:var(--accent); color:#fff; border-color:var(--accent); }
.cards { display:grid; gap:16px; }
.card {
  background:var(--surface); border:1px solid var(--border);
  border-radius:14px; padding:20px 22px;
  box-shadow:var(--shadow); transition:box-shadow .15s, transform .15s;
  text-decoration:none; display:block; color:inherit;
}
.card:hover { box-shadow:0 4px 20px rgba(37,99,235,.13); transform:translateY(-1px); text-decoration:none; }
.card-top { display:flex; align-items:center; gap:8px; margin-bottom:10px; }
.badge {
  display:inline-block; font-size:.7rem; font-weight:700; letter-spacing:.08em;
  text-transform:uppercase; padding:3px 10px; border-radius:999px; border:1px solid transparent;
}
.badge-weekly  { background:var(--badge-weekly-bg);  color:var(--badge-weekly-text);  border-color:#bfdbfe; }
.badge-interim { background:var(--badge-interim-bg); color:var(--badge-interim-text); border-color:#fde68a; }
.card-date { font-size:.85rem; color:var(--text-muted); margin-left:auto; }
.card-title { font-size:1.1rem; font-weight:700; color:var(--text); margin:0 0 6px; }
.card-desc { font-size:.93rem; color:var(--text-soft); margin:0; line-height:1.55; }
.card-arrow { margin-top:12px; font-size:.88rem; color:var(--accent); font-weight:600; }
.empty { text-align:center; color:var(--text-muted); padding:3em 0; font-size:.95rem; }
.footer { margin-top:4em; padding-top:1.4em; border-top:1px solid var(--border);
          font-size:.88em; color:var(--text-muted); text-align:center; }
@media (max-width:640px) {
  body { padding:20px 18px 72px; font-size:16px; }
  .header-banner { margin:-20px -18px 24px; padding:24px 20px 20px; }
  .card { padding:16px 18px; }
  .card-date { display:none; }
}
"""

TYPE_LABELS = {"weekly": "Weekly", "interim": "Interim"}
TYPE_NAMES_KO = {"weekly": "주간 보고", "interim": "중간 보고", "all": "전체 보고서"}


def parse_date(s: str) -> datetime:
    for fmt in ("%Y-%m-%d", "%Y-W%W", "%Y"):
        try:
            return datetime.strptime(s.strip(), fmt)
        except ValueError:
            pass
    return datetime.min


def collect_reports(reports_dir: Path) -> list[dict]:
    """Scan weekly/ and interim/ subdirs for report.md files."""
    items = []
    for rtype in ("weekly", "interim"):
        type_dir = reports_dir / rtype
        if not type_dir.exists():
            continue
        for slug_dir in sorted(type_dir.iterdir()):
            if not slug_dir.is_dir():
                continue
            report_md = slug_dir / "report.md"
            if not report_md.exists():
                continue
            try:
                text = report_md.read_text(encoding="utf-8")
                meta, _ = split_frontmatter(text)
                items.append({
                    "type": rtype,
                    "slug": slug_dir.name,
                    "title": meta.get("title", slug_dir.name),
                    "date": str(meta.get("date", "")),
                    "description": meta.get("description", ""),
                    "week": meta.get("week", ""),
                    "project": meta.get("project", "APOM"),
                    "url_path": f"/page/reports/{rtype}/{slug_dir.name}/",
                })
            except Exception as e:
                print(f"  warn: skipping {report_md}: {e}", file=sys.stderr)
    # Sort: latest first
    items.sort(key=lambda x: parse_date(x["date"]), reverse=True)
    return items


def card_html(item: dict, base_url: str) -> str:
    rtype = item["type"]
    badge_class = f"badge-{rtype}"
    label = TYPE_LABELS.get(rtype, rtype.upper())
    title = html.escape(item["title"])
    desc = html.escape(item["description"] or "")
    date_str = html.escape(item["date"])
    week_str = html.escape(item.get("week", ""))
    date_display = week_str if week_str else date_str
    url = f"{base_url}/reports/{rtype}/{item['slug']}/"
    return f"""<a class="card" href="{url}">
  <div class="card-top">
    <span class="badge {badge_class}">{label}</span>
    <span class="card-date">{date_display}</span>
  </div>
  <div class="card-title">{title}</div>
  {"<p class='card-desc'>" + desc + "</p>" if desc else ""}
  <div class="card-arrow">보고서 보기 →</div>
</a>"""


def nav_tabs(current: str, base_url: str) -> str:
    tabs = [
        ("all",     "전체",    f"{base_url}/reports/"),
        ("weekly",  "주간 보고", f"{base_url}/reports/weekly/"),
        ("interim", "중간 보고", f"{base_url}/reports/interim/"),
    ]
    items = []
    for key, label, url in tabs:
        cls = "nav-tab active" if key == current else "nav-tab"
        items.append(f'<a class="{cls}" href="{url}">{label}</a>')
    return '<nav class="nav-tabs">' + "".join(items) + "</nav>"


def build_index_html(
    title: str,
    subtitle: str,
    items: list[dict],
    current_tab: str,
    base_url: str,
) -> str:
    title_esc = html.escape(title)
    subtitle_esc = html.escape(subtitle)
    cards = "\n".join(card_html(i, base_url) for i in items) if items else '<div class="empty">보고서가 없습니다.</div>'
    count = len(items)

    return f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title_esc}</title>
<meta name="description" content="{subtitle_esc}">
<meta name="theme-color" content="#2563eb">
{PRETENDARD_LINK}
<style>{CSS}</style>
</head>
<body>
<header class="header-banner">
  <h1>{title_esc}</h1>
  <div class="sub">{subtitle_esc} &nbsp;·&nbsp; {count}건</div>
</header>
{nav_tabs(current_tab, base_url)}
<div class="cards">
{cards}
</div>
<footer class="footer">APOM 보고서 시스템 · <a href="{base_url}/">← 홈으로</a></footer>
</body>
</html>
"""


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: update_reports_index.py <page_repo_path> [base_url]", file=sys.stderr)
        return 1

    page_repo = Path(sys.argv[1]).resolve()
    base_url = sys.argv[2].rstrip("/") if len(sys.argv) > 2 else "https://charde023.github.io/page"

    reports_dir = page_repo / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    (reports_dir / "weekly").mkdir(exist_ok=True)
    (reports_dir / "interim").mkdir(exist_ok=True)

    all_items = collect_reports(reports_dir)
    weekly_items  = [i for i in all_items if i["type"] == "weekly"]
    interim_items = [i for i in all_items if i["type"] == "interim"]

    # --- All reports index ---
    html_all = build_index_html(
        title="APOM 보고서",
        subtitle="주간 보고 · 중간 보고 전체 목록",
        items=all_items,
        current_tab="all",
        base_url=base_url,
    )
    (reports_dir / "index.html").write_text(html_all, encoding="utf-8")
    print(f"  wrote reports/index.html  ({len(all_items)} total)")

    # --- Weekly index ---
    html_weekly = build_index_html(
        title="APOM 주간 보고",
        subtitle="주간 보고 목록 · 최신순",
        items=weekly_items,
        current_tab="weekly",
        base_url=base_url,
    )
    (reports_dir / "weekly" / "index.html").write_text(html_weekly, encoding="utf-8")
    print(f"  wrote reports/weekly/index.html  ({len(weekly_items)} weekly)")

    # --- Interim index ---
    html_interim = build_index_html(
        title="APOM 중간 보고",
        subtitle="중간 보고 목록 · 최신순",
        items=interim_items,
        current_tab="interim",
        base_url=base_url,
    )
    (reports_dir / "interim" / "index.html").write_text(html_interim, encoding="utf-8")
    print(f"  wrote reports/interim/index.html  ({len(interim_items)} interim)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
