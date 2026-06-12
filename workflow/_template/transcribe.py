"""Transcribe Korean audio with faster-whisper. GPU first, CPU fallback."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# DLL patch — MUST run before any faster_whisper import
# ---------------------------------------------------------------------------
import os
import sys
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

# ---------------------------------------------------------------------------
# stdlib-only imports (safe before faster_whisper is available)
# ---------------------------------------------------------------------------
import argparse
import json
import time


# ---------------------------------------------------------------------------
# lib bootstrap (resolves whether script is in workflow/, workflow/_template/,
# or a legacy workspaces/<ws>/ copy)
# ---------------------------------------------------------------------------
def _ensure_lib_on_path() -> None:
    here = Path(__file__).resolve()
    for parent in [here.parent, *here.parents]:
        for cand in (parent / "lib", parent / "workflow" / "lib"):
            if (cand / "frontmatter.py").exists():
                if str(cand) not in sys.path:
                    sys.path.insert(0, str(cand))
                return


_ensure_lib_on_path()


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def fmt_ts(seconds: float) -> str:
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", ",")


def _make_log(progress_path: Path):
    """Return a log() function bound to the given progress.log path."""

    def log(msg: str) -> None:
        ts = time.strftime("%H:%M:%S")
        line = f"[{ts}] {msg}\n"
        sys.stdout.write(line)
        sys.stdout.flush()
        with progress_path.open("a", encoding="utf-8") as fp:
            fp.write(line)

    return log


# ---------------------------------------------------------------------------
# model loading
# ---------------------------------------------------------------------------

def load_model(
    log,
    explicit_model: str | None = None,
    explicit_device: str | None = None,
):
    """Load a WhisperModel.

    If both explicit_model and explicit_device are provided, try only that
    combination and raise on failure.  Otherwise run the fallback waterfall.
    """
    # Heavy import lives here so --help works without faster_whisper installed.
    from faster_whisper import WhisperModel  # noqa: PLC0415

    if explicit_model and explicit_device:
        compute = "float16" if explicit_device == "cuda" else "int8"
        log(f"loading model={explicit_model} device={explicit_device} compute={compute} (explicit)")
        model = WhisperModel(explicit_model, device=explicit_device, compute_type=compute)
        log(f"model loaded: {explicit_model} on {explicit_device}")
        return model, explicit_model, explicit_device

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


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Transcribe audio with faster-whisper.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=None,
        help="Workspace directory (default: directory of this script)",
    )
    parser.add_argument(
        "--language",
        default="ko",
        help='Language code passed to Whisper (default: "ko"). Use "auto" to let Whisper detect.',
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Explicit Whisper model size (e.g. large-v3, medium, small). "
             "Must be paired with --device to skip the fallback waterfall.",
    )
    parser.add_argument(
        "--device",
        default=None,
        help='Explicit device (e.g. "cuda", "cpu"). '
             "Must be paired with --model to skip the fallback waterfall.",
    )

    args = parser.parse_args(argv)

    # Resolve workspace
    workspace: Path = (
        args.workspace.resolve()
        if args.workspace is not None
        else Path(__file__).resolve().parent
    )

    # Derived artifact paths
    AUDIO = workspace / "audio.wav"
    OUT_TXT = workspace / "transcript.txt"
    OUT_SRT = workspace / "transcript.srt"
    OUT_JSON = workspace / "segments.json"
    PROGRESS = workspace / "progress.log"

    log = _make_log(PROGRESS)

    # APPEND with a run-header separator (don't truncate history)
    with PROGRESS.open("a", encoding="utf-8") as fp:
        fp.write(
            f"\n{'='*60}\n"
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] transcribe.py started"
            f" workspace={workspace}\n"
            f"{'='*60}\n"
        )

    # Validate audio
    if not AUDIO.exists() or AUDIO.stat().st_size <= 1024:
        msg = (
            f"ERROR: audio file missing or too small (<= 1 KB): {AUDIO}\n"
            "Run extract_audio.ps1 first."
        )
        log(msg)
        print(msg, file=sys.stderr)
        return 1

    log(f"audio={AUDIO} size={AUDIO.stat().st_size} bytes")

    # Language handling: "auto" -> pass language=None to whisper
    whisper_language: str | None = None if args.language == "auto" else args.language

    # Determine explicit model/device (both must be provided together)
    explicit_model: str | None = args.model
    explicit_device: str | None = args.device
    if bool(explicit_model) != bool(explicit_device):
        print(
            "ERROR: --model and --device must be provided together to skip the waterfall.",
            file=sys.stderr,
        )
        return 1

    # Load model
    try:
        model, size, device = load_model(log, explicit_model, explicit_device)
    except Exception as exc:  # noqa: BLE001
        log(f"FATAL: {exc}")
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    log("starting transcription")
    started = time.time()
    segments_iter, info = model.transcribe(
        str(AUDIO),
        language=whisper_language,
        # Greedy decoding (beam_size=1) + condition_on_previous_text=False:
        # beam search on long talks with applause / overlapping speech was
        # observed to loop forever mid-file (~48%) and stall the whole run.
        # Greedy is deterministic, faster, and does not get stuck in that loop.
        beam_size=1,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
        condition_on_previous_text=False,
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
            srt_fp.write(
                f"{idx}\n{fmt_ts(seg.start)} --> {fmt_ts(seg.end)}\n{entry['text']}\n\n"
            )
            if time.time() - last_log > 30:
                pct = (seg.end / info.duration) * 100 if info.duration else 0
                log(
                    f"progress {pct:5.1f}% ({seg.end:.0f}s / {info.duration:.0f}s)"
                    f" segments={idx}"
                )
                last_log = time.time()

    OUT_TXT.write_text(
        "\n".join(s["text"] for s in segments) + "\n", encoding="utf-8"
    )
    OUT_JSON.write_text(
        json.dumps(
            {
                "model": size,
                "device": device,
                "duration": info.duration,
                "segments": segments,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    elapsed = time.time() - started
    n = len(segments)
    d = info.duration

    log(f"done in {elapsed:.1f}s, {n} segments")

    # Sentinel file
    sentinel = workspace / "transcribe.done"
    sentinel.write_text(
        f"segments={n} duration={d:.1f}s model={size} device={device}\n",
        encoding="utf-8",
    )

    # Final stdout marker (parseable by orchestrators)
    print(f"TRANSCRIBE_OK segments={n}")

    # Best-effort manifest stamp
    try:
        from manifest import set_stage  # noqa: PLC0415
        set_stage(workspace, "transcribed")
    except Exception:  # noqa: BLE001
        pass

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
