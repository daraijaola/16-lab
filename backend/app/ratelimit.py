"""Lightweight in-process rate limiting for the paid endpoints.

Single uvicorn worker (see project notes), so a plain dict + lock is enough —
no Redis. Keyed per client IP (behind nginx, the real IP is the first hop in
X-Forwarded-For). Sliding window: we keep recent hit timestamps per bucket and
reject once the count in the trailing window is reached.

Purpose: a public URL hits ElevenLabs STT + Opus on every upload/decode/depth/
compare call, all of which cost money. This caps a single client without
getting in a real user's way.
"""

import threading
import time

from fastapi import HTTPException, Request

_lock = threading.Lock()
_hits: dict[str, list[float]] = {}


def _client_key(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def check(request: Request, bucket: str, limit: int, window: float) -> None:
    """Allow `limit` calls per `window` seconds for this client+bucket.

    Raises 429 (with a Retry-After-style hint) once the limit is hit.
    """
    key = f"{bucket}:{_client_key(request)}"
    now = time.time()
    cutoff = now - window
    with _lock:
        q = _hits.setdefault(key, [])
        # Drop timestamps outside the window.
        q[:] = [t for t in q if t >= cutoff]
        if len(q) >= limit:
            retry = max(1, int(q[0] + window - now) + 1)
            raise HTTPException(
                status_code=429,
                detail=f"Too many requests — slow down and try again in ~{retry}s.",
                headers={"Retry-After": str(retry)},
            )
        q.append(now)
        # Bound memory: occasionally drop empty/stale buckets.
        if len(_hits) > 5000:
            for k in [k for k, v in _hits.items() if not v or v[-1] < cutoff]:
                _hits.pop(k, None)
