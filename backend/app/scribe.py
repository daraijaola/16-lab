"""ElevenLabs Speech-to-Text (Scribe) — word-level transcription.

POST https://api.elevenlabs.io/v1/speech-to-text  (multipart/form-data)
  file=<audio>, model_id=scribe_v1, timestamps_granularity=word,
  diarize=false, language_code=en, [keyterms=<JSON array> to bias slang].
Header: xi-api-key.

Response (verified against the live API docs):
  {language_code, language_probability, text, words:[{text,start,end,type,...}]}
  where `type` is "word" | "spacing" | "audio_event". We keep only "word"
  entries (with their start/end seconds) and chunk them into bars/lines.
"""

import httpx

from . import config

ENDPOINT = "https://api.elevenlabs.io/v1/speech-to-text"
MODEL = "scribe_v1"
_TIMEOUT = 600.0  # long enough for ~7-min uploads


class ScribeError(RuntimeError):
    pass


def transcribe(path: str, keyterms: list[str] | None = None) -> list[dict]:
    """Return the list of word objects (type=="word") with start/end times."""
    if not config.ELEVENLABS_API_KEY:
        raise ScribeError("ELEVENLABS_API_KEY not set")

    form = {
        "model_id": MODEL,
        "timestamps_granularity": "word",
        "diarize": "false",
        "language_code": "en",
    }
    if keyterms:
        # Bias transcription toward UK-rap slang spellings before correction.
        # Sent as repeated `keyterms` form fields (each term must be <50 chars).
        form["keyterms"] = [t for t in keyterms[:100] if t and len(t) < 50]
    headers = {"xi-api-key": config.ELEVENLABS_API_KEY}
    fname = path.rsplit("/", 1)[-1]

    def _call(data: dict) -> httpx.Response:
        with open(path, "rb") as fh:
            return httpx.post(
                ENDPOINT,
                data=data,
                files={"file": (fname, fh)},
                headers=headers,
                timeout=_TIMEOUT,
            )

    try:
        resp = _call(form)
        if resp.status_code in (400, 422) and "keyterms" in form:
            # Never let the (optional) biasing param break the core call.
            resp = _call({k: v for k, v in form.items() if k != "keyterms"})
    except httpx.HTTPError as exc:
        raise ScribeError(f"scribe request failed: {exc}") from exc

    if resp.status_code != 200:
        raise ScribeError(f"scribe returned {resp.status_code}: {resp.text[:300]}")

    body = resp.json()
    return [
        w
        for w in (body.get("words") or [])
        if w.get("type") == "word" and (w.get("text") or "").strip()
    ]


def chunk_lines(words: list[dict], max_words: int = 9, gap: float = 0.6) -> list[dict]:
    """Group words into bars: break on a pause longer than `gap` seconds or after
    `max_words`, whichever comes first. Each line keeps the start time `t` of its
    first word so the karaoke player can track it."""
    lines: list[dict] = []
    cur: list[str] = []
    cur_start: float | None = None
    prev_end: float | None = None

    for w in words:
        s = float(w.get("start", 0.0))
        e = float(w.get("end", s))
        txt = (w.get("text") or "").strip()
        if not txt:
            continue
        broke_on_pause = prev_end is not None and (s - prev_end) > gap
        if cur and (broke_on_pause or len(cur) >= max_words):
            lines.append({"text": " ".join(cur), "t": round(cur_start or 0.0, 2)})
            cur = []
            cur_start = None
        if not cur:
            cur_start = s
        cur.append(txt)
        prev_end = e

    if cur:
        lines.append({"text": " ".join(cur), "t": round(cur_start or 0.0, 2)})

    for i, ln in enumerate(lines):
        ln["id"] = f"L{i}"
    return lines


def duration(words: list[dict]) -> float:
    """End time of the last spoken word — the effective transcript duration."""
    return float(words[-1].get("end", 0.0)) if words else 0.0
