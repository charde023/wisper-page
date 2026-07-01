"""yt_fetch.ps1 이식 (macOS): URL → workspaces/yt-<id>/audio.wav(16k mono) + youtube.json.

yt_lib의 헬퍼(load_config·run_ytdlp·ytdlp_path)를 재사용한다.

Usage:
  python mac/yt_fetch.py --url "https://youtu.be/VIDEO_ID"
  python mac/yt_fetch.py --url "..." --root /Users/charde023/workspace/wisper-page --force
마지막 줄에 워크스페이스 경로를 출력(오케스트레이터가 캡처).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

YT_DIR = Path(__file__).resolve().parent.parent  # workflow/youtube
if str(YT_DIR) not in sys.path:
    sys.path.insert(0, str(YT_DIR))
from yt_lib import load_config, run_ytdlp, ytdlp_path  # noqa: E402


def resolve_id(url: str, js: str) -> str | None:
    r = run_ytdlp(["--skip-download", "--no-warnings", "--print", "%(id)s", url], js)
    lines = (r.stdout or "").strip().splitlines()
    return lines[0].strip() if lines else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fetch YouTube audio into a workspace (macOS).")
    ap.add_argument("--url", required=True)
    ap.add_argument("--root", default=str(YT_DIR.parents[1]), help="프로젝트 루트")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    cfg = load_config()
    js = cfg.get("ytJsRuntime", "node")

    vid = resolve_id(a.url, js)
    if not vid:
        print(f"ERROR: id 해석 실패: {a.url}", file=sys.stderr)
        return 1
    print(f"video id : {vid}")

    ws = Path(a.root) / "workspaces" / f"yt-{vid}"
    ws.mkdir(parents=True, exist_ok=True)
    (ws / ".source-url").write_text(a.url, encoding="utf-8")
    audio = ws / "audio.wav"

    if audio.exists() and audio.stat().st_size > 1024 and not a.force:
        print(f"audio.wav 존재 → 스킵 (use --force)")
    else:
        print("downloading audio (16kHz mono wav)...")
        subprocess.run(
            [
                ytdlp_path(), "--js-runtimes", js,
                "-x", "--audio-format", "wav",
                "--postprocessor-args", "-ar 16000 -ac 1",
                "--write-info-json", "--no-warnings",
                "-o", str(ws / "audio.%(ext)s"), a.url,
            ],
            check=True,
        )
        if not audio.exists() or audio.stat().st_size <= 1024:
            print(
                "ERROR: audio.wav 미생성/과소 "
                "(throttle 시: yt-dlp --remote-components ejs:github ...)",
                file=sys.stderr,
            )
            return 1
    print(f"audio ok : {round(audio.stat().st_size / 1_048_576, 1)} MB")

    # youtube.json (메타 + 프로비넌스)
    prov = YT_DIR / "extract_provenance.py"
    if prov.exists():
        print("extracting metadata + provenance...")
        subprocess.run([sys.executable, str(prov), "--workspace", str(ws)], check=False)
    else:
        print("WARN: extract_provenance.py 없음 — youtube.json 생략", file=sys.stderr)

    print(str(ws))  # 마지막 줄 = 워크스페이스 경로
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
