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
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
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


CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
KEY_RE = re.compile(r"^[a-z0-9_-]{2,20}$")
RSS_TMPL = "https://www.youtube.com/feeds/videos.xml?channel_id={}"


@dataclass(frozen=True)
class Channel:
    """감시·전사·노트화 단위. 설정 1항목 = 채널 1개."""

    key: str
    name: str
    channel_id: str
    note_dir: str
    transcript_source: str = "whisper"        # "caption" | "whisper"
    caption_langs: tuple[str, ...] = ("en", "en-orig")
    whisper_language: str = "en"
    title_prefix_strip: str = ""
    keyword_set: str = "ai"
    min_score: float = 1.0
    min_duration_min: int = 0
    daily_max: int = 2
    enabled: bool = True

    @property
    def rss_url(self) -> str:
        return RSS_TMPL.format(self.channel_id)

    def note_path(self, vault_root: Path) -> Path:
        return Path(vault_root) / self.note_dir


def load_keywords(keyword_set: str) -> list[str]:
    """"ai+startup" → 두 세트 합집합(소문자·중복제거·정렬). 미지원 키는 ValueError."""
    data = _load_json(YT_DIR / "keywords.json")
    out: set[str] = set()
    for part in (keyword_set or "").split("+"):
        part = part.strip()
        if not part:
            continue
        if part not in data:
            raise ValueError(
                f"keywordSet '{part}' 가 keywords.json에 없다 "
                f"(있는 키: {sorted(data)}). 빈 세트로 떨어지면 전부 스킵된다.")
        out |= {str(k).lower() for k in data[part]}
    return sorted(out)


def _channel_from_raw(raw: dict[str, Any]) -> Channel:
    def req(field: str) -> str:
        val = str(raw.get(field) or "").strip()
        if not val:
            raise ValueError(f"채널 필수 필드 누락: {field} (설정: {raw!r})")
        return val

    key, name, cid = req("key"), req("name"), req("channelId")
    if not KEY_RE.match(key):
        raise ValueError(f"key '{key}' 형식 위반 (^[a-z0-9_-]{{2,20}}$)")
    if not CHANNEL_ID_RE.match(cid):
        raise ValueError(f"channelId '{cid}' 형식 위반 (^UC + 22자)")

    note_dir = str(raw.get("noteDir") or name).strip()
    if note_dir.startswith("/") or ".." in Path(note_dir).parts or "/" in note_dir:
        raise ValueError(f"noteDir '{note_dir}' 는 vaultRoot 하위 단일 폴더명이어야 한다")

    src = str(raw.get("transcriptSource") or "whisper")
    if src not in ("caption", "whisper"):
        raise ValueError(f"transcriptSource '{src}' 미지원 (caption|whisper)")

    daily_max = int(raw.get("dailyMax", 2))
    if daily_max < 1:
        raise ValueError(f"dailyMax 는 1 이상이어야 한다 (받음: {daily_max})")
    min_score = float(raw.get("minScore", 1.0))
    if min_score < 0:
        raise ValueError(f"minScore 는 0 이상이어야 한다 (받음: {min_score})")
    min_dur = int(raw.get("minDurationMin", 0))
    if min_dur < 0:
        raise ValueError(f"minDurationMin 는 0 이상이어야 한다 (받음: {min_dur})")

    keyword_set = str(raw.get("keywordSet") or "ai")
    load_keywords(keyword_set)  # 미지원 키를 여기서 즉시 터뜨린다(조용한 빈 세트 금지)

    langs = raw.get("captionLangs")
    caption_langs = tuple(str(x) for x in langs) if isinstance(langs, list) else ("en", "en-orig")

    return Channel(
        key=key, name=name, channel_id=cid, note_dir=note_dir,
        transcript_source=src, caption_langs=caption_langs,
        whisper_language=str(raw.get("whisperLanguage") or "en"),
        title_prefix_strip=str(raw.get("titlePrefixStrip") or ""),
        keyword_set=keyword_set, min_score=min_score, min_duration_min=min_dur,
        daily_max=daily_max, enabled=bool(raw.get("enabled", True)),
    )


def _legacy_channel(cfg: dict[str, Any]) -> tuple[Path, list[Channel]]:
    """구 평면 설정(vaultNoteDir·channelId·topicKeywords) → 채널 1개로 변환."""
    note_dir_abs = Path(str(cfg["vaultNoteDir"])).expanduser()
    return note_dir_abs.parent, [Channel(
        key="techbridge",
        name=cfg.get("channelName") or note_dir_abs.name,
        channel_id=str(cfg.get("channelId") or ""),
        note_dir=note_dir_abs.name,
        transcript_source="whisper",
        whisper_language=str(cfg.get("whisperLanguage") or "en"),
        title_prefix_strip=str(cfg.get("titlePrefixStrip") or ""),
        keyword_set="ai", daily_max=3,
    )]


def load_channels() -> tuple[Path, list[Channel]]:
    """(vaultRoot, enabled 채널 목록). 구·신 설정 우선순위는 기획서 §3-1 계약."""
    cfg = load_config()
    raw_channels = cfg.get("channels")

    if not isinstance(raw_channels, list):
        if cfg.get("vaultNoteDir"):
            return _legacy_channel(cfg)
        raise ValueError(
            "설정이 비어 있다: config.json 에 channels[] 도, 구 vaultNoteDir 도 없다. "
            "볼트 위치를 추측하지 않는다.")

    if cfg.get("vaultNoteDir") or cfg.get("rssUrl") or cfg.get("topicKeywords"):
        print("[config] channels[] 가 있으므로 구 평면 키(vaultNoteDir·rssUrl·topicKeywords)는 무시한다.")

    vault_root = str(cfg.get("vaultRoot") or "").strip()
    if not vault_root:
        raise ValueError("channels[] 를 쓰면 최상위 vaultRoot 가 필수다.")
    root = Path(vault_root).expanduser()
    if not root.is_absolute():
        raise ValueError(f"vaultRoot 는 절대경로여야 한다 (받음: {vault_root})")

    channels = [_channel_from_raw(c) for c in raw_channels]
    for field, getter in (("key", lambda c: c.key), ("noteDir", lambda c: c.note_dir)):
        seen_vals: set[str] = set()
        for ch in channels:
            val = getter(ch)
            if val in seen_vals:
                raise ValueError(f"{field} 중복: '{val}' — 상태·노트가 섞인다")
            seen_vals.add(val)

    by_cid: set[str] = set()
    for ch in channels:
        if ch.channel_id in by_cid:
            print(f"[config] channelId 중복 무시: {ch.channel_id} ({ch.key})")
        by_cid.add(ch.channel_id)

    active = [c for c in channels if c.enabled]
    if not active:
        print("[config] 활성 채널이 0개다 — 감시할 채널 없음(정상 종료 대상).")
    return root, active


def state_name(base: str, key: str) -> str:
    """("seen","yc") → "seen_yc.json" — 채널별 상태 파일명 규칙(단일 출처)."""
    return f"{base}_{key}.json"


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
    import re as _re

    title = (title or "").strip()
    if prefix and title.startswith(prefix):
        title = title[len(prefix):].strip()
    # 일반화: 남은 선두 [..자막] 브래킷([한글자막]·[한영자막] 등)도 제거
    title = _re.sub(r"^\[[^\]]*자막\]\s*", "", title).strip()
    return title
