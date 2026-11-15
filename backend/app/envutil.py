"""Read a setting from the process environment, then backend/.env.

pydantic Settings (config.py) drops keys it does not declare, so lane-owned knobs
(MAX_TOKENS_PER_SURVEY, GEMINI_MODEL_VISION_FALLBACK, CORS_ORIGINS, NESSIE_*_ID ...) are read here.
"""
from __future__ import annotations

import os

from dotenv import dotenv_values

from app.config import BACKEND_DIR


def env_file() -> str:
    """backend/.env, or RETROALPHA_ENV_FILE (tests point it at a nonexistent file to be independent of the machine's .env)."""
    return os.environ.get("RETROALPHA_ENV_FILE") or str(BACKEND_DIR / ".env")


def env_value(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    return dotenv_values(env_file()).get(name) or None
