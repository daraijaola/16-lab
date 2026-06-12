# 16 Lab — Musicathon Build Plan (Refined)

Date: June 12, 2026 (registration deadline day)
Event: Musicathon by Musixmatch Pro, June 15–21, 2026 (remote)
Status: landing page done (`index.html`), product code 0% — this plan is what we build.

This supersedes the MVP scope in `16_lab_research_brief.md`. The research brief
stays as background; where the two disagree, this document wins.

## The one flow we build

One polished flow beats a broad half-product. Everything below serves this:

```
SEARCH PATH (pure Musixmatch)
  query → Musixmatch track.search → metadata + lyrics → tap bar → decode + score

UPLOAD PATH (Musixmatch as the matcher)
  audio → LALAL.AI vocal isolation → ElevenLabs Scribe transcript (word timestamps)
        → Claude slang correction → bars
        → Musixmatch lyrics search on transcribed lines:
            MATCH    → "this is [track] by [artist]" → licensed lyrics + metadata
            NO MATCH → "not in any catalog — bars nobody has written down"
        → tap bar → Claude decode + technical score → shareable bar card
```

The "no match" branch is the demo's killer moment: the host's own API certifies
our differentiator live. Musixmatch does real work in both halves — source of
truth for released tracks, novelty-verifier for freestyles.

## Scope

### Build (must)
- Landing → analyze page wiring (search box + dropzone become real)
- Musixmatch search: `track.search` (incl. lyrics-text search), `track.lyrics.get`, metadata
- Upload pipeline: LALAL.AI (vocal stem, async job) → Scribe (transcript + word timestamps)
- Slang correction pass (Claude Haiku) + Scribe keyterm prompting with UK slang dictionary
- Bar-by-bar decode panel (Claude Opus, structured outputs — guaranteed JSON schema)
- Scoring service (Python): rhyme density, internal rhymes, vocab richness,
  multisyllabic rate, syllable variance (pronouncing/CMUdict)
- Shareable bar card (rendered image)
- Job table + polling for async steps; **pre-processed cache for all 3 demo clips**

### Stretch (day 6 only, in this order)
1. ElevenLabs TTS narration of a bar breakdown ("listen to this decode")
2. Cyanite mood/BPM/energy chips on the track view (build against **V7**, not V6)
3. Songstats artist stats panel

### Cut (do not build)
- Artist comparison, discovery feed, community corrections, accounts,
  TikTok/YouTube ingestion, leaderboards

## Stack (verified June 12, 2026)

| Layer | Choice | Key verified facts |
|---|---|---|
| Lyrics/metadata | Musixmatch API v1.1 | `track.search`, `track.lyrics.get`; free tier = 2,000 calls/day + **30% snippet only** → hackathon Pro access is a hard dependency |
| Stem separation | LALAL.AI API v1 | OpenAPI spec, multi-stem per request, async job-based |
| Transcription | **ElevenLabs Scribe v2** (replaces OpenAI) | Word-level timestamps, keyterm prompting (≤100 terms — load slang dictionary), 2GB/10h files, diarization, async + webhooks |
| Bar analysis LLM | Claude `claude-opus-4-8` | $5/$25 per MTok; structured outputs (`output_config.format` / `messages.parse()` + Pydantic) guarantee schema-valid JSON; prompt-cache the analysis system prompt |
| Slang correction LLM | Claude `claude-haiku-4-5` | $1/$5 per MTok; cheap high-volume pass over transcripts |
| Scoring | Python (`pronouncing`, CMUdict, syllable libs) | Algorithmic metrics, deterministic — "same track, same score" |
| App | Next.js (web) + FastAPI (api) monorepo | SQLite local / Postgres deploy; deploy on **Replit** (sponsor) |
| Stretch enrichment | Cyanite V7 (GraphQL, async), Songstats (REST, `apikey` header) | Both need hackathon keys |

OpenAI is dropped from the stack: Scribe is sponsor-deep, removes the 25MB
limit concern, and its keyterm prompting attacks slang accuracy at the
transcription layer. Local faster-whisper remains an offline fallback only.

## Risk register (updated)

| Risk | Mitigation |
|---|---|
| Musixmatch free tier = 30% snippets | Request Pro access at registration TODAY; if denied, upload path is the product and search path shows snippets + metadata |
| Live demo dies on async APIs | Pre-process and cache all 3 demo clips; demo plays from cache, live upload is the backup flex |
| LLM JSON drift | Solved natively by Claude structured outputs |
| Slang transcription errors | Scribe keyterms + Haiku correction + short curated clips |
| Scope creep | Stretch items gated to day 6; cut list is final |
| API keys arrive late | Request ALL sponsor keys today even though we build narrow |

## Build order (June 12–21)

- **June 12 (today):** register; request API access for Musixmatch Pro, LALAL.AI,
  ElevenLabs, Cyanite, Songstats, Replit credits. Curate 3 demo clips
  (1 released Dave track, 1 short freestyle, 1 slang-heavy clip ≤60s).
- **June 13–14 (pre-hack prep):** monorepo skeleton, env/key plumbing, UK slang
  dictionary draft (~100 terms), bar-analysis prompt + JSON schema drafted.
- **Day 1–2 (Jun 15–16):** Musixmatch search path end-to-end (search → lyrics →
  static decode panel). Scoring service with real metrics.
- **Day 3–4 (Jun 17–18):** upload pipeline (LALAL → Scribe → Haiku correction →
  Musixmatch match/no-match). Job polling UI.
- **Day 5 (Jun 19):** Claude decode panel live on both paths; bar card renderer;
  pre-process + cache demo clips.
- **Day 6 (Jun 20):** polish, deploy to Replit, stretch items only if green;
  record backup demo video.
- **Day 7 (Jun 21):** submission, demo script rehearsal, README.

## Demo script (3 min)

1. Search "Dave — Starlight" → Musixmatch result → lyrics → tap a bar → decode + score.
2. Upload a 30s freestyle → watch pipeline chips light up: isolate → transcribe →
   **match on Musixmatch** → comes back UNMATCHED.
3. "No platform has these lyrics. 16 Lab just decoded them." → tap bar → decode → score.
4. Generate bar card → share it.
5. Close: works for released tracks AND bars nobody has written down yet.
