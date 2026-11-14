import json

import asyncio

from fastapi import FastAPI, HTTPException

from app import events, media
from app.agents import graph
from app.agents.replan import ReplanError, register_survey_runner, replan
from app.config import get_settings
from app.schemas.goal import Goal, OwnerAction
from app.schemas.layout import Layout
from app.storage import data_path, read_json
from app.widgets.registry import json_schemas

app = FastAPI(title="RetroAlpha backend")
app.include_router(events.router)
app.include_router(media.router)
register_survey_runner(graph.survey_runner)  # replan's `goal` action surveys missing buildings via Lane A's graph

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


@app.post("/run")
async def start_run(goal: Goal) -> dict:
    """Survey (Lane A graph) -> pricing -> compose in the background; returns run_id at once.
    The frontend opens GET /events/{run_id} and reads GET /state/{run_id} after the `done` event."""
    run_id = graph.new_run_id()

    async def pipeline() -> None:
        async def compose_goal() -> None:
            async with _compose_lock:
                await replan(OwnerAction(run_id=run_id, type="goal", payload=goal.model_dump(mode="json")))
        await graph.run_full(goal, run_id, compose_goal)

    task = asyncio.create_task(pipeline())
    _runs[run_id] = task
    task.add_done_callback(lambda t: _runs.pop(run_id, None))
    return {"run_id": run_id}


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
