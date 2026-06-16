"""Async upload pipeline (one background thread per job, single worker).

Stages drive the FE "pipeline chips light up" moment:
  uploaded -> transcribing -> correcting -> matching -> done   (or error)

The result is the SAME shape /api/track returns, plus {source, matched, match},
so the existing decode view renders it with zero new UI.
"""

import threading

from . import correct, jobs, matcher, scribe

MAX_DURATION = 150.0  # seconds (~2 min cap; we can only measure post-transcription)


def process(job_id: str, audio_path: str) -> None:
    try:
        jobs.set_stage(job_id, "transcribing")
        words = scribe.transcribe(audio_path, keyterms=correct.SLANG_TERMS)
        lines = scribe.chunk_lines(words)
        dur = scribe.duration(words)
        if not lines:
            jobs.set_error(job_id, "No speech detected in the audio.")
            return
        if dur > MAX_DURATION:
            jobs.set_error(job_id, "Clip too long — keep it under ~2 minutes.")
            return

        jobs.set_stage(job_id, "correcting")
        lines = correct.correct_lines(lines)

        jobs.set_stage(job_id, "matching")
        m = matcher.match(lines)

        result = {
            "id": job_id,
            "title": "Freestyle — Untitled",
            "artist": "You",
            "durationSec": int(round(dur)),
            "coverUrl": None,
            "spotifyId": None,
            "synced": True,
            "sections": [{"name": "Transcript", "lines": lines}],
            "source": "upload",
            "matched": m["matched"],
            "match": m["match"],
        }
        jobs.set_result(job_id, result)
    except scribe.ScribeError as exc:
        jobs.set_error(job_id, f"Transcription failed: {exc}")
    except Exception as exc:  # never let a worker thread die silently
        jobs.set_error(job_id, f"Pipeline error: {exc}")


def start(job_id: str, audio_path: str) -> None:
    threading.Thread(target=process, args=(job_id, audio_path), daemon=True).start()
