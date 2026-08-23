"""caption_fetch — 기획서 §4-2 'VTT 파싱' 6케이스 + '품질 게이트' 5케이스 + 트랙 선택."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "workflow" / "youtube"))
sys.path.insert(0, str(ROOT / "workflow" / "youtube" / "mac"))

import caption_fetch as cf  # noqa: E402

Track = cf.Track


def vtt(tmp_path, body: str) -> Path:
    p = tmp_path / "caption.en.vtt"
    p.write_text("WEBVTT\n\n" + body, encoding="utf-8")
    return p


# ── VTT 파싱 6케이스 ────────────────────────────────────────────
def test_v1_rollup_partial_dedup(tmp_path):
    body = ("00:00:01.000 --> 00:00:03.000\nnever been a better\n\n"
            "00:00:03.000 --> 00:00:05.000\nnever been a better time\n")
    assert cf.parse_vtt(vtt(tmp_path, body)) == "never been a better time"


def test_v2_exact_duplicates_collapse(tmp_path):
    body = "".join(f"00:00:0{i}.000 --> 00:00:0{i+1}.000\nsame line\n\n" for i in (1, 2, 3))
    assert cf.parse_vtt(vtt(tmp_path, body)) == "same line"


def test_v3_inline_tags_stripped(tmp_path):
    body = "00:00:01.000 --> 00:00:03.000\n<c>hello</c> <00:00:12.480>world\n"
    assert cf.parse_vtt(vtt(tmp_path, body)) == "hello world"


def test_v4_entities_decoded(tmp_path):
    body = "00:00:01.000 --> 00:00:03.000\nR&amp;D isn&#39;t cheap\n"
    assert cf.parse_vtt(vtt(tmp_path, body)) == "R&D isn't cheap"


def test_v5_speaker_tag_preserved(tmp_path):
    body = "00:00:01.000 --> 00:00:03.000\n<v Sam>we shipped\n"
    assert cf.parse_vtt(vtt(tmp_path, body)) == "Sam: we shipped"


def test_v6_note_and_cue_settings_removed(tmp_path):
    body = ("NOTE this is a note\n\n"
            "00:00:01.000 --> 00:00:03.000 align:start position:0%\nreal content\n")
    assert cf.parse_vtt(vtt(tmp_path, body)) == "real content"


def test_v7_vtt_meta_headers_removed(tmp_path):
    """yt-dlp 자동자막은 WEBVTT 뒤에 Kind/Language 메타를 붙인다(실측 2026-08-01)."""
    body = ("Kind: captions\nLanguage: en\n\n"
            "00:00:01.000 --> 00:00:03.000\nSam, thanks for joining us.\n")
    assert cf.parse_vtt(vtt(tmp_path, body)) == "Sam, thanks for joining us."


# ── 품질 게이트 5케이스 ─────────────────────────────────────────
def test_q1_boundary_80_wpm_passes():
    ok, reason = cf.quality_check(" ".join(["w"] * 1600), 1200)   # 정확히 80.0
    assert (ok, reason) == (True, "ok")


def test_q2_just_below_80_falls_back():
    ok, reason = cf.quality_check(" ".join(["w"] * 1599), 1200)
    assert ok is False and reason.startswith("low_wpm")


def test_q3_too_short_checked_first():
    ok, reason = cf.quality_check(" ".join(["w"] * 199), 1200)
    assert (ok, reason) == (False, "too_short")


def test_q4_duration_unknown_passes():
    for dur in (None, 0):
        ok, reason = cf.quality_check(" ".join(["w"] * 500), dur)
        assert (ok, reason) == (True, "duration_unknown")


def test_q5_empty_text():
    assert cf.quality_check("", 1200) == (False, "too_short")


# ── 트랙 선택 ───────────────────────────────────────────────────
PREFER = ("en", "en-orig")


def test_t1_manual_en_wins_over_auto():
    tracks = [Track("en", False), Track("en-orig", False), Track("en", True)]
    assert cf.pick_track(tracks, PREFER) == Track("en", True)


def test_t2_auto_en_orig_beats_auto_en():
    assert cf.pick_track([Track("en", False), Track("en-orig", False)], PREFER) \
        == Track("en-orig", False)


def test_t3_manual_variant_beats_auto():
    assert cf.pick_track([Track("en-US", True), Track("en", False)], PREFER) \
        == Track("en-US", True)


def test_t4_non_english_rejected():
    assert cf.pick_track([Track("ko", False), Track("ja", True)], PREFER) is None


def test_t4b_korean_prefer_picks_korean():
    """언어 하드코딩 제거 — prefer=('ko',)면 한국어 트랙이 선택된다(AI Frontier Korea)."""
    tracks = [Track("en", False), Track("ko", False), Track("ko-orig", False)]
    assert cf.pick_track(tracks, ("ko",)) == Track("ko-orig", False)
    assert cf.pick_track([Track("ko", False), Track("ko", True)], ("ko",)) == Track("ko", True)


def test_t5_empty_prefer_disables_captions():
    assert cf.pick_track([Track("en", True)], ()) is None


def test_t6_no_tracks():
    assert cf.pick_track([], PREFER) is None


# ── list_tracks 파싱 (yt-dlp 출력 형태) ─────────────────────────
def test_list_tracks_splits_manual_and_auto(monkeypatch):
    out = (
        "[info] Available subtitles for X:\n"
        "Language Name     Formats\n"
        "en       English  vtt, srt\n"
        "[info] Available automatic captions for X:\n"
        "Language Name              Formats\n"
        "en-orig  English (Original) vtt, srt\n"
        "ko       Korean            vtt, srt\n"
    )

    class R:
        stdout, stderr, returncode = out, "", 0

    monkeypatch.setattr(cf, "run_ytdlp", lambda *a, **k: R())
    tracks = cf.list_tracks("url")
    assert Track("en", True) in tracks
    assert Track("en-orig", False) in tracks
    assert Track("ko", False) in tracks
