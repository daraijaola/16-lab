"""Bar decode service — turns one lyric line into structured analysis.

Uses the LLM gateway when a key is present; otherwise returns a clearly
labelled mock so the API is exercisable with no keys at all.
"""

import json

from pydantic import BaseModel, Field, ValidationError

from . import config, llm

SYSTEM = """You are 16 Lab's decode engine — a scholar of rap lyricism with deep \
expertise in UK rap, drill, grime and road culture, alongside US hip-hop, literary \
devices, phonetics and flow. You read bars the way the sharpest annotators and battle \
analysts do: closely, with an ear for what sits beneath the surface.

Before you answer, work the bar through these layers:
1. Literal surface meaning.
2. Figurative / second meanings — metaphor, simile, extended metaphor.
3. Wordplay — puns, double and triple entendres, homophones, slang flips, names or \
words hidden inside phrases.
4. References — people, places, brands, events, other songs or bars, film, scripture, history.
5. Cultural / regional context — UK slang, postcodes, road life, patois, genre conventions.
6. Sonic devices where notable — internal rhyme, alliteration, assonance, multisyllabic chains.

HONESTY (this matters most): rap is often deep, but not every bar is. Decode to the depth \
the bar actually has. If a line is plain, say so plainly — never invent wordplay or \
references that aren't there. Separate what's clearly intended from a plausible read \
(hedge with "likely" / "could"). Never fabricate a reference. Insight and accuracy beat \
cleverness.

Use any context given (artist, track, surrounding bars, mood, themes) to read the bar in \
its narrative — the meaning frequently depends on the lines around it.

Output ONLY a JSON object — no prose, no markdown fences — with exactly these keys:
- "meaning": 1-3 sentences. What the bar actually says, including the deeper or second \
meaning when there is one.
- "wordplay": name the specific device(s) and unpack how they work — spell out both senses \
of a pun/entendre/homophone. If the bar is plain, say there is no significant wordplay.
- "references": array of short strings for real references only; empty array if none.
- "cultural": one sentence of UK / genre / regional context, or null if none applies.

Be precise, go deep where depth exists, and stay honest where it doesn't."""


class BarDecode(BaseModel):
    meaning: str
    wordplay: str
    references: list[str] = Field(default_factory=list)
    cultural: str | None = None


def _extract_json(text: str) -> dict:
    """Pull the first {...} object out of a model response, tolerating fences."""
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def _mock(text: str) -> BarDecode:
    return BarDecode(
        meaning=f"(mock) A plain reading of: “{text}”.",
        wordplay="(mock) No live model — set GATEWAY_KEY to decode for real.",
        references=[],
        cultural=None,
    )


def _build_prompt(lines: list[str], target: int, track: dict | None) -> str:
    """Render the whole lyric block with the target bar marked, plus metadata.

    Sending every bar (not just the target line) is deliberate: the decode is
    only as good as the context, and rap meaning routinely depends on the lines
    around a bar.
    """
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

    numbered = "\n".join(
        f"{'>>' if i == target else '  '} {i + 1:>2}  {line}"
        for i, line in enumerate(lines)
    )

    parts = []
    if head:
        parts.append("\n".join(head))
    parts.append(
        "Full lyrics below; the bar to decode is marked >> (line "
        f"{target + 1}):\n{numbered}"
    )
    parts.append(f'Decode line {target + 1}: "{lines[target].strip()}"')
    return "\n\n".join(parts)


def decode_bar(lines: list[str], target: int, track: dict | None = None) -> BarDecode:
    """Decode one bar (`lines[target]`) reading it in full-song context."""
    if not lines:
        raise ValueError("no lines provided")
    if not isinstance(target, int) or target < 0 or target >= len(lines):
        raise ValueError("target index out of range")
    if not (lines[target] or "").strip():
        raise ValueError("empty bar")

    if not config.llm_live():
        return _mock(lines[target].strip())

    user = _build_prompt(lines, target, track)

    last_err: Exception | None = None
    for attempt in range(2):
        prompt = user if attempt == 0 else user + "\n\nReturn valid JSON only."
        out = llm.messages(
            system=SYSTEM, user=prompt, model=config.DECODE_MODEL, max_tokens=900
        )
        try:
            return BarDecode(**_extract_json(out["text"]))
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_err = exc
    raise llm.LLMError(f"could not parse decode JSON: {last_err}")
