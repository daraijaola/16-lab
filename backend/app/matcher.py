"""Musixmatch match / no-match check for an uploaded freestyle transcript.

Query track.search by q_lyrics using the most distinctive lines; for each
candidate, fetch its lyrics LIVE and measure word-overlap against the transcript.

COMPLIANCE: candidate lyric content is compared transiently in memory and NEVER
stored. The only thing returned (and later cached in the job) is the match
metadata: {title, artist, trackId}.
"""

import re

from . import musixmatch

_WORD = re.compile(r"[a-z']+")
_MATCH_THRESHOLD = 0.55  # fraction of transcript words that must appear in candidate


def _words(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def _distinctive(lines: list[dict], n: int = 3) -> list[str]:
    """Longest lines carry the most distinctive lyrics for a q_lyrics search."""
    ranked = sorted(lines, key=lambda ln: len(ln.get("text", "")), reverse=True)
    return [ln["text"] for ln in ranked[:n] if ln.get("text")]


def match(lines: list[dict]) -> dict:
    """Return {"matched": bool, "match": {title,artist,trackId} | None}."""
    no_match = {"matched": False, "match": None}
    if not lines:
        return no_match

    try:
        q = " ".join(_distinctive(lines))
        data = musixmatch._get(
            "track.search", q_lyrics=q, page_size=3, s_track_rating="desc", f_has_lyrics=1
        )
        tracks = data.get("message", {}).get("body", {}).get("track_list", [])
    except Exception:
        return no_match

    transcript = set(_words(" ".join(ln.get("text", "") for ln in lines)))
    if not transcript:
        return no_match

    for item in tracks:
        t = item.get("track") or {}
        tid = str(t.get("track_id", "") or "")
        if not tid:
            continue
        try:
            full = musixmatch.track(tid)  # live fetch; lyrics used transiently only
            cand_words: set[str] = set()
            for sec in full.get("sections", []):
                for ln in sec.get("lines", []):
                    cand_words.update(_words(ln.get("text", "")))
        except Exception:
            continue
        if not cand_words:
            continue
        overlap = len(transcript & cand_words) / len(transcript)
        if overlap >= _MATCH_THRESHOLD:
            return {
                "matched": True,
                "match": {
                    "title": t.get("track_name", ""),
                    "artist": t.get("artist_name", ""),
                    "trackId": tid,
                },
            }
    return no_match
