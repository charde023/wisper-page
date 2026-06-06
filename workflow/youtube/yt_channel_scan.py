"""Scan a YouTube channel's recent uploads and dump metadata to channel_index.json.

Uses the NON-flat /videos extraction so upload_date is real (flat-playlist returns
NA — confirmed yt-dlp bug). --break-on-reject stops early at the date cutoff since
the videos tab is newest-first.

Usage:
  python yt_channel_scan.py [CHANNEL_URL] --months 3
  python yt_channel_scan.py --after 20260306
  python yt_channel_scan.py --all          # whole channel (slow; full backfill)

Output: workflow/youtube/state/channel_index.json
  { "scanned_at": ISO, "channel": URL, "count": N, "videos": [ {id,title,upload_date,
    view_count,duration,channel,uploader,url}, ... ] }
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta

from yt_lib import load_config, run_ytdlp, write_state

# Compact per-video field set printed as one JSON object per line.
PRINT_TMPL = "%(.{id,title,upload_date,view_count,duration,channel,uploader,webpage_url})j"


def _cutoff_yyyymmdd(months: int, after: str | None) -> str:
    if after:
        return after
    return (datetime.now() - timedelta(days=months * 30)).strftime("%Y%m%d")


def scan(channel_url: str, months: int | None, after: str | None, scan_all: bool, js_runtime: str) -> list[dict]:
    videos_url = channel_url if channel_url.rstrip("/").endswith("/videos") else channel_url.rstrip("/") + "/videos"
    args = [videos_url, "--skip-download", "--ignore-errors", "--print", PRINT_TMPL]

    if not scan_all:
        cutoff = _cutoff_yyyymmdd(months or 3, after)
        # --dateafter bounds the OUTPUT; --break-match-filters stops enumeration early
        # once a too-old video is hit (videos tab is newest-first). --break-on-reject
        # was removed in recent yt-dlp; --break-match-filters is its replacement.
        args[1:1] = ["--dateafter", cutoff, "--break-match-filters", f"upload_date>={cutoff}"]
        print(f"cutoff = {cutoff}", file=sys.stderr)

    print(f"scanning {videos_url} ... (fetches each recent video's metadata; may take a few minutes)", file=sys.stderr)
    proc = run_ytdlp(args, js_runtime=js_runtime)

    videos: list[dict] = []
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line or not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        videos.append({
            "id": obj.get("id"),
            "title": obj.get("title"),
            "upload_date": obj.get("upload_date"),
            "view_count": obj.get("view_count"),
            "duration": obj.get("duration"),
            "channel": obj.get("channel"),
            "uploader": obj.get("uploader"),
            "url": obj.get("webpage_url") or (f"https://youtu.be/{obj.get('id')}" if obj.get("id") else None),
        })

    if proc.returncode != 0 and not videos:
        sys.stderr.write(proc.stderr or "")
        print(f"WARNING: yt-dlp exited {proc.returncode} with no parsed videos.", file=sys.stderr)
    return videos


def main(argv: list[str] | None = None) -> int:
    cfg = load_config()
    parser = argparse.ArgumentParser(description="Scan a YouTube channel's recent uploads.")
    parser.add_argument("channel", nargs="?", default=cfg["channelUrl"], help="Channel URL (default from config)")
    parser.add_argument("--months", type=int, default=3, help="Look back this many months (default 3)")
    parser.add_argument("--after", default=None, help="Explicit cutoff YYYYMMDD (overrides --months)")
    parser.add_argument("--all", dest="scan_all", action="store_true", help="Scan whole channel (no date filter)")
    args = parser.parse_args(argv)

    videos = scan(args.channel, args.months, args.after, args.scan_all, cfg.get("ytJsRuntime", "node"))
    # newest first (yt-dlp already returns newest-first, but be explicit)
    videos.sort(key=lambda v: (v.get("upload_date") or ""), reverse=True)

    payload = {
        "scanned_at": datetime.now().isoformat(timespec="seconds"),
        "channel": args.channel,
        "window": "all" if args.scan_all else (args.after or f"today-{args.months}months"),
        "count": len(videos),
        "videos": videos,
    }
    path = write_state("channel_index.json", payload)
    print(f"scanned {len(videos)} videos -> {path}")
    for v in videos[:10]:
        print(f"  {v.get('upload_date')}  views={v.get('view_count')}  {v.get('title')}")
    if len(videos) > 10:
        print(f"  ... and {len(videos) - 10} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
