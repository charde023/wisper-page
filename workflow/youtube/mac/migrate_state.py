"""seen 상태 채널별 분리 마이그레이션 (기획서 §3-3).

seen_videos.json(단일 채널 시절) → seen_techbridge.json 으로 **copy**(구 파일 보존).
지우거나 rename하지 않는다 — 구 코드가 남아 있어도 깨지지 않게, 그리고 롤백이 가능하게.

멱등: 몇 번 돌려도 같은 결과. 손상·빈 상태·충돌은 덮지 않고 중단한다.
(빈 상태로 덮으면 151편이 전부 '신규'로 재감지되어 밤새 재처리 폭주)

Usage:
  python mac/migrate_state.py [--key techbridge] [--dry]
Exit: 0 정상/무변경 · 2 손상·빈 상태 · 3 신구 충돌(차드 판단 필요)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime
from pathlib import Path

YT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(YT_DIR))

from yt_lib import STATE_DIR, state_name  # noqa: E402

OLD = "seen_videos.json"


def _read(path: Path) -> tuple[dict | None, str]:
    """(data, error). 파일 없음은 (None, "")."""
    if not path.exists():
        return None, ""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"JSON 파싱 실패: {exc}"
    if not isinstance(data, dict):
        return None, "최상위가 객체가 아니다"
    return data, ""


def _seen_set(data: dict) -> set[str] | None:
    seen = data.get("seen")
    return set(seen) if isinstance(seen, list) else None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--key", default="techbridge", help="구 상태를 넘겨받을 채널 key")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args(argv)

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    old_p = STATE_DIR / OLD
    new_p = STATE_DIR / state_name("seen", a.key)

    new_data, new_err = _read(new_p)
    old_data, old_err = _read(old_p)

    # 3) 신 파일이 손상 — 덮지 않는다
    if new_p.exists() and new_data is None:
        print(f"ERROR: {new_p.name} {new_err} — 덮어쓰지 않고 중단", file=sys.stderr)
        return 2

    # 1) 신 파일 정상 존재
    if new_data is not None:
        new_seen = _seen_set(new_data)
        if new_seen is None:
            print(f"ERROR: {new_p.name} 의 seen 이 리스트가 아니다 — 중단", file=sys.stderr)
            return 2
        if old_data is None:                       # 구 파일 없음 → 이미 이전됨
            print(f"이미 이전됨: {new_p.name} ({len(new_seen)}개). 무변경.")
            return 0
        old_seen = _seen_set(old_data)
        if old_seen is None:
            print(f"ERROR: {OLD} 의 seen 이 리스트가 아니다 — 중단", file=sys.stderr)
            return 2
        if old_seen == new_seen:                   # 6) 내용 동일
            print(f"이미 이전됨(내용 동일 {len(new_seen)}개). 무변경.")
            return 0
        # 7) 둘 다 존재·내용 상이 → 자동 병합 금지
        print(f"ERROR: 신구 상태 충돌 — {OLD}={len(old_seen)}개, "
              f"{new_p.name}={len(new_seen)}개. 어느 쪽이 진실인지 자동 추측하지 않는다.",
              file=sys.stderr)
        print(f"  구에만 있는 것 {len(old_seen - new_seen)}개 / "
              f"신에만 있는 것 {len(new_seen - old_seen)}개", file=sys.stderr)
        return 3

    # 2) 둘 다 없음 → 신규 설치
    if old_data is None:
        if old_p.exists():                          # 존재하는데 파싱 실패
            print(f"ERROR: {OLD} {old_err} — 덮어쓰지 않고 중단", file=sys.stderr)
            return 2
        if not a.dry:
            new_p.write_text(json.dumps(
                {"seen": [], "updated_at": datetime.now().isoformat(timespec="seconds")},
                ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"신규 설치: 빈 상태 생성 {new_p.name}")
        return 0

    # 3) 구 파일만 존재 → 백업 후 copy
    old_seen = _seen_set(old_data)
    if old_seen is None:
        print(f"ERROR: {OLD} 의 seen 이 리스트가 아니다 — 중단", file=sys.stderr)
        return 2
    if not old_seen:
        print(f"ERROR: {OLD} 의 seen 이 비어 있다 — 빈 상태로 이전하면 전체 재처리 폭주. 중단",
              file=sys.stderr)
        return 2

    if a.dry:
        print(f"[dry] {OLD}({len(old_seen)}개) → {new_p.name} copy 예정")
        return 0

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = old_p.with_name(f"{OLD}.bak-{stamp}")
    shutil.copy2(old_p, backup)
    shutil.copy2(old_p, new_p)

    # 검증: 새 파일이 읽히고 개수가 같은가
    check, err = _read(new_p)
    check_seen = _seen_set(check) if check else None
    if check_seen is None or len(check_seen) != len(old_seen):
        new_p.unlink(missing_ok=True)
        print(f"ERROR: 이전 검증 실패({err or '개수 불일치'}) — 새 파일 삭제, 원본 유지",
              file=sys.stderr)
        return 2

    print(f"이전 완료: {OLD}({len(old_seen)}개) → {new_p.name}")
    print(f"  백업: {backup.name} (구 파일은 삭제하지 않는다 — 2주 관찰 후 수동 정리)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
