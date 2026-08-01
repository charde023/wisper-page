"""숏츠 제외 — 감지·전사 단계에서 YouTube Shorts를 걸러낸다.

판정 근거(2026-08-01 yt-dlp 실측):
  TMd5rvh9fCU  35s  aspect 0.56  → 숏츠
  Gn30anFa_2U  55s  aspect 0.56  → 숏츠(노트 제목에 #Shorts 없음 = 제목 매칭은 못 믿는다)
  s-L0F92HCkg 156s  aspect 1.78  → 숏츠 아님(2.6분 정상 영상)
길이만으로 자르면 마지막 건을 오탐한다 → 길이 AND 세로 화면비.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workflow" / "youtube"))
sys.path.insert(0, str(ROOT / "workflow" / "youtube" / "mac"))

import nightly  # noqa: E402
import run_youtube  # noqa: E402
import yt_lib  # noqa: E402

Channel = yt_lib.Channel


# ---------------------------------------------------------------- 판정 함수

@pytest.mark.parametrize("dur,aspect,expected", [
    (35.0, 0.56, True),      # TMd5rvh9fCU 실측
    (55.0, 0.56, True),      # Gn30anFa_2U 실측
    (156.0, 1.78, False),    # s-L0F92HCkg 실측 — 길이만 보면 오탐하는 핵심 케이스
    (209.0, 0.56, False),    # 3분 초과 세로 영상은 숏츠가 아니다
    (180.0, 0.5625, True),   # 경계 포함
    (180.1, 0.5625, False),  # 경계 초과
    (60.0, 1.0, False),      # 정사각형은 세로가 아니다
])
def test_is_short_uses_duration_and_aspect(dur, aspect, expected):
    assert yt_lib.is_short(dur, aspect) is expected


@pytest.mark.parametrize("dur,aspect", [
    (None, None), (35.0, None), (None, 0.56), ("", ""), (0, 0.56), (35.0, 0),
])
def test_is_short_false_when_metadata_missing(dur, aspect):
    """메타 미상이면 정상 영상으로 취급한다 — 조용히 버리는 것이 더 나쁘다."""
    assert yt_lib.is_short(dur, aspect) is False


# ---------------------------------------------------------------- 야간 감지

def mk(key: str) -> Channel:
    return Channel(key=key, name=key, channel_id="UC895rbZX2iXLTDfji7W4PfA",
                   note_dir=key, transcript_source="caption", keyword_set="ai",
                   daily_max=5)


FEED = [
    {"id": "shortA", "title": "agent talk short", "url": "https://youtu.be/shortA",
     "published": "2026-08-01"},
    {"id": "longB", "title": "agent talk long", "url": "https://youtu.be/longB",
     "published": "2026-08-02"},
]

META = {"shortA": (45.0, 0.56), "longB": (1800.0, 1.78)}


@pytest.fixture
def harness(tmp_path, monkeypatch):
    ch = mk("techbridge")
    monkeypatch.setattr(yt_lib, "STATE_DIR", tmp_path / "state")
    monkeypatch.setattr(nightly, "SUMMARY_PATH", str(tmp_path / "summary.json"))
    monkeypatch.setattr(nightly, "HEARTBEAT", tmp_path / "hb")
    monkeypatch.setattr(nightly, "ROOT", tmp_path)
    monkeypatch.setattr(nightly, "healthy", lambda: True)
    monkeypatch.setattr(nightly, "load_channels", lambda: (tmp_path / "vault", [ch]))
    monkeypatch.setattr(nightly, "vault_commit", lambda *a, **k: None)
    monkeypatch.setattr(nightly, "notify", lambda *a, **k: None)
    monkeypatch.setattr(nightly.rss_watch, "fetch_feed", lambda u: list(FEED))
    monkeypatch.setattr(nightly, "fetch_meta",
                        lambda url, key, vid, js: META.get(vid, (None, None)))

    def fake_step(script: str, *args: str) -> bool:
        if script == "run_youtube.py":
            ws = tmp_path / "workspaces" / f"yt-{args[1].rsplit('/', 1)[-1]}"
            ws.mkdir(parents=True, exist_ok=True)
            (ws / "transcript.txt").write_text("x", encoding="utf-8")
        return True

    monkeypatch.setattr(nightly, "step", fake_step)
    yt_lib.write_state(yt_lib.state_name("seen", "techbridge"), {"seen": [], "updated_at": "x"})
    return tmp_path


def test_shorts_are_not_transcribed(harness):
    nightly.main([])
    s = json.loads((harness / "summary.json").read_text(encoding="utf-8"))
    assert s["per_channel"]["techbridge"]["n_note"] == 1        # longB 만 처리
    assert s["per_channel"]["techbridge"]["n_short"] == 1       # shortA 는 숏츠로 집계
    assert not (harness / "workspaces" / "yt-shortA").exists()  # 워크스페이스도 안 만든다


def test_shorts_are_marked_seen_so_they_stop_reappearing(harness):
    nightly.main([])
    seen = set(yt_lib.read_state("seen_techbridge.json")["seen"])
    assert "shortA" in seen      # 매일 밤 다시 후보로 올라오면 안 된다
    assert "longB" in seen


def test_dry_run_reports_shorts_without_transcribing(harness, capsys):
    nightly.main(["--dry"])
    out = capsys.readouterr().out
    assert "숏츠" in out
    assert not (harness / "workspaces").exists()


# ---------------------------------------------------------------- 메타 캐시

def test_fetch_meta_refetches_legacy_cache_without_aspect(tmp_path, monkeypatch):
    """구 캐시({duration, fetched_at})는 aspect가 없다 → 재조회해야 숏츠를 잡는다."""
    monkeypatch.setattr(yt_lib, "STATE_DIR", tmp_path / "state")
    yt_lib.write_state("meta_cache_techbridge.json",
                       {"o5aTK9qBSfA": {"duration": 50.0, "fetched_at": "2026-08-01T10:03:29"}})
    calls = []

    class R:
        stdout = "50.0|0.56\n"

    def fake_ytdlp(args, js=None, check=False):
        calls.append(args)
        return R()

    monkeypatch.setattr(nightly, "run_ytdlp", fake_ytdlp)
    dur, aspect = nightly.fetch_meta("https://youtu.be/o5aTK9qBSfA", "techbridge",
                                     "o5aTK9qBSfA", "node")
    assert len(calls) == 1                       # 구 엔트리는 캐시 히트로 치지 않는다
    assert (dur, aspect) == (50.0, 0.56)
    cached = yt_lib.read_state("meta_cache_techbridge.json")["o5aTK9qBSfA"]
    assert cached["aspect"] == 0.56

    nightly.fetch_meta("https://youtu.be/o5aTK9qBSfA", "techbridge", "o5aTK9qBSfA", "node")
    assert len(calls) == 1                       # 새 스키마는 캐시 히트


# ---------------------------------------------------------------- 수동 실행

def test_manual_run_refuses_a_short(monkeypatch, capsys, tmp_path):
    """수동 --url 로 숏츠를 넣어도 전사하지 않는다(야간 경로만 막으면 새어 나간다)."""
    monkeypatch.setattr(run_youtube, "resolve_meta",
                        lambda url, js: ("shortA", 45.0, 0.56))
    called = []
    monkeypatch.setattr(run_youtube.subprocess, "run",
                        lambda *a, **k: called.append(a) or None)
    rc = run_youtube.main(["--url", "https://youtu.be/shortA", "--root", str(tmp_path)])
    assert rc != 0
    assert "숏츠" in capsys.readouterr().out
    assert not called                             # 페치·전사 자체를 시작하지 않는다
