"""Bar decode service — turns one lyric line into structured analysis.

Uses the LLM gateway when a key is present; otherwise returns a clearly
labelled mock so the API is exercisable with no keys at all.
"""

import json

from pydantic import BaseModel, Field, ValidationError

from . import config, llm

SYSTEM = """You are 16 Lab, a rap lyric decoder. You explain a single bar with \
cultural and technical accuracy, with a strong ear for UK rap slang and references.

Return ONLY a JSON object, no prose, no markdown fences, with these keys:
- "meaning": one or two sentences, plain explanation of what the bar says.
- "wordplay": the device(s) at work (puns, double entendres, homophones). \
If the bar is plain, say so honestly — do not invent wordplay.
- "references": array of short strings for any cultural/person/place/work references (may be empty).
- "cultural": one sentence of UK/genre cultural context, or null if none applies.

Be concise and do not overstate. Output valid JSON only."""


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


def decode_bar(text: str, context: str | None = None) -> BarDecode:
    text = (text or "").strip()
    if not text:
        raise ValueError("empty bar")

    if not config.llm_live():
        return _mock(text)

    user = f'Decode this bar:\n"{text}"'
    if context:
        user += f"\n\nContext (track/section/mood): {context}"

    last_err: Exception | None = None
    for attempt in range(2):
        prompt = user if attempt == 0 else user + "\n\nReturn valid JSON only."
        out = llm.messages(
            system=SYSTEM, user=prompt, model=config.DECODE_MODEL, max_tokens=600
        )
        try:
            return BarDecode(**_extract_json(out["text"]))
        except (ValueError, ValidationError, json.JSONDecodeError) as exc:
            last_err = exc
    raise llm.LLMError(f"could not parse decode JSON: {last_err}")
