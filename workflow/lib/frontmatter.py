"""
frontmatter.py — YAML frontmatter parser for wisper-page guides.

Public API:
    split_frontmatter(text: str) -> tuple[dict, str]

Returns (meta_dict, body_text).  body_text has leading blank lines stripped.
Returns ({}, text) when no valid '---' frontmatter fence is found.

Strategy:
  1. Try PyYAML (yaml.safe_load) when available — handles complex values cleanly.
  2. Fall back to a hand-rolled parser that handles:
     - Colons in values  (split on FIRST colon only)
     - Values wrapped in single or double quotes (outer quotes stripped)
     - Lines starting with '#' (comments, ignored)
     - Blank lines inside the fence (ignored)
"""

from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Hand-rolled fallback parser
# ---------------------------------------------------------------------------

def _parse_frontmatter_manual(fm_text: str) -> dict[str, Any]:
    """Parse a YAML-like frontmatter block without PyYAML."""
    result: dict[str, Any] = {}
    for raw_line in fm_text.splitlines():
        line = raw_line.strip()
        # Skip blank lines and comment lines
        if not line or line.startswith("#"):
            continue
        # Split on the FIRST colon only
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if not key:
            continue
        # Strip surrounding single or double quotes from the value
        if len(value) >= 2 and (
            (value[0] == '"' and value[-1] == '"')
            or (value[0] == "'" and value[-1] == "'")
        ):
            value = value[1:-1]
        result[key] = value
    return result


# ---------------------------------------------------------------------------
# Public function
# ---------------------------------------------------------------------------

def split_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Split *text* into (frontmatter_dict, body).

    Expects the document to begin with a ``---`` fence.  If the opening fence
    is absent (or there is no closing ``---``), returns ``({}, text)`` so
    callers can treat the whole text as body.

    The body returned has its leading blank lines stripped.
    """
    if not text.lstrip("﻿").startswith("---"):
        return {}, text

    # Remove optional BOM, then strip the opening '---' line
    stripped = text.lstrip("﻿")
    # Must start with '---' optionally followed by spaces, then a newline
    first_newline = stripped.find("\n")
    if first_newline == -1:
        return {}, text
    opening_line = stripped[:first_newline].rstrip()
    if opening_line != "---":
        return {}, text

    rest = stripped[first_newline + 1:]  # everything after the opening fence

    # Find the closing '---' fence
    # It must appear as a line that is exactly '---' (possibly with trailing spaces)
    close_match = re.search(r"^---\s*$", rest, re.MULTILINE)
    if close_match is None:
        return {}, text

    fm_text = rest[: close_match.start()]
    body = rest[close_match.end():]
    # Strip leading newline(s) from body
    body = body.lstrip("\n")

    # Try PyYAML first
    try:
        import yaml  # type: ignore[import]
        meta = yaml.safe_load(fm_text)
        if not isinstance(meta, dict):
            meta = {}
    except Exception:
        meta = _parse_frontmatter_manual(fm_text)

    # Coerce every value to a plain string. Downstream consumers (make_html,
    # stage_publish, update_pages_index) all assume string values; PyYAML would
    # otherwise hand back typed objects (e.g. `date:` -> datetime.date, `toc:`
    # -> bool), which break string ops and mixed-type sorts.
    return {k: _stringify(v) for k, v in meta.items()}, body


def _stringify(value: Any) -> str:
    """Render a parsed frontmatter value as the string a guide author wrote."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "true" if value else "false"
    if hasattr(value, "isoformat"):  # date / datetime
        return value.isoformat()
    return str(value)


# ---------------------------------------------------------------------------
# Quick self-test when run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    _sample = """\
---
title: 테스트 제목
date: 2026-05-29
description: "콜론: 포함된 설명"
eyebrow: '따옴표 테스트'
# 이 줄은 주석
source: some-file.mp4
---

본문 내용이 여기 옵니다.
두 번째 줄.
"""
    _meta, _body = split_frontmatter(_sample)
    assert _meta.get("title") == "테스트 제목", f"title mismatch: {_meta}"
    assert _meta.get("date") == "2026-05-29", f"date must be a string: {_meta!r}"
    assert "콜론" in _meta.get("description", ""), f"colon-in-value failed: {_meta}"
    assert _meta.get("eyebrow") == "따옴표 테스트", f"quote strip failed: {_meta}"
    assert "source" in _meta, "source key missing"
    assert "본문" in _body, f"body missing: {_body!r}"

    # No frontmatter
    _m2, _b2 = split_frontmatter("그냥 텍스트")
    assert _m2 == {}, f"expected empty dict, got {_m2}"
    assert _b2 == "그냥 텍스트"

    print("All assertions passed.")
    print("meta:", _meta)
    print("body preview:", _body[:40])
