"""Song-vs-song compare — a short, AI-written verdict on which record is the
deeper WRITE, grounded in the Depth axis (depth.py) we already computed.

COMPLIANCE: we pass ONLY our own derived outputs (Depth headline + the six
Depth sub-scores + the one-line rationale) plus public title/artist — NEVER any
lyric content. The model reasons about the numbers + its own prior rationale,
not the words.

Consistency isn't critical here (it's an opinion line), but we still avoid
`temperature` (Vertex rejects it) and keep the prompt anchored + tiny. If the
gateway is down or the reply won't parse, we fall back to a deterministic
verdict built straight from the Depth numbers.
"""

import json

from pydantic import BaseModel, ValidationError

from . import config, llm

# Sub-score labels in display order — mirrors depth.DIMENSIONS so the prompt
# reads the same axes the rest of the app shows.
_SUB_ORDER = ["message", "imagery", "wordplay", "references", "storytelling", "impact"]

SYSTEM = """You are 16 Lab's compare judge. Two songs have each been scored for \
DEPTH (lyricism / meaning, 0-100) on six dimensions: message, imagery, wordplay, \
references, storytelling, impact. You are given each song's Depth headline and its \
six sub-scores (and a short prior note). Decide which song is the DEEPER WRITE and \
say why, in one tight, concrete sentence.

Rules:
- Judge on DEPTH only — ignore rhyme mechanics / technical craft.
- Ground the reason in the actual dimensions where the gap is biggest (name them).
- Be honest and specific; no hype, no fabrication. If they're genuinely level, say so.
- Refer to songs by their title, not "Song A/B".

Respond with STRICT JSON only — no prose, no fences — exactly:
{"winner":"a"|"b"|"tie","verdict":string}
The verdict is <= 35 words."""


class CompareInput(BaseModel):
    title: str | None = None
    artist: str | None = None
    depth: int | None = None
    depthSub: list[dict] | None = None
    depthRationale: str | None = None


class _Verdict(BaseModel):
    winner: str = "tie"
    verdict: str = ""


def _extract_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def _sub_map(item: dict) -> dict[str, int]:
    out: dict[str, int] = {}
    for m in item.get("depthSub") or []:
        k = m.get("key")
        v = m.get("value")
        if k and isinstance(v, (int, float)):
            out[str(k)] = int(v)
    return out


def _name(item: dict, fallback: str) -> str:
    return (item.get("title") or "").strip() or fallback


def _render_side(tag: str, item: dict) -> str:
    sub = _sub_map(item)
    parts = [f"{k}={sub[k]}" for k in _SUB_ORDER if k in sub]
    line = (
        f'{tag}: "{_name(item, tag)}" by {item.get("artist") or "Unknown"} — '
        f'Depth {item.get("depth")}'
    )
    if parts:
        line += " (" + ", ".join(parts) + ")"
    if (item.get("depthRationale") or "").strip():
        line += f'. Note: {item["depthRationale"].strip()}'
    return line


def _fallback(a: dict, b: dict) -> dict:
    """Deterministic verdict from the Depth numbers when the model is unavailable."""
    na, nb = _name(a, "Track A"), _name(b, "Track B")
    da, db = a.get("depth"), b.get("depth")
    if da is None or db is None:
        return {"winner": "tie", "verdict": "Both need a Depth score before they can be compared."}
    if da == db:
        return {"winner": "tie", "verdict": f"Dead level on depth — {na} and {nb} both land at {da}."}
    # biggest sub-score gap, named, in the winner's favour
    sa, sb = _sub_map(a), _sub_map(b)
    winner, wname, gap = ("a", na, da - db) if da > db else ("b", nb, db - da)
    diffs = [(k, (sa.get(k, 0) - sb.get(k, 0)) * (1 if winner == "a" else -1)) for k in _SUB_ORDER]
    diffs.sort(key=lambda kv: kv[1], reverse=True)
    edge = diffs[0][0] if diffs and diffs[0][1] > 0 else None
    why = f" — strongest on {edge}" if edge else ""
    return {"winner": winner, "verdict": f"{wname} is the deeper write (+{gap} depth){why}."}


def compare(a: dict, b: dict) -> dict:
    """Return {"winner": "a"|"b"|"tie", "verdict": str}. Never raises."""
    if not config.llm_live():
        return _fallback(a, b)
    if a.get("depth") is None or b.get("depth") is None:
        return _fallback(a, b)

    user = (
        _render_side("A", a)
        + "\n"
        + _render_side("B", b)
        + '\n\nWhich is the deeper write, and why? STRICT JSON only.'
    )
    try:
        # The gateway currently only serves DECODE_MODEL (opus-4-8); a verdict is
        # tiny so the cost is negligible, and the deterministic fallback covers any
        # gateway/model error anyway.
        out = llm.messages(
            system=SYSTEM, user=user, model=config.DECODE_MODEL, max_tokens=160
        )
        v = _Verdict(**_extract_json(out["text"]))
        winner = v.winner if v.winner in ("a", "b", "tie") else "tie"
        verdict = (v.verdict or "").strip()
        if not verdict:
            return _fallback(a, b)
        return {"winner": winner, "verdict": verdict}
    except (llm.LLMError, ValueError, ValidationError, json.JSONDecodeError, KeyError):
        return _fallback(a, b)
