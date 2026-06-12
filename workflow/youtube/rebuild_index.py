"""Regenerate _목차.md (note index) and _원작채널.md (original-creator index)
for the TechBridge-KR Obsidian folder from each note's frontmatter.

Usage:
  python rebuild_index.py
  python rebuild_index.py --dir "C:\\...\\학습노트\\TechBridge-KR"
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from yt_lib import load_config

INDEX_FILE = "_목차.md"
CREATOR_FILE = "_원작채널.md"


def _parse_frontmatter(text: str) -> dict:
    """Return frontmatter dict with native scalars/lists. Prefers PyYAML."""
    if not text.lstrip("﻿").startswith("---"):
        return {}
    stripped = text.lstrip("﻿")
    nl = stripped.find("\n")
    if nl == -1:
        return {}
    rest = stripped[nl + 1:]
    m = re.search(r"^---\s*$", rest, re.MULTILINE)
    if not m:
        return {}
    fm = rest[: m.start()]
    try:
        import yaml  # type: ignore
        data = yaml.safe_load(fm)
        return data if isinstance(data, dict) else {}
    except Exception:
        return _manual_fm(fm)


def _manual_fm(fm: str) -> dict:
    out: dict = {}
    for line in fm.splitlines():
        line = line.rstrip()
        if not line or line.lstrip().startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key, val = key.strip(), val.strip()
        if val.startswith("[") and val.endswith("]"):
            out[key] = [x.strip().strip("'\"") for x in val[1:-1].split(",") if x.strip()]
        else:
            out[key] = val.strip("'\"")
    return out


def _as_list(v) -> list[str]:
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v if str(x).strip()]
    return [str(v)] if str(v).strip() else []


def _summary_of(text: str) -> str:
    """One-line summary: frontmatter 'summary', else first [!summary] callout line."""
    fm = _parse_frontmatter(text)
    if fm.get("summary"):
        return str(fm["summary"]).strip()
    m = re.search(r"\[!summary\][^\n]*\n>\s*(.+)", text)
    return m.group(1).strip() if m else ""


def collect(note_dir: Path) -> list[dict]:
    notes = []
    for md in sorted(note_dir.glob("*.md")):
        if md.name.startswith("_"):
            continue
        text = md.read_text(encoding="utf-8")
        fm = _parse_frontmatter(text)
        notes.append({
            "stem": md.stem,
            "title": str(fm.get("title") or md.stem),
            "summary": _summary_of(text),
            "upload_date": str(fm.get("upload_date") or ""),
            "url": str(fm.get("url") or ""),
            "creator": str(fm.get("original_creator") or "").strip(),
            "affiliation": str(fm.get("original_affiliation") or "").strip(),
            "links": _as_list(fm.get("original_links")),
        })
    return notes


def write_index(note_dir: Path, notes: list[dict]) -> None:
    notes_sorted = sorted(notes, key=lambda n: n["upload_date"], reverse=True)
    lines = [
        "# TechBridge-KR 학습노트 목차",
        "",
        "> 자동 생성 (`rebuild_index.py`). 영상별 학습노트 인덱스. 최신순.",
        "",
        f"총 {len(notes_sorted)}개",
        "",
        "| 노트 | 업로드 | 한 줄 요약 |",
        "|---|---|---|",
    ]
    for n in notes_sorted:
        summ = n["summary"].replace("|", "\\|")
        lines.append(f"| [[{n['stem']}]] | {n['upload_date'] or '-'} | {summ} |")
    (note_dir / INDEX_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_creator_index(note_dir: Path, notes: list[dict]) -> None:
    by_creator: dict[str, dict] = {}
    for n in notes:
        if not n["creator"]:
            continue
        c = by_creator.setdefault(n["creator"], {"affiliation": n["affiliation"], "links": set(), "notes": []})
        if n["affiliation"] and not c["affiliation"]:
            c["affiliation"] = n["affiliation"]
        c["links"].update(n["links"])
        c["notes"].append(n["stem"])

    lines = [
        "# 원작 채널 / 크리에이터 인덱스",
        "",
        "> 자동 생성. TechBridge-KR이 큐레이션한 원작자별 참조 영상. 학습을 원작 소스로 확장하는 발판.",
        "",
        f"총 {len(by_creator)}명",
        "",
    ]
    for creator in sorted(by_creator):
        c = by_creator[creator]
        head = f"## {creator}" + (f" — {c['affiliation']}" if c["affiliation"] else "")
        lines.append(head)
        if c["links"]:
            lines.append("- 링크: " + " · ".join(sorted(c["links"])))
        lines.append("- 영상: " + " · ".join(f"[[{s}]]" for s in c["notes"]))
        lines.append("")
    (note_dir / CREATOR_FILE).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Rebuild TechBridge-KR Obsidian indexes.")
    parser.add_argument("--dir", default=cfg.get("vaultNoteDir", ""), help="Note folder (default from config)")
    args = parser.parse_args(argv)

    if not args.dir:
        print("ERROR: vaultNoteDir not set in config and --dir not given.", file=sys.stderr)
        return 1
    note_dir = Path(args.dir)
    if not note_dir.exists():
        note_dir.mkdir(parents=True, exist_ok=True)
        print(f"created note dir: {note_dir}")

    notes = collect(note_dir)
    write_index(note_dir, notes)
    write_creator_index(note_dir, notes)
    print(f"indexed {len(notes)} notes -> {note_dir / INDEX_FILE}, {note_dir / CREATOR_FILE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
