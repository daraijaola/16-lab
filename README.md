# 16 Lab — Decode every bar.

> A rap intelligence lab. Upload a freestyle or search any released track, get accurate lyrics, tap any bar for its meaning and wordplay, and see scores for craft and depth.

**Live:** [16labs.xyz](https://16labs.xyz)

Built for [Musicathon by Musixmatch Pro](https://www.musixmatch.com) · June 2026

---

## What it does

16 Lab covers the messy middle of rap — freestyles, radio sets, unreleased snippets, and slang-heavy bars that no platform has lyrics for yet.

**Search path** — pick any released track, get licensed lyrics via Musixmatch Pro, tap a bar, see the decode and technical score.

**Upload path** — drop an audio file, watch the pipeline run:

```
Audio → LALAL.AI vocal isolation → ElevenLabs Scribe transcription
      → Claude slang correction → bars
      → Musixmatch catalog match:
          MATCH    → "this is [track] by [artist]" → licensed lyrics
          NO MATCH → "not in any catalog — bars nobody has written down yet"
      → tap bar → Claude decode + technical score → shareable bar card
```

The "no match" moment is the product's core differentiator: Musixmatch itself certifies the freestyle isn't in any catalog.

---

## Stack

| Layer | Technology |
|---|---|
| Lyrics & metadata | Musixmatch Pro API v1.1 |
| Vocal stem separation | LALAL.AI API v1 |
| Transcription | ElevenLabs Scribe v2 (word timestamps + slang keyterms) |
| Bar decode | Claude `claude-opus-4-8` (structured outputs) |
| Slang correction | Claude `claude-haiku-4-5` |
| Technical scoring | Python — `pronouncing` / CMUdict (deterministic, no LLM) |
| Backend | FastAPI — served at `/api` behind nginx |
| Frontend | Static HTML/CSS — served at root |
| Infrastructure | Azure VM + nginx + Certbot SSL |
| LLM gateway | Replit (Claude credits) |

---

## Scoring engine

The pen score is fully deterministic — same track, same score, every time. No LLM guessing.

| Metric | Method |
|---|---|
| Rhyme density | End-rhyme detection via phoneme matching |
| Internal rhymes | Mid-line phoneme chain detection |
| Multisyllabic rate | CMUdict syllable count per rhyme group |
| Vocab richness | Type-token ratio across the track |
| Syllable variance | Per-bar syllable consistency |

Rhyme groups are mapped to text spans and highlighted in the UI — tapping any metric reveals the bars behind it.

---

## Backend modules

| Module | Purpose |
|---|---|
| `main.py` | FastAPI app, all routes |
| `decode.py` | Bar-by-bar Claude decode with prompt caching |
| `scoring.py` | Deterministic NLP scoring engine |
| `musixmatch.py` | Search + lyrics integration |
| `pipeline.py` | Full upload pipeline (LALAL → Scribe → correction → match) |
| `scribe.py` | ElevenLabs Scribe transcription + word timestamps |
| `correct.py` | Claude Haiku slang correction pass |
| `matcher.py` | Musixmatch catalog match on transcribed lines |
| `depth.py` | Cultural depth scoring |
| `scoreboard.py` | Leaderboard system |
| `compare.py` | Track comparison |
| `spotify.py` | Spotify metadata integration |
| `jobs.py` | Async job table + polling |
| `ratelimit.py` | Rate limiting |

---

## Pages

| Route | Page |
|---|---|
| `/` | Landing |
| `/lab` | Search + upload (main product) |
| `/decode` | Bar decode view |
| `/decodes` | Decode library |
| `/scores` | Leaderboard |
| `/results` | Search results |

---

## Compliance

Musixmatch lyric content is **never stored or cached** — fetched live at display time only, per contest rules. Our own pipeline outputs (decodes, scores, transcripts) may be cached.

All API keys are env-only. Nothing is hardcoded or committed to the repo.

---

## Docs

- [`musicathon_build_plan.md`](./musicathon_build_plan.md) — full build plan, stack decisions, risk register, demo script
- [`16_lab_research_brief.md`](./16_lab_research_brief.md) — product thesis, competitive landscape, differentiation
- [`backend/README.md`](./backend/README.md) — backend setup and API endpoints
