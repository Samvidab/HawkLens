"""Read recorded history/research and expose the teammate's explicit-input energy/bill tools."""
from __future__ import annotations
import importlib.util
import re
import tempfile
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, ConfigDict
from app.config import get_settings
from app.storage import data_path, read_json

router = APIRouter(tags=["recorded research and history"])

def safe_id(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise HTTPException(422, "Invalid record ID")
    return value

def teammate_module(name):
    path = Path(__file__).resolve().parents[2] / "nessie" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"hawklens_{name}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

@router.get("/history")
def history():
    runs = []
    for path in sorted(data_path("runs").glob("*")):
        if not path.is_dir():
            continue
        s = read_json(path / "state.json", {}) or {}
        runs.append({"run_id": path.name, "status": s.get("status"), "plan_id": s.get("plan_id"),
                     "goal": s.get("goal"), "has_layout": bool(s.get("layout")),
                     "results": s.get("results", {}), "events_available": (path / "events.jsonl").is_file()})
    plans = []
    for path in sorted(data_path("plans").glob("*.json")):
        if path.stem == "current":
            continue
        p = read_json(path, {}) or {}
        plans.append({k: p.get(k) for k in ["plan_id", "goal", "total_upfront", "exp_npv", "tonnes_per_year", "stub", "status"]})
    return {"runs": runs, "plans": plans, "current_plan_id": (read_json(data_path("plans", "current.json"), {}) or {}).get("plan_id")}

@router.get("/history/plans/{plan_id}")
def archived_plan(plan_id: str):
    p = read_json(data_path("plans", safe_id(plan_id) + ".json"), None)
    if p is None:
        raise HTTPException(404, "Saved plan unavailable")
    memo = data_path("memo", plan_id + ".md")
    return {"plan": p, "memo_markdown": memo.read_text() if memo.is_file() else None,
            "notice": "Saved snapshot; viewing does not replace or recalculate the current plan."}

@router.get("/research/{building_id}")
def research(building_id: str):
    bid = safe_id(building_id)
    profile = read_json(data_path("buildings", bid, "profile.json"), None)
    if profile is None:
        raise HTTPException(404, "Recorded building unavailable")
    return {"building_id": bid, "profile": profile,
            "utility_research": read_json(data_path("utility_research", bid + ".json"), None),
            "energy_estimate": read_json(data_path("energy_estimates", bid + ".json"), None),
            "simulation_research": read_json(data_path("simulation_assumptions", "houston.json"), None),
            "end_use_research": read_json(Path(__file__).parent / "agents/sources/houston_office_end_use.json", None),
            "cache_mode": get_settings().cache_mode,
            "notice": "Research citations are recorded claims, not independently audited tariffs or measured building consumption. Active engine assumptions are served separately at /assumptions."}

class EnergyRequest(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    building_id: str
    annual_kwh_per_sqft: float = Field(ge=0)
    electricity_usd_per_kwh: float = Field(ge=0)
    annual_therms_per_sqft: float = Field(ge=0)
    gas_usd_per_therm: float = Field(ge=0)

@router.post("/analysis/energy")
def energy(body: EnergyRequest):
    safe_id(body.building_id)
    try:
        return teammate_module("bills").estimate_energy_costs(**body.model_dump(), data_dir=get_settings().data_dir)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(422, str(exc)) from exc

class BillsRequest(BaseModel):
    building_id: str
    csv_text: str = Field(max_length=1_000_000)

@router.post("/analysis/bills")
def bills(body: BillsRequest):
    bid = safe_id(body.building_id)
    if not data_path("buildings", bid, "profile.json").is_file():
        raise HTTPException(404, "Recorded building unavailable")
    try:
        with tempfile.TemporaryDirectory(prefix="hawklens-bill-validation-") as folder:
            path = Path(folder) / "bills.csv"
            path.write_text(body.csv_text)
            result = teammate_module("actual_bills").summarize_bills(path, bid)
        if not result["bill_count"]:
            raise HTTPException(422, "No matching bill records were supplied for this building")
        return {**result, "measurement_status": "user_provided_bill_records_not_independently_verified", "persisted": False}
    except (ValueError, KeyError, ArithmeticError) as exc:
        raise HTTPException(422, str(exc)) from exc
