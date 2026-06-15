"""Central config — everything comes from environment variables.

MOCK_MODE governs the external data services (Musixmatch / Scribe / LALAL).
The LLM gateway is used live whenever GATEWAY_KEY is set, so the decode lane
can be tested before any other key arrives.
"""

import os


def _bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


GATEWAY_BASE_URL: str = os.getenv(
    "GATEWAY_BASE_URL", "https://hello-world-michealijaola.replit.app/api/gateway"
).rstrip("/")
GATEWAY_KEY: str = os.getenv("GATEWAY_KEY", "")
DECODE_MODEL: str = os.getenv("DECODE_MODEL", "claude-opus-4-8")
CORRECT_MODEL: str = os.getenv("CORRECT_MODEL", "claude-haiku-4-5")
ANTHROPIC_VERSION: str = os.getenv("ANTHROPIC_VERSION", "2023-06-01")

MOCK_MODE: bool = _bool("MOCK_MODE")

MUSIXMATCH_API_KEY: str = os.getenv("MUSIXMATCH_API_KEY", "")
LALAL_LICENSE_KEY: str = os.getenv("LALAL_LICENSE_KEY", "")
ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")

SPOTIFY_CLIENT_ID: str = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET: str = os.getenv("SPOTIFY_CLIENT_SECRET", "")
SPOTIFY_REDIRECT_URI: str = os.getenv(
    "SPOTIFY_REDIRECT_URI", "https://16labs.xyz/api/spotify/callback"
)

CORS_ORIGINS: list[str] = [
    o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()
]

REQUEST_TIMEOUT: float = float(os.getenv("REQUEST_TIMEOUT", "60"))


def llm_live() -> bool:
    """The gateway is usable as soon as a key is present."""
    return bool(GATEWAY_KEY)
