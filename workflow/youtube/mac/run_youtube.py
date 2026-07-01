"""run_youtube.ps1 + transcribe.ps1 이식 (macOS): 큐 → 페치 → 전사 배치.

- 큐(JSON) 또는 --url 목록을 받아 영상별로 fetch → transcribe.
- 멱등: transcript.txt 가 이미 있으면 스킵(캐시).
- 성공 판정 = 산출물 검증(transcript.txt 비어있지 않음 + transcribe.done).

Usage:
  python mac/run_youtube.py --queue workflow/youtube/state/new_queue_20260702.json
  python mac/run_youtube.py --queue ... --limit 2
  python mac/run_youtube.py --url https://youtu.be/ID1 https://youtu.be/ID2
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

YT_DIR = Path(__file__).resolve().parent.parent  # workflow/youtube
MAC = YT_DIR / "mac"
if str(YT_DIR) not in sys.path:
    sys.path.insert(0, str(YT_DIR))
from yt_lib import load_config, run_ytdlp  # noqa: E402


def urls_from_queue(p: Path) -> list[str]:
    q = json.loads(p.read_text(encoding="utf-8"))
    out = []
    for v in q.get("videos", []):
        u = v.get("url") or (f"https://youtu.be/{v['id']}" if v.get("id") else None)
        if u:
            out.append(u)
    return out


def resolve_id(url: str, js: str) -> str | None:
    r = run_ytdlp(["--skip-download", "--no-warnings", "--print", "%(id)s", url], js)
    lines = (r.stdout or "").strip().splitlines()
    return lines[0].strip() if lines else None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Batch fetch+transcribe (macOS/mlx).")
    ap.add_argument("--queue")
    ap.add_argument("--url", nargs="*")
    ap.add_argument("--root", default=str(YT_DIR.parents[1]))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--model", default=None)
    ap.add_argument("--language", default=None)
    a = ap.parse_args(argv)

    cfg = load_config()
    model = a.model or cfg.get("whisperModel", "mlx-community/whisper-large-v3-turbo")
    lang = a.language or cfg.get("whisperLanguage", "en")
    js = cfg.get("ytJsRuntime", "node")

    urls = urls_from_queue(Path(a.queue)) if a.queue else (a.url or [])
    if not urls:
        print("ERROR: --queue <json> 또는 --url <list> 필요", file=sys.stderr)
        return 1
    if a.limit and len(urls) > a.limit:
        urls = urls[: a.limit]
    print(f"queued {len(urls)} video(s)  model={model}  lang={lang}")

    results: list[tuple[str, str, str]] = []
    for i, u in enumerate(urls, 1):
        print(f"\n{'=' * 56}\n[{i}/{len(urls)}] {u}\n{'=' * 56}")
        vid = resolve_id(u, js)
        if not vid:
            results.append(("FAILED", u, "id 해석 실패"))
            continue
        ws = Path(a.root) / "workspaces" / f"yt-{vid}"

        # 멱등: 이미 전사됨?
        tr = ws / "transcript.txt"
        if tr.exists() and tr.stat().st_size > 0:
            print("[transcribe] transcript.txt 존재 → 캐시 스킵")
            results.append(("cached", str(ws), "-"))
            continue

        # 페치
        print("[fetch] downloading audio...")
        try:
            subprocess.run(
                [sys.executable, str(MAC / "yt_fetch.py"), "--url", u, "--root", a.root],
                check=True,
            )
        except subprocess.CalledProcessError as e:
            results.append(("FAILED", str(ws), f"fetch: {e}"))
            continue
        if not (ws / "audio.wav").exists():
            results.append(("FAILED", str(ws), "no audio.wav"))
            continue

        # 전사
        print(f"[transcribe] {model} / mlx ...")
        subprocess.run(
            [
                sys.executable, str(MAC / "transcribe_mlx.py"),
                "--workspace", str(ws), "--language", lang, "--model", model,
            ],
            check=False,  # 종료코드 무시 — 산출물이 진실
        )
        ok = (
            (ws / "transcript.txt").exists()
            and (ws / "transcript.txt").stat().st_size > 0
            and (ws / "transcribe.done").exists()
        )
        results.append(("transcribed" if ok else "FAILED", str(ws),
                        "-" if ok else "no transcript"))

    n_ok = sum(1 for s, *_ in results if s in ("transcribed", "cached"))
    print(f"\n{'=' * 56}\nSUMMARY  {n_ok}/{len(results)} ok\n{'=' * 56}")
    for st, ws, note in results:
        line = f"  {st:<12} {ws}"
        if note != "-":
            line += f"  ({note})"
        print(line)
    print("\nnext: transcript.txt + youtube.json → 학습노트 작성 → rebuild_index.py")
    return 0 if n_ok == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
