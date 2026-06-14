# 16 Lab — Musicathon Build Plan (Refined)

Date: June 12, 2026 (registration deadline day)
Event: Musicathon by Musixmatch Pro, June 15 00:00 UTC – June 21 23:59 UTC (remote)
Status: landing page done (`index.html`), product code 0% — this plan is what we build.

## Official rules (from contest T&Cs — confirmed)

- **Judging:** Musixmatch team selects winners on **creativity, technical
  execution, quality of Musixmatch Pro API integration, and overall impact**.
- **Prizes — top 3 only, no partner tracks:** 1st $3,000 + 1yr Scale plan;
  2nd $1,500 + 1yr Scale plan; 3rd $500 + 1yr Grow plan. Strategy: aim top 3.
- **API access:** every registered participant gets a **Musixmatch Pro key with
  Scale-plan access for the contest period** → the 30%-snippet risk is gone
  during the week. Key is contest-use only; don't share or reuse it after.
- **Entry requirements:** meaningful Musixmatch Pro API integration, working
  demo + brief written description, original work, ONE submission per team.
- **⚠️ COMPLIANCE — no caching Musixmatch content:** rules forbid bulk-download,
  caching, scraping, or persistent storage of Musixmatch API content beyond
  real-time display. So: lyrics are fetched live at display time, never stored.
  We MAY cache our own pipeline outputs (LALAL stems, Scribe transcripts,
  Claude decodes, scores) — those are not Musixmatch content.
- Replit credits are claimable and optional.

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
- **Visible rhyme/flow highlighting** — the scoring service returns rhyme groups
  mapped to text spans; the transcript colors end rhymes, internal rhymes and
  multisyllabic chains, and tapping a metric reveals the spans behind it. Makes
  the pen score tangible and proves the NLP is real (not just an LLM guess).
- **Musixmatch mood/theme/genre context** — pull the track's mood, themes and
  genre and show them as context chips, and feed them into the decode prompt.
  Widens Musixmatch surface area beyond search + lyrics.get (depth-of-integration).
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
| LLM access | **Replit AI gateway** (proxy in front of the model) | Routes all Claude traffic through Replit so model access is billed to the Replit credits; keys live in **Replit Secrets** (server-only, never in repo/frontend); gateway dashboard tracks cost / requests / tokens per key. Opus 4.8 on the decode lane, Haiku on the correction lane. Keep a direct-key env var as demo-day fallback. |
| Stretch enrichment | Cyanite V7 (GraphQL, async), Songstats (REST, `apikey` header) | Both need hackathon keys |

OpenAI is dropped from the stack: Scribe is sponsor-deep, removes the 25MB
limit concern, and its keyterm prompting attacks slang accuracy at the
transcription layer. Local faster-whisper remains an offline fallback only.

## Risk register (updated)

| Risk | Mitigation |
|---|---|
| ~~Musixmatch free tier = 30% snippets~~ | RESOLVED — all participants get Scale-plan Pro keys for the contest week |
| Musixmatch caching ban (disqualification risk) | Never store lyric content; live fetch at display; cache only our own pipeline outputs; record a backup demo VIDEO as the fallback, not cached lyric responses |
| Live demo dies on async APIs | Pre-process and cache our pipeline outputs (stems/transcripts/decodes) for 3 demo clips; Musixmatch calls stay live but they're fast REST; backup video recorded day 6 |
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
