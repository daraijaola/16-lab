# 16 Lab Research Brief

Current date: June 9, 2026  
Project: 16 Lab, "Decode every bar."

## Executive Direction

16 Lab should be positioned as a rap intelligence product, not just a lyric explainer. The strongest hackathon angle is:

> Upload or search a rap track, get accurate lyrics, tap any bar, and see the meaning, wordplay, references, and technical score.

The winning demo should focus on one complete flow:

1. Upload/paste audio or pick a released track.
2. Get lyrics/transcript.
3. Click a line.
4. See a bar breakdown.
5. See technical metrics.
6. Generate a shareable bar card.

The full long-term idea includes artist comparison, discovery, Songstats profiles, voice playback, and automation, but the first build should optimize for a polished, defensible demo.

## Verified Hackathon Context

Public Musicathon posts confirm the key timing and partner stack:

| Item | Current Finding |
| --- | --- |
| Event | Musicathon by Musixmatch Pro |
| Dates | June 15-21, 2026 |
| Format | Fully remote, global |
| Registration closes | June 12, 2026 |
| Prize pool | $25k+ total, including $5,000 cash |
| Partners mentioned publicly | Musixmatch Pro, Replit, ElevenLabs, Songstats, LALAL.AI, Cyanite |

Sources:

- Musixmatch LinkedIn post: https://www.linkedin.com/posts/musixmatch_musixmatch-musixmatchpro-musicathon-activity-7464631426483736576-uS1v
- Musixmatch LinkedIn announcement: https://www.linkedin.com/posts/musixmatch_musixmatch-musicathon-hackathon-activity-7461083279702683649-p82J
- LALAL.AI Reddit partner post: https://www.reddit.com/r/LALALAI/comments/1tgh5cf/hackathon_music_industry_were_teaming_up_with/

## Product Thesis

Most lyric products cover released music. 16 Lab wins by covering the messy middle:

- Freestyles.
- Radio sets.
- TikTok/YouTube clips.
- Unreleased snippets.
- Regional slang-heavy rap.
- Bars that need cultural context.

The clearest wedge is UK rap, because the product can be culturally specific instead of generic. Dave, Stormzy, Central Cee, Kojey Radical, Little Simz, Ghetts, J Hus, Skepta, Headie One, and similar artists give enough public reference material for demos while making the slang/context problem obvious.

## Competitive Landscape

### Genius

Genius is the obvious comparison: community annotations and lyrics. The weakness is slow coverage, uneven quality, and limited support for unreleased/freestyle audio.

### Musixmatch

Musixmatch has licensed lyrics, metadata, synced lyric infrastructure, and API access. For the hackathon, it should be treated as the source of truth for released tracks and metadata.

Musixmatch docs confirm the API supports authenticated access to a licensed lyrics database, with search parameters for track, artist, lyrics, common track IDs, lyrics availability, subtitles, genre, language, artist ID, sorting, and pagination.

Source: https://musixmatch.mintlify.app/api-methods

### DecodeBars

DecodeBars is a direct competitor for AI rap lyric analysis. Its public positioning includes wordplay, double entendres, cultural references, flow pattern analysis, literary device breakdown, battle judging, source transparency, and social optimization.

Source: https://www.decodebars.com/

### RHYMEBOOK

RHYMEBOOK has tools for lyric analysis, rhyme density, multisyllabic rhyme detection, vocabulary diversity, syllable consistency, sentiment, and flow/cadence analysis. This confirms there is already user demand around technical rap metrics.

Sources:

- https://www.rhymebook.com/tools/music/lyrics-analyzer
- https://www.rhymebook.com/tools/music/flow-analyzer

## Differentiation

16 Lab should not pitch itself as "Genius with AI." That is too easy to copy.

Stronger positioning:

> 16 Lab is a technical and cultural decoder for rap, starting with tracks nobody has lyrics for.

Defensible differences:

- Starts from audio, not only existing lyric text.
- Uses stem separation before transcription.
- Adds slang-aware transcript correction.
- Combines cultural explanation with measurable technical scoring.
- Creates shareable bar cards with context.
- Uses sponsor tools deeply, not as decorations.

## API And Model Findings

### Musixmatch Pro

Use for:

- Released-track search.
- Artist/track metadata.
- Licensed lyrics when available.
- Lyrics/subtitle availability checks.
- Potential analysis/metadata features if hackathon access exposes the newer Pro APIs.

Implementation note: keep Musixmatch usage central in the demo because it is the host platform. Even if upload transcription is the novel feature, the product should visibly include Musixmatch search and metadata.

### LALAL.AI

Use for:

- Vocal isolation before transcription.
- Optional stem preview in the demo: original vs isolated vocal.

Public partner material confirms LALAL.AI is a Musicathon partner and provides stem separation/audio processing. LALAL.AI has public API positioning for stem separation at scale.

Source: https://www.lalal.ai/api/

### OpenAI Audio

The original plan mentions Whisper large-v3. Current OpenAI API docs list `whisper-1` plus newer transcription models:

- `gpt-4o-mini-transcribe`
- `gpt-4o-transcribe`
- `gpt-4o-transcribe-diarize`

OpenAI docs also note a 25 MB upload limit for audio transcription endpoints and supported formats including mp3, mp4, mpeg, mpga, m4a, wav, and webm.

Source: https://platform.openai.com/docs/guides/speech-to-text

Recommended adjustment: use `gpt-4o-transcribe` or `gpt-4o-transcribe-diarize` if API budget/access allows; keep local Whisper/faster-whisper as a fallback.

### ElevenLabs

Use for:

- "Listen to this breakdown" narration.
- Accessibility feature.
- Demo polish.

ElevenLabs docs position text-to-speech as natural speech generation, with model options including Eleven v3, Eleven Multilingual v2, and Eleven Flash v2.5.

Source: https://elevenlabs.io/docs/capabilities/text-to-speech

### Cyanite

Use for:

- Mood/energy/genre/instrument tagging.
- Beat context in bar breakdowns.
- Artist/track profile enrichment.

Cyanite docs describe audio analysis, mood classifiers, emotional layers, tagging categories, and music perception metadata.

Sources:

- https://api-docs.cyanite.ai/
- https://api-docs.cyanite.ai/docs/audio-analysis-v6-classifier/

### Songstats

Use for:

- Artist profile stats.
- Streaming/social data.
- Chart/playlist proof for artist pages.

Songstats API docs describe artist, label, and track data across streaming/social services, including follower numbers, play counts, popularity, playlist positions, chart entries, DJ supports, and features.

Source: https://docs.songstats.com/

## Research Notes For Scoring Engine

Rap scoring should be framed carefully. Do not claim absolute objectivity over artistry. Claim repeatable technical metrics.

Good metrics for MVP:

| Metric | MVP Method |
| --- | --- |
| Rhyme density | Phonetic rhyme groups per line |
| Internal rhyme count | Rhyming tokens inside a line |
| End rhyme strength | Rhyme match at line endings |
| Vocabulary richness | Unique normalized words / total words |
| Multisyllabic rhyme rate | Rhyming spans with 2+ syllables |
| Syllable variance | Syllables per line/bar standard deviation |
| Reference density | LLM-extracted cultural/person/place references per 100 words |
| Wordplay density | LLM-extracted wordplay devices per 100 words |

Use algorithmic metrics for rhyme/vocab/syllables. Use LLM extraction for metaphors, cultural references, and wordplay type because pure NLP metaphor detection will be fragile in a one-week build.

Relevant research/tools:

- DopeLearning/KDD work treats rhyme density as a measurable feature of rap lyric quality and style: https://www.kdd.org/kdd2016/papers/files/adf0399-malmiA.pdf
- Research on automatic rhyme detection notes rap requires imperfect and internal rhyme handling, not only end rhymes: https://docslib.org/doc/12947631/using-automated-rhyme-detection-to-characterize-rhyming-style-in-rap-music
- Recent source separation + Whisper research supports the core idea that lyric transcription remains hard and can benefit from source separation: https://arxiv.org/abs/2506.15514

## MVP Scope

### Must Build

- Landing/upload page.
- Track analysis page.
- Musixmatch released-track search.
- Audio upload transcription path.
- Bar-by-bar breakdown panel.
- Technical scoring panel.
- Shareable bar card.
- Basic artist comparison with 2 artists or 2 tracks.

### Should Build If Time Allows

- ElevenLabs narration for selected bar breakdown.
- Cyanite mood/energy labels on track view.
- Songstats artist stats on artist page.

### Defer

- Full community corrections.
- Full discovery feed.
- TikTok/YouTube downloader automation.
- Public auth/accounts unless needed for submission.
- Large catalogue ingestion.
- Multi-artist leaderboard.

## Suggested Architecture For The Hackathon

Use a monorepo:

```txt
apps/
  web/        Next.js + Tailwind
  api/        FastAPI
packages/
  scoring/    Python scoring logic
  prompts/    Bar analysis prompts and schemas
```

Backend services:

- `lyrics_service`: Musixmatch search and lyrics fetch.
- `transcription_service`: upload -> LALAL.AI -> transcription -> slang correction.
- `analysis_service`: LLM bar breakdown, JSON schema output.
- `scoring_service`: rhyme/vocab/syllable metrics.
- `card_service`: render bar card image.

Database tables:

- `tracks`
- `lyrics`
- `bars`
- `bar_breakdowns`
- `track_scores`
- `artist_scores`
- `bar_cards`

For speed, SQLite is fine locally and Supabase/Postgres for deployment.

## Demo Script

1. Start with a released Dave track searched through Musixmatch.
2. Show lyrics and metadata.
3. Click one strong bar and show meaning, wordplay, references, and complexity.
4. Show technical score: rhyme density, internal rhymes, vocabulary richness.
5. Upload a short freestyle clip.
6. Show LALAL.AI vocal isolation -> transcription -> slang correction.
7. Generate a bar card and download/share it.
8. Finish with "this works for released tracks and for bars nobody has written down yet."

## Risk Register

| Risk | Mitigation |
| --- | --- |
| Lyrics licensing restrictions | Use Musixmatch only through allowed API display rules; do not scrape lyrics. |
| Audio upload too large | Cap demo files to 25 MB or pre-trim audio. |
| Transcription mistakes | Use short demo clips, vocal isolation, slang dictionary, and confidence flags. |
| LLM over-explains/simple bars | Force structured JSON and "do not overstate wordplay" prompt rule. |
| Scoring feels subjective | Separate "technical metrics" from "complexity score"; explain weighting. |
| Too many sponsor APIs creates shallow product | Make Musixmatch + LALAL.AI deep; add ElevenLabs/Cyanite/Songstats only where visible. |

## Immediate Checklist

- Register by June 12, 2026.
- Get hackathon/API access for Musixmatch Pro, LALAL.AI, ElevenLabs, Cyanite, Songstats.
- Create repo skeleton.
- Build the frontend first screen and API skeleton.
- Add 3 curated demo examples: released track, short freestyle clip, generated/shareable bar card.
- Lock the pitch: "lyrics plus context for rap that no lyrics platform covers."

