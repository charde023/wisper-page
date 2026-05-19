"""Transcribe Korean audio with faster-whisper. GPU first, CPU fallback."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

for _candidate in (
    Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cublas" / "bin",
    Path(sys.prefix) / "Lib" / "site-packages" / "nvidia" / "cudnn" / "bin",
):
    if _candidate.exists():
        os.add_dll_directory(str(_candidate))
        # PATH prepend covers child-process or non-interactive shells where
        # add_dll_directory alone has been observed to fail.
        os.environ["PATH"] = str(_candidate) + os.pathsep + os.environ.get("PATH", "")

from faster_whisper import WhisperModel

HERE = Path(__file__).parent
AUDIO = HERE / "audio.wav"
OUT_TXT = HERE / "transcript.txt"
OUT_SRT = HERE / "transcript.srt"
OUT_JSON = HERE / "segments.json"
PROGRESS = HERE / "progress.log"


def fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def log(msg: str) -> None:
    ts = time.strftime("%H:%M:%S")
    line = f"[{ts}] {msg}\n"
    sys.stdout.write(line)
    sys.stdout.flush()
    with PROGRESS.open("a", encoding="utf-8") as fp:
        fp.write(line)


def load_model() -> tuple[WhisperModel, str, str]:
    attempts = [
        ("large-v3", "cuda", "float16"),
        ("medium", "cuda", "float16"),
        ("medium", "cpu", "int8"),
        ("small", "cpu", "int8"),
    ]
    last_err: Exception | None = None
    for size, device, compute in attempts:
        try:
            log(f"loading model={size} device={device} compute={compute}")
            model = WhisperModel(size, device=device, compute_type=compute)
            log(f"model loaded: {size} on {device}")
            return model, size, device
        except Exception as exc:  # noqa: BLE001
            log(f"failed {size}/{device}: {exc}")
            last_err = exc
    raise RuntimeError(f"no whisper model could be loaded: {last_err}")


def main() -> int:
    PROGRESS.write_text("", encoding="utf-8")
    log(f"audio={AUDIO} exists={AUDIO.exists()}")
    model, size, device = load_model()

    log("starting transcription")
    started = time.time()
    segments_iter, info = model.transcribe(
        str(AUDIO),
        language="ko",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )
    log(
        f"detected language={info.language} prob={info.language_probability:.2f} "
        f"duration={info.duration:.1f}s"
    )

    segments: list[dict] = []
    last_log = time.time()
    with OUT_SRT.open("w", encoding="utf-8") as srt_fp:
        for idx, seg in enumerate(segments_iter, start=1):
            entry = {
                "id": idx,
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            }
            segments.append(entry)
            srt_fp.write(f"{idx}\n{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}\n{entry['text']}\n\n")
            if time.time() - last_log > 30:
                pct = (seg.end / info.duration) * 100 if info.duration else 0
                log(f"progress {pct:5.1f}% ({seg.end:.0f}s / {info.duration:.0f}s) segments={idx}")
                last_log = time.time()

    OUT_TXT.write_text(
        "\n".join(s["text"] for s in segments) + "\n", encoding="utf-8"
    )
    OUT_JSON.write_text(
        json.dumps(
            {"model": size, "device": device, "duration": info.duration, "segments": segments},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    elapsed = time.time() - started
    log(f"done in {elapsed:.1f}s, {len(segments)} segments")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
