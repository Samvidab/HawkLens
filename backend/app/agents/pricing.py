"""Pricing node: calls the engine (simulate, macc, optimize, baseline) and stores the plan.

Never edits numbers; writes data/plans/current.json and data/plans/<plan_id>.json in the shape
documented in widgets/resolver.py, plus fields every page reads instead of recomputing:

  coverage    which requested buildings were surveyed, which were not, which the owner excluded
  line_items  one row per selected upgrade (building, type, size, upfront, tonnes, NPV) from simulate()
  bundles     line_items summed by upgrade type (backend sums, so the UI never adds money)
  reconciles  sum(line_items.upfront_usd) == total_upfront

Before calling the optimizer it checks there is something to optimize. With no surveyed buildings or no
feasible upgrades it writes a plan with status "no_data" (every metric null) instead of letting the
optimizer report an empty plan as hitting a 0-tonne target with probability 1.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Iterable

from app import events
from app.config import get_settings
from app.integrations import engine_client as engine
from app.schemas.goal import Goal
from app.schemas.upgrades import FeasibleUpgrade
from app.storage import data_path, read_json, write_json
from app.widgets.resolver import CONTRACTOR

log = logging.getLogger(__name__)
RECONCILE_TOLERANCE_USD = 0.01


def load_upgrades(building_ids: Iterable[str] | None = None) -> dict[str, list[FeasibleUpgrade]]:
    root = data_path("buildings")
    wanted = set(building_ids) if building_ids is not None else None
    out: dict[str, list[FeasibleUpgrade]] = {}
    for d in sorted(p for p in root.glob("*") if p.is_dir()):
        if wanted is not None and d.name not in wanted:
            continue
        raw = read_json(d / "feasibility.json")
        if raw is not None:
            out[d.name] = [FeasibleUpgrade.model_validate(u) for u in raw]
    return out


def portfolio_ids() -> list[str]:
    p = read_json(data_path("portfolio.json"), {}) or {}
    return [b["building_id"] for b in p.get("buildings", [])]


def requested_ids(goal: Goal) -> list[str]:
    """The buildings this goal is about: its explicit list, else the whole portfolio (portfolio.json; without
    one, every building folder on disk)."""
    if goal.building_ids:
        return list(goal.building_ids)
    return portfolio_ids() or sorted(d.name for d in data_path("buildings").glob("*") if d.is_dir())


def _names() -> dict[str, str]:
    out = {}
    for d in data_path("buildings").glob("*"):
        prof = read_json(d / "profile.json") if d.is_dir() else None
        if prof and prof.get("name"):
            out[d.name] = prof["name"]
    for b in (read_json(data_path("portfolio.json"), {}) or {}).get("buildings", []):
        out.setdefault(b["building_id"], b.get("name") or b["building_id"])
    return out


def _coverage(goal: Goal, by_building: dict, excluded: set[str]) -> dict:
    req = requested_ids(goal)
    surveyed = sorted(b for b in req if b in by_building)
    return {
        "requested": req,
        "surveyed": surveyed,
        "not_surveyed": sorted(b for b in req if b not in by_building and b not in excluded),
        "excluded": sorted(b for b in req if b in excluded),
        "priced": sorted(b for b in surveyed if b not in excluded),
        "baseline_missing": [],
    }


def _price_sync(goal: Goal, by_building: dict[str, list[FeasibleUpgrade]], exclusions: list[str],
                owner_included: set[str], baseline_ids: list[str]) -> dict:
    upgrades = [u.model_copy(update={"include_in_optimizer": True}) if u.upgrade_id in owner_included else u
                for ups in by_building.values() for u in ups]
    sim = engine.simulate(upgrades, {"discount_rate": goal.discount_rate})
    bars = engine.macc(exclusions)
    base, missing = {}, []
    for b in baseline_ids:
        try:
            base[b] = engine.baseline(b)
        except (FileNotFoundError, ValueError, KeyError) as e:  # no profile / no rba_sqft: say so, don't guess
            log.warning("no baseline for %s: %s", b, e)
            missing.append(b)
    ok_ids = [b for b in baseline_ids if b in base]
    opt = engine.optimize(goal.target_pct, goal.risk_lambda, goal.budget_usd, exclusions,
                          baseline_building_ids=ok_ids)
    return {"sim": sim, "macc": bars, "opt": opt, "baseline": base, "baseline_missing": missing}


def _drift(r: dict) -> list[str]:
    return engine.check_outputs(r["sim"], r["macc"], r["opt"], r["baseline"])


def line_items(selected: list[str], sim: dict, by_building: dict[str, list[FeasibleUpgrade]],
               names: dict[str, str]) -> list[dict]:
    ups = {u.upgrade_id: u for lst in by_building.values() for u in lst}
    rows = []
    for uid in selected:
        u, m = ups.get(uid), sim.get(uid, {})
        rows.append({
            "upgrade_id": uid,
            "building_id": u.building_id if u else None,
            "building_name": names.get(u.building_id, u.building_id) if u else None,
            "type": u.type if u else None,
            "category": u.category if u else None,
            "size_value": u.size_value if u else None,
            "size_unit": u.size_unit if u else None,
            "verified": u.verified if u else None,
            "upfront_usd": m.get("upfront_usd"),
            "tonnes_per_year": m.get("tonnes_per_year"),
            "exp_npv": m.get("exp_npv"),
        })
    return rows


def bundles(items: list[dict]) -> list[dict]:
    """Line items grouped by upgrade type; sums only, in descending upfront order."""
    acc: dict[str, dict] = {}
    for r in items:
        b = acc.setdefault(r["type"], {"type": r["type"], "contractor": CONTRACTOR.get(r["type"]),
                                       "n_upgrades": 0, "building_ids": [],
                                       "upfront_usd": 0.0, "tonnes_per_year": 0.0, "exp_npv": 0.0})
        b["n_upgrades"] += 1
        if r["building_id"] not in b["building_ids"]:
            b["building_ids"].append(r["building_id"])
        for k in ("upfront_usd", "tonnes_per_year", "exp_npv"):
            b[k] = None if (b[k] is None or r[k] is None) else b[k] + r[k]
    out = list(acc.values())
    for b in out:
        b["n_buildings"] = len(b["building_ids"])
    return sorted(out, key=lambda b: -(b["upfront_usd"] or 0.0))


def reconciles(items: list[dict], total: float | None) -> bool:
    if total is None or any(r["upfront_usd"] is None for r in items):
        return False
    return abs(sum(r["upfront_usd"] for r in items) - total) <= RECONCILE_TOLERANCE_USD


def _no_data_plan(goal: Goal, coverage: dict, exclusions: list[str], reason: str, base: dict) -> dict:
    key = json.dumps([goal.model_dump(mode="json"), exclusions, coverage], sort_keys=True)
    return {
        "plan_id": "nodata_" + hashlib.sha256(key.encode()).hexdigest()[:10],
        "status": "no_data",
        "reason": reason,
        "selected": [], "line_items": [], "bundles": [],
        "exp_npv": None, "cvar5": None, "p_loss": None, "p_hit_target": None,
        "total_upfront": None, "tonnes_per_year": None, "tonnes_needed": None,
        "shortfall_tonnes": None, "cheapest_extra": [], "hist_bins": [],
        "reconciles": False, "risk_supported": False, "tonnes_margin": None, "profitable_tonnes_per_year": None,
        "macc": {"bars": []}, "simulate": {}, "baseline": base,
    }


async def run_pricing(run_id: str, goal: Goal, *, excluded_building_ids: Iterable[str] = (),
                      excluded_upgrade_ids: Iterable[str] = (), owner_included: Iterable[str] = ()) -> dict:
    """Price the surveyed portfolio for `goal`; returns (and stores) the plan dict."""
    excluded_buildings, owner_inc = sorted(set(excluded_building_ids)), set(owner_included)
    exclusions = excluded_buildings + sorted(set(excluded_upgrade_ids))
    by_building = load_upgrades(requested_ids(goal))
    coverage = _coverage(goal, by_building, set(excluded_buildings))
    names = _names()
    n_upgrades = sum(len(by_building[b]) for b in coverage["priced"])

    reason = None
    if not coverage["requested"]:
        reason = "no buildings in the portfolio"
    elif not coverage["surveyed"]:
        reason = f"none of the {len(coverage['requested'])} buildings has survey results; run the survey"
    elif not coverage["priced"]:
        reason = "every surveyed building is excluded"
    elif n_upgrades == 0:
        reason = "the survey found no feasible upgrades in the included buildings"

    if reason:
        plan = _no_data_plan(goal, coverage, exclusions, reason, {})
        events.emit(run_id, "Pricing", "error", f"not priced: {reason}")
    else:
        r = await asyncio.to_thread(_price_sync, goal, {b: by_building[b] for b in coverage["surveyed"]},
                                    exclusions, owner_inc, coverage["priced"])
        coverage["baseline_missing"] = r["baseline_missing"]
        opt = r["opt"]
        if drift := _drift(r):  # live engine differs from the contract: say so, keep going with what we have
            events.emit(run_id, "Pricing", "error", ("engine contract drift: " + "; ".join(drift))[:90])
        items = line_items(opt["selected"], r["sim"], by_building, names)
        bars = r["macc"].get("bars", [])
        tpy, need = opt.get("tonnes_per_year"), opt.get("tonnes_needed")
        plan = {
            **opt,
            # planned minus needed, t/yr (>= 0 when the target is met); the gap card shows it as-is
            "tonnes_margin": (tpy - need) if isinstance(tpy, (int, float)) and isinstance(need, (int, float)) else None,
            # abatement-curve summary: CO2 of the eligible upgrades that pay for themselves (cost per tonne < 0)
            "profitable_tonnes_per_year": sum(b["tonnes_per_year"] for b in bars
                                              if isinstance(b.get("cost_per_tonne"), (int, float)) and b["cost_per_tonne"] < 0),
            "line_items": items,
            "bundles": bundles(items),
            "reconciles": reconciles(items, opt.get("total_upfront")),
            "macc": r["macc"],
            "simulate": r["sim"],
            "baseline": r["baseline"],
        }
    sim = plan.get("simulate", {})
    selected, excl_u = set(plan.get("selected", [])), set(excluded_upgrade_ids)
    plan["upgrades_by_building"] = {  # every feasible upgrade, for the building page's include toggles
        b: [{"upgrade_id": u.upgrade_id, "type": u.type, "size_value": u.size_value, "size_unit": u.size_unit,
             "verified": u.verified, "in_plan": u.upgrade_id in selected, "excluded": u.upgrade_id in excl_u,
             "upfront_usd": sim.get(u.upgrade_id, {}).get("upfront_usd"),
             "tonnes_per_year": sim.get(u.upgrade_id, {}).get("tonnes_per_year"),
             "exp_npv": sim.get(u.upgrade_id, {}).get("exp_npv")} for u in ups]
        for b, ups in by_building.items()}
    totals: dict[str, dict] = {}
    for r in plan.get("line_items", []):
        t = totals.setdefault(r["building_id"], {"n_upgrades": 0, "upfront_usd": 0.0, "tonnes_per_year": 0.0, "exp_npv": 0.0})
        t["n_upgrades"] += 1
        for k in ("upfront_usd", "tonnes_per_year", "exp_npv"):
            t[k] = None if (t[k] is None or r[k] is None) else t[k] + r[k]
    plan["building_totals"] = totals  # the selected upgrades' sums per building
    plan.update({
        "run_id": run_id,
        "goal": goal.model_dump(mode="json"),
        "coverage": coverage,
        "building_names": {b: names.get(b, b) for b in coverage["requested"]},
        "excluded_building_ids": excluded_buildings,
        "excluded_upgrade_ids": sorted(set(excluded_upgrade_ids)),
        "owner_included": sorted(owner_inc),
        "stub": bool(plan.get("stub", False)),
        "engine_mode": get_settings().engine_mode,
    })
    write_json(data_path("plans", f"{plan['plan_id']}.json"), plan)
    write_json(data_path("plans", "current.json"), plan)
    if plan["status"] != "no_data":
        events.emit(run_id, "Pricing", "price",
                    f"optimize: {goal.target_pct:g}% target, p(hit) {plan['p_hit_target']:.2f}"
                    + ("" if plan["status"] == "ok" else f", {plan['shortfall_tonnes']:,.0f} t/yr short"))
    return plan
