import json

import asyncio

from fastapi import FastAPI, HTTPException

from app import events, media
from app.agents.composer import compose_v0, save_state
from app.agents.finance import ApprovalError, run_finance
from app.agents.memo import write_memo
from app.agents.pricing import run_pricing
from app.config import get_settings
from app.schemas.goal import Goal, OwnerAction
from app.schemas.layout import Layout
from app.storage import data_path, read_json
from app.widgets.registry import json_schemas

app = FastAPI(title="RetroAlpha backend")
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
PRICING_ACTIONS = {"goal", "set_target", "set_budget", "set_risk"}


async def _approve(action: OwnerAction) -> Layout:
    """finance -> memo -> `approved` layout. Gated on the current plan_id; a repeat approve books
    nothing and returns the same executed layout."""
    try:
        await run_finance(action.run_id, action.payload.get("plan_id"))
    except ApprovalError as e:
        raise HTTPException(409, str(e)) from e
    plan = read_json(data_path("plans", "current.json"))
    if not data_path("memo", f"{plan['plan_id']}.md").exists():
        await write_memo(action.run_id, plan)
    layout = compose_v0(action.run_id, situation="approved")
    save_state(action.run_id, layout, plan.get("goal"), plan["plan_id"])
    return layout


@app.post("/compose", response_model=Layout)
async def compose(action: OwnerAction) -> Layout:
    """v0: re-price for goal/target/budget/risk actions, then return the portfolio_overview layout.
    `approve` runs finance -> memo -> approved layout. Other action types (exclude, toggle, ...) arrive with T3.1 and currently just recompose."""
    async with _compose_lock:
        if action.type == "approve":
            return await _approve(action)
        plan = read_json(data_path("plans", "current.json"))
        goal_dict = (plan or {}).get("goal")
        if action.type in PRICING_ACTIONS:
            try:
                if action.type == "goal":
                    goal = Goal.model_validate(action.payload)
                else:
                    if not goal_dict:
                        raise HTTPException(409, "no current goal; send a `goal` action first")
                    key = {"set_target": "target_pct", "set_budget": "budget_usd", "set_risk": "risk_lambda"}[action.type]
                    goal = Goal.model_validate({**goal_dict, key: action.payload.get(key)})
            except ValueError as e:
                raise HTTPException(422, str(e)) from e
            plan = await run_pricing(action.run_id, goal, excluded_building_ids=(plan or {}).get("excluded_building_ids", []),
                                     owner_included=(plan or {}).get("owner_included", []))
            goal_dict = plan["goal"]
        layout = compose_v0(action.run_id)
        save_state(action.run_id, layout, goal_dict, (plan or {}).get("plan_id"))
        return layout


@app.get("/state/{run_id}")
def state(run_id: str) -> dict:
    """Latest snapshot for a run (layout, goal, plan id) for the frontend after `done` or on reload."""
    st = read_json(data_path("runs", run_id, "state.json"))
    if st is None:
        raise HTTPException(404, f"no state for run {run_id}")
    return st
