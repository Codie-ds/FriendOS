"""
FriendOS configuration.
Loads and validates required environment variables from .env.
"""

import os
from dotenv import load_dotenv

load_dotenv()


def _require_env(name: str) -> str:
    """Return the value of an environment variable or raise with a clear message."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


GEMMA_API_KEY: str = _require_env("GEMMA_API_KEY")
GEMMA_MODEL: str = _require_env("GEMMA_MODEL")
MONGODB_URI: str = _require_env("MONGODB_URI")

# CORS origins – extend via CORS_ORIGINS env var (comma-separated) if needed.
_default_origins = ["http://localhost:3000", "http://localhost:5173"]
_extra = os.getenv("CORS_ORIGINS", "")
CORS_ORIGINS: list[str] = _default_origins + ([o.strip() for o in _extra.split(",") if o.strip()] if _extra else [])
