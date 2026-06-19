"""Freestyle transcript bar shaping.

Scribe gives word timings, then our first chunker makes rough timed lines. That
rough split is mechanical, so this pass asks Haiku to reshape corrected chunks
into lyric-style rap bars before matching, scoring, and display.
"""

import json
import re

from . import config, llm

BAR_SHAPER_MODEL = "claude-haiku-4-5"

SYSTEM = """You are 16 Lab's freestyle lyric line editor.
You receive a corrected rap transcript split into rough timed chunks.

Your job is to reshape those chunks into clean lyric bars like a synced lyrics
provider would show them.

HARD RULES:
- Keep the artist's words in order.
- Do not rewrite meaning, invent words, censor, translate, or explain.
- You may merge short fragments into one complete bar.
- You may split a long chunk into two bars when it clearly contains two bars.
- Prefer natural rap bar boundaries: cadence, breath, end rhyme, punchline turn,
  and complete lyrical thoughts.
- Avoid tiny one-word/phrase rows unless it is clearly an ad-lib.
- Return STRICT JSON only: an array of objects with:
  {"text": string, "source_start": number, "source_end": number}
- source_start/source_end are zero-based inclusive indexes from the input chunks
  that supplied the bar.
No prose, no markdown fences."""

_WORD_RE = re.compile(r"[A-Za-z0-9']+")
_BATCH = 45


def _extract_array(text: str) -> list:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON array in response")
    return json.loads(text[start : end + 1])


def _token_count(text: str) -> int:
    return len(_WORD_RE.findall(text.lower()))


def _fallback(lines: list[dict]) -> list[dict]:
    return [{**ln, "id": f"L{i}"} for i, ln in enumerate(lines)]


def _shape_batch(batch: list[dict]) -> list[dict]:
    numbered = "\n".join(f"{i}\t{ln.get('text', '')}" for i, ln in enumerate(batch))
    user = (
        f"Rough transcript chunks ({len(batch)} rows, index<TAB>text):\n"
        f"{numbered}\n\n"
        "Return the reshaped lyric bars as strict JSON."
    )

    out = llm.messages(
        system=SYSTEM,
        user=user,
        model=BAR_SHAPER_MODEL,
        max_tokens=2200,
    )
    arr = _extract_array(out["text"])
    if not isinstance(arr, list):
        raise ValueError("bar shaper did not return an array")

    shaped: list[dict] = []
    for item in arr:
        if not isinstance(item, dict):
            continue
        text = str(item.get("text", "")).strip()
        if not text:
            continue
        try:
            start = int(item.get("source_start", 0))
            end = int(item.get("source_end", start))
        except (TypeError, ValueError):
            continue
        start = max(0, min(start, len(batch) - 1))
        end = max(start, min(end, len(batch) - 1))
        shaped.append({"text": text, "t": batch[start].get("t"), "_source_end": end})

    in_tokens = _token_count(" ".join(str(ln.get("text", "")) for ln in batch))
    out_tokens = _token_count(" ".join(ln["text"] for ln in shaped))
    if not shaped or in_tokens == 0:
        raise ValueError("empty bar shaper output")
    if out_tokens < in_tokens * 0.68 or out_tokens > in_tokens * 1.45:
        raise ValueError("bar shaper changed too much text")
    return shaped


def shape_bars(lines: list[dict]) -> list[dict]:
    """Return lyric-style bars, preserving approximate start timestamps.

    This is best-effort. If the gateway/model is unavailable or the model returns
    unsafe JSON, we keep the existing corrected chunks so upload still works.
    """
    if not lines or not config.llm_live():
        return _fallback(lines)

    shaped: list[dict] = []
    try:
        for i in range(0, len(lines), _BATCH):
            shaped.extend(_shape_batch(lines[i : i + _BATCH]))
    except Exception:
        return _fallback(lines)

    out: list[dict] = []
    for i, ln in enumerate(shaped):
        clean = {k: v for k, v in ln.items() if not k.startswith("_")}
        clean["id"] = f"L{i}"
        out.append(clean)
    return out or _fallback(lines)
