"""채널 실패 격리 — 기획서 DoD #6. 외부 네트워크·신규 영상에 의존하지 않는 결정적 시험.

rss_watch.fetch_feed / 전사·LLM 단계를 전부 스텁으로 교체하고,
sequoia 채널에서만 예외를 던져 나머지 채널이 완주하는지 확인한다.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workflow" / "youtube"))
sys.path.insert(0, str(ROOT / "workflow" / "youtube" / "mac"))

import nightly  # noqa: E402
import yt_lib  # noqa: E402

Channel = yt_lib.Channel


def mk(key: str, name: str, cid: str) -> Channel:
    return Channel(key=key, name=name, channel_id=cid, note_dir=name,
                   transcript_source="caption", keyword_set="ai", daily_max=2)


CHANNELS = [
    mk("techbridge", "TechBridge-KR", "UC895rbZX2iXLTDfji7W4PfA"),
    mk("yc", "Y-Combinator", "UCcefcZRL2oaA_uBNeo5UOWg"),
    mk("sequoia", "Sequoia", "UCWrF0oN6unbXrWsTN7RctTw"),
]


def feed_for(key: str) -> list[dict]:
    return [{"id": f"{key}{i}", "title": f"{key} agent talk {i}",
             "url": f"https://youtu.be/{key}{i}", "published": f"2026-08-0{i+1}"}
            for i in range(2)]


@pytest.fixture
def harness(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(yt_lib, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(nightly, "SUMMARY_PATH", str(tmp_path / "summary.json"))
    monkeypatch.setattr(nightly, "HEARTBEAT", tmp_path / "hb")
    monkeypatch.setattr(nightly, "ROOT", tmp_path)
    monkeypatch.setattr(nightly, "healthy", lambda: True)
    monkeypatch.setattr(nightly, "load_channels", lambda: (tmp_path / "vault", CHANNELS))
    monkeypatch.setattr(nightly, "fetch_duration", lambda *a, **k: 1800.0)
    monkeypatch.setattr(nightly, "vault_commit", lambda *a, **k: None)
    monkeypatch.setattr(nightly, "notify", lambda *a, **k: None)

    def fake_feed(rss_url: str):
        for ch in CHANNELS:
            if ch.channel_id in rss_url:
                if ch.key == "sequoia":
                    raise RuntimeError("HTTPError 404")     # 이 채널만 죽인다
                return feed_for(ch.key)
        return []

    monkeypatch.setattr(nightly.rss_watch, "fetch_feed", fake_feed)

    def fake_step(script: str, *args: str) -> bool:
        if script == "run_youtube.py":                      # transcript.txt 존재 조건 충족
            ws = tmp_path / "workspaces" / f"yt-{args[1].rsplit('/', 1)[-1]}"
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "transcript.txt").write_text("x", encoding="utf-8")
        return True

    monkeypatch.setattr(nightly, "step", fake_step)
    # 기존 채널을 흉내낸다: seen 상태 파일이 이미 있어야 '최초 실행 시딩'을 타지 않는다.
    for ch in CHANNELS:
        yt_lib.write_state(yt_lib.state_name("seen", ch.key), {"seen": [], "updated_at": "x"})
    return tmp_path


def test_one_channel_dies_others_finish(harness):
    rc = nightly.main([])
    import json
    s = json.loads((harness / "summary.json").read_text(encoding="utf-8"))
    per = s["per_channel"]

    assert per["sequoia"]["channel_error"] is not None       # 죽은 채널은 error로
    assert per["sequoia"]["n_note"] == 0
    assert per["sequoia"]["n_fail"] == 0                     # 영상 실패와 섞지 않는다
    assert per["techbridge"]["n_note"] == 2                  # 나머지는 완주
    assert per["yc"]["n_note"] == 2
    assert s["n_note"] == 4
    assert rc == 0                                           # 일부 실패는 exit 0
    assert (harness / "hb").exists()                         # heartbeat 갱신


def test_all_channels_dead_exits_1_without_heartbeat(harness, monkeypatch):
    def dead(rss_url: str):
        raise RuntimeError("HTTPError 404")

    monkeypatch.setattr(nightly.rss_watch, "fetch_feed", dead)
    rc = nightly.main([])
    assert rc == 1
    assert not (harness / "hb").exists()                     # 전 채널 실패면 heartbeat 안 찍는다


def test_daily_max_defers_excess(harness, monkeypatch):
    monkeypatch.setattr(nightly.rss_watch, "fetch_feed",
                        lambda u: [{"id": f"v{i}", "title": f"agent talk {i}",
                                    "url": f"https://youtu.be/v{i}",
                                    "published": f"2026-08-{i+1:02d}"} for i in range(5)])
    nightly.main(["--channel", "yc"])
    import json
    s = json.loads((harness / "summary.json").read_text(encoding="utf-8"))
    assert s["per_channel"]["yc"]["n_note"] == 2             # dailyMax=2 상한
    seen = yt_lib.read_state("seen_yc.json")["seen"]
    assert len(seen) == 2                                    # 이월분은 seen 마킹 안 함


def test_first_run_seeds_seen_without_backfill(harness, monkeypatch):
    """신규 채널 합류 시 피드의 과거분을 소급 처리하지 않는다(기획서 결정 ①)."""
    import json
    (harness / "state" / "seen_yc.json").unlink()          # 상태 없음 = 신규 채널 합류
    nightly.main(["--channel", "yc"])
    s = json.loads((harness / "summary.json").read_text(encoding="utf-8"))
    assert s["per_channel"]["yc"]["n_note"] == 0          # 첫 밤엔 0편
    assert len(yt_lib.read_state("seen_yc.json")["seen"]) == 2   # 현재 피드는 전부 seen

    # 두 번째 밤: 새 영상 1편이 올라오면 그것만 처리
    monkeypatch.setattr(nightly.rss_watch, "fetch_feed",
                        lambda u: feed_for("yc") + [{"id": "ycNEW", "title": "agent new",
                                                     "url": "https://youtu.be/ycNEW",
                                                     "published": "2026-08-09"}])
    nightly.main(["--channel", "yc"])
    s2 = json.loads((harness / "summary.json").read_text(encoding="utf-8"))
    assert s2["per_channel"]["yc"]["n_note"] == 1
