import asyncio
import json
import logging
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app import events
from app.agents import graph, store
from app.config import get_settings
from app.schemas.goal import Goal

log = logging.getLogger(__name__)

app = FastAPI(title="RetroAlpha backend")
app.include_router(events.router)

_runs: dict[str, asyncio.Task] = {}  # keep references so background runs aren't garbage-collected


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


@app.post("/run")
async def start_run(goal: Goal) -> dict:
    """Start survey (→ pricing → compose, once those exist) in the background; returns run_id."""
    run_id = graph.new_run_id()
    task = asyncio.create_task(graph.run(goal, run_id))
    _runs[run_id] = task
    task.add_done_callback(lambda t: _runs.pop(run_id, None))
    return {"run_id": run_id}


@app.get("/state/{run_id}")
def get_state(run_id: str) -> dict:
    p = store.run_dir(run_id) / "state.json"
    if not p.exists():
        raise HTTPException(404, f"unknown run {run_id}")
    return json.loads(p.read_text())


@app.get("/portfolio")
def get_portfolio() -> dict:
    p = Path(get_settings().data_dir) / "portfolio.json"
    if not p.exists():
        raise HTTPException(404, "portfolio.json not found")
    return json.loads(p.read_text())


@app.get("/registry")
def get_registry() -> dict:
    from app.widgets import registry
    return registry.json_schemas()


@app.get("/media/mesh/{model_id}/{filename}")
def get_mesh_file(model_id: str, filename: str):
    root = (Path(get_settings().cache_dir) / "media" / "mesh" / model_id).resolve()
    path = (root / filename).resolve()
    if path.parent != root or filename.startswith(".") or not path.is_file():
        raise HTTPException(404, "not found")
    return FileResponse(path)


@app.get("/media/{image_id}")
def get_media(image_id: str):
    ref = store.find_image(image_id)
    if not ref or not Path(ref.local_path).is_file():
        raise HTTPException(404, f"unknown image {image_id}")
    return FileResponse(ref.local_path, media_type="image/jpeg")
