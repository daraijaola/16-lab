"""Unit tests for the deterministic technical scoring (app/scoring.py)."""

from app import scoring


def _lines(*texts):
    return [{"id": f"l{i}", "text": t} for i, t in enumerate(texts)]


def test_returns_expected_shape():
    out = scoring.score_track(_lines("the cat sat on the mat", "i had a chat then took a nap"))
    assert set(out) == {"score", "metrics", "rhymes"}
    assert 0 <= out["score"] <= 100
    keys = {m["key"] for m in out["metrics"]}
    assert keys == {"rhyme", "internal", "vocab", "multi", "variance"}
    for m in out["metrics"]:
        assert 0 <= m["value"] <= 100


def test_is_deterministic():
    lines = _lines("rolling with the gang in the rain", "feeling all the pain in my brain")
    assert scoring.score_track(lines) == scoring.score_track(lines)


def test_detects_end_rhyme():
    out = scoring.score_track(_lines("i was chasing the bag", "now i'm waving the flag"))
    # "bag"/"flag" rhyme -> at least one rhyme span, tagged end (or multi).
    assert out["rhymes"], "expected rhyme spans for an obvious end rhyme"
    assert any(r["type"] in {"end", "multi"} for r in out["rhymes"])
    # rhyme spans carry valid char offsets into the line they belong to.
    for r in out["rhymes"]:
        assert r["start"] < r["end"]


def test_single_line_has_zero_variance():
    out = scoring.score_track(_lines("just one solitary bar here"))
    variance = next(m["value"] for m in out["metrics"] if m["key"] == "variance")
    assert variance == 0
