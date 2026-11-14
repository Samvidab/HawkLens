"""Pricing node: calls the engine (simulate, macc, optimize, baseline) and stores the plan.

Never edits numbers; writes data/plans/current.json and data/plans/<plan_id>.json in the shape
documented in widgets/resolver.py.
"""
from __future__ import annotations

import asyncio
from typing import Iterable

from app import events
from app.integrations import engine_client as engine
from app.schemas.goal import Goal
from app.schemas.upgrades import FeasibleUpgrade
from app.storage import data_path, read_json, write_json


def load_upgrades(building_ids: Iterable[str] | None = None) -> dict[str, list[FeasibleUpgrade]]:
    root = data_path("buildings")
    out: dict[str, list[FeasibleUpgrade]] = {}
    for d in sorted(p for p in root.glob("*") if p.is_dir()):
        if building_ids is not None and d.name not in set(building_ids):
            continue
        raw = read_json(d / "feasibility.json")
        if raw is not None:
            out[d.name] = [FeasibleUpgrade.model_validate(u) for u in raw]
    return out


def _price_sync(goal: Goal, by_building: dict[str, list[FeasibleUpgrade]], exclusions: list[str],
                owner_included: set[str]) -> dict:
    upgrades = [u.model_copy(update={"include_in_optimizer": True}) if u.upgrade_id in owner_included else u
                for ups in by_building.values() for u in ups]
    sim = engine.simulate(upgrades, {"discount_rate": goal.discount_rate})
    bars = engine.macc(exclusions)
    opt = engine.optimize(goal.target_pct, goal.risk_lambda, goal.budget_usd, exclusions)
    return {"sim": sim, "macc": bars, "opt": opt, "baseline": {b: engine.baseline(b) for b in by_building}}


async def run_pricing(run_id: str, goal: Goal, *, excluded_building_ids: Iterable[str] = (),
                      excluded_upgrade_ids: Iterable[str] = (), owner_included: Iterable[str] = ()) -> dict:
    """Price the surveyed portfolio for `goal`; returns (and stores) the plan dict."""
    by_building = load_upgrades(goal.building_ids)
    excluded_buildings, owner_inc = sorted(set(excluded_building_ids)), set(owner_included)
    exclusions = excluded_buildings + sorted(set(excluded_upgrade_ids))
    r = await asyncio.to_thread(_price_sync, goal, by_building, exclusions, owner_inc)
    opt = r["opt"]
    plan = {
        **opt,
        "goal": goal.model_dump(mode="json"),
        "excluded_building_ids": excluded_buildings,
        "excluded_upgrade_ids": sorted(set(excluded_upgrade_ids)),
        "owner_included": sorted(owner_inc),
        "macc": r["macc"],
        "simulate": r["sim"],
        "baseline": r["baseline"],
        "stub": bool(opt.get("stub", False)),
    }
    write_json(data_path("plans", f"{plan['plan_id']}.json"), plan)
    write_json(data_path("plans", "current.json"), plan)
    events.emit(run_id, "Pricing", "price",
                f"optimize: {goal.target_pct:g}% target, p(hit) {plan['p_hit_target']:.2f}"
                + ("" if plan["status"] == "ok" else f", {plan['shortfall_tonnes']:,.0f} t/yr short"))
    return plan
