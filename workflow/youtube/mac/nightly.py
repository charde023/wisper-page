"""야간 오케스트레이터(다채널): 감시→큐레이션→전사→교정→노트→인덱스·커밋→발행→요약.

차미(헤르메스) cron 'youtube-nightly'(매일 23시)이 --script로 호출. 멱등·부분실패 복구.
결과는 SUMMARY_PATH(JSON)로만 방출 — 팀 보고 발행은 차미가 그 파일을 읽어 수행(파이프라인은 실행만).

설계: design/2026-08-01_YC-Sequoia-채널-학습노트-자동화-기획서.md
- 채널 루프. 한 채널이 죽어도 나머지는 완주(채널 단위 실패 격리).
- 큐레이션 순서: RSS → 제목 점수 → (통과분만) duration 조회 → 길이 필터 → dailyMax 절단.
- 전사: transcriptSource=caption 이면 자막 우선(실패 시 Whisper 폴백), whisper면 1회만.
- seen 마킹은 '완주분 + 저가치 스킵분'만 → 실패분은 다음 밤 재개. 3회 연속 실패는 격리.
- LLM(교정·노트)은 코덱스 프록시(종량0). claude -p 안 씀.
- 볼트 커밋·발행은 채널별이 아니라 끝에 1회(push 레이스·커밋 파편화 방지).

수동 실행: python mac/nightly.py [--dry] [--limit N] [--channel KEY]
Exit: 0 정상(노트 0편 포함) · 1 전 채널 실패 · 2 코덱스 프록시 다운
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

YT_DIR = Path(__file__).resolve().parent.parent
MAC = YT_DIR / "mac"
ROOT = YT_DIR.parents[1]
sys.path.insert(0, str(YT_DIR))
sys.path.insert(0, str(MAC))

import curate  # noqa: E402
import rss_watch  # noqa: E402
from yt_lib import (load_channels, load_config, load_keywords,  # noqa: E402
                    read_state, run_ytdlp, state_name, write_state)
from llm import healthy  # noqa: E402

PY = sys.executable
PAGE_URL = "https://charde023.github.io/page/study-notes/"
SUMMARY_PATH = os.environ.get("TB_SUMMARY_PATH", "/tmp/techbridge-nightly-summary.json")
HEARTBEAT = Path.home() / ".gbrain" / ".heartbeat" / "kr.apom.youtube-nightly"
QUARANTINE_AT = 3          # 연속 실패 N회면 격리(무한 재시도 방지)


@dataclass
class ChannelResult:
    key: str
    n_note: int = 0
    n_skip: int = 0
    n_fail: int = 0            # 처리를 시도했으나 실패한 '영상' 수
    n_fallback: int = 0
    quarantined: list[dict] = field(default_factory=list)
    done_info: list[dict] = field(default_factory=list)
    error: str | None = None   # 채널 자체가 죽은 경우(RSS·설정). n_fail 과 섞지 않는다.


def notify(title: str, msg: str) -> None:
    print(f"[notify] {title}: {msg}")
    try:
        subprocess.run(["osascript", "-e",
                        f'display notification "{msg}" with title "{title}"'], check=False)
    except Exception:
        pass


def sh(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd) if cwd else None, text=True, capture_output=True)


def step(script: str, *args: str) -> bool:
    r = sh([PY, str(MAC / script), *args])
    sys.stdout.write(r.stdout[-400:])
    if r.returncode != 0:
        sys.stderr.write(r.stderr[-400:])
    return r.returncode == 0


def fetch_duration(url: str, key: str, vid: str, js: str) -> float | None:
    """RSS엔 길이가 없다 → 점수 통과분만 1회 조회하고 캐시(기획서 §3-1b)."""
    cache_name = state_name("meta_cache", key)
    cache = read_state(cache_name) or {}
    if vid in cache:
        return cache[vid].get("duration")
    r = run_ytdlp(["--skip-download", "--no-warnings", "--print", "%(duration)s", url], js)
    raw = (r.stdout or "").strip().splitlines()
    dur: float | None = None
    if raw and raw[0].strip() not in ("", "NA", "None"):
        try:
            dur = float(raw[0].strip())
        except ValueError:
            dur = None
    cache[vid] = {"duration": dur, "fetched_at": datetime.now().isoformat(timespec="seconds")}
    write_state(cache_name, cache)
    return dur


def bump_failure(key: str, vid: str, title: str, reason: str) -> int:
    fname = state_name("failures", key)
    data = read_state(fname) or {}
    rec = data.get(vid, {"count": 0})
    rec["count"] = int(rec.get("count", 0)) + 1
    rec.update(last_error=reason, last_at=datetime.now().isoformat(timespec="seconds"),
               title=title)
    data[vid] = rec
    write_state(fname, data)
    return rec["count"]


def clear_failure(key: str, vid: str) -> None:
    fname = state_name("failures", key)
    data = read_state(fname) or {}
    if data.pop(vid, None) is not None:
        write_state(fname, data)


def run_channel(ch, vault_root: Path, limit: int = 0, dry: bool = False) -> ChannelResult:
    res = ChannelResult(key=ch.key)
    cfg = load_config()
    js = cfg.get("ytJsRuntime", "node")
    seen_name = state_name("seen", ch.key)
    state = read_state(seen_name)
    feed = rss_watch.fetch_feed(ch.rss_url)

    # 최초 실행(상태 파일 없음) = 신규 채널 합류. 현재 피드를 통째로 seen 처리하고 끝낸다.
    # 이게 없으면 피드에 남아 있는 과거 15편이 전부 '신규'가 되어 매일 dailyMax 만큼
    # 소급 처리된다 — 기획서 결정 "백필 안 함(신규 업로드부터)"과 어긋난다.
    if state is None:
        if dry:
            print(f"[{ch.key}] 최초 실행 예정 — 현재 피드 {len(feed)}편을 seen 초기화하게 된다"
                  f"(dry라 기록하지 않음)")
            return res
        write_state(seen_name, {"seen": sorted(v["id"] for v in feed),
                                "updated_at": datetime.now().isoformat(timespec="seconds")})
        print(f"[{ch.key}] 최초 실행 — 현재 피드 {len(feed)}편을 seen 초기화(백필 안 함). "
              f"다음 업로드부터 처리한다.")
        return res

    seen = set(state.get("seen", []))
    new = [v for v in feed if v["id"] not in seen]
    if not new:
        print(f"[{ch.key}] 신규 없음")
        return res

    kw = load_keywords(ch.keyword_set)
    scored, skipped = [], []
    for v in new:
        sc = curate.score_video({"title": v["title"], "view_count": 0}, kw, 0.0)["score"]
        (scored if sc >= ch.min_score else skipped).append(v)
    res.n_skip = len(skipped)

    # 점수 통과분만 길이 조회(호출 절약) → 길이 필터
    todo = []
    for v in scored:
        dur = fetch_duration(v["url"], ch.key, v["id"], js)
        if ch.min_duration_min and dur and dur / 60.0 < ch.min_duration_min:
            print(f"[{ch.key}] 길이 미달 {int(dur/60)}분 < {ch.min_duration_min}분  {v['title'][:40]}")
            skipped.append(v)
            res.n_skip += 1
            continue
        todo.append(v)

    todo.sort(key=lambda v: v.get("published", ""), reverse=True)
    cap = min(ch.daily_max, limit) if limit else ch.daily_max
    deferred = todo[cap:]                      # 초과분은 seen 마킹하지 않는다 → 다음 밤 재후보
    todo = todo[:cap]
    print(f"[{ch.key}] 신규 {len(new)} · 처리 {len(todo)} · 스킵 {res.n_skip} · 이월 {len(deferred)}")

    if dry:
        for v in todo:
            print(f"    처리예정 {v['title'][:50]}")
        return res

    processed = []
    for v in todo:
        url, vid = v["url"], v["id"]
        ws = ROOT / "workspaces" / f"yt-{vid}"
        ok = (step("run_youtube.py", "--url", url, "--channel", ch.key)
              and (ws / "transcript.txt").exists()
              and step("transcript_clean.py", str(ws))
              and step("author_note.py", str(ws), "--channel", ch.key))
        if ok:
            processed.append(vid)
            res.done_info.append({"title": v["title"], "url": url, "channel": ch.name})
            clear_failure(ch.key, vid)
            meta_p = ws / "youtube.json"
            if meta_p.exists():
                try:
                    src = json.loads(meta_p.read_text(encoding="utf-8")).get("transcript_source", "")
                    if "fallback" in str(src):
                        res.n_fallback += 1
                except Exception:  # noqa: BLE001
                    pass
        else:
            res.n_fail += 1
            cnt = bump_failure(ch.key, vid, v["title"], "pipeline")
            if cnt >= QUARANTINE_AT:
                seen.add(vid)      # 재시도 중단
                res.quarantined.append({"id": vid, "title": v["title"], "last_error": "pipeline"})
                print(f"[{ch.key}] 격리({cnt}회 연속 실패): {v['title'][:40]}")

    res.n_note = len(processed)
    seen |= {v["id"] for v in skipped} | set(processed)
    write_state(seen_name, {"seen": sorted(seen),
                            "updated_at": datetime.now().isoformat(timespec="seconds")})
    return res


def vault_commit(vault_root: Path) -> None:
    vault = vault_root.parent               # …/학습노트 → 볼트 루트
    sh([PY, str(YT_DIR / "rebuild_index.py")])
    sh(["git", "fetch", "-q", "origin", "main"], cwd=vault)
    sh(["git", "reset", "--soft", "origin/main"], cwd=vault)   # 워킹트리 불변 → 레이스 회피
    sh(["git", "add", "-A"], cwd=vault)
    sh(["git", "commit", "-q", "-m",
        f"학습노트: 야간 자동 파이프라인 ({datetime.now():%Y-%m-%d})"], cwd=vault)
    sh(["git", "push", "origin", "HEAD"], cwd=vault)


def write_summary(results: list[ChannelResult]) -> None:
    per = {r.key: {"n_note": r.n_note, "n_skip": r.n_skip, "n_fail": r.n_fail,
                   "n_fallback": r.n_fallback, "channel_error": r.error,
                   "quarantined": r.quarantined} for r in results}
    summary = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "page_url": PAGE_URL,
        "n_note": sum(r.n_note for r in results),
        "n_skip": sum(r.n_skip for r in results),
        "n_fail": sum(r.n_fail for r in results),
        "per_channel": per,
        "new_notes": [n for r in results for n in r.done_info],
    }
    try:
        Path(SUMMARY_PATH).write_text(json.dumps(summary, ensure_ascii=False, indent=2),
                                      encoding="utf-8")
        print(f"[summary] {SUMMARY_PATH} 기록")
    except Exception as exc:  # noqa: BLE001
        print(f"[summary] 기록 실패(무시): {exc}")


def touch_heartbeat() -> None:
    try:
        HEARTBEAT.parent.mkdir(parents=True, exist_ok=True)
        HEARTBEAT.touch()
    except Exception as exc:  # noqa: BLE001
        print(f"[heartbeat] touch 실패(무시): {exc}")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true", help="감지·점수만 출력, 처리 안 함")
    ap.add_argument("--limit", type=int, default=0, help="채널별 추가 상한(디버그). 0=무제한")
    ap.add_argument("--channel", default=None, help="이 채널만 실행")
    a = ap.parse_args(argv)

    try:
        vault_root, channels = load_channels()
    except ValueError as exc:
        notify("YouTube 야간", f"설정 오류: {exc}")
        return 2
    if a.channel:
        channels = [c for c in channels if c.key == a.channel]
        if not channels:
            print(f"ERROR: 채널 '{a.channel}' 없음", file=sys.stderr)
            return 2
    if not channels:
        print("활성 채널 없음.")
        write_summary([])
        return 0

    if not healthy():
        notify("YouTube 야간", "코덱스 프록시(:18080) 응답 없음 — 중단")
        return 2

    results: list[ChannelResult] = []
    for ch in channels:
        try:
            results.append(run_channel(ch, vault_root, a.limit, a.dry))
        except Exception as exc:  # noqa: BLE001 — 채널 단위 격리
            print(f"[{ch.key}] 채널 실패: {exc!r}", file=sys.stderr)
            results.append(ChannelResult(key=ch.key, error=repr(exc)))

    if a.dry:
        return 0

    if any(r.n_note for r in results):
        vault_commit(vault_root)
        step("publish_study_notes.py", "--all")

    write_summary(results)

    n_note = sum(r.n_note for r in results)
    n_fail = sum(r.n_fail for r in results)
    all_dead = all(r.error for r in results)
    notify("YouTube 야간 완료" if not all_dead else "YouTube 야간 실패",
           f"노트 {n_note} · 스킵 {sum(r.n_skip for r in results)} · 실패 {n_fail}")
    for r in results:
        mark = f"채널실패({r.error})" if r.error else f"노트 {r.n_note}·스킵 {r.n_skip}·실패 {r.n_fail}"
        print(f"  {r.key:12} {mark}")

    if all_dead:
        print("전 채널 실패 — heartbeat 미갱신(관제탑이 신선도로 잡는다)", file=sys.stderr)
        return 1
    touch_heartbeat()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
