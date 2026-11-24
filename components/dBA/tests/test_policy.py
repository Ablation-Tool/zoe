"""Pure-function tests for the dBA policy engine.

These never touch ffmpeg or the filesystem — they feed `analyze_metadata`
synthetic ffprobe-shaped dicts. That is possible only because the engine is
pure over `raw_meta`, which is the whole point of that design choice.
"""
from __future__ import annotations

import main


# --------------------------------------------------------------------------- #
# helpers to build ffprobe-shaped inputs
# --------------------------------------------------------------------------- #
AUDIO = {
    "codec_type": "audio", "codec_name": "pcm_s16le",
    "sample_rate": "16000", "channels": 1, "bit_rate": "256000",
}


def raw(fmt=None, streams=None) -> dict:
    return {"format": fmt or {}, "streams": streams if streams is not None else [dict(AUDIO)]}


def ids(indicators) -> set[str]:
    return {i.id for i in indicators}


# --------------------------------------------------------------------------- #
# sanitized_metadata — the allowlist
# --------------------------------------------------------------------------- #
def test_sanitized_metadata_extracts_technical_fields():
    sm, _, _, _ = main.analyze_metadata(
        raw(fmt={"format_name": "wav", "duration": "0.5", "bit_rate": "256000"}), "audit"
    )
    assert sm.duration == 0.5
    assert sm.sample_rate == 16000
    assert sm.channels == 1
    assert sm.codec_name == "pcm_s16le"
    assert sm.container_format == "wav"


def test_free_form_tags_are_always_dropped():
    r = raw(fmt={"format_name": "wav", "tags": {"ISFT": "anything", "artist": "x"}})
    sm, _, _, _ = main.analyze_metadata(r, "audit")
    assert sm.tags == {}  # invariant: no free-form tag survives by default


def test_allowed_tag_keys_pass_through(monkeypatch):
    monkeypatch.setattr(main, "ALLOWED_TAG_KEYS", {"language"})
    r = raw(fmt={"format_name": "wav", "tags": {"language": "eng", "comment": "drop me"}})
    sm, _, _, _ = main.analyze_metadata(r, "audit")
    assert sm.tags == {"language": "eng"}


# --------------------------------------------------------------------------- #
# content indicators — suspicious markers in tag values
# --------------------------------------------------------------------------- #
def test_viper_payload_raises_high_indicators():
    r = raw(fmt={"format_name": "wav",
                 "tags": {"ISFT": "[VIPER] <SEIZURE_SHORT> OP=<OPERATION_ID> -dbug"}})
    _, inds, score, disp = main.analyze_metadata(r, "strict")
    assert {"TAG_VIPER", "TAG_SEIZURE_MARKER", "TAG_OPERATION_ID", "TAG_DEBUG_FLAG"} <= ids(inds)
    assert score == 100
    assert disp == "reject"


def test_indicator_value_snippet_is_truncated():
    long_val = "https://evil.example/" + "A" * 500
    r = raw(fmt={"format_name": "wav", "tags": {"comment": long_val}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    url = next(i for i in inds if i.id == "TAG_GENERIC_URL")
    assert url.value_snippet is not None
    assert len(url.value_snippet) <= main.VALUE_SNIPPET_LEN


def test_stream_level_tags_are_scanned():
    stream = dict(AUDIO, tags={"comment": "[VIPER]"})
    _, inds, _, _ = main.analyze_metadata(raw(fmt={"format_name": "wav"}, streams=[stream]), "audit")
    assert "TAG_VIPER" in ids(inds)


def test_secret_patterns_detected():
    r = raw(fmt={"format_name": "wav", "tags": {
        "a": "key AKIAIOSFODNN7EXAMPLE here",
        "b": "-----BEGIN RSA PRIVATE KEY-----",
        "c": "reach me at analyst@example.com",
    }})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert {"TAG_AWS_KEY", "TAG_PRIVATE_KEY", "TAG_EMAIL_PII"} <= ids(inds)


# --------------------------------------------------------------------------- #
# structural indicators — file shape, no suspicious strings required
# --------------------------------------------------------------------------- #
def test_trailing_data_detected_from_stream_rate():
    # size dwarfs what a 256kbps 0.5s stream can hold => appended payload.
    r = raw(fmt={"format_name": "wav", "duration": "0.5", "size": str(5_000_000)})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "TRAILING_DATA" in ids(inds)


def test_trailing_data_not_falsely_flagged_on_normal_file():
    # ~16KB of audio for a 0.5s 256kbps stream — expected, must not flag.
    r = raw(fmt={"format_name": "wav", "duration": "0.5", "size": str(16_044)})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "TRAILING_DATA" not in ids(inds)


def test_trailing_data_uses_stream_rate_not_format_bitrate():
    # format.bit_rate is (circularly) size*8/duration; the check must ignore it
    # and use the stream's own rate, or it can never fire.
    r = raw(fmt={"format_name": "wav", "duration": "0.5",
                 "size": str(5_000_000), "bit_rate": str(5_000_000 * 8 * 2)})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "TRAILING_DATA" in ids(inds)


def test_unusual_duration_detected():
    r = raw(fmt={"format_name": "wav", "duration": "0.01", "size": str(5_000_000)})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "UNUSUAL_DURATION" in ids(inds)


def test_unexpected_codec_detected():
    r = raw(streams=[dict(AUDIO, codec_name="g729")])
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "UNEXPECTED_CODEC" in ids(inds)


def test_multiple_audio_streams_detected():
    r = raw(streams=[dict(AUDIO), dict(AUDIO)])
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "MULTIPLE_AUDIO_STREAMS" in ids(inds)


def test_embedded_nonaudio_stream_detected():
    r = raw(streams=[dict(AUDIO), {"codec_type": "video", "codec_name": "mjpeg"}])
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "EMBEDDED_NONAUDIO_STREAM" in ids(inds)


def test_clean_file_has_no_indicators():
    sm, inds, score, disp = main.analyze_metadata(
        raw(fmt={"format_name": "wav", "duration": "0.5", "size": "16044"}), "strict"
    )
    assert inds == []
    assert score == 0
    assert disp == "allow"


# --------------------------------------------------------------------------- #
# scoring
# --------------------------------------------------------------------------- #
def test_severity_weights_in_audit_mode():
    # audit does not adjust the base score, so it reveals raw weights.
    low = raw(fmt={"format_name": "wav", "tags": {"c": "http://x"}})       # low = 10
    med = raw(fmt={"format_name": "wav", "tags": {"c": "<script>"}})        # medium = 25
    high = raw(fmt={"format_name": "wav", "tags": {"c": "[VIPER]"}})        # high = 40
    assert main.analyze_metadata(low, "audit")[2] == 10
    assert main.analyze_metadata(med, "audit")[2] == 25
    assert main.analyze_metadata(high, "audit")[2] == 40


def test_score_is_capped_at_100():
    r = raw(fmt={"format_name": "wav", "tags": {
        "a": "[VIPER]", "b": "<SEIZURE_SHORT>", "c": "<OPERATION_ID>", "d": "; curl x",
    }})
    assert main.analyze_metadata(r, "audit")[2] == 100


def test_strict_adds_ten_when_any_indicator():
    r = raw(fmt={"format_name": "wav", "tags": {"c": "http://x"}})  # base 10
    assert main.analyze_metadata(r, "audit")[2] == 10
    assert main.analyze_metadata(r, "strict")[2] == 20


def test_lenient_subtracts_ten_floored_at_zero():
    r = raw(fmt={"format_name": "wav", "tags": {"c": "http://x"}})  # base 10
    assert main.analyze_metadata(r, "lenient")[2] == 0


# --------------------------------------------------------------------------- #
# disposition thresholds
# --------------------------------------------------------------------------- #
def test_disposition_default_thresholds():
    assert main._decide_disposition(0, "default") == "allow"
    assert main._decide_disposition(19, "default") == "allow"
    assert main._decide_disposition(20, "default") == "quarantine"
    assert main._decide_disposition(59, "default") == "quarantine"
    assert main._decide_disposition(60, "default") == "reject"


def test_disposition_strict_is_tighter():
    assert main._decide_disposition(9, "strict") == "allow"
    assert main._decide_disposition(10, "strict") == "quarantine"
    assert main._decide_disposition(40, "strict") == "reject"


def test_disposition_lenient_is_looser():
    assert main._decide_disposition(29, "lenient") == "allow"
    assert main._decide_disposition(30, "lenient") == "quarantine"
    assert main._decide_disposition(80, "lenient") == "reject"


def test_audit_always_allows_even_at_max_score():
    r = raw(fmt={"format_name": "wav",
                 "tags": {"c": "[VIPER] <SEIZURE_SHORT> <OPERATION_ID> ; curl evil"}})
    _, _, score, disp = main.analyze_metadata(r, "audit")
    assert score == 100  # four high markers, capped
    assert disp == "allow"


# --------------------------------------------------------------------------- #
# New findings — H-1, key scanning, masking, dedup, NO_AUDIO_STREAM
# --------------------------------------------------------------------------- #

def test_no_audio_stream_raises_high_indicator():
    # A file with only a video stream has no audio for ASR — HIGH structural indicator.
    r = raw(streams=[{"codec_type": "video", "codec_name": "mjpeg"}])
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "NO_AUDIO_STREAM" in ids(inds)
    viper = next(i for i in inds if i.id == "NO_AUDIO_STREAM")
    assert viper.severity == "high"


def test_tag_key_scanning_detects_payload_in_key():
    # Attacker places payload in the tag KEY, not the value — must still fire.
    stream = dict(AUDIO, tags={"[VIPER]": "innocent_value"})
    _, inds, _, _ = main.analyze_metadata(raw(fmt={"format_name": "wav"}, streams=[stream]), "audit")
    assert "TAG_VIPER" in ids(inds)


def test_tag_key_is_truncated_in_indicator():
    long_key = "x" * 500
    r = raw(fmt={"format_name": "wav", "tags": {long_key: "[VIPER]"}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    viper = next(i for i in inds if i.id == "TAG_VIPER")
    assert viper.key is not None
    assert len(viper.key) <= main.VALUE_SNIPPET_LEN


def test_aws_key_is_masked_in_snippet():
    aws_key = "AKIAIOSFODNN7EXAMPLE"
    r = raw(fmt={"format_name": "wav", "tags": {"comment": f"key={aws_key} end"}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    ind = next(i for i in inds if i.id == "TAG_AWS_KEY")
    assert ind.value_snippet is not None
    assert aws_key not in ind.value_snippet
    assert "***" in ind.value_snippet


def test_private_key_is_masked_in_snippet():
    pem = "-----BEGIN RSA PRIVATE KEY-----"
    r = raw(fmt={"format_name": "wav", "tags": {"comment": pem}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    ind = next(i for i in inds if i.id == "TAG_PRIVATE_KEY")
    assert ind.value_snippet is not None
    assert pem not in ind.value_snippet
    assert "***" in ind.value_snippet


def test_email_pii_is_masked_in_snippet():
    email = "analyst@example.com"
    r = raw(fmt={"format_name": "wav", "tags": {"comment": email}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    ind = next(i for i in inds if i.id == "TAG_EMAIL_PII")
    assert ind.value_snippet is not None
    assert email not in ind.value_snippet
    assert "***" in ind.value_snippet


def test_non_secret_pattern_value_not_masked():
    # [VIPER] is not a secret — snippet should contain the matched text.
    r = raw(fmt={"format_name": "wav", "tags": {"c": "[VIPER]"}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    ind = next(i for i in inds if i.id == "TAG_VIPER")
    assert ind.value_snippet is not None
    assert "[VIPER]" in ind.value_snippet


def test_duplicate_indicators_across_streams_are_deduplicated():
    # Same [VIPER] value in two streams — should produce one indicator, not two.
    stream_a = dict(AUDIO, tags={"comment": "[VIPER]"})
    stream_b = dict(AUDIO, tags={"comment": "[VIPER]"})
    _, inds, _, _ = main.analyze_metadata(raw(fmt={"format_name": "wav"}, streams=[stream_a, stream_b]), "audit")
    viper_hits = [i for i in inds if i.id == "TAG_VIPER"]
    assert len(viper_hits) == 1


def test_distinct_keys_same_pattern_not_deduplicated():
    # Same pattern in two *different* keys — two distinct injection vectors; both kept.
    r = raw(fmt={"format_name": "wav", "tags": {"key_a": "[VIPER]", "key_b": "[VIPER]"}})
    _, inds, _, _ = main.analyze_metadata(r, "audit")
    viper_hits = [i for i in inds if i.id == "TAG_VIPER"]
    assert len(viper_hits) == 2


# --------------------------------------------------------------------------- #
# allowed tag pass-through with indicator match drops the tag
# --------------------------------------------------------------------------- #
def test_allowed_tag_with_indicator_value_is_dropped(monkeypatch):
    # An allowed key whose value matches TAG_AWS_KEY must not pass through to sanitized.tags.
    monkeypatch.setattr(main, "ALLOWED_TAG_KEYS", {"language"})
    r = raw(fmt={"format_name": "wav", "tags": {"language": "contact AKIAABCDEFGHIJKLMNOP"}})
    sm, inds, _, _ = main.analyze_metadata(r, "audit")
    assert "TAG_AWS_KEY" in ids(inds)
    assert "language" not in sm.tags


def test_allowed_tag_with_benign_value_passes_through(monkeypatch):
    # An allowed key whose value does not match any indicator must still pass through.
    monkeypatch.setattr(main, "ALLOWED_TAG_KEYS", {"language"})
    r = raw(fmt={"format_name": "wav", "tags": {"language": "en"}})
    sm, inds, _, _ = main.analyze_metadata(r, "audit")
    assert sm.tags == {"language": "en"}
    assert not any(i.id.startswith("TAG_") for i in inds)
