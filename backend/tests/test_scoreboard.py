"""Unit tests for the scoreboard (app/scoreboard.py).

These cover the pure / validation paths only — we deliberately do NOT exercise a
successful upsert, because that writes through to the live scoreboard.json.
"""

import pytest

from app import scoreboard


def test_owner_hash_is_stable_and_opaque():
    a = scoreboard.owner_hash("user-123")
    assert a == scoreboard.owner_hash("user-123")
    assert a != scoreboard.owner_hash("user-456")
    assert len(a) == 12 and all(c in "0123456789abcdef" for c in a)


def test_upsert_rejects_missing_id():
    with pytest.raises(ValueError):
        scoreboard.upsert({"source": "catalog", "technical": 80}, owner="o")


def test_upsert_rejects_bad_source():
    with pytest.raises(ValueError):
        scoreboard.upsert({"id": "x", "source": "bogus", "technical": 80}, owner="o")


def test_upsert_rejects_missing_technical():
    with pytest.raises(ValueError):
        scoreboard.upsert({"id": "x", "source": "catalog"}, owner="o")


def test_query_returns_list_within_limit():
    items = scoreboard.query(window="all", scope="global", sort="overall", owner=None, limit=5)
    assert isinstance(items, list)
    assert len(items) <= 5
