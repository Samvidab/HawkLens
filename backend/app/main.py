import asyncio
import json
import logging

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app import events, media
from app.agents import approval, finance, graph
from app.agents.replan import ReplanError, register_survey_runner, replan
from app.config import get_settings
from app.envutil import env_value
from app.integrations import nessie_client
from app.matterport.routes import router as matterport_router
from app.schemas.goal import Goal, OwnerAction
from app.schemas.layout import Layout
from app.storage import data_path, read_json
from app.widgets.registry import json_schemas

log = logging.getLogger(__name__)

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
app.include_router(events.router)  # GET /events/{run_id}
app.include_router(media.router)   # GET /media/mesh/{model_id}/{file}, GET /media/{image_id}
app.include_router(matterport_router)  # GET /properties, /properties/{id}, /properties/{id}/thumbnail
register_survey_runner(graph.survey_runner)  # replan's `goal` action surveys missing buildings via Lane A's graph

_runs: dict[str, asyncio.Task] = {}  # keep references so background runs aren't garbage-collected
_compose_lock = asyncio.Lock()  # engine state is process-wide; one re-plan at a time


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
    """Latest snapshot for a run: the survey's status/results (graph.py) plus layout, goal, plan id and
    view (composer). Both write the same runs/<id>/state.json by merging fields."""
    st = read_json(data_path("runs", run_id, "state.json"))
    if st is None:
        raise HTTPException(404, f"unknown run {run_id}")
    return st


@app.get("/plan")
def current_plan() -> dict:
    """The one persisted plan (plans/current.json) every page reads, plus the approval verdict and funding mode.
    Numbers are the quant engine's; the frontend formats them and never recomputes them.
    status: "ok" | "infeasible" | "no_data"; 404 until a goal has been priced."""
    plan = read_json(data_path("plans", "current.json"))
    if not plan:
        raise HTTPException(404, "no plan yet; POST /run to survey and price the portfolio")
    plan.pop("simulate", None)  # per-upgrade scenario summaries: large, and already folded into line_items
    fin = plan.get("financing") or {}
    return {**plan, "approval": approval.check(read_json(data_path("plans", "current.json"))),
            "funding": {"mode": get_settings().nessie_mode, "simulated": finance.simulated(),
                        "state": fin.get("state", "proposed"), "executed": fin.get("state") == "executed"}}


@app.get("/funding-account")
def funding_account() -> dict:
    """The Nessie source account the approved amount is drawn from. Live: its real balance from Nessie.
    Stub: no account exists, so balance is null and simulated is true (nothing is invented)."""
    s = get_settings()
    src = env_value("NESSIE_SOURCE_ACCOUNT_ID")
    if s.nessie_mode != "live":
        return {"mode": s.nessie_mode, "simulated": True, "configured": bool(src),
                "account_id": None, "nickname": None, "balance": None}
    if not src:
        return {"mode": "live", "simulated": False, "configured": False,
                "account_id": None, "nickname": None, "balance": None, "error": "NESSIE_SOURCE_ACCOUNT_ID is not set"}
    try:
        acct = nessie_client.get_account(src)
    except Exception as e:  # noqa: BLE001 - surface the failure; never fall back to a made-up balance
        raise HTTPException(502, f"Nessie account lookup failed: {type(e).__name__}") from e
    return {"mode": "live", "configured": True, **acct, "account_id": "…" + str(acct["account_id"])[-4:]}
