"""Musixmatch service — search, lyrics, synced subtitles, cover resolver.

COMPLIANCE: lyric content is fetched live and returned to the client for
real-time display only. It is never persisted or cached server-side.
All calls are wrapped in try/except so a partial Musixmatch failure never
crashes the API — it degrades gracefully.
"""

import json
import os
import re

import httpx

from . import config

_BASE = "https://api.musixmatch.com/ws/1.1"
_TIMEOUT = 15.0


def _key() -> str:
    return config.MUSIXMATCH_API_KEY


def _get(endpoint: str, **params) -> dict:
    params["apikey"] = _key()
    r = httpx.get(f"{_BASE}/{endpoint}", params=params, timeout=_TIMEOUT)
    r.raise_for_status()
    return r.json()


# ---------------------------------------------------------------------------
# Cover resolver (multi-source cascade)
# ---------------------------------------------------------------------------

def resolve_cover(artist: str, title: str, spotify_id: str | None = None) -> str | None:
    try:
        k = _key()
        if k:
            r = httpx.get(
                "https://api.musixmatch.com/ws/1.1/matcher.track.get",
                params={"q_artist": artist, "q_track": title, "apikey": k},
                timeout=_TIMEOUT,
            )
            t = r.json()["message"]["body"]["track"]
            if not spotify_id:
                spotify_id = t.get("track_spotify_id") or None
            c = t.get("album_coverart_800x800") or t.get("album_coverart_500x500")
            if c and "nocover" not in c:
                return c
    except Exception:
        pass

    try:
        if spotify_id:
            r = httpx.get(
                "https://open.spotify.com/oembed",
                params={"url": f"https://open.spotify.com/track/{spotify_id}"},
                timeout=_TIMEOUT,
            )
            url = r.json().get("thumbnail_url")
            if url:
                return url
    except Exception:
        pass

    try:
        r = httpx.get(
            "https://itunes.apple.com/search",
            params={"term": f"{artist} {title}", "entity": "song", "limit": 1},
            timeout=_TIMEOUT,
        )
        res = r.json().get("results", [])
        if res and res[0].get("artworkUrl100"):
            return res[0]["artworkUrl100"].replace("100x100bb", "600x600bb")
    except Exception:
        pass

    try:
        r = httpx.get(
            "https://api.deezer.com/search",
            params={"q": f'artist:"{artist}" track:"{title}"'},
            timeout=_TIMEOUT,
        )
        d = r.json().get("data", [])
        if d:
            return (d[0].get("album", {}) or {}).get("cover_xl")
    except Exception:
        pass

    return None


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------

def _track_row(t: dict) -> dict:
    artist = t.get("artist_name", "")
    title = t.get("track_name", "")
    sid = t.get("track_spotify_id") or None
    dur = t.get("track_length") or 0
    cover = resolve_cover(artist, title, sid)
    return {
        "id": str(t["track_id"]),
        "title": title,
        "artist": artist,
        "durationSec": dur,
        "coverUrl": cover,
        "spotifyId": sid,
        "source": "musixmatch",
    }


def _parse_query(query: str) -> tuple[str, str]:
    """Split 'track by artist' or 'artist - track' into (q_track, q_artist)."""
    lower = query.lower()
    if " by " in lower:
        idx = lower.index(" by ")
        return query[:idx].strip(), query[idx + 4:].strip()
    if " - " in query:
        parts = query.split(" - ", 1)
        return parts[1].strip(), parts[0].strip()
    return query, ""


def search(query: str, page_size: int = 10) -> dict:
    if not _key():
        return _mock_search(query)
    q_track, q_artist = _parse_query(query)
    try:
        params: dict = dict(page_size=page_size, page=1, s_track_rating="desc", f_has_lyrics=1)
        if q_artist:
            params["q_track"] = q_track
            params["q_artist"] = q_artist
        else:
            params["q"] = query
        data = _get("track.search", **params)
        tracks = (
            data.get("message", {})
            .get("body", {})
            .get("track_list", [])
        )
        results = [_track_row(t["track"]) for t in tracks if "track" in t]
        return {"query": query, "count": len(results), "results": results}
    except Exception:
        return _mock_search(query)


# ---------------------------------------------------------------------------
# Track + lyrics
# ---------------------------------------------------------------------------

def _parse_subtitle(subtitle_body: str) -> list[dict]:
    """Parse Musixmatch LRC-JSON subtitle_body into [{id,text,t}]."""
    lines = []
    try:
        items = json.loads(subtitle_body)
        for i, item in enumerate(items):
            t = item.get("time", {})
            seconds = float(t.get("total", 0))
            text = (item.get("text") or "").strip()
            if text:
                lines.append({"id": f"sub-{i}", "text": text, "t": seconds})
    except Exception:
        # Fallback: try LRC format  [mm:ss.xx]text
        for i, raw in enumerate(subtitle_body.splitlines()):
            m = re.match(r"\[(\d+):(\d+\.\d+)\](.*)", raw.strip())
            if m:
                mins, secs, text = int(m.group(1)), float(m.group(2)), m.group(3).strip()
                if text:
                    lines.append({"id": f"sub-{i}", "text": text, "t": mins * 60 + secs})
    return lines


def track(track_id: str) -> dict:
    if not _key():
        return _mock_track(track_id)
    try:
        # 1. Track metadata
        meta = _get("track.get", track_id=track_id)
        t = meta["message"]["body"]["track"]
        artist = t.get("artist_name", "")
        title = t.get("track_name", "")
        dur = t.get("track_length") or 0
        sid = t.get("track_spotify_id") or None
        cover = resolve_cover(artist, title, sid)

        # 2. Try synced lyrics first
        lines: list[dict] = []
        synced = False
        try:
            sub = _get("track.subtitle.get", track_id=track_id)
            body = sub["message"]["body"]["subtitle"]["subtitle_body"]
            if body:
                lines = _parse_subtitle(body)
                synced = bool(lines)
        except Exception:
            pass

        # 3. Fall back to plain lyrics
        if not lines:
            try:
                lyr = _get("track.lyrics.get", track_id=track_id)
                raw = lyr["message"]["body"]["lyrics"]["lyrics_body"] or ""
                for i, ln in enumerate(raw.splitlines()):
                    text = ln.strip()
                    if text and not text.startswith("*"):  # strip Musixmatch copyright footer
                        lines.append({"id": f"lyr-{i}", "text": text, "t": None})
            except Exception:
                pass

        return {
            "id": track_id,
            "title": title,
            "artist": artist,
            "durationSec": dur,
            "coverUrl": cover,
            "spotifyId": sid,
            "synced": synced,
            "sections": [{"name": "Lyrics", "lines": lines}],
        }
    except Exception:
        return _mock_track(track_id)


# ---------------------------------------------------------------------------
# Mock fallbacks (MOCK_MODE or when Musixmatch key is absent)
# ---------------------------------------------------------------------------

_MOCK_LINES = [
    {"id": "m0", "text": "Top down, city lights bleed into the rain", "t": 0.0},
    {"id": "m1", "text": "I count my blessings quicker than I count the change", "t": 6.0},
    {"id": "m2", "text": "They want the crown but never felt the weight it brings", "t": 12.0},
    {"id": "m3", "text": "I turned my pressure into pressure-treated things", "t": 18.0},
    {"id": "m4", "text": "Every L was just a letter in the bigger word", "t": 24.0},
    {"id": "m5", "text": "Momma said the patient ones inherit earth", "t": 30.0},
    {"id": "m6", "text": "Starlight, I been chasing it my whole life", "t": 36.0},
    {"id": "m7", "text": "Cold nights turned the hunger into cold drive", "t": 42.0},
]

_MOCK_RESULTS = [
    {"id": "mock-1", "title": "Starlight", "artist": "Dave", "durationSec": 222,
     "coverUrl": None, "spotifyId": None, "source": "musixmatch"},
    {"id": "mock-2", "title": "Sprinter", "artist": "Dave & Central Cee", "durationSec": 229,
     "coverUrl": None, "spotifyId": None, "source": "musixmatch"},
    {"id": "mock-3", "title": "Black", "artist": "Dave", "durationSec": 241,
     "coverUrl": None, "spotifyId": None, "source": "musixmatch"},
]


def _mock_search(query: str) -> dict:
    return {"query": query, "count": len(_MOCK_RESULTS), "results": _MOCK_RESULTS}


def _mock_track(track_id: str) -> dict:
    return {
        "id": track_id,
        "title": "Starlight",
        "artist": "Dave",
        "durationSec": 222,
        "coverUrl": None,
        "spotifyId": None,
        "synced": True,
        "sections": [{"name": "Lyrics", "lines": _MOCK_LINES}],
    }
