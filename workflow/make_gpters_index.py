"""Generate gpters/index.html — 지피터스 22기 강의만 '봐야 하는 순서'(커리큘럼 순)로 모은 인덱스.

루트 index.html(update_pages_index.py)은 page 리포 전체를 날짜 내림차순으로 보여준다.
이 스크립트는 그 중 지피터스 22기 강의 26편만 골라 주차별로 묶고, 각 카드에 시청 순번을
붙여 별도 페이지(gpters/index.html)로 만든다. 두 페이지는 상단 링크로 연결된다.

Usage:
    python workflow/make_gpters_index.py <page-repo-path>
"""
from __future__ import annotations

import argparse
import html as _html
import shutil
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
from config import load_config  # noqa: E402

# ---------------------------------------------------------------------------
# 커리큘럼(봐야 하는) 순서: 슬러그 → 주차 그룹.
# 위에서부터 1번. 영상자료 파일명의 01_~26_ 번호와 동일한 순서다.
# ---------------------------------------------------------------------------
ORDER: list[tuple[str, str]] = [
    ("2026-04-29-ai-study-22-info-session-1", "AI 토크"),
    ("2026-05-06-ai-beginner-four-weeks", "AI 토크"),
    ("2026-05-07-ai-next-step", "AI 토크"),
    ("2026-05-08-ai-personal-system", "AI 토크"),
    ("2026-05-11-ai-study-22-info-session-2", "AI 토크"),
    ("2026-02-14-ai-study-onboarding", "온보딩"),
    ("2026-05-18-week1-lecture", "1주차"),
    ("2026-05-17-antigravity", "1주차"),
    ("2026-05-18-installation", "1주차"),
    ("2026-05-19-hermes-install", "1주차"),
    ("2026-05-19-life-os-week-1", "1주차"),
    ("2026-05-23-week1-offline", "1주차"),
    ("2026-05-25-week2-lecture", "2주차"),
    ("2026-05-26-week2-practice", "2주차"),
    ("2026-05-26-claude-cowork", "2주차"),
    ("2026-05-26-life-os-week-2", "2주차"),
    ("2026-06-01-best-business", "3주차"),
    ("2026-06-01-best-content-1", "3주차"),
    ("2026-06-02-best-content-2", "3주차"),
    ("2026-06-02-best-dev-agent", "3주차"),
    ("2026-06-02-week3-practice", "3주차"),
    ("2026-06-02-ai-chief-life-os", "3주차"),
    ("2026-06-08-best-business", "4주차"),
    ("2026-06-08-best-content", "4주차"),
    ("2026-06-08-best-dev-agent", "4주차"),
    ("2026-06-09-week4-practice", "4주차"),
]

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
  margin: -32px -24px 28px; padding: 34px 28px 28px;
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
.backlink {
  display: inline-block; margin-bottom: 22px; font-size: 0.9rem;
  color: var(--accent); text-decoration: none; font-weight: 600;
}
.backlink:hover { text-decoration: underline; }
.group-title {
  margin: 30px 0 12px; font-size: 1.05rem; font-weight: 700; color: var(--accent-deep);
  padding-bottom: 6px; border-bottom: 2px solid var(--accent-soft);
}
.group-title:first-of-type { margin-top: 4px; }
.card-list { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.card {
  display: flex; gap: 14px; align-items: flex-start; padding: 16px 20px; background: var(--surface);
  border: 1px solid var(--border); border-radius: 12px;
  text-decoration: none; color: var(--text); box-shadow: var(--shadow);
  transition: border-color 0.15s, transform 0.15s;
}
.card:hover { border-color: var(--accent); transform: translateY(-1px); }
.card .num {
  flex: 0 0 auto; min-width: 34px; height: 34px; display: flex; align-items: center;
  justify-content: center; background: var(--accent-soft); color: var(--accent-deep);
  font-weight: 700; font-size: 0.92rem; border-radius: 9px; margin-top: 2px;
}
.card .body { flex: 1 1 auto; min-width: 0; }
.card .date { font-size: 0.82rem; color: var(--accent); font-weight: 600; letter-spacing: 0.04em; }
.card h2 { margin: 4px 0 3px; font-size: 1.12rem; color: var(--text); }
.card .sub { color: var(--text-soft); font-size: 0.92rem; }
.empty {
  text-align: center; color: var(--text-soft); padding: 40px 20px;
  background: var(--surface); border: 1px dashed var(--border); border-radius: 12px;
}
.footer {
  margin-top: 3em; padding-top: 1.4em; border-top: 1px solid var(--border);
  font-size: 0.88em; color: var(--text-soft); text-align: center;
}
@media (max-width: 640px) {
  body { padding: 20px 18px 72px; font-size: 16px; }
  .header { margin: -20px -18px 22px; padding: 24px 20px 20px; }
  .header h1 { font-size: 1.5rem; }
  .card { padding: 14px 16px; gap: 12px; }
}
"""


def main() -> int:
    cfg = load_config()
    site_eyebrow = cfg.get("siteEyebrow", "지피터스 22기 · 끌림 영상 스터디")

    parser = argparse.ArgumentParser()
    parser.add_argument("repo", type=Path, help="path to charde023/page checkout")
    args = parser.parse_args()

    repo = args.repo.resolve()
    if not repo.is_dir():
        print(f"not a directory: {repo}")
        return 1

    # 게시된 슬러그만 순번대로 카드화 (미게시는 건너뜀)
    cards: list[dict] = []
    n = 0
    for slug, group in ORDER:
        guide = repo / slug / "guide.md"
        if not guide.exists():
            continue
        n += 1
        meta, _ = split_frontmatter(guide.read_text(encoding="utf-8"))
        cards.append({
            "num": n,
            "group": group,
            "slug": slug,
            "title": meta.get("title", slug),
            "date": meta.get("date", slug[:10]),
            "subtitle": meta.get("subtitle", ""),
        })

    # 그룹별 섹션 HTML (ORDER 순서가 곧 그룹 순서)
    blocks: list[str] = []
    seen_group: str | None = None
    open_list = False
    for c in cards:
        if c["group"] != seen_group:
            if open_list:
                blocks.append("    </ul>")
            blocks.append(f'  <div class="group-title">{_html.escape(c["group"])}</div>')
            blocks.append('    <ul class="card-list">')
            seen_group = c["group"]
            open_list = True
        blocks.append(
            f'      <li><a class="card" href="../{c["slug"]}/">\n'
            f'        <span class="num">{c["num"]:02d}</span>\n'
            f'        <span class="body">\n'
            f'          <span class="date">{_html.escape(str(c["date"]))}</span>\n'
            f'          <h2>{_html.escape(c["title"])}</h2>\n'
            f'          <span class="sub">{_html.escape(c["subtitle"])}</span>\n'
            f'        </span>\n'
            f'      </a></li>'
        )
    if open_list:
        blocks.append("    </ul>")
    list_html = "\n".join(blocks) if cards else '<div class="empty">아직 등록된 강의가 없습니다.</div>'

    html = f"""<!DOCTYPE html>
<html lang="ko">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>지피터스 22기 강의 — 주차순 모음</title>
<meta name="description" content="{site_eyebrow} 강의를 주차순(봐야 하는 순서)으로 모은 목록입니다.">
<meta name="theme-color" content="#2563eb">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>{CSS}</style>
</head>
<body>
<header class="header">
  <span class="eyebrow">{site_eyebrow}</span>
  <h1>지피터스 22기 강의 모음</h1>
  <div class="sub">AI 토크 · 온보딩 · 1~4주차를 봐야 하는 순서대로 정리했습니다.</div>
</header>
{list_html}
<footer class="footer">
  charde023 · 지피터스 22기 강의 {len(cards)}편 (주차순)
</footer>
</body>
</html>
"""

    dest_dir = repo / "gpters"
    dest_dir.mkdir(exist_ok=True)
    dest = dest_dir / "index.html"

    if dest.exists() and dest.read_text(encoding="utf-8") == html:
        print("gpters index unchanged")
        return 0
    if dest.exists():
        shutil.copy2(dest, dest.with_suffix(".html.bak"))
    dest.write_text(html, encoding="utf-8")
    print(f"wrote {dest} ({len(cards)} gpters cards)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
