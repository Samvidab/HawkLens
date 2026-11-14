import json

import asyncio

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import events, media
from app.agents.replan import ReplanError, replan
from app.config import get_settings
from app.envutil import env_value
from app.schemas.goal import OwnerAction
from app.schemas.layout import Layout
from app.storage import data_path, read_json
from app.widgets.registry import json_schemas

DEFAULT_CORS = "http://localhost:5173,http://localhost:3000"  # local frontend dev servers


def cors_origins() -> list[str]:
    """CORS_ORIGINS: comma-separated frontend origins (e.g. https://retroalpha.example.com)."""
    return [o.strip().rstrip("/") for o in (env_value("CORS_ORIGINS") or DEFAULT_CORS).split(",") if o.strip()]


def configure_cors(application: FastAPI) -> None:
    """GET/POST from the listed origins only (also covers the EventSource /events stream).
    CORS_ORIGIN_REGEX optionally allows e.g. Vercel preview URLs."""
    application.add_middleware(
        CORSMiddleware, allow_origins=cors_origins(), allow_origin_regex=env_value("CORS_ORIGIN_REGEX"),
        allow_methods=["GET", "POST", "OPTIONS"], allow_headers=["*"], allow_credentials=False, max_age=600)


app = FastAPI(title="RetroAlpha backend")
configure_cors(app)
app.include_router(events.router)
app.include_router(media.router)


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {
        "status": "ok",
        "cache_mode": s.cache_mode,
        "engine_mode": s.engine_mode,
        "nessie_mode": s.nessie_mode,
        "demo_city": s.demo_city,
    }


@app.get("/registry")
def registry() -> dict:
    """Widget JSON Schemas (frontend mirrors these as TypeScript)."""
    return json_schemas()


@app.get("/portfolio")
def portfolio():
    """data/portfolio.json as written by scripts/pick_portfolio.py."""
    path = get_settings().data_dir / "portfolio.json"
    if not path.exists():
        raise HTTPException(404, "portfolio.json not found; run scripts/pick_portfolio.py")
    return json.loads(path.read_text())


_compose_lock = asyncio.Lock()  # engine state is process-wide; one re-plan at a time


@app.post("/compose", response_model=Layout)
async def compose(action: OwnerAction) -> Layout:
    """Owner action -> re-plan (agents/replan.py, TRD §9) -> new layout."""
    async with _compose_lock:
        try:
            return await replan(action)
        except ReplanError as e:
            raise HTTPException(e.status, str(e)) from e


@app.get("/state/{run_id}")
def state(run_id: str) -> dict:
    """Latest snapshot for a run (layout, goal, plan id) for the frontend after `done` or on reload."""
    st = read_json(data_path("runs", run_id, "state.json"))
    if st is None:
        raise HTTPException(404, f"no state for run {run_id}")
    return st
