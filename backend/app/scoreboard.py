"""Scoreboard — persistent dual-axis scores for every track/freestyle that gets
decoded. Powers scores.html (leaderboard + compare).

COMPLIANCE: an entry stores ONLY our own outputs + public metadata — never lyric
content (catalog or freestyle transcript). The board links back to the decode
view, which re-fetches/re-derives lyrics live. We whitelist fields on the way in.

Persistence mirrors the depth cache: in-process dict in front of a JSON file
(backend/data/scoreboard.json, gitignored), write-through, survives restart.
Single uvicorn worker, so a simple lock is enough.
"""

import hashlib
import json
import threading
import time
from pathlib import Path

CAP = 300  # max entries; eviction protects catalog + owned entries (see _evict)

_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
_STORE = _DATA_DIR / "scoreboard.json"
_lock = threading.Lock()


def _load() -> dict:
    try:
        with open(_STORE, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


_board: dict = _load()


def _persist() -> None:
    try:
        _DATA_DIR.mkdir(parents=True, exist_ok=True)
        tmp = _STORE.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(_board, fh, ensure_ascii=False)
        tmp.replace(_STORE)
    except OSError:
        pass


def _migrate() -> None:
    """Backfill the `overall` field on entries persisted before it existed, so
    legacy rows still rank under the default Overall board."""
    changed = False
    for e in _board.values():
        if "overall" not in e:
            d = e.get("depth")
            t = e.get("technical", 0)
            e["overall"] = None if d is None else int(round((t + d) / 2))
            changed = True
    if changed:
        _persist()


_migrate()


def owner_hash(uid: str) -> str:
    """Short, non-reversible hash of the anonymous 16lab_uid cookie."""
    return hashlib.sha1(f"16lab|{uid}".encode()).hexdigest()[:12]


def _clamp(v, lo: int = 0, hi: int = 100):
    try:
        return max(lo, min(hi, int(round(float(v)))))
    except (TypeError, ValueError):
        return 0


def _clean_metrics(items, n: int):
    """Whitelist metric/sub-score shape: [{key,label,value}]. Drops anything
    else (so no stray text — e.g. lyric fragments — can ride along)."""
    out = []
    if isinstance(items, list):
        for it in items[:n]:
            if isinstance(it, dict) and "value" in it:
                out.append(
                    {
                        "key": str(it.get("key", ""))[:24],
                        "label": str(it.get("label", ""))[:40],
                        "value": _clamp(it.get("value")),
                    }
                )
    return out


def upsert(payload: dict, owner: str) -> dict:
    """UPSERT by id. Builds the entry from a strict whitelist — only our scores
    and public metadata are ever stored, never lyric content."""
    eid = str(payload.get("id") or "").strip()
    if not eid:
        raise ValueError("id required")
    source = payload.get("source")
    if source not in ("catalog", "freestyle"):
        raise ValueError("source must be 'catalog' or 'freestyle'")
    if payload.get("technical") is None:
        raise ValueError("technical is required (deterministic axis)")

    depth = payload.get("depth")
    depth_sub = payload.get("depthSub")
    technical = _clamp(payload.get("technical"))
    depth_val = None if depth is None else _clamp(depth)
    # overall = mean of the two axes; omitted (None) until Depth lands, so a
    # Technical-only entry doesn't rank in the default Overall/Today board.
    overall = None if depth_val is None else int(round((technical + depth_val) / 2))
    entry = {
        "id": eid[:120],
        "source": source,
        "title": str(payload.get("title") or "")[:200],
        "artist": str(payload.get("artist") or "")[:200],
        "coverUrl": (str(payload["coverUrl"])[:500] if payload.get("coverUrl") else None),
        "spotifyId": (str(payload["spotifyId"])[:64] if payload.get("spotifyId") else None),
        "technical": technical,
        "metrics": _clean_metrics(payload.get("metrics"), 6),
        "depth": depth_val,
        "depthSub": (None if depth_sub is None else _clean_metrics(depth_sub, 6)),
        "depthRationale": (
            str(payload["depthRationale"])[:300] if payload.get("depthRationale") else None
        ),
        "overall": overall,
        "owner": owner,
        "ts": int(time.time()),
    }
    with _lock:
        _board[entry["id"]] = entry
        _evict(owner)
        _persist()
    return entry


def _evict(current_owner: str) -> None:
    """Keep the board under CAP. Evict oldest NON-owned freestyles first, then
    oldest freestyles, and only touch catalog entries if nothing else remains —
    so freestyle test-spam can never bury real catalog tracks."""
    while len(_board) > CAP:
        items = list(_board.values())
        fs_other = [e for e in items if e["source"] == "freestyle" and e["owner"] != current_owner]
        fs_any = [e for e in items if e["source"] == "freestyle"]
        pool = fs_other or fs_any or items
        victim = min(pool, key=lambda e: e["ts"])
        _board.pop(victim["id"], None)


def get(entry_id: str) -> dict | None:
    return _board.get(entry_id)


def _utc_day_start(now: float | None = None) -> int:
    """Epoch seconds at 00:00 UTC of the current day (daily board boundary)."""
    import datetime as _dt
    n = _dt.datetime.now(_dt.timezone.utc) if now is None else _dt.datetime.fromtimestamp(now, _dt.timezone.utc)
    midnight = _dt.datetime(n.year, n.month, n.day, tzinfo=_dt.timezone.utc)
    return int(midnight.timestamp())


def query(
    window: str = "today",
    scope: str = "global",
    sort: str = "overall",
    owner: str | None = None,
    limit: int = 300,
):
    """Global leaderboard. window=today restricts to the current UTC day;
    scope=mine restricts to the caller's owner hash. Sorting:
      - overall: only entries with a computed overall (both axes); desc.
      - technical: all entries (Technical is always present); desc.
      - depth: all entries, higher depth first, null-depth last.
    Ties always break by most-recent ts."""
    items = list(_board.values())

    if window == "today":
        start = _utc_day_start()
        items = [e for e in items if e["ts"] >= start]

    if scope == "mine":
        items = [e for e in items if owner and e["owner"] == owner]

    # Stable base order: ts desc so ties break by most-recent.
    items.sort(key=lambda e: e["ts"], reverse=True)

    if sort == "recent":
        pass  # already ts desc — the decode library / recents feed
    elif sort == "depth":
        items.sort(
            key=lambda e: (e["depth"] is not None, e["depth"] if e["depth"] is not None else -1),
            reverse=True,
        )
    elif sort == "technical":
        items.sort(key=lambda e: e["technical"], reverse=True)
    else:  # overall (default) — Technical-only entries omitted until Depth lands
        items = [e for e in items if e.get("overall") is not None]
        items.sort(key=lambda e: e["overall"], reverse=True)

    return items[: max(1, min(500, limit))]
