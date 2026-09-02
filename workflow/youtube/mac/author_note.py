"""transcript_clean + youtube.json + note_template → 한국어 학습노트 MD (코덱스 gpt-5.5).

수동 소넷 작성 단계를 대체한다. 볼트 학습노트 규칙을 프롬프트에 고정.
★ v2(2026-09-03): 파인만 + 4렌즈 스키마. 설계 = 볼트 내CLAUDE-설정/2026-09-03_학습노트-v2-파인만렌즈-설계서.md

Usage:
  python mac/author_note.py <workspace>            # 볼트에 저장
  python mac/author_note.py <workspace> --out X.md # 지정 경로(검증용)
  python mac/author_note.py <workspace> --channel yc --variant v2   # 같은 영상의 대조본(파일명·제목·slug에 접미)
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
from yt_lib import load_channels, load_config  # noqa: E402
from llm import MODEL_NOTE, chat, healthy  # noqa: E402
from frontmatter_contract import FM_RE, normalize_markdown, validate_markdown  # noqa: E402

RULES_TMPL = (
    "당신은 차드를 위한 한국어 학습노트 작성자다. 독자는 차드 한 명이며 네 역할을 동시에 가진다: "
    "교육자(강의 경험), 사업가(에이폼: 이커머스·물류 운영), 마케터, AI·소프트웨어 학습자(비개발자 출신, 클로드코드·코덱스로 자동화 운영 중). "
    "제공한 note_template.md 골격을 그대로 채운다.\n"
    "규칙(엄수):\n"
    "- 교정 전사를 한국어로 번역·재구성한다. 원문 나열 금지.\n"
    "- 본문 순서는 학습 순서다: 카드 → 쉬운 말 → 정확한 용어 → 숫자 → 막히는 곳 → 4렌즈 통찰 → 파인만 과제. "
    "영상 발화 순서는 접기(Z2) '섹션별 상세'에서만 따른다.\n"
    "- [카드] 질문은 의문문 1개. 답은 1문장. 통찰은 요약이 아니라 '화자가 직접 말하지 않았지만 묶으면 드러나는 결론' "
    "또는 '독자 세계에 대한 함의'이며 반드시 'X이므로 Y다' 꼴(근거+주장). 비유는 가장 쉬운 것 1개.\n"
    "- [§1 쉬운 말로] 파인만 구간. 초등 6학년 어휘로 6~12문장. 영어 단어·알파벳 약어·전문용어·회사/제품/칩 이름을 단 하나도 쓰지 않는다. "
    "고유명사는 '한 회사', '최신 그래픽 칩'처럼 풀어 쓴다. 이 구간에 알파벳이 들어가면 실패다.\n"
    "- [§2 이제 정확한 말로] §1에서 쓴 쉬운 표현을 정확한 용어와 짝지운다. 한국어(English) 병기, IPA는 진짜 사전 단어에만 "
    "(약어·제품명엔 없음, 풀네임이 영어단어면 풀네임에). 어원 칸은 라틴·그리스 어근 또는 은유의 출처 1줄.\n"
    "- [§3 숫자] 화자가 흘린 구체 수치·설정값·명령어. 셋째 열 '이 숫자가 바꾸는 것'을 반드시 채운다.\n"
    "- [§4 막히는 곳] 독자가 막힐 지점 1~3개와 원문 회귀 지점. 화자가 인정한 한계, 작성자의 의심.\n"
    "- [§5 4렌즈] 렌즈 4개 모두 채우되 억지 매핑 금지. 해당 없으면 '—'. 렌즈당 2문장 이내. "
    "각 통찰은 영상 고유의 이름·숫자를 최소 1개 담는다(일반론 금지). 사업가 렌즈의 '우리'는 에이폼(이커머스·물류)이다.\n"
    "- [§6 파인만 과제] '__에게 이 개념을 3문장으로 설명해 본다' 1개(대상은 빈칸). 행동은 선택이며 30분짜리만.\n"
    "- [길이] §1~§6 합계는 접기 교정 전사보다 짧게. 영상이 3분 미만이면 카드·§1·§2·§5·과제만 채우고 §3·§4·섹션별 상세는 생략한다.\n"
    "- 이모지 금지. '==하이라이트==' 금지. 강조는 **볼드**와 "
    '<span style="color:#ef6c00">…</span> 두 종류만.\n'
    "- frontmatter를 메타에서 채운다: title·channel({channel})·original_creator·"
    "original_affiliation·video_id·url·upload_date(YYYY-MM-DD)·duration_min·"
    "status(정리완료)·created({today})·summary('Q. 질문 · 통찰' 160자 이내)·tags·aliases·note_version(v2).\n"
    "- frontmatter는 표준 YAML이어야 한다. 콜론이 든 문자열과 URL·wikilink·목록 원소는 반드시 따옴표로 감싼다.\n"
    "- 섹션: 카드 콜아웃 → 영상정보 콜아웃 → §1 쉬운 말로 → §2 이제 정확한 말로(표) → §3 숫자와 디테일(표) → "
    "§4 막히는 곳·반론 → §5 4렌즈 통찰(표) → §6 파인만 과제 → 접기 '섹션별 상세'(한눈에보기 표 + 영상 순서 본문) → "
    "출처 콜아웃 → 접기식 교정 전사(> [!note]- ...).\n"
    "출력은 완성된 마크다운 본문만. 코드펜스(```)로 감싸지 말 것."
)


def build_rules(channel_name: str) -> str:
    from datetime import date
    return RULES_TMPL.format(channel=channel_name, today=date.today().isoformat())


# ---- L0 수용 기준(설계서 §5) ---------------------------------------------------
_EN_RE = re.compile(r"[A-Za-z]{2,}")


def _section(md: str, start_pat: str, end_pat: str) -> str:
    m = re.search(start_pat, md, re.M)
    if not m:
        return ""
    rest = md[m.end():]
    e = re.search(end_pat, rest, re.M)
    return rest[: e.start()] if e else rest


def l0_check(md: str) -> list[str]:
    """설계서 §5 수용 기준. 위반 문자열 목록(빈 리스트=합격)."""
    bad: list[str] = []
    card = _section(md, r"^> \[!summary\]", r"^\s*$")
    for lab in ("**질문**", "**답**", "**통찰**", "**비유**"):
        if lab not in card:
            bad.append(f"카드에 {lab} 라벨 없음")
    if card and not re.search(r"이므로|때문에|→|므로", card.split("**통찰**", 1)[-1].split("\n", 1)[0]):
        bad.append("카드 통찰이 'X이므로 Y다' 꼴이 아님")
    s1 = _section(md, r"^## 1\. 쉬운 말로", r"^## 2\.")
    if not s1.strip():
        bad.append("§1 쉬운 말로 없음")
    else:
        en = _EN_RE.findall(s1)
        if en:
            bad.append(f"§1에 영어 {len(en)}개: {sorted(set(en))[:8]}")
    lens = _section(md, r"^## 5\. 4렌즈", r"^## 6\.")
    rows = [ln for ln in lens.splitlines() if ln.startswith("| ") and not ln.startswith("| 렌즈") and not ln.startswith("|---")]
    if len(rows) < 4:
        bad.append(f"4렌즈 행 {len(rows)}개(<4)")
    z1 = _section(md, r"^## 1\. 쉬운 말로", r"^> \[!note\]- 섹션별 상세")
    tr = _section(md, r"^## 교정 전사", r"\Z")
    # 교정 전사도 LLM이 압축하므로 비율만으론 흔들린다 → 절대 상한 6,000자를 함께 둔다(실측: 104분 영상 Z1 5.2K)
    if tr and len(z1) > max(len(tr), 6000):
        bad.append(f"Z1 {len(z1)}자 > 교정전사 {len(tr)}자")
    return bad


VARIANT_LABEL = {"v2": "클로드 버전"}  # 제목 옆 표시명(차드 지시 2026-09-03). slug는 ASCII 접미 유지


def apply_variant(md: str, variant: str) -> str:
    """대조본: title 접미(표시명) + slug_suffix(ASCII). frontmatter를 YAML로 다시 쓴다."""
    import yaml
    label = VARIANT_LABEL.get(variant, variant)
    m = FM_RE.search(md)
    data = yaml.safe_load(m.group(1))
    data["title"] = f"{data.get('title', '')} ({label})"
    data["slug_suffix"] = variant
    fm = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, width=10_000).rstrip("\n")
    body = md[m.end():]
    body = re.sub(r"^\n# .*$", lambda mm: mm.group(0) + f" ({label})", body, count=1, flags=re.M)
    return f"---\n{fm}\n---" + body


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("workspace")
    ap.add_argument("--out", default=None, help="지정 저장경로(검증용). 생략 시 볼트")
    ap.add_argument("--channel", default=None, help="채널 key (노트 폴더·채널명·톤 결정)")
    ap.add_argument("--variant", default=None, help="대조본 접미(예: v2) — 파일명·제목·slug에 붙는다")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args(argv)

    w = Path(a.workspace)
    clean_p = w / "transcript_clean.txt"
    src = clean_p if clean_p.exists() else (w / "transcript.txt")
    clean = src.read_text(encoding="utf-8")
    meta = json.loads((w / "youtube.json").read_text(encoding="utf-8"))
    tmpl = (Path(__file__).resolve().parent.parent / "note_template.md").read_text(encoding="utf-8")

    ch = None
    if a.channel:
        vault_root, chans = load_channels()
        ch = next((c for c in chans if c.key == a.channel), None)
        if ch is None:
            print(f"ERROR: 채널 '{a.channel}' 을 설정에서 찾을 수 없다", file=sys.stderr)
            return 1

    if a.out:
        dest = Path(a.out)
    else:
        title = re.sub(r'[\\/:*?"<>|]', "-", meta.get("title") or meta["id"]).strip()
        if a.variant:
            title = f"{title} ({a.variant})"
        note_dir = ch.note_path(vault_root) if ch else Path(load_config()["vaultNoteDir"])
        dest = note_dir / f"{title}.md"
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
    channel_name = ch.name if ch else "TechBridge-KR"
    rules = build_rules(channel_name)

    md = ""
    for attempt in (1, 2):
        md = chat(MODEL_NOTE, rules, user).strip()
        if md.startswith("```"):  # 혹시 코드펜스로 감싸 왔으면 벗김
            md = re.sub(r"^```[a-zA-Z]*\n", "", md)
            md = re.sub(r"\n```\s*$", "", md)
        bad = l0_check(md)
        if not bad:
            break
        print(f"[L0 {attempt}회차 위반] " + " / ".join(bad))
        if attempt == 1:
            user = user + "\n\n[직전 생성 위반 — 아래를 고쳐 전체를 다시 출력]\n- " + "\n- ".join(bad)
    else:
        print("WARN: L0 2회 위반, 마지막 결과로 저장(사람 검토 필요)")

    try:
        md, normalized = normalize_markdown(md)
        validate_markdown(md)
        if normalized:
            print("[frontmatter] 비표준 YAML 자동 정규화")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: 생성 노트 frontmatter 계약 위반: {exc}", file=sys.stderr)
        return 3
    if a.variant:
        md = apply_variant(md, a.variant)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md + "\n", encoding="utf-8")
    print(f"NOTE_OK {len(md)} chars -> {dest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
