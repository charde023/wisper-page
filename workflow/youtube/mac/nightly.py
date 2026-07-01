"""야간 오케스트레이터: 감시→큐레이션→전사→교정→노트→인덱스·커밋→발행→알림.

launchd(kr.techbridge.nightly, 매일 23시)가 호출. 멱등·부분실패 복구.
- 큐레이션: curate 점수 >= TB_CURATE_MIN(기본 1.0)만 노트화. 미만은 스킵(+seen 마킹).
- LLM(교정·노트)은 코덱스 프록시(종량0). claude -p 안 씀.
- seen 마킹은 '완주한 영상만' → 실패분 다음 밤 재개.

수동 실행: python mac/nightly.py [--dry] [--limit N]
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

YT_DIR = Path(__file__).resolve().parent.parent
MAC = YT_DIR / "mac"
ROOT = YT_DIR.parents[1]
sys.path.insert(0, str(YT_DIR))
sys.path.insert(0, str(MAC))

import curate  # noqa: E402
import rss_watch  # noqa: E402
from yt_lib import load_config, read_state, write_state  # noqa: E402
from llm import healthy  # noqa: E402

THRESHOLD = float(os.environ.get("TB_CURATE_MIN", "1.0"))
SEEN = "seen_videos.json"
PY = sys.executable


def notify(title: str, msg: str) -> None:
    print(f"[notify] {title}: {msg}")
    try:  # macOS 데스크톱 알림
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "{title}"'], check=False)
    except Exception:
        pass


def score_title(title: str, kw: list[str]) -> float:
    return curate.score_video({"title": title, "view_count": 0}, kw, 0.0)["score"]


def sh(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True)


def step(script: str, *args: str) -> bool:
    r = sh([PY, str(MAC / script), *args])
    sys.stdout.write(r.stdout[-400:])
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-400:])
    return r.returncode == 0


def vault_commit(cfg: dict) -> None:
    vault = Path(cfg["vaultNoteDir"]).parents[1]  # …/charde_n
    sh([PY, str(YT_DIR / "rebuild_index.py")])
    sh(["git", "fetch", "-q", "origin", "main"], cwd=vault)
    sh(["git", "reset", "--soft", "origin/main"], cwd=vault)  # 워킹트리 불변→레이스 회피
    sh(["git", "add", "-A"], cwd=vault)
    sh(["git", "commit", "-q", "-m",
        f"학습노트: 야간 자동 파이프라인 ({datetime.now():%Y-%m-%d})"], cwd=vault)
    sh(["git", "push", "origin", "HEAD"], cwd=vault)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="감지·점수만 출력, 처리 안 함")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args(argv)

    cfg = load_config()
    kw = [k.lower() for k in cfg.get("topicKeywords", [])]

    if not healthy():
        notify("TechBridge 야간", "코덱스 프록시(:18080) 응답 없음 — 중단")
        return 2

    feed = rss_watch.fetch_feed(cfg["rssUrl"])
    state = read_state(SEEN) or {}
    seen = set(state.get("seen", []))
    new = [v for v in feed if v["id"] not in seen]
    if a.limit:
        new = new[: a.limit]

    if not new:
        print("신규 영상 없음.")
        return 0

    print(f"신규 {len(new)}개 · 큐레이션 임계 {THRESHOLD}")
    todo, skip = [], []
    for v in new:
        sc = score_title(v["title"], kw)
        (todo if sc >= THRESHOLD else skip).append((v, sc))
        print(f"  {'노트' if sc>=THRESHOLD else '스킵'} score={sc:>4}  {v['title'][:44]}")

    if a.dry:
        return 0

    processed, failed = [], []
    for v, sc in todo:
        url, vid = v["url"], v["id"]
        ws = ROOT / "workspaces" / f"yt-{vid}"
        ok = (step("run_youtube.py", "--url", url)
              and (ws / "transcript.txt").exists()
              and step("transcript_clean.py", str(ws))
              and step("author_note.py", str(ws)))
        (processed if ok else failed).append(vid)

    # 저가치 스킵분도 seen 마킹(재알림 방지). 완주분도 마킹. 실패분은 남겨 재시도.
    seen |= {v["id"] for v, _ in skip} | set(processed)
    write_state(SEEN, {"seen": sorted(seen),
                       "updated_at": datetime.now().isoformat(timespec="seconds")})

    if processed:
        vault_commit(cfg)
        step("publish_study_notes.py", "--all")

    notify("TechBridge 야간 완료",
           f"노트 {len(processed)} · 스킵 {len(skip)} · 실패 {len(failed)}")
    print(f"\n요약: 노트 {len(processed)} · 스킵 {len(skip)} · 실패 {len(failed)}")
    if failed:
        print("실패(다음 밤 재시도):", ", ".join(failed))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
