"""Poll a YouTube channel RSS feed and report videos not seen before.

First run with no seen-state initialises silently (marks current feed as seen, 0 new)
so the scheduled watcher doesn't alert on the existing backlog. Subsequent runs report
genuinely new uploads.

Usage (scheduled task):
  python rss_watch.py --json --mark      # report new (JSON) and mark them seen
Other:
  python rss_watch.py                     # human-readable
  python rss_watch.py --init              # force re-init: mark whole current feed seen
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from yt_lib import load_config, read_state, write_state

NS = {
    "a": "http://www.w3.org/2005/Atom",
    "yt": "http://www.youtube.com/xml/schemas/2015",
    "media": "http://search.yahoo.com/mrss/",
}
SEEN_FILE = "seen_videos.json"


def fetch_feed(rss_url: str) -> list[dict]:
    req = urllib.request.Request(rss_url, headers={"User-Agent": "Mozilla/5.0 techbridge-watch"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read()
    root = ET.fromstring(raw)
    out = []
    for entry in root.findall("a:entry", NS):
        vid = entry.findtext("yt:videoId", default="", namespaces=NS)
        title = entry.findtext("a:title", default="", namespaces=NS)
        published = entry.findtext("a:published", default="", namespaces=NS)
        link_el = entry.find("a:link", NS)
        url = link_el.get("href") if link_el is not None else (f"https://youtu.be/{vid}" if vid else "")
        if vid:
            out.append({"id": vid, "title": title, "published": published, "url": url})
    return out


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Watch a YouTube channel RSS for new videos.")
    parser.add_argument("--rss", default=cfg.get("rssUrl", ""), help="RSS URL (default from config)")
    parser.add_argument("--json", action="store_true", help="Emit new videos as JSON")
    parser.add_argument("--mark", action="store_true", help="Mark new videos as seen after reporting")
    parser.add_argument("--init", action="store_true", help="Force-mark the whole current feed as seen (0 new)")
    args = parser.parse_args(argv)

    if not args.rss:
        print("ERROR: rssUrl not set in config and --rss not given.", file=sys.stderr)
        return 1

    try:
        feed = fetch_feed(args.rss)
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: failed to fetch/parse RSS: {exc}", file=sys.stderr)
        return 1

    state = read_state(SEEN_FILE) or {}
    seen: set[str] = set(state.get("seen", []))
    fresh_init = not state.get("seen")

    feed_ids = [v["id"] for v in feed]

    if args.init or fresh_init:
        seen.update(feed_ids)
        write_state(SEEN_FILE, {"seen": sorted(seen), "updated_at": datetime.now().isoformat(timespec="seconds")})
        msg = {"initialized": True, "marked": len(feed_ids), "new": []}
        print(json.dumps(msg, ensure_ascii=False) if args.json else
              f"initialized seen-state with {len(feed_ids)} current videos; 0 new.")
        return 0

    new = [v for v in feed if v["id"] not in seen]

    if args.mark and new:
        seen.update(v["id"] for v in new)
        write_state(SEEN_FILE, {"seen": sorted(seen), "updated_at": datetime.now().isoformat(timespec="seconds")})

    if args.json:
        print(json.dumps({"new": new, "count": len(new)}, ensure_ascii=False))
    else:
        if not new:
            print("no new videos.")
        else:
            print(f"{len(new)} new video(s):")
            for v in new:
                print(f"  {v['published'][:10]}  {v['title']}  {v['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
