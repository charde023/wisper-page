"""옵시디언 학습노트 MD → 자체완결 HTML → charde023/page 의 study-notes/ 그룹 발행.

- 루트 index.html(지피터스 랜딩)은 건드리지 않는다 → 완전 격리.
- study-notes/<slug>/index.html 발행 + study-notes/index.html(전용 랜딩) 재생성.
- 옵시디언 콜아웃(> [!summary]/[!info]/[!note]-)·<span> 강조·[[위키링크]] 변환.

Usage:
  python mac/publish_study_notes.py --all            # 볼트 TechBridge-KR 전체 발행
  python mac/publish_study_notes.py --note "<제목>.md"
  python mac/publish_study_notes.py --all --no-push  # 로컬 빌드만(검증)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from yt_lib import load_config  # noqa: E402

REPO = "charde023/page"
GROUP = "study-notes"
LIVE = f"https://charde023.github.io/page/{GROUP}/"

PAGE_CSS = """
:root{--bg:#f7f9fc;--surface:#fff;--text:#1f2a44;--text-soft:#5a6b87;--border:#e3e9f3;
--accent:#2563eb;--accent-soft:#dbeafe;--orange:#ef6c00;--shadow:0 1px 2px rgba(31,42,68,.04),0 8px 24px rgba(31,42,68,.06)}
*{box-sizing:border-box}
body{font-family:'Pretendard Variable','Pretendard',-apple-system,BlinkMacSystemFont,'Apple SD Gothic Neo','Noto Sans KR',sans-serif;
line-height:1.65;max-width:820px;margin:0 auto;padding:32px 24px 96px;color:var(--text);background:var(--bg);
font-size:17px;-webkit-font-smoothing:antialiased;word-break:keep-all}
a{color:var(--accent)}
.header{margin:-32px -24px 28px;padding:34px 28px 24px;background:linear-gradient(160deg,#e0ecff 0%,#f1f6ff 55%,#fff 100%);border-bottom:1px solid var(--border)}
.header .eyebrow{display:inline-block;font-size:.78rem;font-weight:600;letter-spacing:.08em;text-transform:uppercase;
color:var(--accent);background:var(--surface);padding:4px 10px;border-radius:999px;border:1px solid var(--accent-soft);margin-bottom:12px}
.header h1{margin:0;font-size:1.7rem;line-height:1.32}
.meta{margin-top:10px;color:var(--text-soft);font-size:.92rem}
.callout{margin:18px 0;padding:14px 16px;border-radius:10px;border:1px solid var(--border);background:var(--surface);box-shadow:var(--shadow)}
.callout .ct{font-weight:700;font-size:.86rem;margin-bottom:6px;color:var(--accent)}
.callout-info{border-left:4px solid var(--accent)}
.callout-summary{border-left:4px solid var(--orange)}.callout-summary .ct{color:var(--orange)}
.callout-cite{border-left:4px solid #94a3b8;background:#f8fafc}
details{margin:18px 0;padding:12px 16px;border:1px solid var(--border);border-radius:10px;background:var(--surface)}
details summary{cursor:pointer;font-weight:700;color:var(--accent)}
details[open] summary{margin-bottom:10px}
table{border-collapse:collapse;width:100%;margin:16px 0;font-size:.95rem}
th,td{border:1px solid var(--border);padding:7px 10px;text-align:left;vertical-align:top}
th{background:var(--accent-soft)}
h2{margin-top:32px;font-size:1.3rem;border-bottom:1px solid var(--border);padding-bottom:6px}
h3{margin-top:24px;font-size:1.1rem}
code{background:#eef2f9;padding:1px 5px;border-radius:5px;font-size:.9em}
.back{display:inline-block;margin-bottom:8px;font-size:.9rem}
"""

NOTE_TMPL = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<meta name="description" content="{summary}"><meta name="theme-color" content="#2563eb">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>{css}</style></head><body>
<div class="header"><a class="back" href="../">← 학습노트 목록</a>
<div class="eyebrow">TechBridge-KR 학습노트</div><h1>{title}</h1>
<div class="meta">{meta}</div></div>
{body}
</body></html>"""

LANDING_TMPL = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>학습노트 — TechBridge-KR</title>
<meta name="description" content="AI·코딩 유튜브 강연을 전사·정리한 한국어 학습노트 모음.">
<meta name="theme-color" content="#2563eb">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>{css}
.card-list{{list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:14px}}
.card{{display:block;padding:18px 20px;background:var(--surface);border:1px solid var(--border);border-radius:12px;
box-shadow:var(--shadow);text-decoration:none;color:inherit;transition:transform .12s}}
.card:hover{{transform:translateY(-2px)}}
.card h2{{margin:0 0 6px;font-size:1.1rem;border:0;padding:0}}
.card .cmeta{{color:var(--text-soft);font-size:.85rem;margin-bottom:6px}}
.card .csum{{color:var(--text-soft);font-size:.93rem}}
</style></head><body>
<div class="header"><div class="eyebrow">TechBridge-KR</div><h1>학습노트</h1>
<div class="meta">AI·코딩 유튜브 강연을 Whisper로 전사하고 한국어로 정리한 학습노트 모음 · 총 {count}개</div></div>
<ul class="card-list">{cards}</ul></body></html>"""


def _fm_fallback(block: str) -> dict:
    """YAML 파싱 실패 시(예: title 값이 '['로 시작) 핵심 키만 라인 파싱."""
    fm = {}
    for line in block.split("\n"):
        m = re.match(r"^([a-zA-Z_]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return fm


def parse_frontmatter(text: str):
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not m:
        return {}, text
    import yaml

    try:
        fm = yaml.safe_load(m.group(1))
        if not isinstance(fm, dict):
            raise ValueError("frontmatter not a mapping")
    except Exception:
        fm = _fm_fallback(m.group(1))
    return fm, m.group(2)


def convert_callouts(md: str):
    """옵시디언 콜아웃 블록 → 플레이스홀더 + {토큰: HTML}. 접기(-)는 <details>.

    플레이스홀더는 markdown 렌더를 통과한 뒤 최종 HTML로 치환한다(중첩 div 파손 방지)."""
    lines = md.split("\n")
    out, i, k = [], 0, 0
    blocks: dict[str, str] = {}
    head_re = re.compile(r"^>\s*\[!(\w+)\](-)?\s*(.*)$")
    while i < len(lines):
        m = head_re.match(lines[i])
        if not m:
            out.append(lines[i])
            i += 1
            continue
        ctype, fold, title = m.group(1).lower(), m.group(2), m.group(3).strip()
        i += 1
        body = []
        while i < len(lines) and (lines[i].startswith(">") or lines[i].strip() == ""):
            if head_re.match(lines[i]):  # 다음 콜아웃 시작 → 현재 블록 종료
                break
            if lines[i].strip() == "" and (i + 1 >= len(lines) or not lines[i + 1].startswith(">")):
                break
            body.append(re.sub(r"^>\s?", "", lines[i]))
            i += 1
        inner = _md(("\n".join(body)).strip())
        if fold:
            label = title or {"note": "펼치기"}.get(ctype, "펼치기")
            html_block = f'<details><summary>{html.escape(label)}</summary>\n{inner}\n</details>'
        else:
            label = {"summary": "요약", "info": "정보", "cite": "출처", "note": "노트"}.get(ctype, ctype)
            head = f'<div class="ct">{html.escape(title or label)}</div>' if (title or label) else ""
            html_block = f'<div class="callout callout-{ctype}">{head}\n{inner}\n</div>'
        token = f"XCALLOUTX{k}X"
        blocks[token] = html_block
        out.append("")
        out.append(token)   # 자체 문단으로 → markdown이 <p>token</p>로 감쌈
        out.append("")
        k += 1
    return "\n".join(out), blocks


def _md(text: str) -> str:
    import markdown

    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)   # [[a|b]] -> b
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)               # [[a]] -> a
    return markdown.markdown(text, extensions=["tables", "fenced_code"], output_format="html5")


def note_to_html(md_text: str):
    fm, body_md = parse_frontmatter(md_text)
    title = fm.get("title", "학습노트")
    summary = (fm.get("summary") or "")[:180]
    meta_bits = []
    if fm.get("original_creator"):
        aff = f" · {fm['original_affiliation']}" if fm.get("original_affiliation") else ""
        meta_bits.append(f"원작자 {fm['original_creator']}{aff}")
    if fm.get("upload_date"):
        meta_bits.append(f"업로드 {fm['upload_date']}")
    if fm.get("duration_min"):
        meta_bits.append(f"{fm['duration_min']}분")
    if fm.get("url"):
        meta_bits.append(f'<a href="{fm["url"]}" target="_blank" rel="noopener">원본 영상 ↗</a>')
    meta = " · ".join(meta_bits)
    # 본문: 콜아웃→플레이스홀더 → 전체 마크다운 렌더 → 플레이스홀더를 콜아웃 HTML로 치환.
    body_md = re.sub(r"^#\s+.*\n", "", body_md, count=1)  # H1 제목 중복 제거
    staged, blocks = convert_callouts(body_md)
    body_html = _md(staged)
    for token, block in blocks.items():
        body_html = body_html.replace(f"<p>{token}</p>", block).replace(token, block)
    page = NOTE_TMPL.format(title=html.escape(title), summary=html.escape(summary),
                            css=PAGE_CSS, meta=meta, body=body_html)
    return page, fm


def slug_for(fm: dict, fallback: str) -> str:
    vid = fm.get("video_id")
    up = (str(fm.get("upload_date") or "")).replace("-", "")
    if vid:
        return f"{up}-{vid}" if up else vid
    return re.sub(r"[^a-zA-Z0-9]+", "-", fallback).strip("-").lower()[:60]


def run(cmd, cwd=None, check=True):
    return subprocess.run(cmd, cwd=cwd, check=check, capture_output=True, text=True)


def build_landing(group_dir: Path):
    metas = []
    for mj in group_dir.glob("*/meta.json"):
        metas.append(json.loads(mj.read_text(encoding="utf-8")))
    metas.sort(key=lambda m: str(m.get("upload_date") or ""), reverse=True)
    cards = []
    for m in metas:
        sub = html.escape((m.get("summary") or "")[:160])
        cm = []
        if m.get("original_creator"):
            cm.append(html.escape(m["original_creator"]))
        if m.get("upload_date"):
            cm.append(str(m["upload_date"]))
        cards.append(
            f'<li><a class="card" href="{m["slug"]}/"><h2>{html.escape(m["title"])}</h2>'
            f'<div class="cmeta">{" · ".join(cm)}</div><div class="csum">{sub}</div></a></li>'
        )
    (group_dir / "index.html").write_text(
        LANDING_TMPL.format(css=PAGE_CSS, count=len(metas), cards="\n".join(cards)),
        encoding="utf-8",
    )
    return len(metas)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--note", default=None)
    ap.add_argument("--no-push", action="store_true")
    a = ap.parse_args(argv)

    vault = Path(load_config()["vaultNoteDir"])
    if a.all:
        notes = [p for p in vault.glob("*.md") if not p.name.startswith("_")]
    elif a.note:
        notes = [vault / a.note]
    else:
        print("--all 또는 --note 필요", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="pageclone_"))
    clone = tmp / "page"
    print(f"[1/4] clone {REPO}")
    run(["gh", "repo", "clone", REPO, str(clone), "--", "-q", "--depth", "1"])
    gdir = clone / GROUP
    gdir.mkdir(exist_ok=True)

    n = 0
    built_slugs = set()
    for np_ in notes:
        md_text = np_.read_text(encoding="utf-8")
        page, fm = note_to_html(md_text)
        slug = slug_for(fm, np_.stem)
        built_slugs.add(slug)
        d = gdir / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        (d / "meta.json").write_text(json.dumps({
            "slug": slug, "title": fm.get("title", np_.stem),
            "summary": fm.get("summary", ""), "upload_date": str(fm.get("upload_date") or ""),
            "original_creator": fm.get("original_creator", ""), "url": fm.get("url", ""),
        }, ensure_ascii=False), encoding="utf-8")
        n += 1
        print(f"  built {slug}  ({fm.get('title','')[:40]})")

    # --all = 전체 desired set → 볼트에 없는 유령 폴더 프루닝(오슬러그·삭제된 노트 자가치유)
    if a.all:
        import shutil as _sh

        for sub in gdir.iterdir():
            if sub.is_dir() and sub.name not in built_slugs:
                _sh.rmtree(sub)
                print(f"  pruned {sub.name}")

    total = build_landing(gdir)
    print(f"[2/4] landing 재생성: {total}개 카드")

    if a.no_push:
        print(f"[--no-push] 로컬 빌드만: {clone}/{GROUP}")
        return 0

    run(["git", "config", "user.name", "charde023"], cwd=clone)
    run(["git", "config", "user.email", "inwonshands@gmail.com"], cwd=clone)
    run(["git", "add", GROUP], cwd=clone)
    r = run(["git", "-c", "commit.gpgsign=false", "commit", "-q", "-m",
             f"study-notes: publish {n} note(s)"], cwd=clone, check=False)
    if r.returncode != 0 and "nothing to commit" in (r.stdout + r.stderr):
        print("변경 없음")
        return 0
    print("[3/4] push")
    run(["git", "push", "origin", "HEAD"], cwd=clone)
    print(f"[4/4] 폴링 {LIVE}")
    for _ in range(30):
        try:
            with urllib.request.urlopen(LIVE, timeout=8) as resp:
                if resp.status == 200:
                    print(f"LIVE ✅ {LIVE}")
                    return 0
        except Exception:
            pass
    print(f"발행됨(전파 대기중): {LIVE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
