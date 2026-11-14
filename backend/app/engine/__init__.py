"""HawkLens quant engine: the contract functions (TRD §8.1, engine/CLAUDE.md "Contract").

    simulate(upgrades, assumptions)                      -> {upgrade_id: {...}}
    macc(exclusions)                                     -> {bars: [...]}
    optimize(target_pct, risk_lambda, budget_usd, exclusions) -> {plan_id, selected, ...}
    set_assumption(key, value)                           -> {ok}
    baseline(building_id)                                -> {annual_spend_usd, tonnes_per_year}

Imported in-process by the backend. Every number comes from code; no LLM calls.

Assumptions, lowest to highest priority:
1. assumptions.json
2. the `assumptions` dict passed to simulate() (nested like the file, or dotted keys
   such as {"global.discount_rate": 0.05})
3. set_assumption() overrides (kept until the process restarts or state.clear())

Fields beyond the TRD (they only add to it; agent owner: these exist):
  simulate:  upfront_usd, tonnes_per_year per upgrade
  optimize:  status, p_loss, hist_bins, tonnes_needed, shortfall_tonnes, cheapest_extra
             (each with verified, fits_budget), internal_target_pct, min_p_hit,
             met_min_p_hit, p_hit_retries
  configure(buildings_root=...): setup only, outside the contract
  set_assumption: error (when ok is False)
"""
from __future__ import annotations

import copy
import math
from pathlib import Path
from typing import Any, Iterable

from . import curve as _curve
from . import monte_carlo as _mc
from . import optimizer as _opt
from . import risk as _risk
from . import state
from .buildings import BuildingFacts, baseline_kwh_per_year, baseline_tonnes_per_year, load_building
from .models import FeasibleUpgrade, load_assumptions

__all__ = ["simulate", "macc", "optimize", "set_assumption", "baseline", "configure"]

_VALIDATION_SCENARIOS = 50


# --- assumptions -------------------------------------------------------------------------

def _resolve_key(base: dict, key: str) -> list[str]:
    """'global.discount_rate' -> ['global', 'discount_rate']; a bare global key is allowed too."""
    if "." not in key and key in base.get("global", {}):
        return ["global", key]
    return key.split(".")


def _get_path(d: dict, path: list[str]) -> Any:
    for p in path:
        if not isinstance(d, dict) or p not in d:
            raise KeyError(".".join(path))
        d = d[p]
    return d


def _set_path(d: dict, path: list[str], value: Any) -> None:
    _get_path(d, path)                                   # must already exist: no new keys
    for p in path[:-1]:
        d = d[p]
    d[path[-1]] = value


def _same_kind(old: Any, new: Any) -> bool:
    num = lambda v: isinstance(v, (int, float)) and not isinstance(v, bool)
    if num(old):
        return num(new) and math.isfinite(new)
    if isinstance(old, list):
        return isinstance(new, list) and len(new) == len(old) and all(num(v) for v in new)
    return type(old) is type(new)


def _apply(base: dict, changes: dict, prefix: list[str] | None = None) -> None:
    """Apply nested and/or dotted changes onto base, refusing unknown keys and wrong types."""
    for k, v in changes.items():
        path = prefix + k.split(".") if prefix else _resolve_key(base, k)
        target = _get_path(base, path)
        if isinstance(target, dict) and isinstance(v, dict):
            _apply(base, v, path)
        else:
            if not _same_kind(target, v):
                raise TypeError(f"{'.'.join(path)}: expected a value like {target!r}, got {v!r}")
            _set_path(base, path, v)


def _effective(request: dict | None) -> dict:
    path = state.assumptions_path()
    a = copy.deepcopy(load_assumptions(path) if path is not None else load_assumptions())
    if request:
        _apply(a, request)
    for k, v in state.overrides().items():
        _apply(a, {k: v})
    return a


# --- helpers -----------------------------------------------------------------------------

def _num(x: float) -> float | None:
    x = float(x)
    return x if math.isfinite(x) else None


def _as_upgrades(upgrades: Iterable[Any]) -> list[FeasibleUpgrade]:
    """Accept our FeasibleUpgrade, the agent's app.schemas.upgrades.FeasibleUpgrade (or any
    pydantic model with the same fields), or plain dicts. Pydantic refuses another class's
    instance directly, so foreign models are validated from their fields."""
    out = []
    for u in upgrades:
        if isinstance(u, FeasibleUpgrade):
            out.append(u)
        elif hasattr(u, "model_dump"):
            out.append(FeasibleUpgrade.model_validate(u.model_dump()))
        else:
            out.append(FeasibleUpgrade.model_validate(u))
    return out


def _load_buildings(ids: Iterable[str], a: dict) -> dict[str, BuildingFacts]:
    """Facts for each building: from the cache if already loaded, else from configure()'s root."""
    cached, root = state.buildings(), state.buildings_root()
    return {b: cached[b] if b in cached else load_building(b, root=root, assumptions=a)
            for b in sorted(set(ids))}


def _run(upgrades: list[FeasibleUpgrade], buildings: dict[str, BuildingFacts], a: dict,
         request: dict | None) -> _mc.SimulationResult:
    sim = _mc.simulate(upgrades, buildings, a)
    state.set_simulation(sim, upgrades, buildings=buildings, assumptions=request or {})
    return sim


def _ensure_fresh() -> _mc.SimulationResult:
    """Re-simulate after set_assumption(), with the same upgrades and buildings."""
    sim, upgrades = state.current()
    if state.is_stale():
        request = state.request_assumptions()
        sim = _run(upgrades, state.buildings(), _effective(request), request)
    return sim


# --- setup (not part of the TRD contract) ------------------------------------------------

def configure(*, buildings_root: str | Path | None = None,
              assumptions_path: str | Path | None = None) -> None:
    """Setup, outside the TRD contract (so the five contract signatures stay exact; the
    agent's engine_client checks parameter names).

    buildings_root:   where <building_id>/profile.json lives (default data_dir/buildings)
    assumptions_path: base assumptions file (default app/engine/assumptions.json). Tests
                      point it at a frozen copy so mechanics tests don't move when the
                      sourced values change.
    Each call sets both; omitted = default.
    """
    state.set_buildings_root(buildings_root)
    state.set_assumptions_path(assumptions_path)


# --- contract ----------------------------------------------------------------------------

def simulate(upgrades: list[FeasibleUpgrade | dict], assumptions: dict | None = None) -> dict[str, dict]:
    """Simulate every upgrade and cache the result for macc()/optimize().

    Re-reads buildings from disk each time (the survey may have updated them).
    """
    ups = _as_upgrades(upgrades)
    a = _effective(assumptions)
    state.forget_buildings()
    buildings = _load_buildings((u.building_id for u in ups), a)
    sim = _run(ups, buildings, a, assumptions)
    cpt = _curve.cost_per_tonne(sim.npv, sim.tonnes_lifetime)
    out = {}
    for i, uid in enumerate(sim.upgrade_ids):
        r = _risk.summarize(sim.npv[i])
        out[uid] = {
            "exp_npv": r["exp_npv"],
            "p_loss": r["p_loss"],
            "cvar5": r["cvar5"],
            "tonnes_lifetime": float(sim.tonnes_lifetime[i].mean()),
            "cost_per_tonne": _num(cpt[i]),          # None if the upgrade avoids no CO2
            "hist_bins": r["hist_bins"],
            "upfront_usd": sim.inputs[i].upfront_usd,
            "tonnes_per_year": float(sim.tonnes_per_year[i].mean()),
        }
    return out


def macc(exclusions: list[str] | None = None) -> dict:
    _ensure_fresh()
    return _curve.macc(exclusions or [])


def optimize(target_pct: float, risk_lambda: float = 0.0, budget_usd: float | None = None,
             exclusions: list[str] | None = None) -> dict:
    """Cheapest plan (max expected NPV) that hits target_pct % of the portfolio's baseline CO2.

    The target's denominator is every simulated building, excluded or not.
    risk_lambda >= 0: maximize E[NPV] + risk_lambda x CVaR5 (worst-5% mean NPV) over
    global.n_scenarios_optimizer scenarios. 0 = expected NPV only.
    global.min_p_hit (assumptions; default 0.8, set_assumption("min_p_hit", x) to change,
    0 turns it off): raise the internal target until the plan hits the real target in at
    least this share of scenarios (see optimizer.solve_with_min_p_hit).
    """
    sim = _ensure_fresh()
    _, upgrades = state.current()
    a = _effective(state.request_assumptions())
    base = sum(baseline_tonnes_per_year(b, a) for b in state.buildings().values())
    return _opt.solve_with_min_p_hit(
        sim, upgrades, baseline_tonnes_per_year=base, target_pct=target_pct,
        min_p_hit=a["global"]["min_p_hit"], budget_usd=budget_usd, exclusions=exclusions or [],
        risk_lambda=risk_lambda, n_risk_scenarios=a["global"]["n_scenarios_optimizer"],
    )


def set_assumption(key: str, value: Any) -> dict:
    """Change one assumption (dotted key, e.g. 'upgrades.led_retrofit.unit_cost').

    Refuses unknown keys, wrong types, and values the engine rejects (e.g. a
    discount rate of 7 instead of 0.07): those return {ok: False, error} and change
    nothing. On success the cache is marked stale; the next macc()/optimize()
    re-simulates.
    """
    try:
        trial = _effective(state.request_assumptions())
        _apply(trial, {key: value})
        if not 0 <= trial["global"]["min_p_hit"] <= 1:
            raise ValueError("global.min_p_hit is a probability 0-1, e.g. 0.8")
        if state.has_simulation():      # dry run on the cached upgrades to catch bad values
            _, ups = state.current()
            _mc.simulate(ups, state.buildings(), trial, n_scenarios=_VALIDATION_SCENARIOS)
    except (KeyError, TypeError, ValueError) as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}
    state.set_override(key, value)
    return {"ok": True}


def baseline(building_id: str) -> dict:
    """Annual electricity spend and CO2 for one building (benchmark until bills are wired in)."""
    a = _effective(state.request_assumptions())
    b = _load_buildings([building_id], a)[building_id]
    kwh = baseline_kwh_per_year(b, a)
    return {
        "annual_spend_usd": kwh * a["cities"][b.city]["electricity_rate_usd_per_kwh"],
        "tonnes_per_year": baseline_tonnes_per_year(b, a),
    }
