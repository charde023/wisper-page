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
