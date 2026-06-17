"""16 Lab backend — core API.

Served under /api on the same origin as the static front end.
"""

import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from pydantic import BaseModel

from . import (
    compare,
    config,
    decode,
    depth,
    jobs,
    llm,
    musixmatch,
    pipeline,
    scoreboard,
    scoring,
    spotify,
)

app = FastAPI(title="16 Lab API", version="0.2.0")

if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=True,
    )

api = FastAPI()  # sub-app mounted at /api keeps all routes under one prefix


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@api.get("/health")
def health():
    return {
        "ok": True,
        "mock_mode": config.MOCK_MODE,
        "llm_live": config.llm_live(),
        "musixmatch": bool(config.MUSIXMATCH_API_KEY),
        "spotify": bool(config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET),
    }


# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------

@api.get("/llm/ping")
def llm_ping():
    if not config.llm_live():
        raise HTTPException(503, "GATEWAY_KEY not set")
    try:
        return llm.ping()
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))


# ---------------------------------------------------------------------------
# Decode
# ---------------------------------------------------------------------------

class TrackMeta(BaseModel):
    title: str | None = None
    artist: str | None = None
    mood: str | None = None
    themes: list[str] | None = None


class DecodeRequest(BaseModel):
    # The front end sends the WHOLE lyric block plus the target index so the
    # model reads the bar in context. Keep this contract (see decode.py).
    lines: list[str]
    target: int
    track: TrackMeta | None = None


@api.post("/decode/bar")
def decode_bar(req: DecodeRequest):
    try:
        track = req.track.model_dump() if req.track else None
        return decode.decode_bar(req.lines, req.target, track).model_dump()
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))


# ---------------------------------------------------------------------------
# Search — Musixmatch track.search
# ---------------------------------------------------------------------------

@api.get("/search")
def search(q: str = ""):
    if not q.strip():
        raise HTTPException(400, "q is required")
    return musixmatch.search(q.strip())


# ---------------------------------------------------------------------------
# Track — metadata + lyrics (synced or plain). Real data only: if the track or
# its lyrics can't be fetched we return an error, never canned demo lyrics.
# ---------------------------------------------------------------------------

@api.get("/track/{track_id}")
def track(track_id: str):
    try:
        return musixmatch.track(track_id)
    except musixmatch.TrackUnavailable as exc:
        raise HTTPException(502, str(exc))


# ---------------------------------------------------------------------------
# Spotify OAuth
# ---------------------------------------------------------------------------

@api.get("/spotify/login")
def spotify_login(response: Response):
    if not (config.SPOTIFY_CLIENT_ID and config.SPOTIFY_CLIENT_SECRET):
        raise HTTPException(503, "Spotify credentials not configured")
    url, sid = spotify.login_url()
    r = RedirectResponse(url=url, status_code=302)
    # Set cookie so we can restore the session on callback
    r.set_cookie(
        key=spotify._COOKIE,
        value=sid,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=600,
    )
    return r


@api.get("/spotify/callback")
def spotify_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    if error or not code or not state:
        return RedirectResponse(url="/?spotify_error=1", status_code=302)
    sid = spotify.handle_callback(code, state)
    if not sid:
        return RedirectResponse(url="/?spotify_error=1", status_code=302)
    # Figure out which track page the user came from (stored in cookie)
    # and send them back there; default to decode page.
    track_id = request.cookies.get("16lab_track", "")
    back = f"/decode.html?id={track_id}" if track_id else "/decode.html"
    r = RedirectResponse(url=back, status_code=302)
    r.set_cookie(
        key=spotify._COOKIE,
        value=sid,
        httponly=True,
        samesite="lax",
        secure=True,
        max_age=60 * 60 * 8,  # 8 hours
    )
    return r


@api.get("/spotify/now")
def spotify_now(request: Request):
    sid = request.cookies.get(spotify._COOKIE)
    return spotify.now_playing(sid)


class PlayRequest(BaseModel):
    spotifyId: str


@api.put("/spotify/play")
def spotify_play(req: PlayRequest, request: Request):
    sid = request.cookies.get(spotify._COOKIE)
    if not req.spotifyId:
        raise HTTPException(400, "spotifyId required")
    return spotify.play(sid, req.spotifyId)


@api.put("/spotify/pause")
def spotify_pause(request: Request):
    sid = request.cookies.get(spotify._COOKIE)
    return spotify.pause(sid)


# ---------------------------------------------------------------------------
# Score — stateless: accepts the rendered lines, returns score + rhyme spans.
# Offsets are guaranteed to align with the displayed text because the FE sends
# exactly what it rendered. Never stores any lyric content.
# ---------------------------------------------------------------------------

class ScoreRequest(BaseModel):
    lines: list[dict]


@api.post("/score")
def score_lines(req: ScoreRequest):
    if not req.lines:
        raise HTTPException(400, "lines required")
    return scoring.score_track(req.lines)


# ---------------------------------------------------------------------------
# Depth — AI-judged lyricism axis, cached for consistency.
# Same track -> same number on every load (cache hit = no model call). We store
# only our derived output keyed on a lyrics hash; never the lyric text itself.
# ---------------------------------------------------------------------------

class DepthRequest(BaseModel):
    trackId: str
    lines: list[str]
    track: TrackMeta | None = None


@api.post("/depth")
def depth_score(req: DepthRequest):
    if not req.trackId or not req.lines:
        raise HTTPException(400, "trackId and lines required")
    try:
        meta = req.track.model_dump() if req.track else None
        return depth.depth_for(req.trackId, req.lines, meta)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))


# ---------------------------------------------------------------------------
# Compare — short AI verdict on which of two songs is the deeper write, grounded
# in their Depth sub-scores. Sends ONLY our derived scores + public metadata,
# never lyric content. Never 500s: falls back to a deterministic verdict.
# ---------------------------------------------------------------------------

class CompareSide(BaseModel):
    title: str | None = None
    artist: str | None = None
    depth: int | None = None
    depthSub: list[dict] | None = None
    depthRationale: str | None = None


class CompareRequest(BaseModel):
    a: CompareSide
    b: CompareSide


@api.post("/compare")
def compare_tracks(req: CompareRequest):
    return compare.compare(req.a.model_dump(), req.b.model_dump())


# ---------------------------------------------------------------------------
# Upload pipeline — Scribe → correction → Musixmatch match → freestyle decode.
# Async job; FE polls /upload/{jobId} then loads /upload/{jobId}/result into the
# existing decode view. The stored audio (the user's own file) is streamed back
# for the karaoke player. We store our pipeline outputs only — never lyric content.
# ---------------------------------------------------------------------------

_UPLOAD_DIR = Path(__file__).resolve().parent.parent.parent / "uploads"
_MAX_BYTES = 90 * 1024 * 1024  # ~90MB (covers ~7 min, incl. WAV)
_MAX_UPLOAD_AGE = 24 * 3600  # delete stored uploads older than a day
_AUDIO_EXT = {"mp3", "wav", "m4a", "aac", "ogg", "flac", "webm", "mp4"}
_MIME = {
    "mp3": "audio/mpeg", "wav": "audio/wav", "m4a": "audio/mp4",
    "aac": "audio/aac", "ogg": "audio/ogg", "flac": "audio/flac",
    "webm": "audio/webm", "mp4": "audio/mp4",
}


def _sweep_uploads() -> None:
    """Best-effort cleanup so stored audio can't pile up on disk over time."""
    try:
        now = time.time()
        for f in _UPLOAD_DIR.glob("*"):
            try:
                if f.is_file() and now - f.stat().st_mtime > _MAX_UPLOAD_AGE:
                    f.unlink()
            except OSError:
                pass
    except OSError:
        pass


@api.post("/upload")
async def upload(file: UploadFile = File(...)):
    ctype = file.content_type or ""
    ext = os.path.splitext(file.filename or "")[1].lower().lstrip(".")
    if not (ctype.startswith("audio/") or ext in _AUDIO_EXT):
        raise HTTPException(415, "Upload an audio file (MP3, WAV, M4A…).")
    if ext not in _AUDIO_EXT:
        ext = "mp3"

    _UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    _sweep_uploads()
    jid = jobs.create(ext)
    dest = _UPLOAD_DIR / f"{jid}.{ext}"
    size = 0
    try:
        with open(dest, "wb") as out:
            while True:
                chunk = await file.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                if size > _MAX_BYTES:
                    out.close()
                    dest.unlink(missing_ok=True)
                    jobs.set_error(jid, "File too large (max 90MB / ~7 min).")
                    raise HTTPException(413, "File too large (max 90MB / ~7 min).")
                out.write(chunk)
    finally:
        await file.close()

    pipeline.start(jid, str(dest))
    return {"jobId": jid}


@api.get("/upload/{job_id}")
def upload_status(job_id: str):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    out = {"jobId": job_id, "stage": j["stage"]}
    if j.get("error"):
        out["error"] = j["error"]
    if j.get("result"):
        out["matched"] = j["result"].get("matched")
    return out


@api.get("/upload/{job_id}/result")
def upload_result(job_id: str):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    if j["stage"] == "error":
        raise HTTPException(500, j.get("error") or "pipeline error")
    if j["stage"] != "done" or not j.get("result"):
        raise HTTPException(409, "not ready")
    return j["result"]


@api.get("/upload/{job_id}/audio")
def upload_audio(job_id: str):
    j = jobs.get(job_id)
    if not j:
        raise HTTPException(404, "unknown job")
    ext = j.get("ext", "mp3")
    path = _UPLOAD_DIR / f"{job_id}.{ext}"
    if not path.exists():
        raise HTTPException(404, "audio not found")
    return FileResponse(str(path), media_type=_MIME.get(ext, "application/octet-stream"))


# ---------------------------------------------------------------------------
# Scoreboard — dual-axis leaderboard fed by what users actually decode.
# Stores only our outputs + public metadata (never lyric content). Entries are
# upserted by id; "mine" filtering uses an anonymous httponly 16lab_uid cookie.
# ---------------------------------------------------------------------------

_UID_COOKIE = "16lab_uid"


class ScoreboardEntry(BaseModel):
    # Pydantic drops any extra fields, so a stray lyrics/lines field can't ride
    # in; scoreboard.upsert also rebuilds the entry from a strict whitelist.
    id: str
    source: str
    title: str | None = None
    artist: str | None = None
    coverUrl: str | None = None
    spotifyId: str | None = None
    technical: int
    metrics: list[dict] | None = None
    depth: int | None = None
    depthSub: list[dict] | None = None
    depthRationale: str | None = None


def _uid(request: Request) -> str | None:
    return request.cookies.get(_UID_COOKIE)


@api.post("/scoreboard")
def scoreboard_post(req: ScoreboardEntry, request: Request, response: Response):
    uid = _uid(request)
    issue = not uid
    if issue:
        uid = secrets.token_hex(8)
    try:
        entry = scoreboard.upsert(req.model_dump(), scoreboard.owner_hash(uid))
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    if issue:
        response.set_cookie(
            _UID_COOKIE, uid, httponly=True, samesite="lax", secure=True,
            max_age=60 * 60 * 24 * 365,
        )
    return entry


@api.get("/scoreboard")
def scoreboard_list(
    request: Request,
    window: str = "today",
    scope: str = "global",
    sort: str = "overall",
    limit: int = 300,
):
    uid = _uid(request)
    owner = scoreboard.owner_hash(uid) if uid else None
    return scoreboard.query(window=window, scope=scope, sort=sort, owner=owner, limit=limit)


@api.get("/scoreboard/{entry_id}")
def scoreboard_get(entry_id: str):
    e = scoreboard.get(entry_id)
    if not e:
        raise HTTPException(404, "not found")
    return e


app.mount("/api", api)
