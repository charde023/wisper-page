"""transcript_clean + youtube.json + note_template → 한국어 학습노트 MD (코덱스 gpt-5.5).

수동 소넷 작성 단계를 대체한다. 볼트 학습노트 규칙을 프롬프트에 고정.

Usage:
  python mac/author_note.py <workspace>            # 볼트에 저장
  python mac/author_note.py <workspace> --out X.md # 지정 경로(검증용)
멱등: 대상 노트가 이미 있으면 스킵(--force).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # workflow/youtube
sys.path.insert(0, str(Path(__file__).resolve().parent))         # mac
from yt_lib import load_config  # noqa: E402
from llm import MODEL_NOTE, chat, healthy  # noqa: E402

RULES = (
    "당신은 차드(비개발자·이커머스/물류 사장, AI·코딩 학습 중)를 위한 한국어 학습노트 작성자다. "
    "제공한 note_template.md 골격을 그대로 채운다.\n"
    "규칙(엄수):\n"
    "- 영어 교정 전사를 한국어로 번역·요약·구조화한다. 원문 나열 금지, 이해되게 재구성.\n"
    "- 이모지 금지. '==하이라이트==' 금지. 강조는 **볼드**와 "
    '<span style="color:#ef6c00">…</span> 두 종류만.\n'
    "- 핵심 영어 용어는 한국어(영어) 괄호 병기. 음성인식 의심은 [?원문].\n"
    "- frontmatter를 메타에서 채운다: title·channel(TechBridge-KR)·original_creator·"
    "original_affiliation·video_id·url·upload_date(YYYY-MM-DD)·duration_min·"
    "status(정리완료)·created(2026-07-02)·summary(목차 노출 한 줄)·tags·aliases.\n"
    "- 섹션: 한줄요약 콜아웃 → 영상정보 콜아웃 → 핵심 학습 포인트(표) → 내가 모를 만한 것 → "
    "화자의 디테일(수치·구체값) → 한눈에보기(표) → 섹션별 본문(상세) → 종합 체크리스트 → "
    "출처 콜아웃 → 접기식 교정 전사(> [!note]- ...).\n"
    "출력은 완성된 마크다운 본문만. 코드펜스(```)로 감싸지 말 것."
)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--out", default=None, help="지정 저장경로(검증용). 생략 시 볼트")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    w = Path(a.workspace)
    clean_p = w / "transcript_clean.txt"
    src = clean_p if clean_p.exists() else (w / "transcript.txt")
    clean = src.read_text(encoding="utf-8")
    meta = json.loads((w / "youtube.json").read_text(encoding="utf-8"))
    tmpl = (Path(__file__).resolve().parent.parent / "note_template.md").read_text(encoding="utf-8")

    if a.out:
        dest = Path(a.out)
    else:
        title = re.sub(r'[\\/:*?"<>|]', "-", meta.get("title") or meta["id"]).strip()
        dest = Path(load_config()["vaultNoteDir"]) / f"{title}.md"
    if dest.exists() and dest.stat().st_size > 0 and not a.force:
        print(f"노트 존재 → 스킵 {dest}")
        return 0

    if not healthy():
        print("ERROR: 코덱스 프록시(:18080) 응답 없음", file=sys.stderr)
        return 2

    user = (
        f"[note_template.md]\n{tmpl}\n\n"
        f"[메타(youtube.json)]\n{json.dumps(meta, ensure_ascii=False)[:3000]}\n\n"
        f"[교정 전사]\n{clean}"
    )
    md = chat(MODEL_NOTE, RULES, user).strip()
    # 혹시 코드펜스로 감싸 왔으면 벗김
    if md.startswith("```"):
        md = re.sub(r"^```[a-zA-Z]*\n", "", md)
        md = re.sub(r"\n```\s*$", "", md)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md + "\n", encoding="utf-8")
    print(f"NOTE_OK {len(md)} chars -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
