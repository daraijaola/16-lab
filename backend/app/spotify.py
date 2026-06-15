"""Spotify OAuth (Authorization Code) + playback control.

Tokens are stored server-side only, keyed by an httponly session cookie.
The client never sees a Spotify token.

Session store is an in-process dict — fine for a single-process uvicorn
deployment (one Azure VM). For multi-process / multi-worker: swap for Redis
or a DB-backed store.
"""

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.parse
from typing import Optional

import httpx

from . import config

_ACCOUNTS = "https://accounts.spotify.com"
_API = "https://api.spotify.com/v1"
_TIMEOUT = 10.0
_COOKIE = "16lab_sid"

# In-process session store: sid -> {access_token, refresh_token, expires_at}
_sessions: dict[str, dict] = {}

# Pending OAuth states: state -> sid (prevents CSRF)
_pending: dict[str, str] = {}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _creds() -> tuple[str, str]:
    return config.SPOTIFY_CLIENT_ID, config.SPOTIFY_CLIENT_SECRET


def _refresh(session: dict) -> dict:
    cid, secret = _creds()
    r = httpx.post(
        f"{_ACCOUNTS}/api/token",
        data={
            "grant_type": "refresh_token",
            "refresh_token": session["refresh_token"],
        },
        auth=(cid, secret),
        timeout=_TIMEOUT,
    )
    r.raise_for_status()
    data = r.json()
    session["access_token"] = data["access_token"]
    session["expires_at"] = time.time() + int(data.get("expires_in", 3600)) - 60
    if data.get("refresh_token"):
        session["refresh_token"] = data["refresh_token"]
    return session


def _bearer(session: dict) -> str:
    if time.time() > session.get("expires_at", 0):
        _refresh(session)
    return session["access_token"]


def _get_session(sid: Optional[str]) -> Optional[dict]:
    if not sid:
        return None
    return _sessions.get(sid)


# ---------------------------------------------------------------------------
# Public API (called by main.py)
# ---------------------------------------------------------------------------

def login_url() -> str:
    """Build the Spotify authorise URL and stash the CSRF state."""
    cid, _ = _creds()
    sid = secrets.token_urlsafe(24)
    state = secrets.token_urlsafe(16)
    _pending[state] = sid
    params = urllib.parse.urlencode({
        "response_type": "code",
        "client_id": cid,
        "redirect_uri": config.SPOTIFY_REDIRECT_URI,
        "scope": "user-read-playback-state user-modify-playback-state user-read-currently-playing",
        "state": state,
    })
    return f"{_ACCOUNTS}/authorize?{params}", sid


def handle_callback(code: str, state: str) -> Optional[str]:
    """Exchange auth code for tokens; return the session id (or None on error)."""
    sid = _pending.pop(state, None)
    if not sid:
        return None
    cid, secret = _creds()
    try:
        r = httpx.post(
            f"{_ACCOUNTS}/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            },
            auth=(cid, secret),
            timeout=_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        _sessions[sid] = {
            "access_token": data["access_token"],
            "refresh_token": data["refresh_token"],
            "expires_at": time.time() + int(data.get("expires_in", 3600)) - 60,
        }
        return sid
    except Exception:
        return None


def now_playing(sid: Optional[str]) -> dict:
    """Return {isPlaying, progressMs, trackId, durationMs} or {isPlaying:false}."""
    session = _get_session(sid)
    if not session:
        return {"isPlaying": False, "connected": False}
    try:
        token = _bearer(session)
        r = httpx.get(
            f"{_API}/me/player",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
        if r.status_code == 204:
            return {"isPlaying": False, "connected": True}
        r.raise_for_status()
        data = r.json()
        item = data.get("item") or {}
        return {
            "isPlaying": data.get("is_playing", False),
            "progressMs": data.get("progress_ms", 0),
            "trackId": item.get("id"),
            "durationMs": item.get("duration_ms", 0),
            "connected": True,
        }
    except Exception:
        return {"isPlaying": False, "connected": True}


def play(sid: Optional[str], spotify_id: str) -> dict:
    """Start playing a track. Returns {ok, nonPremium}."""
    session = _get_session(sid)
    if not session:
        return {"ok": False, "connected": False}
    try:
        token = _bearer(session)
        r = httpx.put(
            f"{_API}/me/player/play",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json={"uris": [f"spotify:track:{spotify_id}"]},
            timeout=_TIMEOUT,
        )
        if r.status_code == 403:
            return {"ok": False, "nonPremium": True, "connected": True}
        if r.status_code in (200, 204):
            return {"ok": True, "connected": True}
        return {"ok": False, "connected": True}
    except Exception:
        return {"ok": False, "connected": True}


def pause(sid: Optional[str]) -> dict:
    """Pause playback. Returns {ok}."""
    session = _get_session(sid)
    if not session:
        return {"ok": False, "connected": False}
    try:
        token = _bearer(session)
        r = httpx.put(
            f"{_API}/me/player/pause",
            headers={"Authorization": f"Bearer {token}"},
            timeout=_TIMEOUT,
        )
        if r.status_code in (200, 204):
            return {"ok": True, "connected": True}
        return {"ok": False, "connected": True}
    except Exception:
        return {"ok": False, "connected": True}
