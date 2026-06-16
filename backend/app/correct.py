"""Slang-aware transcript correction via Claude Haiku (CORRECT_MODEL).

Scribe mishears slang and proper nouns. This pass fixes transcription errors and
UK-rap slang spelling WITHOUT changing meaning, and without merging or splitting
lines — the line count, order and timestamps must stay exactly aligned for the
karaoke player. On any failure it returns the input unchanged (best-effort).

No temperature param to the gateway (Anthropic-on-Vertex rejects it).
"""

import json

from . import config, llm

# Compact UK-rap / road slang reference (<=100 terms) with canonical spellings.
# Doubles as Scribe `keyterms` biasing so accuracy improves before this runs.
SLANG_TERMS = [
    "mandem", "gyaldem", "wagwan", "wasteman", "roadman", "endz", "manor",
    "yard", "trap", "bando", "block", "ends", "opps", "opp", "oppblock",
    "gang", "gng", "ged", "cuz", "fam", "blud", "bruv", "akh", "rudeboy",
    "skeng", "shank", "rambo", "ramz", "corn", "kitchen", "spinner", "stica",
    "wap", "burner", "strap", "mash", "ting", "tingz", "peng", "pengting",
    "buff", "calm", "safe", "sound", "lengs", "lurk", "creep", "dip", "duppy",
    "cheffed", "splash", "wet", "dotty", "rambo", "nank", "spin", "swing",
    "trapping", "bagging", "whipping", "cooking", "pebs", "food", "work",
    "p", "ps", "paigon", "paro", "moist", "wetwipe", "donny", "gally",
    "galdem", "wifey", "link", "linkup", "beef", "violation", "vio",
    "active", "cheesed", "vexed", "gassed", "long", "bait", "dead", "dench",
    "garms", "creps", "trims", "drip", "iced", "froze", "bandz", "racks",
    "stacks", "guala", "bread", "cheddar", "wonga", "gwop", "bagged",
    "olympic", "duck", "ducking", "boyed", "moed", "smoked", "deeped",
    "cheesing", "lacking", "slipping", "tryna", "gonna", "wanna", "innit",
]
# Dedupe (preserve order) and cap at 100 — Scribe `keyterms` allows many but the
# spec keeps the dictionary <=100 terms.
SLANG_TERMS = list(dict.fromkeys(SLANG_TERMS))[:100]

SYSTEM = """You are 16 Lab's transcript corrector for UK rap and drill freestyles.
You receive an automatic speech-to-text transcript split into numbered lines.
Your ONLY job is to fix transcription mistakes — mishears, wrong homophones, and
slang/proper-noun spelling — so each line reads as the artist actually said it.

HARD RULES:
- Return EXACTLY one corrected string per input line, in the same order. Never
  merge, split, add or drop lines — the count must match exactly (timestamps
  depend on it).
- Do NOT rewrite, paraphrase, censor, translate or "improve" the lyrics. Keep the
  artist's words, slang and grammar. Only fix what was clearly mis-transcribed.
- Keep slang spelled the UK-rap way (e.g. "mandem", "wagwan", "innit", "endz",
  "ting", "skeng", "trap", "opps", "gyaldem"), not "corrected" into standard English.
- If a line is already correct, return it unchanged.

Respond with STRICT JSON only — a single array of strings, one per line, no keys,
no prose, no markdown fences."""


def _extract_array(text: str) -> list:
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise ValueError("no JSON array in response")
    return json.loads(text[start : end + 1])


# Correct in bounded batches so a long (e.g. 7-min) transcript never overruns the
# model's output budget — that would length-mismatch and silently skip correction.
_BATCH = 40


def _correct_batch(batch: list[dict]) -> list[dict]:
    """Correct one batch; return it unchanged on any failure (best-effort)."""
    numbered = "\n".join(f"{i}\t{ln['text']}" for i, ln in enumerate(batch))
    dictionary = ", ".join(SLANG_TERMS)
    user = (
        "UK-rap slang reference (spell these the slang way, do not standardise):\n"
        f"{dictionary}\n\n"
        f"Transcript ({len(batch)} lines, index<TAB>text):\n{numbered}\n\n"
        f"Return a JSON array of exactly {len(batch)} corrected strings, in order."
    )
    try:
        out = llm.messages(
            system=SYSTEM, user=user, model=config.CORRECT_MODEL, max_tokens=1600
        )
        arr = _extract_array(out["text"])
        if isinstance(arr, list) and len(arr) == len(batch):
            return [
                {**batch[i], "text": (str(arr[i]).strip() or batch[i]["text"])}
                for i in range(len(batch))
            ]
    except Exception:
        pass
    return batch


def correct_lines(lines: list[dict]) -> list[dict]:
    """Return lines with corrected `text`, preserving id/t and exact count/order.
    Batched so length always matches even for long uploads."""
    if not lines or not config.llm_live():
        return lines
    out: list[dict] = []
    for i in range(0, len(lines), _BATCH):
        out.extend(_correct_batch(lines[i : i + _BATCH]))
    return out
