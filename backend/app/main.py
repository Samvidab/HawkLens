import json

from fastapi import FastAPI, HTTPException

from app import events
from app.config import get_settings
from app.widgets.registry import json_schemas

app = FastAPI(title="RetroAlpha backend")
app.include_router(events.router)


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
