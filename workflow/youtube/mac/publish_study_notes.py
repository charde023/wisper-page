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
from yt_lib import load_channels, load_config  # noqa: E402

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
.badge{display:inline-block;font-size:.72rem;font-weight:600;padding:2px 8px;border-radius:999px;
border:1px solid var(--accent-soft);color:var(--accent);background:var(--surface);margin-bottom:6px}
.filters{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 20px}
.filters input{position:absolute;opacity:0;pointer-events:none}
.filters label{cursor:pointer;font-size:.86rem;font-weight:600;padding:6px 14px;border-radius:999px;
border:1px solid var(--border);background:var(--surface);color:var(--text-soft);user-select:none}
"""

NOTE_TMPL = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title>
<meta name="description" content="{summary}"><meta name="theme-color" content="#2563eb">
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable.min.css">
<style>{css}</style></head><body>
<div class="header"><a class="back" href="../">← 학습노트 목록</a>
<div class="eyebrow">{eyebrow}</div><h1>{title}</h1>
<div class="meta">{meta}</div></div>
{body}
</body></html>"""

LANDING_TMPL = """<!DOCTYPE html><html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>학습노트 — AI·창업</title>
<meta name="description" content="AI·코딩·창업 유튜브 강연을 전사·정리한 한국어 학습노트 모음.">
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
{filter_css}
</style></head><body>
<div class="header"><div class="eyebrow">AI · 창업</div><h1>학습노트</h1>
<div class="meta">AI·코딩·창업 유튜브 강연을 전사하고 한국어로 정리한 학습노트 모음 · 총 {count}개</div></div>
<div class="filters">{chips}</div>
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


def note_to_html(md_text: str, channel: str = "TechBridge-KR"):
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
                            css=PAGE_CSS, meta=meta, body=body_html,
                            eyebrow=html.escape(f"{channel} 학습노트"))
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

    # 채널 목록은 하드코딩하지 않고 실제 meta에서 뽑는다(채널이 늘어도 무수정).
    chans: dict[str, str] = {}
    for m in metas:
        key = m.get("channel_key") or "techbridge"      # 구 meta = TechBridge 시절
        chans.setdefault(key, m.get("channel") or "TechBridge-KR")

    cards = []
    for m in metas:
        key = m.get("channel_key") or "techbridge"
        sub = html.escape((m.get("summary") or "")[:160])
        cm = []
        if m.get("original_creator"):
            cm.append(html.escape(m["original_creator"]))
        if m.get("upload_date"):
            cm.append(str(m["upload_date"]))
        badge = f'<div class="badge">{html.escape(chans.get(key, key))}</div>'
        cards.append(
            f'<li data-ch="{html.escape(key)}"><a class="card" href="{m["slug"]}/">{badge}'
            f'<h2>{html.escape(m["title"])}</h2>'
            f'<div class="cmeta">{" · ".join(cm)}</div><div class="csum">{sub}</div></a></li>'
        )

    ordered = sorted(chans.items(), key=lambda kv: kv[1])
    chips = ['<input type="radio" name="chf" id="f-all" checked>'
             '<label for="f-all">전체</label>']
    rules = []
    for key, label in ordered:
        chips.append(f'<input type="radio" name="chf" id="f-{key}">'
                     f'<label for="f-{key}">{html.escape(label)}</label>')
        rules.append(f'#f-{key}:checked ~ .card-list li:not([data-ch="{key}"]){{display:none}}')
        rules.append(f'#f-{key}:checked ~ .filters label[for="f-{key}"]'
                     f'{{background:var(--accent);color:#fff;border-color:var(--accent)}}')
    # 칩 자신도 .filters 안에 있어 형제 선택자가 닿지 않는다 → :has() 로 활성 표시
    rules.append('.filters:has(#f-all:checked) label[for="f-all"]'
                 '{background:var(--accent);color:#fff;border-color:var(--accent)}')
    for key, _ in ordered:
        rules.append(f'.filters:has(#f-{key}:checked) label[for="f-{key}"]'
                     f'{{background:var(--accent);color:#fff;border-color:var(--accent)}}')

    (group_dir / "index.html").write_text(
        LANDING_TMPL.format(css=PAGE_CSS, count=len(metas), cards="\n".join(cards),
                            chips="\n".join(chips), filter_css="\n".join(rules)),
        encoding="utf-8",
    )
    return len(metas)


def collect_notes(vault_root: Path, channels, only: str | None = None):
    """[(channel, note_path)] — only 지정 시 그 채널만."""
    out = []
    for ch in channels:
        if only and ch.key != only:
            continue
        d = ch.note_path(vault_root)
        if not d.is_dir():
            print(f"  (스킵) 노트 폴더 없음: {d}")
            continue
        out += [(ch, pth) for pth in sorted(d.glob("*.md")) if not pth.name.startswith("_")]
    return out


def existing_slugs(group_dir: Path) -> set[str]:
    return {d.name for d in group_dir.iterdir() if d.is_dir()} if group_dir.is_dir() else set()


def prune_guard(before: set[str], after: set[str], confirm: bool) -> None:
    """사라지는 slug가 있으면 삭제하지 않고 중단한다. 개수가 아니라 집합 포함으로 판정."""
    lost = sorted(before - after)
    if not lost:
        return
    print(f"\n⛔ 발행하면 기존 slug {len(lost)}개가 사라진다:", file=sys.stderr)
    for sl in lost:
        print(f"   - {sl}", file=sys.stderr)
    if not confirm:
        print("의도한 삭제면 --prune-confirm 을 붙여라. 중단한다.", file=sys.stderr)
        raise SystemExit(3)
    print("--prune-confirm 지정됨 → 삭제 진행", file=sys.stderr)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--note", default=None)
    ap.add_argument("--channel", default=None, help="이 채널만 발행(프루닝 잠금)")
    ap.add_argument("--no-push", action="store_true")
    ap.add_argument("--prune-confirm", action="store_true",
                    help="기존 slug가 사라지는 것을 의도한 경우에만")
    a = ap.parse_args(argv)

    try:
        vault_root, channels = load_channels()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if a.note:
        legacy_dir = Path(load_config().get("vaultNoteDir") or channels[0].note_path(vault_root))
        pairs = [(channels[0], legacy_dir / a.note)]
    elif a.all or a.channel:
        pairs = collect_notes(vault_root, channels, only=a.channel)
    else:
        print("--all / --channel / --note 중 하나 필요", file=sys.stderr)
        return 1

    tmp = Path(tempfile.mkdtemp(prefix="pageclone_"))
    clone = tmp / "page"
    print(f"[1/4] clone {REPO}")
    run(["gh", "repo", "clone", REPO, str(clone), "--", "-q", "--depth", "1"])
    gdir = clone / GROUP
    gdir.mkdir(exist_ok=True)

    before = existing_slugs(gdir)
    n = 0
    built_slugs = set()
    for ch, np_ in pairs:
        md_text = np_.read_text(encoding="utf-8")
        page, fm = note_to_html(md_text, ch.name)
        slug = slug_for(fm, np_.stem)
        built_slugs.add(slug)
        d = gdir / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(page, encoding="utf-8")
        (d / "meta.json").write_text(json.dumps({
            "slug": slug, "title": fm.get("title", np_.stem),
            "summary": fm.get("summary", ""), "upload_date": str(fm.get("upload_date") or ""),
            "original_creator": fm.get("original_creator", ""), "url": fm.get("url", ""),
            "channel": ch.name, "channel_key": ch.key,
        }, ensure_ascii=False), encoding="utf-8")
        n += 1
        print(f"  built [{ch.key}] {slug}  ({fm.get('title','')[:36]})")

    # 프루닝은 '전 채널을 빌드했을 때'만. 단일 채널·단일 노트 실행에서는 잠근다.
    full_build = bool(a.all) and not a.channel and not a.note
    if full_build:
        import shutil as _sh

        prune_guard(before, built_slugs, a.prune_confirm)
        for sub in gdir.iterdir():
            if sub.is_dir() and sub.name not in built_slugs:
                _sh.rmtree(sub)
                print(f"  pruned {sub.name}")
    elif before - built_slugs:
        print(f"  (부분 실행 — 프루닝 잠금, 기존 {len(before - built_slugs)}개 유지)")

    total = build_landing(gdir)
    print(f"[2/4] landing 재생성: {total}개 카드")

    after = existing_slugs(gdir)
    lost = sorted(before - after)
    if lost:
        print(f"⚠ 사라진 slug {len(lost)}개: {lost[:5]}", file=sys.stderr)
    else:
        print(f"  무손실 확인: 기존 {len(before)}개 ⊆ 발행 후 {len(after)}개")

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
