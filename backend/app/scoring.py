"""Deterministic technical scoring + rhyme spans for highlighting.

Pure Python, no LLM, no network. Uses the `pronouncing` library (bundled
CMUdict) for phonetic rhyme/syllable data, with heuristic fallbacks for
out-of-dictionary words so it never crashes on slang.

The same track always scores the same — that's the point.
"""

import re
import statistics

try:
    import pronouncing  # bundles CMUdict
except Exception:  # pragma: no cover - fallback if unavailable
    pronouncing = None

_WORD_RE = re.compile(r"[A-Za-z']+")
_VOWELS = "aeiouy"


def _syllables(word: str) -> int:
    w = word.lower().strip("'")
    if pronouncing:
        phones = pronouncing.phones_for_word(w)
        if phones:
            return max(1, pronouncing.syllable_count(phones[0]))
    # heuristic: count vowel groups
    groups = re.findall(r"[aeiouy]+", w)
    return max(1, len(groups))


def _rhyme_key(word: str) -> str:
    """A string that is equal for words that rhyme."""
    w = word.lower().strip("'")
    if pronouncing:
        phones = pronouncing.phones_for_word(w)
        if phones:
            return pronouncing.rhyming_part(phones[0])
    # heuristic: from the last vowel group to the end of the word
    idxs = [i for i, c in enumerate(w) if c in _VOWELS]
    if not idxs:
        return w
    last = idxs[-1]
    while last - 1 in idxs:
        last -= 1
    return w[last:]


def _multisyllabic(word: str) -> bool:
    return _syllables(word) >= 2


def _tokens(text: str):
    """Yield (word, start, end) for each word, preserving char offsets."""
    for m in _WORD_RE.finditer(text):
        yield m.group(0), m.start(), m.end()


def score_track(lines: list[dict]) -> dict:
    """lines: [{"id": str, "text": str}]  ->  {score, metrics, rhymes}."""
    # Per-line token tables.
    line_tokens = []  # [(line_id, [(word, start, end, key, multi)])]
    for ln in lines:
        toks = []
        for word, start, end in _tokens(ln["text"]):
            toks.append((word, start, end, _rhyme_key(word), _multisyllabic(word)))
        line_tokens.append((ln["id"], toks))

    # Assign a rhyme group id per distinct key that appears 2+ times overall.
    key_counts: dict[str, int] = {}
    for _, toks in line_tokens:
        for _, _, _, key, _ in toks:
            key_counts[key] = key_counts.get(key, 0) + 1
    group_ids: dict[str, int] = {}
    for key, count in key_counts.items():
        if count >= 2:
            group_ids[key] = len(group_ids)

    rhymes: list[dict] = []
    total_words = 0
    rhyming_words = 0
    multi_rhyming = 0
    internal_pairs = 0
    syllables_per_line: list[int] = []
    unique_words: set[str] = set()

    for line_id, toks in line_tokens:
        total_words += len(toks)
        syllables_per_line.append(sum(_syllables(w) for w, *_ in toks) or 0)
        end_key = toks[-1][3] if toks else None
        seen_keys_in_line: dict[str, int] = {}

        for word, start, end, key, multi in toks:
            unique_words.add(word.lower())
            if key in group_ids:
                rhyming_words += 1
                if multi:
                    multi_rhyming += 1
                # type: end rhyme if it's the line-final word, else internal
                is_end = (word, start, end, key, multi) is toks[-1]
                rtype = "multi" if multi else ("end" if is_end else "internal")
                rhymes.append(
                    {
                        "lineId": line_id,
                        "start": start,
                        "end": end,
                        "group": group_ids[key],
                        "type": rtype,
                    }
                )
                seen_keys_in_line[key] = seen_keys_in_line.get(key, 0) + 1

        # internal rhyme pairs within this line
        for cnt in seen_keys_in_line.values():
            if cnt >= 2:
                internal_pairs += cnt - 1

    def pct(n: float) -> int:
        return max(0, min(100, round(n)))

    n_lines = max(1, len(lines))
    total = max(1, total_words)

    rhyme_density = pct(100 * rhyming_words / total)
    internal = pct(100 * internal_pairs / total * 3.0)
    vocab = pct(100 * len(unique_words) / total)
    multisyllabic = pct(100 * multi_rhyming / max(1, rhyming_words))
    if len(syllables_per_line) > 1:
        stdev = statistics.pstdev(syllables_per_line)
        variance = pct(100 * min(1.0, stdev / 4.0))
    else:
        variance = 0

    metrics = [
        {"key": "rhyme", "label": "Rhyme density", "value": rhyme_density},
        {"key": "internal", "label": "Internal rhymes", "value": internal},
        {"key": "vocab", "label": "Vocabulary richness", "value": vocab},
        {"key": "multi", "label": "Multisyllabic rate", "value": multisyllabic},
        {"key": "variance", "label": "Syllable variance", "value": variance},
    ]
    weights = {"rhyme": 0.3, "internal": 0.2, "vocab": 0.25, "multi": 0.15, "variance": 0.1}
    score = round(sum(m["value"] * weights[m["key"]] for m in metrics))

    return {"score": score, "metrics": metrics, "rhymes": rhymes}
