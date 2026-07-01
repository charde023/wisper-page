"""Transcribe audio with mlx-whisper (Apple MLX / Metal GPU).

_template/transcribe.py와 동일한 산출물 계약을 지킨다:
  transcript.txt · segments.json · transcript.srt · transcribe.done · stdout 'TRANSCRIBE_OK'
성공 판정은 종료코드가 아니라 산출물 검증(기존 .ps1 철학을 흡수).

Usage:
  python transcribe_mlx.py --workspace workspaces/yt-<id> --language en
  python transcribe_mlx.py --workspace <ws> --model mlx-community/whisper-large-v3
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path


def fmt_ts(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    x = s - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{x:06.3f}".replace(".", ",")


def log(ws: Path, msg: str) -> None:
    line = f"[{time.strftime('%H:%M:%S')}] {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    with (ws / "progress.log").open("a", encoding="utf-8") as f:
        f.write(line)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="mlx-whisper transcription (Apple Silicon)")
    ap.add_argument("--workspace", type=Path, required=True)
    ap.add_argument("--language", default="en", help='언어코드 또는 "auto"')
    ap.add_argument("--model", default="mlx-community/whisper-large-v3-turbo")
    a = ap.parse_args(argv)

    ws = a.workspace.resolve()
    if not ws.exists():
        print(f"ERROR: workspace 없음: {ws}", file=sys.stderr)
        return 1
    audio = ws / "audio.wav"
    if not audio.exists() or audio.stat().st_size <= 1024:
        print(f"ERROR: audio 없음/과소: {audio}", file=sys.stderr)
        return 1

    lang = None if a.language == "auto" else a.language
    (ws / "transcribe.done").unlink(missing_ok=True)  # 이전 run 센티넬 제거
    log(ws, f"start model={a.model} lang={a.language} audio={audio.stat().st_size}B")

    import mlx_whisper  # 무거운 임포트는 여기(--help는 가볍게)

    t0 = time.time()
    r = mlx_whisper.transcribe(
        str(audio),
        path_or_hf_repo=a.model,
        language=lang,
        word_timestamps=True,
        condition_on_previous_text=False,  # 긴 강연 루프 방지(현행과 동일 철학)
    )

    segs = [
        {"id": i + 1, "start": s["start"], "end": s["end"], "text": s["text"].strip()}
        for i, s in enumerate(r.get("segments", []))
    ]
    if not segs:
        print("ERROR: 세그먼트 0개 (무음/VAD 필요?)", file=sys.stderr)
        return 1
    duration = segs[-1]["end"]

    (ws / "transcript.txt").write_text(
        "\n".join(s["text"] for s in segs) + "\n", encoding="utf-8"
    )
    (ws / "segments.json").write_text(
        json.dumps(
            {"model": a.model, "device": "mlx", "duration": duration, "segments": segs},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    with (ws / "transcript.srt").open("w", encoding="utf-8") as f:
        for s in segs:
            f.write(f"{s['id']}\n{fmt_ts(s['start'])} --> {fmt_ts(s['end'])}\n{s['text']}\n\n")
    (ws / "transcribe.done").write_text(
        f"segments={len(segs)} duration={duration:.1f}s model={a.model} device=mlx\n",
        encoding="utf-8",
    )

    el = time.time() - t0
    rt = duration / el if el else 0
    log(ws, f"done {len(segs)} segs in {el:.1f}s ({rt:.1f}x realtime)")
    print(f"TRANSCRIBE_OK segments={len(segs)}")

    # manifest 스탬프(있으면) — best-effort
    try:
        sys.path.insert(0, str(ws.parents[1] / "workflow" / "lib"))
        from manifest import set_stage  # type: ignore  # noqa: PLC0415

        set_stage(ws, "transcribed")
    except Exception:  # noqa: BLE001
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
