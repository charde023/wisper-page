"""
workflow/lib/config.py
Provides load_config() which merges DEFAULTS -> config.example.json -> config.json.
Base dir is the workflow/ directory (parent of this lib/ directory).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Canonical defaults (used when keys are absent from both JSON files)
DEFAULTS: dict[str, Any] = {
    "pageRepoPath": "",
    "pageBaseUrl": "https://charde023.github.io/page",
    "siteEyebrow": "지피터스 22기 · 끌림 영상 스터디",
    "siteTitle": "스터디 가이드 모음",
    "siteSubtitle": "라이브 강의 녹화본을 보고서 형태로 정리한 모음입니다.",
    "siteFooter": "charde023 · 자동 생성 인덱스",
    "defaultLanguage": "ko",
}

# workflow/ dir = parent of this file's parent (lib/ -> workflow/)
_WORKFLOW_DIR = Path(__file__).resolve().parent.parent


def _load_json(path: Path) -> dict[str, Any]:
    """Return parsed JSON dict, or {} if file does not exist or is invalid."""
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def load_config() -> dict[str, Any]:
    """
    Return merged config dict.

    Merge order (later values win):
      1. DEFAULTS
      2. workflow/config.example.json
      3. workflow/config.json  (gitignored; user-local overrides)
    """
    result: dict[str, Any] = dict(DEFAULTS)
    result.update(_load_json(_WORKFLOW_DIR / "config.example.json"))
    result.update(_load_json(_WORKFLOW_DIR / "config.json"))
    return result
