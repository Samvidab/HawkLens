"""Settings loaded from env / backend/.env. Model names and keys never live in code."""
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    # Gemini
    gemini_api_key: str | None = None
    gemini_model_vision: str | None = None
    gemini_model_fast: str | None = None

    # Toolkit keys (exact SDK/API usage discovered in T0.3)
    costar_api_key: str | None = None
    vexcel_api_key: str | None = None
    matterport_api_key: str | None = None  # legacy; unused by the Matterport platform

    # Matterport platform (HTTP basic auth: token id = user, secret = password)
    mp_token_id: str | None = None
    mp_token_secret: str | None = None
    mp_api_url: str = "https://api.matterport.com/api/models/graph"
    mp_max_retries: int = 5
    mp_backoff_base_s: float = 0.5
    mp_asset_types: str = "mesh,images"  # comma list; add "pointcloud" to include
    mp_enable_webhooks: bool = False
    mp_enable_gltf_viewer: bool = False

    # Modes
    cache_mode: Literal["off", "read_write", "read_only"] = "read_write"
    engine_mode: Literal["stub", "live"] = "stub"
    nessie_mode: Literal["stub", "live"] = "stub"

    demo_city: Literal["Houston", "Los Angeles"] = "Houston"
    max_concurrent_buildings: int = 4

    # Paths
    cache_dir: Path = BACKEND_DIR / "cache"
    data_dir: Path = BACKEND_DIR / "data"


@lru_cache
def get_settings() -> Settings:
    return Settings()
