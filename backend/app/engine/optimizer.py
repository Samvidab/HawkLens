"""Plan optimizer (engine/CLAUDE.md "Optimizer", step 1: maximize expected NPV).

Pick a set of upgrades (x_i = 1 means "do upgrade i") that:
    maximizes   sum_i E[NPV_i] x_i
    subject to  sum_i E[tonnes_per_year_i] x_i >= target_pct/100 x portfolio baseline tonnes/yr
                at most one upgrade per (building, category)
                sum_i upfront_i x_i <= budget_usd            (only if a budget is given)
                x_i = 0 for excluded upgrades (by upgrade ID or building ID) and for
                upgrades with include_in_optimizer == False

Two solvers for the same problem:
- brute_force(): tries every plan. Exact and obviously right, but only for small
  inputs. It is the test oracle for the PuLP model.
- solve(): the PuLP integer program, solved with CBC (HiGHS as fallback).

If no plan reaches the target, the result has status "infeasible", the plan that
gets closest (most tonnes), shortfall_tonnes, and cheapest_extra: up to 3 excluded
or unselected upgrades with the lowest cost per tonne that would add tonnes (their
building/category slot is empty, or they avoid more CO2 than what's in it).

Step 7 adds the CVaR risk term; risk_lambda is not used yet.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import warnings
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

import numpy as np
import pulp

from .macc import cost_per_tonne
from .models import FeasibleUpgrade
from .monte_carlo import SimulationResult
from .risk import summarize

EPS_TONNES = 1e-6          # tolerance on the tonnes constraint (same for both solvers)
MAX_BRUTE_FORCE_PLANS = 1 << 20
N_CHEAPEST_EXTRA = 3


@dataclass(frozen=True)
class Candidate:
    index: int                 # row in the simulation arrays
    upgrade_id: str
    building_id: str
    type: str
    category: str
    exp_npv: float
    tonnes_per_year: float     # expected (mean over scenarios)
    upfront_usd: float
    cost_per_tonne: float
    eligible: bool             # passes exclusions and include_in_optimizer
    user_excluded: bool        # excluded by the caller (not by include_in_optimizer)


@dataclass(frozen=True)
class Problem:
    sim: SimulationResult
    candidates: list[Candidate]
    tonnes_needed: float
    budget_usd: float | None
    target_pct: float
    exclusions: tuple[str, ...]


def build_problem(sim: SimulationResult, upgrades: list[FeasibleUpgrade], *,
                  baseline_tonnes_per_year: float, target_pct: float,
                  budget_usd: float | None = None, exclusions: Iterable[str] = ()) -> Problem:
    if [u.upgrade_id for u in upgrades] != sim.upgrade_ids:
        raise ValueError("upgrades must be the same list, in the same order, that was simulated")
    if not 0 <= target_pct <= 100:
        raise ValueError("target_pct is a percentage 0-100, e.g. 40 for 40%")
    if budget_usd is not None and budget_usd < 0:
        raise ValueError("budget_usd must be >= 0")
    ex = tuple(sorted(set(exclusions)))
    cpt = cost_per_tonne(sim.npv, sim.tonnes_lifetime)
    exp_npv = sim.npv.mean(axis=1)
    tpy = sim.tonnes_per_year.mean(axis=1)
    cands = []
    for i, u in enumerate(upgrades):
        user_ex = u.upgrade_id in ex or u.building_id in ex
        cands.append(Candidate(
            index=i, upgrade_id=u.upgrade_id, building_id=u.building_id, type=u.type,
            category=u.category, exp_npv=float(exp_npv[i]), tonnes_per_year=float(tpy[i]),
            upfront_usd=sim.inputs[i].upfront_usd, cost_per_tonne=float(cpt[i]),
            eligible=u.include_in_optimizer and not user_ex, user_excluded=user_ex,
        ))
    return Problem(sim=sim, candidates=cands,
                   tonnes_needed=target_pct / 100.0 * baseline_tonnes_per_year,
                   budget_usd=budget_usd, target_pct=target_pct, exclusions=ex)


# --- brute force (test oracle) -----------------------------------------------------------

def _groups(p: Problem) -> list[list[Candidate]]:
    """Eligible candidates grouped by (building, category): a plan picks at most one per group."""
    groups: dict[tuple[str, str], list[Candidate]] = {}
    for c in p.candidates:
        if c.eligible:
            groups.setdefault((c.building_id, c.category), []).append(c)
    return [groups[k] for k in sorted(groups)]


def brute_force(p: Problem) -> dict:
    """Try every plan; same result format as solve()."""
    groups = _groups(p)
    n_plans = int(np.prod([len(g) + 1 for g in groups])) if groups else 1
    if n_plans > MAX_BRUTE_FORCE_PLANS:
        raise ValueError(f"{n_plans} plans is too many for brute force; use solve()")

    best_ok: tuple[float, list[Candidate]] | None = None        # max NPV among plans hitting target
    best_any: tuple[float, float, list[Candidate]] | None = None  # max tonnes (then NPV) overall
    for choice in itertools.product(*[[None, *g] for g in groups]):
        plan = [c for c in choice if c is not None]
        if p.budget_usd is not None and sum(c.upfront_usd for c in plan) > p.budget_usd + 1e-6:
            continue
        npv = sum(c.exp_npv for c in plan)
        tonnes = sum(c.tonnes_per_year for c in plan)
        if tonnes >= p.tonnes_needed - EPS_TONNES and (best_ok is None or npv > best_ok[0]):
            best_ok = (npv, plan)
        if best_any is None or (tonnes, npv) > (best_any[0], best_any[1]):
            best_any = (tonnes, npv, plan)

    if best_ok is not None:
        return _result(p, [c.index for c in best_ok[1]], status="ok")
    return _result(p, [c.index for c in best_any[2]], status="infeasible")


# --- PuLP model --------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _solver_name() -> str:
    available = pulp.listSolvers(onlyAvailable=True)
    for name in ("PULP_CBC_CMD", "HiGHS", "HiGHS_CMD"):
        if name in available:
            return name
    raise RuntimeError(f"no MILP solver available (found {available}); "
                       "install pulp[cbc] or highspy")


def _solver() -> pulp.LpSolver:
    name = _solver_name()
    if name == "PULP_CBC_CMD":
        # PuLP 3.3 marks PULP_CBC_CMD deprecated (removed in 4.0; requirements pin 3.3.2).
        # Silence only that warning, only here. Before upgrading PuLP, switch to
        # COIN_CMD(path=<venv>/bin/cbc, msg=0), which works without warnings.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", message="PULP_CBC_CMD is deprecated",
                                    category=DeprecationWarning)
            return pulp.PULP_CBC_CMD(msg=0)
    if name == "HiGHS":
        return pulp.HiGHS(msg=0)
    return pulp.HiGHS_CMD(msg=0)


def _model(p: Problem, objective: str) -> tuple[pulp.LpProblem, dict[int, pulp.LpVariable]]:
    """objective = "npv" (with tonnes >= target) or "tonnes" (max tonnes, no target)."""
    m = pulp.LpProblem("plan", pulp.LpMaximize)
    x = {c.index: m.add_variable(f"x_{c.index}", cat="Binary") for c in p.candidates if c.eligible}
    by = {c.index: c for c in p.candidates}
    tonnes = pulp.lpSum(by[i].tonnes_per_year * v for i, v in x.items())
    if objective == "npv":
        m += pulp.lpSum(by[i].exp_npv * v for i, v in x.items())
        m += tonnes >= p.tonnes_needed - EPS_TONNES, "target"
    else:
        # Max tonnes; tiny NPV term breaks ties toward the more valuable plan.
        scale = 1e-9 / (1 + max((abs(c.exp_npv) for c in p.candidates), default=1))
        m += tonnes + scale * pulp.lpSum(by[i].exp_npv * v for i, v in x.items())
    for g, group in enumerate(_groups(p)):
        m += pulp.lpSum(x[c.index] for c in group) <= 1, f"one_per_group_{g}"
    if p.budget_usd is not None:
        m += pulp.lpSum(by[i].upfront_usd * v for i, v in x.items()) <= p.budget_usd, "budget"
    return m, x


def _run(m: pulp.LpProblem, x: dict[int, pulp.LpVariable]) -> list[int] | None:
    m.solve(_solver())
    if m.status != pulp.LpStatusOptimal:
        return None
    return sorted(i for i, v in x.items() if (v.value() or 0) > 0.5)


def solve(p: Problem) -> dict:
    """PuLP model; same result format as brute_force()."""
    selected = _run(*_model(p, "npv"))
    if selected is not None:
        return _result(p, selected, status="ok")
    closest = _run(*_model(p, "tonnes"))
    if closest is None:
        raise RuntimeError("solver failed on the max-tonnes model, which is always feasible")
    return _result(p, closest, status="infeasible")


# --- shared result -----------------------------------------------------------------------

def plan_id(p: Problem, risk_lambda: float = 0.0) -> str:
    """Same inputs -> same ID. Hashes the simulated NPVs too, so changed assumptions change it."""
    h = hashlib.sha256()
    h.update(json.dumps({
        "upgrades": p.sim.upgrade_ids, "seed": p.sim.seed, "k": p.sim.n_scenarios,
        "target_pct": p.target_pct, "budget_usd": p.budget_usd, "exclusions": p.exclusions,
        "risk_lambda": risk_lambda,
    }, sort_keys=True).encode())
    h.update(np.ascontiguousarray(p.sim.npv).tobytes())
    return h.hexdigest()[:12]


def _bar(c: Candidate) -> dict:
    return {"upgrade_id": c.upgrade_id, "building_id": c.building_id, "type": c.type,
            "tonnes_per_year": c.tonnes_per_year, "cost_per_tonne": c.cost_per_tonne}


def _result(p: Problem, selected: list[int], *, status: str) -> dict:
    sel = sorted(selected)
    sim = p.sim
    plan_npv = sim.npv[sel].sum(axis=0) if sel else np.zeros(sim.n_scenarios)
    plan_tonnes = sim.tonnes_per_year[sel].sum(axis=0) if sel else np.zeros(sim.n_scenarios)
    risk = summarize(plan_npv)
    exp_tonnes = float(plan_tonnes.mean())
    chosen = set(sel)

    if status == "infeasible":
        shortfall = max(p.tonnes_needed - exp_tonnes, 0.0)
        # Only suggest upgrades that would ADD tonnes: their (building, category) slot is
        # empty, or they'd replace a selected upgrade that avoids less CO2.
        slot_tonnes = {(c.building_id, c.category): c.tonnes_per_year
                       for c in p.candidates if c.index in chosen}
        extras = [c for c in p.candidates
                  if c.index not in chosen and (c.eligible or c.user_excluded)
                  and np.isfinite(c.cost_per_tonne)
                  and c.tonnes_per_year > slot_tonnes.get((c.building_id, c.category), 0.0)]
        extras.sort(key=lambda c: (c.cost_per_tonne, c.upgrade_id))
        cheapest_extra = [_bar(c) for c in extras[:N_CHEAPEST_EXTRA]]
    else:
        shortfall, cheapest_extra = 0.0, []

    return {
        "plan_id": plan_id(p),
        "selected": [sim.upgrade_ids[i] for i in sel],
        "exp_npv": risk["exp_npv"],
        "cvar5": risk["cvar5"],
        "p_hit_target": float((plan_tonnes >= p.tonnes_needed - EPS_TONNES).mean()),
        "total_upfront": float(sum(sim.inputs[i].upfront_usd for i in sel)),
        "tonnes_per_year": exp_tonnes,
        "status": status,
        "p_loss": risk["p_loss"],
        "hist_bins": risk["hist_bins"],
        "tonnes_needed": p.tonnes_needed,
        "shortfall_tonnes": shortfall,
        "cheapest_extra": cheapest_extra,
    }
