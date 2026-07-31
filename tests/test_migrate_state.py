"""migrate_state 7분기 — 기획서 §4-2 '마이그레이션' 테스트 벡터."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
YT = ROOT / "workflow" / "youtube"
sys.path.insert(0, str(YT))
sys.path.insert(0, str(YT / "mac"))

import migrate_state  # noqa: E402
import yt_lib  # noqa: E402


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setattr(yt_lib, "STATE_DIR", tmp_path)
    monkeypatch.setattr(migrate_state, "STATE_DIR", tmp_path)
    return tmp_path


def write(p: Path, seen):
    p.write_text(json.dumps({"seen": seen, "updated_at": "x"}), encoding="utf-8")


def test_1_new_only_is_idempotent(state):
    write(state / "seen_techbridge.json", ["a", "b"])
    assert migrate_state.main([]) == 0
    assert json.loads((state / "seen_techbridge.json").read_text())["seen"] == ["a", "b"]


def test_2_nothing_creates_empty(state):
    assert migrate_state.main([]) == 0
    assert json.loads((state / "seen_techbridge.json").read_text())["seen"] == []


def test_3_old_only_copies_with_backup(state):
    write(state / "seen_videos.json", [f"v{i}" for i in range(151)])
    assert migrate_state.main([]) == 0
    new = json.loads((state / "seen_techbridge.json").read_text())
    assert len(new["seen"]) == 151
    assert (state / "seen_videos.json").exists()                    # 구 파일 보존
    assert list(state.glob("seen_videos.json.bak-*"))               # 백업 생성


def test_4_corrupt_old_aborts(state):
    (state / "seen_videos.json").write_text("{broken", encoding="utf-8")
    assert migrate_state.main([]) == 2
    assert not (state / "seen_techbridge.json").exists()            # 덮지 않음


def test_5_empty_old_aborts(state):
    write(state / "seen_videos.json", [])
    assert migrate_state.main([]) == 2
    assert not (state / "seen_techbridge.json").exists()


def test_6_both_identical_no_change(state):
    write(state / "seen_videos.json", ["a"])
    write(state / "seen_techbridge.json", ["a"])
    assert migrate_state.main([]) == 0
    assert not list(state.glob("*.bak-*"))                          # 무변경


def test_7_both_differ_aborts_no_merge(state):
    write(state / "seen_videos.json", ["a", "b"])
    write(state / "seen_techbridge.json", ["a"])
    assert migrate_state.main([]) == 3
    assert json.loads((state / "seen_techbridge.json").read_text())["seen"] == ["a"]


def test_corrupt_new_aborts(state):
    write(state / "seen_videos.json", ["a"])
    (state / "seen_techbridge.json").write_text("{broken", encoding="utf-8")
    assert migrate_state.main([]) == 2


def test_dry_does_not_write(state):
    write(state / "seen_videos.json", ["a"])
    assert migrate_state.main(["--dry"]) == 0
    assert not (state / "seen_techbridge.json").exists()


def test_custom_key(state):
    write(state / "seen_videos.json", ["a"])
    assert migrate_state.main(["--key", "yc"]) == 0
    assert (state / "seen_yc.json").exists()
