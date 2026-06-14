"""16 Lab backend — core API.

Served under /api on the same origin as the static front end. This is the
core slice: gateway health, bar decode (live LLM), and deterministic scoring.
Musixmatch / upload / scores endpoints layer on after.
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import config, decode, llm, mock, scoring

app = FastAPI(title="16 Lab API", version="0.1.0")

if config.CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.CORS_ORIGINS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

api = FastAPI()  # sub-app mounted at /api keeps all routes under one prefix


@api.get("/health")
def health():
    return {"ok": True, "mock_mode": config.MOCK_MODE, "llm_live": config.llm_live()}


@api.get("/llm/ping")
def llm_ping():
    if not config.llm_live():
        raise HTTPException(503, "GATEWAY_KEY not set")
    try:
        return llm.ping()
    except llm.LLMError as exc:
        raise HTTPException(502, str(exc))


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


@api.get("/track/{track_id}/score")
def track_score(track_id: str):
    # Lyrics come from the mock library now; live Musixmatch lyrics later.
    lines = mock.lyric_lines(track_id)
    result = scoring.score_track(lines)
    result["trackId"] = track_id
    return result


app.mount("/api", api)
