"""Manage per-workspace pipeline.json state.

pipeline.json schema:
  {
    "video": "<abs>",
    "created": "<ISO sec>",
    "language": "ko",
    "mode": "lecture|transcribe-only",
    "slug": null,
    "stages": {
      "audio": null,
      "transcribed": null,
      "cleaned": null,
      "guide": null,
      "html": null,
      "staged": null,
      "deployed": null
    }
  }

CLI:
  python manifest.py <workspace> init --video <abs> [--language ko] [--mode lecture] [--slug <s>]
  python manifest.py <workspace> set <stage>
  python manifest.py <workspace> show

Functions:
  init_manifest(ws, video, language, mode, slug)
  set_stage(ws, stage)
  read_manifest(ws) -> dict
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

PIPELINE_FILE = "pipeline.json"

ALL_STAGES = ("audio", "transcribed", "cleaned", "guide", "html", "staged", "deployed")


def _pipeline_path(ws: Path) -> Path:
    return ws / PIPELINE_FILE


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _default_manifest(video: str, language: str, mode: str, slug: str | None) -> dict:
    return {
        "video": video,
        "created": _now(),
        "language": language,
        "mode": mode,
        "slug": slug,
        "stages": {stage: None for stage in ALL_STAGES},
    }


def read_manifest(ws: Path | str) -> dict:
    """Read and return the pipeline.json dict. Raises FileNotFoundError if absent."""
    ws = Path(ws).resolve()
    return json.loads(_pipeline_path(ws).read_text(encoding="utf-8"))


def init_manifest(
    ws: Path | str,
    video: str,
    language: str = "ko",
    mode: str = "lecture",
    slug: str | None = None,
) -> dict:
    """Initialise pipeline.json in workspace directory.

    Idempotent: if pipeline.json already exists, existing stage timestamps are
    preserved.  Top-level fields (video, language, mode, slug) are only written
    when creating fresh — they are NOT overwritten on subsequent calls.
    """
    ws = Path(ws).resolve()
    ws.mkdir(parents=True, exist_ok=True)
    path = _pipeline_path(ws)

    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        # Ensure stages block has all expected keys (forward-compat)
        stages = existing.setdefault("stages", {})
        for stage in ALL_STAGES:
            stages.setdefault(stage, None)
        path.write_text(json.dumps(existing, ensure_ascii=False, indent=2), encoding="utf-8")
        return existing

    manifest = _default_manifest(video, language, mode, slug)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def set_stage(ws: Path | str, stage: str) -> None:
    """Stamp stage=now in pipeline.json.  Best-effort: swallows all errors."""
    try:
        ws = Path(ws).resolve()
        path = _pipeline_path(ws)

        if path.exists():
            manifest = json.loads(path.read_text(encoding="utf-8"))
        else:
            # Create a minimal manifest so this never crashes the caller
            manifest = {
                "video": "",
                "created": _now(),
                "language": "ko",
                "mode": "lecture",
                "slug": None,
                "stages": {s: None for s in ALL_STAGES},
            }

        manifest.setdefault("stages", {})
        manifest["stages"][stage] = _now()

        # Ensure all stage keys exist
        for s in ALL_STAGES:
            manifest["stages"].setdefault(s, None)

        path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass  # Never crash the caller


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _cmd_init(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    manifest = init_manifest(
        ws,
        video=args.video,
        language=args.language,
        mode=args.mode,
        slug=args.slug,
    )
    print(f"pipeline.json initialised at {ws / PIPELINE_FILE}")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return 0


def _cmd_set(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    set_stage(ws, args.stage)
    print(f"stage '{args.stage}' stamped")
    return 0


def _cmd_show(args: argparse.Namespace) -> int:
    ws = Path(args.workspace).resolve()
    try:
        manifest = read_manifest(ws)
        print(json.dumps(manifest, ensure_ascii=False, indent=2))
    except FileNotFoundError:
        print(f"no pipeline.json found in {ws}", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Manage per-workspace pipeline.json state.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("workspace", help="Workspace directory path")
    sub = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = sub.add_parser("init", help="Initialise pipeline.json (idempotent)")
    p_init.add_argument("--video", required=True, help="Absolute path to source video")
    p_init.add_argument("--language", default="ko", help="Language code (default: ko)")
    p_init.add_argument(
        "--mode",
        default="lecture",
        choices=["lecture", "transcribe-only"],
        help="Processing mode",
    )
    p_init.add_argument("--slug", default=None, help="URL slug for the guide page")

    # set
    p_set = sub.add_parser("set", help="Stamp a stage timestamp")
    p_set.add_argument("stage", choices=list(ALL_STAGES), help="Stage name to stamp")

    # show
    sub.add_parser("show", help="Print pipeline.json contents")

    args = parser.parse_args(argv)

    if args.command == "init":
        return _cmd_init(args)
    if args.command == "set":
        return _cmd_set(args)
    if args.command == "show":
        return _cmd_show(args)

    parser.print_help()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
