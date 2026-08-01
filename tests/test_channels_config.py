"""load_channels() 계약 테스트 — 기획서 §4-2 '로더' 테스트 벡터 9케이스.

설계: design/2026-08-01_YC-Sequoia-채널-학습노트-자동화-기획서.md
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

YT = Path(__file__).resolve().parents[1] / "workflow" / "youtube"
sys.path.insert(0, str(YT))

import yt_lib  # noqa: E402


VAULT = "/tmp/wp-test-vault"
YC = {"key": "yc", "name": "Y Combinator", "channelId": "UCcefcZRL2oaA_uBNeo5UOWg",
      "noteDir": "Y-Combinator", "transcriptSource": "caption", "keywordSet": "ai+startup"}
TB = {"key": "techbridge", "name": "TechBridge-KR", "channelId": "UC895rbZX2iXLTDfji7W4PfA",
      "noteDir": "TechBridge-KR", "transcriptSource": "whisper", "keywordSet": "ai"}


@pytest.fixture
def cfg(tmp_path, monkeypatch):
    """config.json/config.example.json을 임시 디렉터리로 갈아끼운다."""
    def _write(data: dict, example: dict | None = None):
        (tmp_path / "config.json").write_text(json.dumps(data), encoding="utf-8")
        (tmp_path / "config.example.json").write_text(
            json.dumps(example if example is not None else {}), encoding="utf-8")
        (tmp_path / "keywords.json").write_text(json.dumps(
            {"ai": ["agent", "claude"], "startup": ["founder", "pmf"]}), encoding="utf-8")
        monkeypatch.setattr(yt_lib, "YT_DIR", tmp_path)
        return tmp_path
    return _write


def test_1_duplicate_key(cfg):
    cfg({"vaultRoot": VAULT, "channels": [YC, dict(YC, name="Other", noteDir="Other")]})
    with pytest.raises(ValueError, match="key"):
        yt_lib.load_channels()


def test_2_duplicate_note_dir(cfg):
    cfg({"vaultRoot": VAULT, "channels": [
        YC, dict(YC, key="yc2", channelId="UCWrF0oN6unbXrWsTN7RctTw")]})
    with pytest.raises(ValueError, match="noteDir"):
        yt_lib.load_channels()


def test_3_unknown_keyword_set(cfg):
    cfg({"vaultRoot": VAULT, "channels": [dict(YC, keywordSet="ai+bogus")]})
    with pytest.raises(ValueError, match="keywordSet|bogus"):
        yt_lib.load_channels()


def test_4_bad_channel_id(cfg):
    cfg({"vaultRoot": VAULT, "channels": [dict(YC, channelId="XXnope")]})
    with pytest.raises(ValueError, match="channelId"):
        yt_lib.load_channels()


def test_5_new_and_legacy_coexist_prefers_channels(cfg, capsys):
    cfg({"vaultRoot": VAULT, "channels": [YC],
         "rssUrl": "https://legacy", "vaultNoteDir": f"{VAULT}/TechBridge-KR"})
    root, chans = yt_lib.load_channels()
    assert [c.key for c in chans] == ["yc"]
    assert "무시" in capsys.readouterr().out          # 조용한 무시 금지


def test_6_legacy_only_converts(cfg):
    cfg({"vaultNoteDir": f"{VAULT}/TechBridge-KR",
         "channelId": "UC895rbZX2iXLTDfji7W4PfA", "topicKeywords": ["agent"]})
    root, chans = yt_lib.load_channels()
    assert len(chans) == 1
    c = chans[0]
    assert (c.key, c.note_dir, c.transcript_source) == ("techbridge", "TechBridge-KR", "whisper")
    assert str(root) == VAULT                          # vaultNoteDir의 부모가 vaultRoot


def test_7_nothing_configured(cfg):
    cfg({})
    with pytest.raises(ValueError, match="설정"):
        yt_lib.load_channels()


def test_8_disabled_channel_excluded(cfg):
    cfg({"vaultRoot": VAULT, "channels": [YC, dict(TB, enabled=False)]})
    _, chans = yt_lib.load_channels()
    assert [c.key for c in chans] == ["yc"]


def test_9_empty_channels_warns_not_raises(cfg, capsys):
    cfg({"vaultRoot": VAULT, "channels": []})
    _, chans = yt_lib.load_channels()
    assert chans == []
    assert "채널" in capsys.readouterr().out


def test_defaults_and_derived(cfg):
    cfg({"vaultRoot": VAULT, "channels": [YC]})
    _, chans = yt_lib.load_channels()
    c = chans[0]
    assert c.daily_max == 2 and c.min_score == 1.0 and c.enabled is True
    assert c.caption_langs == ("en", "en-orig")   # frozen dataclass → tuple
    assert c.rss_url == ("https://www.youtube.com/feeds/videos.xml"
                         "?channel_id=UCcefcZRL2oaA_uBNeo5UOWg")
    assert c.note_path(Path(VAULT)) == Path(VAULT) / "Y-Combinator"


def test_vault_root_required_when_channels(cfg):
    cfg({"channels": [YC]})
    with pytest.raises(ValueError, match="vaultRoot"):
        yt_lib.load_channels()


def test_vault_root_must_be_absolute(cfg):
    cfg({"vaultRoot": "relative/path", "channels": [YC]})
    with pytest.raises(ValueError, match="vaultRoot"):
        yt_lib.load_channels()


def test_note_dir_traversal_rejected(cfg):
    cfg({"vaultRoot": VAULT, "channels": [dict(YC, noteDir="../escape")]})
    with pytest.raises(ValueError, match="noteDir"):
        yt_lib.load_channels()


def test_daily_max_must_be_positive(cfg):
    cfg({"vaultRoot": VAULT, "channels": [dict(YC, dailyMax=0)]})
    with pytest.raises(ValueError, match="dailyMax"):
        yt_lib.load_channels()


def test_bad_transcript_source(cfg):
    cfg({"vaultRoot": VAULT, "channels": [dict(YC, transcriptSource="magic")]})
    with pytest.raises(ValueError, match="transcriptSource"):
        yt_lib.load_channels()


def test_load_keywords_union(cfg):
    cfg({"vaultRoot": VAULT, "channels": [YC]})
    kw = yt_lib.load_keywords("ai+startup")
    assert set(kw) == {"agent", "claude", "founder", "pmf"}
    assert yt_lib.load_keywords("ai") == ["agent", "claude"]


def test_state_name():
    assert yt_lib.state_name("seen", "yc") == "seen_yc.json"
    assert yt_lib.state_name("channel_index", "techbridge") == "channel_index_techbridge.json"
