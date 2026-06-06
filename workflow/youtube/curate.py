"""Score and select a BALANCED curated subset from channel_index.json.

Balances three signals so popular how-to tutorials don't crowd out high-value
conceptual / conference talks:
  topic_hits   — channel topic keywords in title (config.topicKeywords)
  concept_hits — conceptual/depth terms (harness, agent memory, architecture, ...)
  speaker      — named speaker or conference talk (Karpathy, Hassabis, "— Name, Org", ...)
  view_pct     — view-count percentile (down-weighted; newer深 talks have few views)

score = 2.0*topic + 1.6*concept + 3.0*speaker + 1.0*view_pct

Usage:
  python curate.py --top 45
  python curate.py --top 45 --include-ids ID1,ID2 --exclude-ids ID3
"""
from __future__ import annotations

import argparse
import re
import sys

from yt_lib import load_config, read_state, strip_title_prefix, write_state

# Conceptual / depth terms (bilingual). Kept tight so plain how-to tutorials
# ("팁 12가지") are NOT lifted — only genuinely conceptual talks.
CONCEPT_KEYWORDS = [
    "하네스", "harness", "에이전틱", "agentic", "에이전트", "메모리", "memory", "드리밍", "dreaming",
    "컨텍스트", "context", "운영체제", "설계도", "blueprint", "청사진", "엔지니어", "engineering",
    "변곡점", "미래", "future", "심층", "deep dive", "동작", "원리", "패러다임", "paradigm",
    "아키텍처", "architecture", "추론", "reasoning", "기본기", "네이티브", "native",
    "장시간", "long-running", "코드를 읽", "reading code", "조직", "변화", "코드베이스",
]

# Named speakers / conference markers (lowercased substrings).
SPEAKER_TOKENS = [
    "karpathy", "카파시", "하사비스", "hassabis", "보리스", "체르니", "cherny",
    "andrew ng", "앤드루 응", "dario", "다리오", "amodei", "philipp schmid",
    "dex horthy", "humanlayer", "matt pocock", "michael truell", "공동창업자",
    "patrick debois", "tessl", "tejas kumar", "ryan lopopolo", "nick nisi", "workos",
    "prasenjit", "sonar", "garry tan", "demis", "code w/ claude", "ai dev",
    "replay 2026", "@ replay", "발표 세션", "keynote", "키노트", "ceo",
]
# "— Name, Org" / "| Name(Org)" credit pattern in the title.
CREDIT_RE = re.compile(r"[—–\-|]\s*[^,—–|]+,\s*[^—–|]+$|\([^)]*(?:Anthropic|OpenAI|Google|Meta|IBM|DeepMind)[^)]*\)")


def percentile_ranks(values: list[float]) -> dict[float, float]:
    if not values:
        return {}
    ordered = sorted(set(values))
    n = len(ordered)
    return {v: (i / (n - 1) if n > 1 else 1.0) for i, v in enumerate(ordered)}


def score_video(v: dict, keywords: list[str], view_pct: float) -> dict:
    tl = (v.get("title") or "").lower()
    topic = sorted({k for k in keywords if k in tl})
    concept = sorted({k for k in CONCEPT_KEYWORDS if k.lower() in tl})
    speaker = bool([t for t in SPEAKER_TOKENS if t in tl]) or bool(CREDIT_RE.search(v.get("title") or ""))
    score = 2.0 * len(topic) + 1.6 * len(concept) + 4.0 * (1 if speaker else 0) + 0.8 * view_pct
    return {"topic": topic, "concept": concept, "speaker": speaker, "score": score, "view_pct": view_pct}


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    keywords = [k.lower() for k in cfg.get("topicKeywords", [])]
    prefix = cfg.get("titlePrefixStrip", "")

    parser = argparse.ArgumentParser(description="Balanced curation of the channel index.")
    parser.add_argument("--top", type=int, default=45, help="Select top N by score (default 45)")
    parser.add_argument("--include-ids", default="", help="Comma-separated video IDs to force-include")
    parser.add_argument("--exclude-ids", default="", help="Comma-separated video IDs to drop")
    args = parser.parse_args(argv)

    include = {x.strip() for x in args.include_ids.split(",") if x.strip()}
    exclude = {x.strip() for x in args.exclude_ids.split(",") if x.strip()}

    index = read_state("channel_index.json")
    if not index or not index.get("videos"):
        print("ERROR: no channel_index.json — run yt_channel_scan.py first.", file=sys.stderr)
        return 1

    videos = [v for v in index["videos"] if v.get("id") not in exclude]
    pct = percentile_ranks([float(v.get("view_count") or 0) for v in videos])

    scored = []
    for v in videos:
        s = score_video(v, keywords, pct.get(float(v.get("view_count") or 0), 0.0))
        dur = v.get("duration")
        scored.append({
            "id": v.get("id"),
            "url": v.get("url") or (f"https://youtu.be/{v.get('id')}" if v.get("id") else None),
            "title": strip_title_prefix(v.get("title") or "", prefix),
            "raw_title": v.get("title"),
            "upload_date": v.get("upload_date"),
            "view_count": v.get("view_count"),
            "duration_min": round(dur / 60, 1) if isinstance(dur, (int, float)) else None,
            "score": round(s["score"], 3),
            "topic_hits": s["topic"],
            "concept_hits": s["concept"],
            "speaker": s["speaker"],
            "reason": f"토픽{len(s['topic'])}·개념{len(s['concept'])}·{'화자' if s['speaker'] else '-'}·조회{v.get('view_count')}",
        })

    scored.sort(key=lambda s: s["score"], reverse=True)
    selected = scored[: args.top]
    sel_ids = {s["id"] for s in selected}
    # force-include
    for s in scored:
        if s["id"] in include and s["id"] not in sel_ids:
            selected.append(s)
            sel_ids.add(s["id"])

    payload = {"source": "channel_index.json", "top": args.top, "count": len(selected), "videos": selected}
    path = write_state("curated_queue.json", payload)

    n_speaker = sum(1 for s in selected if s["speaker"])
    n_concept = sum(1 for s in selected if s["concept_hits"])
    print(f"selected {len(selected)} / {len(scored)} -> {path}")
    print(f"  화자/컨퍼런스 {n_speaker}개 · 개념 포함 {n_concept}개")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
