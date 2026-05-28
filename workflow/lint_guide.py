"""Lint one or more guide.md files for structural and content correctness.

Usage:
    python workflow/lint_guide.py path/to/guide.md [path/to/other.md ...]

Exit codes:
    0 — all files passed (or were skipped)
    1 — one or more files failed

Checks performed:
    (1) All 6 required frontmatter keys present and non-empty.
    (2) "## 결론" / TL;DR section exists and contains >= 2 markdown tables
        before the next "## " heading.
    (3) Required sections appear in order: TL;DR (결론) → 강의는 어떤 내용이었나
        → ## 0. → numbered body (## 1. or higher).
    (4) No emoji characters outside fenced code blocks.
    (5) A "자주 막히는 곳" section exists somewhere.

Files without frontmatter are treated as transcribe-only and SKIPped.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

# On Windows the default stdout encoding may be cp949 which cannot represent
# all Unicode (emoji, Korean in error messages, etc.).  Reconfigure to UTF-8
# so output never crashes on surrogate/emoji characters.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# ---------------------------------------------------------------------------
# Shared frontmatter bootstrap (contract-mandated pattern)
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

try:
    from frontmatter import split_frontmatter  # type: ignore[import]
except ImportError:
    # Fallback hand-rolled parser (identical to existing workflow scripts)
    def split_frontmatter(text: str) -> tuple[dict, str]:  # type: ignore[misc]
        m = re.match(r"^---\n(.*?)\n---\n(.*)", text, re.DOTALL)
        if not m:
            return {}, text
        fm_text, body = m.group(1), m.group(2)
        meta: dict = {}
        for line in fm_text.splitlines():
            if ":" in line and not line.lstrip().startswith("#"):
                key, value = line.split(":", 1)
                v = value.strip().strip("'\"")
                meta[key.strip()] = v
        return meta, body


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REQUIRED_FRONTMATTER_KEYS = ("title", "eyebrow", "subtitle", "source", "description", "date")

# Unicode ranges to flag as emoji / decorative symbols:
#   U+1F300–U+1FAFF  — Misc symbols / emoji / supplemental
#   U+2600–U+27BF    — Misc symbols, Dingbats (includes ★ U+2605, ⚠ U+26A0)
#   U+2194–U+21FF    — Exotic/decorative arrows (excluding ←↑→↓ U+2190–U+2193
#                       which are commonly used as structural prose markers in
#                       Korean tech writing)
# Explicitly ALLOW: Korean/Hangul, CJK, middle-dot U+00B7 (·),
#   em-dash U+2014 (—), and the four basic arrows U+2190–U+2193 (←↑→↓).
_EMOJI_RANGES: list[tuple[int, int]] = [
    (0x1F300, 0x1FAFF),
    (0x2600, 0x27BF),
    (0x2194, 0x21FF),  # decorative arrows only (←↑→↓ excluded)
]

# Pattern that matches the opening fence of a code block (``` or ~~~)
_FENCE_OPEN = re.compile(r"^(`{3,}|~{3,})")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_fenced_blocks(lines: list[str]) -> list[str]:
    """Return lines with fenced code block content replaced by empty strings.

    Keeps the fence lines themselves so heading/structure scans still work,
    but removes the body lines so emoji checks don't fire inside code.
    """
    result: list[str] = []
    in_fence = False
    fence_char = ""
    for line in lines:
        m = _FENCE_OPEN.match(line)
        if not in_fence and m:
            in_fence = True
            fence_char = m.group(1)[0]
            result.append(line)
        elif in_fence and line.rstrip().startswith(fence_char * 3):
            in_fence = False
            result.append(line)
        elif in_fence:
            result.append("")  # blank out code content for emoji scan
        else:
            result.append(line)
    return result


def _is_emoji_char(ch: str) -> bool:
    cp = ord(ch)
    for lo, hi in _EMOJI_RANGES:
        if lo <= cp <= hi:
            return True
    return False


def _find_emoji(lines: list[str]) -> list[tuple[int, str]]:
    """Return list of (1-based line number, character) for each emoji found."""
    hits: list[tuple[int, str]] = []
    clean = _strip_fenced_blocks(lines)
    for lineno, line in enumerate(clean, start=1):
        for ch in line:
            if _is_emoji_char(ch):
                hits.append((lineno, ch))
    return hits


def _h2_sections(lines: list[str]) -> list[tuple[int, str]]:
    """Return list of (line_index, heading_text) for every ## heading."""
    result: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        m = re.match(r"^##\s+(.+)", line)
        if m:
            result.append((i, m.group(1).strip()))
    return result


def _count_tables_before_next_h2(lines: list[str], start_idx: int) -> int:
    """Count distinct markdown tables between start_idx and the next ## heading."""
    table_lines = 0
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if re.match(r"^##\s", line):
            break
        if "|" in line:
            table_lines += 1
    # A table needs a separator row (|---|) so count by separator rows
    # which appear exactly once per table.  Fall back to counting any line
    # that looks like a table separator: starts with | and contains ---.
    sep_count = 0
    for i in range(start_idx + 1, len(lines)):
        line = lines[i]
        if re.match(r"^##\s", line):
            break
        stripped = line.strip()
        if stripped.startswith("|") and re.search(r"-{2,}", stripped):
            sep_count += 1
    return sep_count


# ---------------------------------------------------------------------------
# Check functions — each returns a list of error strings (empty = passed)
# ---------------------------------------------------------------------------


def check_frontmatter_keys(meta: dict) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_FRONTMATTER_KEYS:
        if key not in meta:
            errors.append(f"frontmatter key '{key}' missing or empty")
            continue
        # PyYAML may parse 'date' as datetime.date; stringify before strip check
        value = str(meta[key]).strip()
        if not value:
            errors.append(f"frontmatter key '{key}' missing or empty")
    return errors


def check_tldr_section(lines: list[str]) -> list[str]:
    """Check ## 결론 exists and has >= 2 tables before the next ## heading."""
    errors: list[str] = []
    sections = _h2_sections(lines)
    tldr_idx: int | None = None
    for idx, heading in sections:
        if "결론" in heading or "TL;DR" in heading.upper() or "TLDR" in heading.upper():
            tldr_idx = idx
            break
    if tldr_idx is None:
        errors.append("missing '## 결론' (TL;DR) section")
        return errors
    table_count = _count_tables_before_next_h2(lines, tldr_idx)
    if table_count < 2:
        errors.append(
            f"'## 결론' section has {table_count} table(s); need >= 2 markdown tables"
        )
    return errors


def check_section_order(lines: list[str]) -> list[str]:
    """Check required sections appear in the expected order."""
    errors: list[str] = []
    sections = _h2_sections(lines)

    def find_first(pattern: str) -> int | None:
        """Return line index of first ## heading matching regex pattern, or None."""
        for idx, heading in sections:
            if re.search(pattern, heading):
                return idx
        return None

    # Also check ## 0. which may appear as a heading like "## 0. ..."
    def find_h2_numbered(num: int) -> int | None:
        for idx, _ in sections:
            line = lines[idx]
            if re.match(rf"^##\s+{num}\.", line):
                return idx
        return None

    def find_numbered_body() -> int | None:
        """First ## N. heading where N >= 1."""
        for idx, _ in sections:
            line = lines[idx]
            m = re.match(r"^##\s+(\d+)\.", line)
            if m and int(m.group(1)) >= 1:
                return idx
        return None

    tldr = find_first(r"결론|TL;?DR")
    intro = find_first(r"강의는 어떤 내용이었나")
    section0 = find_h2_numbered(0)
    body = find_numbered_body()

    required = [
        (tldr, "결론/TL;DR"),
        (intro, "강의는 어떤 내용이었나"),
        (section0, "## 0."),
        (body, "numbered body section (## 1. or higher)"),
    ]

    # Check presence
    for pos, name in required:
        if pos is None:
            errors.append(f"missing required section: {name}")

    # Check order (only for sections that exist)
    present = [(pos, name) for pos, name in required if pos is not None]
    for i in range(len(present) - 1):
        a_pos, a_name = present[i]
        b_pos, b_name = present[i + 1]
        if a_pos >= b_pos:
            errors.append(
                f"section order violation: '{a_name}' (line {a_pos + 1}) "
                f"must come before '{b_name}' (line {b_pos + 1})"
            )

    return errors


def check_no_emoji(lines: list[str]) -> list[str]:
    hits = _find_emoji(lines)
    if not hits:
        return []
    # Deduplicate by character, report first 5 occurrences to keep output readable
    errors: list[str] = []
    for lineno, ch in hits[:5]:
        name = unicodedata.name(ch, f"U+{ord(ch):04X}")
        errors.append(f"emoji/symbol '{ch}' ({name}) on line {lineno}")
    if len(hits) > 5:
        errors.append(f"... and {len(hits) - 5} more emoji/symbol occurrence(s)")
    return errors


def check_faq_section(lines: list[str]) -> list[str]:
    for _, heading in _h2_sections(lines):
        if "자주 막히는 곳" in heading:
            return []
    return ["missing '## 자주 막히는 곳' section"]


# ---------------------------------------------------------------------------
# Main linting logic
# ---------------------------------------------------------------------------

CheckResult = tuple[str, list[str]]  # (check_name, errors)


def lint_file(path: Path) -> tuple[str, list[CheckResult]]:
    """Lint a single guide.md.

    Returns (status, checks) where status is 'PASS', 'FAIL', or 'SKIP'.
    checks is a list of (check_name, errors) pairs.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return "FAIL", [("read", [str(exc)])]

    meta, body = split_frontmatter(text)

    # If no frontmatter at all → transcribe-only, skip
    if not meta:
        return "SKIP", []

    lines = text.splitlines()

    checks: list[CheckResult] = [
        ("frontmatter_keys", check_frontmatter_keys(meta)),
        ("tldr_section", check_tldr_section(lines)),
        ("section_order", check_section_order(lines)),
        ("no_emoji", check_no_emoji(lines)),
        ("faq_section", check_faq_section(lines)),
    ]

    has_errors = any(errs for _, errs in checks)
    status = "FAIL" if has_errors else "PASS"
    return status, checks


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print("usage: lint_guide.py <guide.md> [...]", file=sys.stderr)
        return 2

    paths = [Path(a) for a in args]
    overall_pass = True

    for path in paths:
        status, checks = lint_file(path)

        if status == "SKIP":
            print(f"SKIP  {path}  (no frontmatter — transcribe-only file)")
            continue

        if status == "PASS":
            print(f"PASS  {path}")
        else:
            overall_pass = False
            print(f"FAIL  {path}")
            for check_name, errors in checks:
                for err in errors:
                    print(f"      [{check_name}] {err}")

    return 0 if overall_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
