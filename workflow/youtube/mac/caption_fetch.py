"""YouTube 자막(VTT) → transcript.txt (기획서 §3-2).

영어 원어민 채널(YC·Sequoia)은 자막이 이미 있어 Whisper 전사를 건너뛴다.
자막이 없거나 부실하면 None을 돌려 호출자가 Whisper로 폴백하게 한다.

트랙 우선순위: 수동 en → 수동 en-* → 자동 en-orig → 자동 en (captionLangs 집합 안에서만)
품질 게이트: 단어수 >= 200, wpm >= 80(경계 포함). duration 미상이면 밀도 검사 생략.

Usage:
  python mac/caption_fetch.py --url <URL> --workspace <ws> [--langs en,en-orig]
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

YT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(YT_DIR))

from yt_lib import run_ytdlp  # noqa: E402

MIN_WORDS = 200
MIN_WPM = 80.0

TS_RE = re.compile(r"-->")
CUE_SETTING_RE = re.compile(r"^\s*(align|position|line|size|region):", re.I)
# WEBVTT 블록 뒤에 붙는 메타 헤더(yt-dlp 자동자막은 "Kind: captions"·"Language: en"을 낸다)
VTT_META_RE = re.compile(r"^(Kind|Language):", re.I)
TAG_TIME_RE = re.compile(r"<\d{2}:\d{2}:\d{2}[.,]\d{3}>")
TAG_C_RE = re.compile(r"</?c[^>]*>")
TAG_V_RE = re.compile(r"<v\s+([^>]+)>")
TAG_ANY_RE = re.compile(r"</?[a-zA-Z][^>]*>")
# "en-orig  English (Original)    vtt, srt, ttml, …" — 이름에 공백이 있어 첫 토큰 + 포맷 존재로 잡는다
LIST_LINE_RE = re.compile(r"^(\S+)\s+.*\b(?:vtt|srt|ttml)\b", re.I)


@dataclass(frozen=True)
class Track:
    """같은 언어의 수동·자동 트랙이 공존할 수 있어 lang만으로는 식별되지 않는다."""

    lang: str
    is_manual: bool


def list_tracks(url: str, js: str = "node") -> list[Track]:
    r = run_ytdlp(["--skip-download", "--no-warnings", "--list-subs", url], js)
    out: list[Track] = []
    manual_section = False
    for line in (r.stdout or "").splitlines():
        low = line.lower()
        if "available subtitles" in low:
            manual_section = True
            continue
        if "available automatic captions" in low:
            manual_section = False
            continue
        if low.startswith("language") or not line.strip():
            continue
        m = LIST_LINE_RE.match(line)
        if m:
            out.append(Track(m.group(1), manual_section))
    return out


def _rank(t: Track) -> int:
    if t.is_manual:
        if t.lang == "en":
            return 0
        if t.lang.startswith("en"):
            return 1
    else:
        if t.lang == "en-orig":
            return 2
        if t.lang == "en":
            return 3
        if t.lang.startswith("en"):
            return 4
    return 99


def pick_track(tracks: list[Track], prefer: list[str] | tuple[str, ...]) -> Track | None:
    """prefer 집합 안에서만 고른다. prefer가 비면 자막 경로를 끄는 것과 같다."""
    if not prefer:
        return None
    allowed = [t for t in tracks
               if t.lang in prefer or any(t.lang.startswith(f"{p}-") for p in prefer)]
    ranked = sorted((t for t in allowed if _rank(t) < 99), key=_rank)
    return ranked[0] if ranked else None


def download_vtt(url: str, track: Track, ws: Path, js: str = "node") -> Path | None:
    ws.mkdir(parents=True, exist_ok=True)
    flag = "--write-subs" if track.is_manual else "--write-auto-subs"
    r = run_ytdlp(["--skip-download", "--no-warnings", flag,
                   "--sub-langs", track.lang, "--sub-format", "vtt",
                   "-o", str(ws / "caption.%(ext)s"), url], js)
    if r.returncode != 0:
        print(f"[caption] yt-dlp 실패({r.returncode}): {(r.stderr or '')[-200:]}", file=sys.stderr)
    found = sorted(ws.glob("caption*.vtt"))
    return found[0] if found else None


def parse_vtt(path: Path) -> str:
    """롤업 자막의 반복 큐를 증분만 남겨 이어붙인다."""
    lines_out: list[str] = []
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.upper().startswith("WEBVTT") or line.startswith("NOTE"):
            continue
        if (TS_RE.search(line) or CUE_SETTING_RE.match(line)
                or VTT_META_RE.match(line) or line.isdigit()):
            continue
        line = TAG_TIME_RE.sub("", line)
        line = TAG_C_RE.sub("", line)
        m = TAG_V_RE.search(line)
        speaker = m.group(1).strip() if m else None
        line = TAG_V_RE.sub("", line)
        line = TAG_ANY_RE.sub("", line)
        line = html.unescape(line).strip()
        if not line:
            continue
        if speaker:
            line = f"{speaker}: {line}"

        if lines_out:
            prev = lines_out[-1]
            if line == prev:
                continue                      # 완전 중복
            if line.startswith(prev):         # 롤업 증분 — 확장분으로 교체
                lines_out[-1] = line
                continue
            if prev.startswith(line):         # 이전이 더 길다 = 되감김
                continue
        lines_out.append(line)
    return "\n".join(lines_out)


def quality_check(text: str, duration_sec: float | None) -> tuple[bool, str]:
    words = len(text.split())
    if words < MIN_WORDS:
        return False, "too_short"
    if not duration_sec or duration_sec <= 0:
        return True, "duration_unknown"       # 길이 미상을 이유로 버리지 않는다
    wpm = words / (duration_sec / 60.0)
    if wpm < MIN_WPM:
        return False, f"low_wpm:{int(wpm)}"
    return True, "ok"


def fetch_caption(url: str, ws: Path, ch, js: str = "node",
                  duration_sec: float | None = None) -> str | None:
    """성공하면 transcript.txt를 쓰고 본문을 돌려준다. 실패면 None(호출자가 Whisper 폴백)."""
    meta_p = ws / "youtube.json"
    meta = json.loads(meta_p.read_text(encoding="utf-8")) if meta_p.exists() else {}
    if duration_sec is None:
        duration_sec = meta.get("duration")

    def _record(source: str, lang: str | None, quality: str | None) -> None:
        meta.update(transcript_source=source, caption_lang=lang, caption_quality=quality)
        ws.mkdir(parents=True, exist_ok=True)
        meta_p.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

    track = pick_track(list_tracks(url, js), ch.caption_langs)
    if track is None:
        print("[caption] en 계열 트랙 없음 → Whisper 폴백")
        _record("whisper(fallback)", None, "no_track")
        return None

    vtt = download_vtt(url, track, ws, js)
    if vtt is None:
        print("[caption] VTT 다운로드 실패 → Whisper 폴백")
        _record("whisper(fallback)", track.lang, "download_failed")
        return None

    text = parse_vtt(vtt)
    ok, reason = quality_check(text, duration_sec)
    if not ok:
        print(f"[caption] 품질 미달({reason}) → Whisper 폴백")
        _record("whisper(fallback)", track.lang, reason)
        return None

    (ws / "transcript.txt").write_text(text + "\n", encoding="utf-8")
    (ws / "transcribe.done").write_text(f"caption:{track.lang}\n", encoding="utf-8")
    _record("caption", track.lang, reason)
    print(f"[caption] OK {len(text.split())} words "
          f"({'수동' if track.is_manual else '자동'} {track.lang}, {reason})")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--workspace", required=True)
    ap.add_argument("--langs", default="en,en-orig")
    ap.add_argument("--duration", type=float, default=None)
    a = ap.parse_args(argv)

    class _Ch:  # 단독 실행용 최소 채널
        caption_langs = tuple(x.strip() for x in a.langs.split(",") if x.strip())

    text = fetch_caption(a.url, Path(a.workspace), _Ch(), duration_sec=a.duration)
    return 0 if text else 1


if __name__ == "__main__":
    raise SystemExit(main())
