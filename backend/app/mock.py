"""Canned data for MOCK_MODE so the API runs with no external keys.

Scoring is always computed for real on these lines — only the *source* of the
lyrics is mocked, never the scoring math.
"""

# Placeholder, original lines (NOT real copyrighted lyrics). Real lyrics are
# fetched live from Musixmatch at runtime once that key is wired in.
_STARLIGHT = [
    "Top down, city lights bleed into the rain",
    "I count my blessings quicker than I count the change",
    "They want the crown but never felt the weight it brings",
    "I turned my pressure into pressure-treated things",
    "Every L was just a letter in the bigger word",
    "Momma said the patient ones inherit earth",
    "Starlight, I been chasing it my whole life",
    "Cold nights turned the hunger into cold drive",
]

_FREESTYLE = [
    "No beat picked, I'm just talking off the dome",
    "Mic in the kitchen, made a studio at home",
    "First take energy, I never write it twice",
    "Every other bar I'm rolling double on the dice",
    "Freestyle therapy, cheaper than the fees",
    "Stop the tape right there, that's the one",
]

_LIBRARY: dict[str, list[str]] = {
    "starlight": _STARLIGHT,
    "freestyle03": _FREESTYLE,
}


def lyric_lines(track_id: str) -> list[dict]:
    """Return [{id, text}] for a mock track (falls back to Starlight)."""
    raw = _LIBRARY.get(track_id, _STARLIGHT)
    return [{"id": f"{track_id}-{i}", "text": t} for i, t in enumerate(raw)]
