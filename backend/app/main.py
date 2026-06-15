"""16 Lab backend — core API.

Served under /api on the same origin as the static front end.
"""

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from . import config, decode, llm, mock, musixmatch, scoring, spotify

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
# Scoring (uses mock lyrics until Musixmatch is live)
# ---------------------------------------------------------------------------

@api.get("/track/{track_id}/score")
def track_score(track_id: str):
    lines = mock.lyric_lines(track_id)
    result = scoring.score_track(lines)
    result["trackId"] = track_id
    return result


# ---------------------------------------------------------------------------
# Search — Musixmatch track.search
# ---------------------------------------------------------------------------

@api.get("/search")
def search(q: str = ""):
    if not q.strip():
        raise HTTPException(400, "q is required")
    return musixmatch.search(q.strip())


# ---------------------------------------------------------------------------
# Track — metadata + lyrics (synced or plain)
# ---------------------------------------------------------------------------

@api.get("/track/{track_id}")
def track(track_id: str):
    return musixmatch.track(track_id)


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


app.mount("/api", api)
