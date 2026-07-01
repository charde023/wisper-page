"""raw 전사 → 문맥교정 transcript_clean.txt (코덱스 프록시 gpt-5.4-mini).

youtube.json의 제목·description·링크를 고유명사 힌트로 프롬프트에 주입해
ASR 오인식(예: Cloud→Claude, 인명·제품명)을 문맥으로 교정한다.

Usage:
  python mac/transcript_clean.py <workspace>
멱등: transcript_clean.txt 있으면 스킵(--force로 재생성).
긴 전사는 문단 단위 청크로 분할 호출 후 이어붙임.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm import MODEL_CLEAN, chat, healthy  # noqa: E402

SYS = (
    "You are an expert transcript editor for English tech-talk transcriptions produced by "
    "automatic speech recognition (ASR). Fix ASR errors: correct misheard proper nouns, "
    "product/company/person names, and 'Cloud'->'Claude' type substitutions using the HINTS. "
    "Fix sentence boundaries and remove verbal filler (um, uh, you know). Keep ALL substantive "
    "content and meaning — do not summarize or drop information. "
    "Output ONLY the cleaned English transcript text, no preamble."
)

# 한 청크당 대략 문자 수(토큰 여유). 초과 시 문단 경계로 분할.
CHUNK_CHARS = 12000


def _chunks(text: str, size: int) -> list[str]:
    if len(text) <= size:
        return [text]
    out, buf = [], []
    n = 0
    for para in text.split("\n"):
        if n + len(para) > size and buf:
            out.append("\n".join(buf))
            buf, n = [], 0
        buf.append(para)
        n += len(para) + 1
    if buf:
        out.append("\n".join(buf))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    w = Path(a.workspace)
    out_path = w / "transcript_clean.txt"
    if out_path.exists() and out_path.stat().st_size > 0 and not a.force:
        print(f"clean 존재 → 스킵 {out_path}")
        return 0

    raw = (w / "transcript.txt").read_text(encoding="utf-8")
    meta = json.loads((w / "youtube.json").read_text(encoding="utf-8"))
    hints = (
        f"Title: {meta.get('title')}\n"
        f"Channel/Speaker: {meta.get('provenance', {}).get('creator') or meta.get('uploader')}\n"
        f"Description (proper-noun source):\n{(meta.get('description') or '')[:2000]}"
    )

    if not healthy():
        print("ERROR: 코덱스 프록시(:18080) 응답 없음", file=sys.stderr)
        return 2

    parts = _chunks(raw, CHUNK_CHARS)
    cleaned = []
    for i, ch in enumerate(parts, 1):
        user = f"HINTS:\n{hints}\n\nTRANSCRIPT (part {i}/{len(parts)}):\n{ch}"
        cleaned.append(chat(MODEL_CLEAN, SYS, user).strip())
        print(f"  clean part {i}/{len(parts)} ({len(ch)} chars)")

    text = "\n\n".join(cleaned).strip() + "\n"
    out_path.write_text(text, encoding="utf-8")
    print(f"CLEAN_OK {len(text)} chars ({len(parts)} chunk) -> {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
