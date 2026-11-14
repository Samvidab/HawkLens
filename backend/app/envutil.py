"""Read a setting from the process environment, then backend/.env.

pydantic Settings (config.py) drops keys it does not declare, so lane-owned knobs
(MAX_TOKENS_PER_SURVEY, GEMINI_MODEL_VISION_FALLBACK, CORS_ORIGINS, NESSIE_*_ID ...) are read here.
"""
from __future__ import annotations

import os

from dotenv import dotenv_values

from app.config import BACKEND_DIR


def env_value(name: str) -> str | None:
    if os.environ.get(name):
        return os.environ[name]
    return dotenv_values(BACKEND_DIR / ".env").get(name) or None
