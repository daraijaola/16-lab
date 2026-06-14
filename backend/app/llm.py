"""Thin client for the Anthropic Messages API, called through the gateway.

The gateway is a transparent passthrough: POST {base}/v1/messages with an
x-api-key header and anthropic-version header. We never hold a first-party
Anthropic key here — only the gateway key, which lives in the environment.
"""

import httpx

from . import config


class LLMError(RuntimeError):
    pass


def _endpoint() -> str:
    return f"{config.GATEWAY_BASE_URL}/v1/messages"


def messages(
    *,
    user: str,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = 1024,
    temperature: float = 0.4,
) -> dict:
    """Call the gateway and return {"text": str, "model": str}."""
    if not config.GATEWAY_KEY:
        raise LLMError("GATEWAY_KEY is not set")

    body: dict = {
        "model": model or config.DECODE_MODEL,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": user}],
    }
    if system:
        body["system"] = system

    headers = {
        "x-api-key": config.GATEWAY_KEY,
        "anthropic-version": config.ANTHROPIC_VERSION,
        "content-type": "application/json",
    }

    try:
        resp = httpx.post(
            _endpoint(), json=body, headers=headers, timeout=config.REQUEST_TIMEOUT
        )
    except httpx.HTTPError as exc:
        raise LLMError(f"gateway request failed: {exc}") from exc

    if resp.status_code != 200:
        raise LLMError(f"gateway returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    parts = data.get("content") or []
    text = "".join(p.get("text", "") for p in parts if p.get("type") == "text")
    return {"text": text, "model": data.get("model", "")}


def ping() -> dict:
    """Tiny call to confirm the gateway routes and which model answers."""
    out = messages(user="Reply with exactly: gateway ok", max_tokens=16, temperature=0)
    return {"ok": "gateway ok" in out["text"].lower(), "model": out["model"]}
