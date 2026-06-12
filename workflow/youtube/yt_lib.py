"""Shared helpers for the TechBridge-KR YouTube -> Obsidian pipeline.

Config merge order (later wins): DEFAULTS -> config.example.json -> config.json
(config.json is gitignored, machine-local overrides).

State files live in workflow/youtube/state/ (gitignored):
  channel_index.json   — scanned video metadata
  curated_queue.json   — selected videos to transcribe
  seen_videos.json     — RSS watcher state
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# Windows consoles default to cp949 here, which crashes on em-dash / CJK in prints.
# Force UTF-8 with replacement so scripts never die on a cosmetic print.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except Exception:  # noqa: BLE001
        pass

YT_DIR = Path(__file__).resolve().parent
STATE_DIR = YT_DIR / "state"

DEFAULTS: dict[str, Any] = {
    "channelUrl": "https://www.youtube.com/@TechBridge-KR",
    "channelId": "",
    "rssUrl": "",
    "vaultNoteDir": "",
    "whisperModel": "large-v3",
    "whisperDevice": "cuda",
    "whisperLanguage": "auto",
    "ytJsRuntime": "node",
    "titlePrefixStrip": "[한글자막]",
    "topicKeywords": [],
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_config() -> dict[str, Any]:
    cfg = dict(DEFAULTS)
    cfg.update(_load_json(YT_DIR / "config.example.json"))
    cfg.update(_load_json(YT_DIR / "config.json"))
    return cfg


def state_file(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / name


def read_state(name: str, default: Any = None) -> Any:
    path = STATE_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return default


def write_state(name: str, data: Any) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    path = STATE_DIR / name
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def ytdlp_path() -> str:
    exe = shutil.which("yt-dlp")
    if not exe:
        print("ERROR: yt-dlp not found on PATH.", file=sys.stderr)
        raise SystemExit(2)
    return exe


def run_ytdlp(args: list[str], js_runtime: str = "node", check: bool = False) -> subprocess.CompletedProcess:
    """Run yt-dlp with --js-runtimes prepended. Returns CompletedProcess (text)."""
    cmd = [ytdlp_path()]
    if js_runtime:
        cmd += ["--js-runtimes", js_runtime]
    cmd += args
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", check=check)


def strip_title_prefix(title: str, prefix: str) -> str:
    title = (title or "").strip()
    if prefix and title.startswith(prefix):
        title = title[len(prefix):].strip()
    return title
