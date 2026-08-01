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
from yt_lib import load_channels, load_config, run_ytdlp  # noqa: E402
sys.path.insert(0, str(MAC))
import caption_fetch  # noqa: E402


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


def fetch_meta_only(url: str, ws: Path, js: str) -> bool:
    """오디오 없이 메타만 받아 youtube.json을 만든다(자막 경로용).

    산출물 계약은 whisper 경로와 동일하게 유지한다 — 다운스트림(author_note·인덱스)이
    transcript_source를 몰라도 되게(CHARTER '전사 산출물 계약 고정')."""
    ws.mkdir(parents=True, exist_ok=True)
    (ws / ".source-url").write_text(url, encoding="utf-8")
    run_ytdlp(["--skip-download", "--write-info-json", "--no-warnings",
               "-o", str(ws / "audio.%(ext)s"), url], js)
    prov = YT_DIR / "extract_provenance.py"
    if prov.exists():
        subprocess.run([sys.executable, str(prov), "--workspace", str(ws)], check=False)
    return (ws / "youtube.json").exists()


def try_caption(url: str, ws: Path, ch, js: str) -> bool:
    """자막 경로 1회 시도. 성공하면 True(전사 스킵), 실패하면 False(Whisper 폴백)."""
    if not fetch_meta_only(url, ws, js):
        print("[caption] youtube.json 생성 실패 → Whisper 폴백", file=sys.stderr)
        return False
    return caption_fetch.fetch_caption(url, ws, ch, js) is not None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Batch fetch+transcribe (macOS/mlx).")
    ap.add_argument("--queue")
    ap.add_argument("--url", nargs="*")
    ap.add_argument("--root", default=str(YT_DIR.parents[1]))
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--channel", default=None, help="채널 key (자막 우선 여부를 결정)")
    ap.add_argument("--model", default=None)
    ap.add_argument("--language", default=None)
    a = ap.parse_args(argv)

    cfg = load_config()
    ch = None
    if a.channel:
        _, chans = load_channels()
        ch = next((c for c in chans if c.key == a.channel), None)
        if ch is None:
            print(f"ERROR: 채널 '{a.channel}' 을 설정에서 찾을 수 없다", file=sys.stderr)
            return 1
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

        # 자막 우선 채널: 오디오 없이 자막으로 끝낼 수 있으면 전사 자체를 건너뛴다
        if ch is not None and ch.transcript_source == "caption":
            if try_caption(u, ws, ch, js):
                results.append(("caption", str(ws), "-"))
                continue
            print("[transcribe] 자막 실패 → Whisper 폴백")

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

    n_ok = sum(1 for s, *_ in results if s in ("transcribed", "cached", "caption"))
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
