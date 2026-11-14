"""Quant-engine client (TRD §8.1). ENGINE_MODE=stub|live.

stub: deterministic placeholder pricing from fixtures/engine/stub_params.json — flagged `stub: true`
      in optimize() output so the UI shows the "sample pricing" badge. Not real numbers.
live: delegates to the in-process engine `app.engine` (quant-engine branch), whose contract adds the
      same extras this stub returns (upfront_usd, tonnes_per_year, status, p_loss, hist_bins,
      tonnes_needed, shortfall_tonnes, cheapest_extra, baseline()).
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.schemas.upgrades import FeasibleUpgrade

PARAMS_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "engine" / "stub_params.json"
EXTRA_CUTS = 3

_assumptions: dict[str, Any] = {}
_state: dict[str, Any] = {"upgrades": {}, "models": {}}


def _live():
    from app import engine  # noqa: PLC0415 - only exists once the quant-engine branch is merged
    return engine


def _live_mode() -> bool:
    return get_settings().engine_mode == "live"


def _params() -> dict:
    return json.loads(PARAMS_PATH.read_text())


def reset_stub() -> None:
    _assumptions.clear()
    _state.update(upgrades={}, models={})


# ---- stub math ---------------------------------------------------------------------------------
def _phi(x: float) -> float:
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def _cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _hist(mean: float, sd: float, n_bins: int) -> list[dict]:
    lo, hi = mean - 2.5 * sd, mean + 2.5 * sd
    w = (hi - lo) / n_bins
    return [{"x0": round(lo + i * w, 2), "x1": round(lo + (i + 1) * w, 2),
             "count": round(1000 * _phi((lo + (i + 0.5) * w - mean) / sd) * w / sd)} for i in range(n_bins)]


def _risk(mean: float, sd: float, n_bins: int) -> dict:
    sd = max(sd, 1.0)
    return {"exp_npv": round(mean, 2), "p_loss": round(_cdf(-mean / sd), 4),
            "cvar5": round(mean - sd * _phi(1.645) / 0.05, 2), "hist_bins": _hist(mean, sd, n_bins)}


def _model(u: FeasibleUpgrade, p: dict) -> dict:
    t = u.type
    upfront = u.size_value * p["unit_cost_usd"][t] * _assumptions.get("cost_multiplier", 1.0)
    life, r = p["life_years"][t], _assumptions.get("discount_rate", p["discount_rate"])
    annuity = (1 - (1 + r) ** -life) / r
    npv = u.size_value * p["annual_savings_usd_per_unit"][t] * annuity - upfront
    tpy = u.size_value * p["tonnes_per_year_per_unit"][t]
    out = {"exp_npv": 0.0, "p_loss": 0.0, "cvar5": 0.0, "tonnes_lifetime": round(tpy * life, 2),
           "cost_per_tonne": round(-npv / (tpy * life), 2) if tpy else 0.0, "hist_bins": [],
           "upfront_usd": round(upfront, 2), "tonnes_per_year": round(tpy, 2)}
    out.update(_risk(npv, p["npv_sd_fraction_of_upfront"] * upfront, p["n_hist_bins"]))
    return out


# ---- public contract ---------------------------------------------------------------------------
def simulate(upgrades: list[FeasibleUpgrade], assumptions: dict | None = None) -> dict[str, dict]:
    """{upgrade_id: {exp_npv, p_loss, cvar5, tonnes_lifetime, cost_per_tonne, hist_bins,
    upfront_usd, tonnes_per_year}}"""
    if _live_mode():
        return _live().simulate(upgrades, assumptions or {})
    if assumptions:
        _assumptions.update(assumptions)
    p = _params()
    _state["upgrades"] = {u.upgrade_id: u for u in upgrades}
    _state["models"] = {u.upgrade_id: _model(u, p) for u in upgrades}
    return dict(_state["models"])


def _eligible(exclusions: list[str], explicit_include: set[str] = frozenset()) -> list[FeasibleUpgrade]:
    ex = set(exclusions)
    return [u for u in _state["upgrades"].values()
            if u.upgrade_id not in ex and u.building_id not in ex
            and (u.include_in_optimizer or u.upgrade_id in explicit_include)]


def _bar(u: FeasibleUpgrade) -> dict:
    m = _state["models"][u.upgrade_id]
    return {"upgrade_id": u.upgrade_id, "building_id": u.building_id, "type": u.type,
            "tonnes_per_year": m["tonnes_per_year"], "cost_per_tonne": m["cost_per_tonne"]}


def macc(exclusions: list[str]) -> dict:
    """{bars: [{upgrade_id, building_id, type, tonnes_per_year, cost_per_tonne}]} sorted ascending."""
    if _live_mode():
        return _live().macc(exclusions)
    bars = sorted((_bar(u) for u in _eligible(exclusions)), key=lambda b: (b["cost_per_tonne"], b["upgrade_id"]))
    return {"bars": bars}


def baseline(building_id: str) -> dict:
    """{annual_spend_usd, tonnes_per_year} (stub: benchmark per sq ft from the building profile)."""
    if _live_mode():
        return _live().baseline(building_id)
    b = _params()["baseline"]
    sqft = b["default_sqft"]
    prof = get_settings().data_dir / "buildings" / building_id / "profile.json"
    if prof.exists():
        sqft = json.loads(prof.read_text()).get("rba_sqft") or sqft
    return {"annual_spend_usd": round(sqft * b["spend_usd_per_sqft_year"], 2),
            "tonnes_per_year": round(sqft * b["kg_co2_per_sqft_year"] / 1000, 2)}


def optimize(target_pct: float, risk_lambda: float, budget_usd: float | None, exclusions: list[str]) -> dict:
    """Stub optimizer: greedy by cost per tonne, one upgrade per building per category, within budget.
    target_pct is 0-100."""
    if _live_mode():
        return _live().optimize(target_pct, risk_lambda, budget_usd, exclusions)
    p = _params()
    buildings = sorted({u.building_id for u in _state["upgrades"].values()})
    needed = round(sum(baseline(b)["tonnes_per_year"] for b in buildings) * target_pct / 100, 2)
    pool = sorted(_eligible(exclusions), key=lambda u: (_state["models"][u.upgrade_id]["cost_per_tonne"], u.upgrade_id))
    chosen: list[FeasibleUpgrade] = []
    used: set[tuple[str, str]] = set()
    tonnes = upfront = 0.0
    for u in pool:
        if tonnes >= needed:
            break
        m = _state["models"][u.upgrade_id]
        if (u.building_id, u.category) in used or (budget_usd is not None and upfront + m["upfront_usd"] > budget_usd):
            continue
        chosen.append(u); used.add((u.building_id, u.category))
        tonnes += m["tonnes_per_year"]; upfront += m["upfront_usd"]
    ms = [_state["models"][u.upgrade_id] for u in chosen]
    risk = _risk(sum(m["exp_npv"] for m in ms),
                 0.7 * sum(p["npv_sd_fraction_of_upfront"] * m["upfront_usd"] for m in ms), p["n_hist_bins"])
    ok = tonnes >= needed
    chosen_ids = {u.upgrade_id for u in chosen}
    extra = sorted((_bar(u) for u in _eligible(exclusions) if u.upgrade_id not in chosen_ids),
                   key=lambda b: (b["cost_per_tonne"], b["upgrade_id"]))[:EXTRA_CUTS]
    key = json.dumps([target_pct, risk_lambda, budget_usd, sorted(exclusions), sorted(_state["models"])], sort_keys=True)
    return {
        "plan_id": "plan_" + hashlib.sha256(key.encode()).hexdigest()[:10],
        "selected": [u.upgrade_id for u in chosen], "exp_npv": risk["exp_npv"], "cvar5": risk["cvar5"],
        "p_hit_target": 1.0 if ok else round(_cdf((tonnes - needed) / max(needed * 0.15, 1.0)), 4),
        "total_upfront": round(upfront, 2), "tonnes_per_year": round(tonnes, 2),
        "status": "ok" if ok else "infeasible", "p_loss": risk["p_loss"], "hist_bins": risk["hist_bins"],
        "tonnes_needed": needed, "shortfall_tonnes": 0.0 if ok else round(needed - tonnes, 2),
        "cheapest_extra": [] if ok else [{k: b[k] for k in ("upgrade_id", "cost_per_tonne", "tonnes_per_year")} for b in extra],
        "stub": True,
    }


def set_assumption(key: str, value: Any) -> dict:
    if _live_mode():
        return _live().set_assumption(key, value)
    _assumptions[key] = value
    if _state["upgrades"]:  # re-simulate so later optimize() calls see the new assumption
        simulate(list(_state["upgrades"].values()))
    return {"ok": True}
