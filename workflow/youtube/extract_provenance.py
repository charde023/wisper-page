"""Build youtube.json (metadata + provenance) from a workspace's audio.info.json.

Provenance = the original creator/source this curation channel credits. The channel
does NOT link the source video, but it credits the speaker by name + personal socials
in the description, and often "— Name, Org" in the title. We capture both.

Usage:
  python extract_provenance.py --workspace <ws>
  python extract_provenance.py --info <path/to/audio.info.json>
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

from yt_lib import load_config, strip_title_prefix

URL_RE = re.compile(r"https?://[^\s)\]\>\"']+", re.IGNORECASE)
SOCIAL_HOSTS = ("x.com", "twitter.com", "linkedin.com", "github.com", "youtube.com", "youtu.be", "t.me", "instagram.com")
# Generic hosts that are NOT a creator's product/org site.
GENERIC_HOSTS = ("ycombinator.com", "youtube.com", "youtu.be", "google.com", "github.io", "linktr.ee")

# Title credit patterns, applied to the prefix-stripped title:
#   "... — Nick Nisi, WorkOS"      -> ("Nick Nisi", "WorkOS")
#   "... - Philipp Schmid, Google DeepMind"
TITLE_CREDIT_RE = re.compile(r"[—–\-]\s*([^,—–]+?),\s*([^—–]+?)\s*$")
# A run of 2-3 capitalized Latin tokens (likely a person name), tolerant of a
# trailing Korean particle (가/는/이 …) which simply isn't consumed.
NAME_RUN_RE = re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z'’.\-]+){1,2})")
# Product/org names that look like a person-name run but are NOT people.
NAME_STOPLIST = {
    "claude code", "claude", "codex", "anthropic", "openai", "google", "github",
    "cursor", "conductor", "gemini", "opus", "sonnet", "agent view", "context mode",
    "code w", "ai dev", "tech bridge", "claude managed", "claude mythos", "ultra plan",
    "google deepmind", "open claw", "openclaw",
}


def categorize(links: list[str]) -> tuple[list[str], list[str]]:
    socials, others = [], []
    seen = set()
    for u in links:
        u = u.rstrip(".,);]")
        if u in seen:
            continue
        seen.add(u)
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0].lower()
        if any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS):
            socials.append(u)
        else:
            others.append(u)
    return socials, others


def _org_from_links(other_links: list[str]) -> str | None:
    for u in other_links:
        host = re.sub(r"^https?://(www\.)?", "", u).split("/")[0].lower()
        if any(host == h or host.endswith("." + h) for h in GENERIC_HOSTS):
            continue
        label = host.split(".")[0]
        return label[:1].upper() + label[1:] if label else None
    return None


def derive_creator(title: str, description: str, other_links: list[str]) -> tuple[str | None, str | None]:
    # priority 1: explicit English "— Name, Org" suffix
    m = TITLE_CREDIT_RE.search(title)
    if m:
        name = m.group(1).strip()
        org = m.group(2).strip()
        if 1 <= len(name.split()) <= 5 and len(name) <= 40:
            return name, org
    # priority 2: capitalized Latin name run in title (e.g. "Charlie Holtz"),
    # skipping product/org names; org hinted from a non-generic product domain.
    cands = [c.strip() for c in NAME_RUN_RE.findall(title or "")
             if c.strip().lower() not in NAME_STOPLIST]
    name = cands[-1] if cands else None
    org = _org_from_links(other_links)
    if name:
        return name, org
    # fallback: "by <Name>" in first lines of description
    for line in (description or "").splitlines()[:6]:
        bm = re.search(r"\bby\s+([A-Z][\w.'-]+(?:\s+[A-Z][\w.'-]+){0,3})", line)
        if bm:
            return bm.group(1).strip(), org
    return None, org


def build(info: dict, prefix: str) -> dict:
    raw_title = info.get("title") or ""
    title = strip_title_prefix(raw_title, prefix)
    description = info.get("description") or ""
    links = URL_RE.findall(description)
    socials, others = categorize(links)
    creator, affiliation = derive_creator(title, description, others)
    dur = info.get("duration")
    return {
        "id": info.get("id"),
        "title": title,
        "raw_title": raw_title,
        "url": info.get("webpage_url") or (f"https://youtu.be/{info.get('id')}" if info.get("id") else None),
        "upload_date": info.get("upload_date"),
        "view_count": info.get("view_count"),
        "duration": dur,
        "duration_min": round(dur / 60, 1) if isinstance(dur, (int, float)) else None,
        "channel": info.get("channel"),
        "channel_url": info.get("channel_url"),
        "uploader": info.get("uploader"),
        "description": description,
        "provenance": {
            "creator": creator,
            "affiliation": affiliation,
            "social_links": socials,
            "other_links": others,
            "note": "채널이 원본 영상 링크를 안 검 — 화자 이름+SNS 기준 추정 출처",
        },
    }


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Extract metadata + provenance into youtube.json")
    parser.add_argument("--workspace", default=None, help="Workspace dir (reads <ws>/audio.info.json)")
    parser.add_argument("--info", default=None, help="Explicit path to *.info.json")
    args = parser.parse_args(argv)

    if args.info:
        info_path = Path(args.info)
        out_dir = info_path.parent
    elif args.workspace:
        out_dir = Path(args.workspace)
        info_path = out_dir / "audio.info.json"
    else:
        print("ERROR: pass --workspace or --info", file=sys.stderr)
        return 1

    if not info_path.exists():
        print(f"ERROR: info json not found: {info_path}", file=sys.stderr)
        return 1

    info = json.loads(info_path.read_text(encoding="utf-8"))
    data = build(info, cfg.get("titlePrefixStrip", ""))
    out = out_dir / "youtube.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    prov = data["provenance"]
    print(f"youtube.json written -> {out}")
    print(f"  title   : {data['title']}")
    print(f"  creator : {prov['creator']}  ({prov['affiliation']})")
    print(f"  socials : {', '.join(prov['social_links']) or '(none)'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
