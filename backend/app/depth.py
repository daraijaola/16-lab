"""Depth score — an AI-judged lyricism axis, complementary to the deterministic
technical score in scoring.py.

scoring.py measures rhyme MECHANICS only, so a plain-rhyming but profound record
(protest, identity, storytelling) under-scores there. Depth is the second axis:
the model reads the WHOLE lyric block and rates six meaning/craft dimensions
against fixed anchored bands. Python computes the weighted headline so the number
is deterministic given the sub-scores, and the anchors curb model drift.

CONSISTENCY: same track -> same Depth number on every load. The model isn't
deterministic (and the gateway rejects `temperature`), so we guarantee it by
caching keyed on a lyrics HASH. A cache hit never calls the model.

PRIVACY: we NEVER persist Musixmatch lyric content. The cache stores only our
derived output (score + sub-scores + rationale); the lyrics hash IS the key.
"""

import hashlib
import json
import re
import threading
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError, field_validator

from . import config, llm

# Six dimensions, in display order. (key, human label, weight).
DIMENSIONS = [
    ("message", "Message", 0.25),
    ("imagery", "Imagery", 0.15),
    ("wordplay", "Wordplay", 0.15),
    ("references", "References", 0.15),
    ("storytelling", "Storytelling", 0.15),
    ("impact", "Impact", 0.15),
]

SYSTEM = """You are 16 Lab's depth judge — a scholar of lyricism scoring a song on \
MEANING and CRAFT QUALITY, not rhyme mechanics. You read the whole lyric block (and \
any mood/themes given) and rate SIX dimensions as integers 0-100.

Score each dimension against these FIXED anchored bands (apply to EVERY dimension):
  90-100  exceptional / canonical
  75-89   strong
  60-74   solid
  40-59   average
  20-39   weak
  0-19    absent

The six dimensions:
- message      : substance / theme / what it's actually about
- imagery      : vividness, specificity, sensory detail
- wordplay     : QUALITY (not quantity) of double meanings / metaphor
- references   : allusions, intertextuality, cultural / historical weight
- storytelling : narrative cohesion, perspective, arc
- impact       : emotional / cultural resonance

Rules:
- Judge the WRITING, not the artist's fame or popularity.
- IGNORE rhyme mechanics entirely — that is the separate technical score's job.
- A plain-rhyming but PROFOUND record (protest, identity, storytelling) SHOULD score \
high here. Do not penalise simple rhyme schemes.
- Be honest and calibrated: not every song is deep. Use the full range; reserve 90+ \
for genuinely canonical writing.

Respond with STRICT JSON only — no prose, no markdown fences — exactly:
{"message":int,"imagery":int,"wordplay":int,"references":int,"storytelling":int,\
"impact":int,"rationale":str}
The rationale is <=12 words."""


class DepthScores(BaseModel):
    message: int
    imagery: int
    wordplay: int
    references: int
    storytelling: int
    impact: int
    rationale: str = ""

    @field_validator(
        "message", "imagery", "wordplay", "references", "storytelling", "impact"
    )
    @classmethod
    def _clamp(cls, v: int) -> int:
        return max(0, min(100, int(v)))

    @field_validator("rationale")
    @classmethod
    def _trim(cls, v: str) -> str:
        return (v or "").strip()


# ---------------------------------------------------------------------------
# Cache key — sha1(trackId + "\n" + normalized joined lyrics)
# ---------------------------------------------------------------------------

_WS = re.compile(r"\s+")


def _normalize(lines: list[str]) -> str:
    """Lowercase, collapse all whitespace. Used only to build the hash key;
    the lyric text itself is never stored."""
    return _WS.sub(" ", "\n".join(lines)).strip().lower()


def cache_key(track_id: str, lines: list[str]) -> str:
    raw = f"{track_id or ''}\n{_normalize(lines)}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Persistent cache — JSON file + in-process dict, write-through.
# Survives a service restart so Depth never drifts after a deploy.
# Stores ONLY { key: {depth, sub, rationale} } — never lyric text.
# ---------------------------------------------------------------------------

_CACHE_PATH = Path(__file__).resolve().parent.parent / "data" / "depth_cache.json"
_lock = threading.Lock()


def _load_cache() -> dict:
    try:
        with open(_CACHE_PATH, encoding="utf-8") as fh:
            data = json.load(fh)
            return data if isinstance(data, dict) else {}
    except (FileNotFoundError, ValueError, OSError):
        return {}


_cache: dict = _load_cache()


def cache_get(key: str) -> dict | None:
    return _cache.get(key)


def cache_put(key: str, result: dict) -> None:
    with _lock:
        _cache[key] = result
        try:
            _CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
            tmp = _CACHE_PATH.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump(_cache, fh, ensure_ascii=False)
            tmp.replace(_CACHE_PATH)
        except OSError:
            # In-process dict still holds it; persistence is best-effort.
            pass


# ---------------------------------------------------------------------------
# Compute
# ---------------------------------------------------------------------------

def _extract_json(text: str) -> dict:
    """Pull the first {...} object out of a model response, tolerating fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def _build_prompt(lines: list[str], track: dict | None) -> str:
    track = track or {}
    title = (track.get("title") or "").strip()
    artist = (track.get("artist") or "").strip()
    mood = (track.get("mood") or "").strip()
    themes = track.get("themes") or []

    head = []
    if title or artist:
        who = " by ".join(p for p in (title and f'"{title}"', artist) if p)
        head.append(f"Track: {who}")
    if mood:
        head.append(f"Mood: {mood}")
    if themes:
        head.append("Themes: " + ", ".join(str(t) for t in themes))

    body = "\n".join(line for line in lines)
    parts = []
    if head:
        parts.append("\n".join(head))
    parts.append("Full lyrics:\n" + body)
    parts.append("Score the six dimensions now. STRICT JSON only.")
    return "\n\n".join(parts)


def score_depth(lines: list[str], track: dict | None = None) -> dict:
    """Call the model once, parse the six sub-scores, and compute the weighted
    headline in Python. Returns {"depth", "sub", "rationale"}.

    Raises llm.LLMError if the gateway is unavailable or the response can't be
    parsed (the endpoint turns that into a 502 and the FE hides the tile)."""
    cleaned = [ln for ln in lines if (ln or "").strip()]
    if not cleaned:
        raise ValueError("no lines provided")
    if not config.llm_live():
        raise llm.LLMError("GATEWAY_KEY not set")

    user = _build_prompt(cleaned, track)

    last_err: Exception | None = None
    scores: DepthScores | None = None
    for attempt in range(2):
        prompt = user if attempt == 0 else user + "\n\nReturn valid JSON only."
        # No temperature param — Anthropic-on-Vertex rejects it; anchors + cache
        # are what give us consistency.
        out = llm.messages(
            system=SYSTEM, user=prompt, model=config.DECODE_MODEL, max_tokens=300
        )
        try:
            scores = DepthScores(**_extract_json(out["text"]))
            break
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_err = exc
    if scores is None:
        raise llm.LLMError(f"could not parse depth JSON: {last_err}")

    values = {k: getattr(scores, k) for k, _, _ in DIMENSIONS}
    depth = round(sum(values[k] * w for k, _, w in DIMENSIONS))
    sub = [{"key": k, "label": label, "value": values[k]} for k, label, _ in DIMENSIONS]
    return {"depth": depth, "sub": sub, "rationale": scores.rationale}


def depth_for(track_id: str, lines: list[str], track: dict | None = None) -> dict:
    """Cache-aware entry point: hit -> stored result instantly (no model call);
    miss -> compute once, store, return."""
    key = cache_key(track_id, lines)
    hit = cache_get(key)
    if hit is not None:
        return hit
    result = score_depth(lines, track)
    cache_put(key, result)
    return result
