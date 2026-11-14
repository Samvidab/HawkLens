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
gets closest (most tonnes), shortfall_tonnes, and cheapest_extra: up to 3 unselected,
owner-excluded or unverified upgrades with the lowest cost per tonne that would add
tonnes (their building/category slot is empty, or they avoid more CO2 than what's in
it). Each item has verified (False = needs "include unverified") and fits_budget.

Risk (build step 7): with risk_lambda > 0 the objective becomes
    E[NPV] + risk_lambda x CVaR5(plan NPV)
CVaR5 = mean NPV of the worst 5% of scenarios (usually negative; higher = safer). It is
linearised with Rockafellar-Uryasev over the first n_risk_scenarios scenarios
(assumptions global.n_scenarios_optimizer, 1000):
    eta free, u_k >= 0, u_k >= eta - sum_i npv[i,k] x_i,  CVaR = eta - sum_k u_k / (alpha K)
At the optimum eta is the 5% quantile and the u_k are how far each scenario falls below
it, so the term equals the exact worst-5% mean when alpha K is a whole number (50 of 1000).
E[NPV] in the objective still uses all scenarios. risk_lambda = 0 is plain step 5.
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

from .curve import cost_per_tonne
from .models import FeasibleUpgrade
from .monte_carlo import SimulationResult
from .risk import ALPHA, cvar, summarize

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
    verified: bool             # False only for verified == "unverified" (assumed counts as verified)


@dataclass(frozen=True)
class Problem:
    sim: SimulationResult
    candidates: list[Candidate]
    tonnes_needed: float
    budget_usd: float | None
    target_pct: float
    exclusions: tuple[str, ...]
    risk_lambda: float = 0.0
    risk_npv: np.ndarray | None = None      # (n_upgrades, K_risk) scenarios the CVaR term uses

    def plan_cvar(self, indices: list[int]) -> float:
        """Exact worst-5% mean of the plan's NPV over the risk scenarios (0 for an empty plan)."""
        if not indices:
            return 0.0
        return float(cvar(self.risk_npv[sorted(indices)].sum(axis=0), ALPHA))

    def score(self, indices: list[int]) -> float:
        """The objective both solvers maximize: E[NPV] + risk_lambda x CVaR5."""
        by = {c.index: c for c in self.candidates}
        npv = sum(by[i].exp_npv for i in indices)
        return npv + (self.risk_lambda * self.plan_cvar(indices) if self.risk_lambda else 0.0)


def build_problem(sim: SimulationResult, upgrades: list[FeasibleUpgrade], *,
                  baseline_tonnes_per_year: float, target_pct: float,
                  budget_usd: float | None = None, exclusions: Iterable[str] = (),
                  risk_lambda: float = 0.0, n_risk_scenarios: int = 1000) -> Problem:
    if [u.upgrade_id for u in upgrades] != sim.upgrade_ids:
        raise ValueError("upgrades must be the same list, in the same order, that was simulated")
    if not 0 <= target_pct <= 100:
        raise ValueError("target_pct is a percentage 0-100, e.g. 40 for 40%")
    if budget_usd is not None and budget_usd < 0:
        raise ValueError("budget_usd must be >= 0")
    if risk_lambda < 0:
        raise ValueError("risk_lambda must be >= 0 (0 = ignore risk)")
    if n_risk_scenarios < 1:
        raise ValueError("n_risk_scenarios must be >= 1")
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
            verified=u.verified != "unverified",
        ))
    return Problem(sim=sim, candidates=cands,
                   tonnes_needed=target_pct / 100.0 * baseline_tonnes_per_year,
                   budget_usd=budget_usd, target_pct=target_pct, exclusions=ex,
                   risk_lambda=float(risk_lambda),
                   risk_npv=np.ascontiguousarray(sim.npv[:, :min(n_risk_scenarios, sim.n_scenarios)]))


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

    best_ok: tuple[float, list[Candidate]] | None = None        # max score among plans hitting target
    best_any: tuple[float, float, list[Candidate]] | None = None  # max tonnes (then NPV) overall
    for choice in itertools.product(*[[None, *g] for g in groups]):
        plan = [c for c in choice if c is not None]
        if p.budget_usd is not None and sum(c.upfront_usd for c in plan) > p.budget_usd + 1e-6:
            continue
        npv = sum(c.exp_npv for c in plan)
        tonnes = sum(c.tonnes_per_year for c in plan)
        if tonnes >= p.tonnes_needed - EPS_TONNES:
            score = p.score([c.index for c in plan])
            if best_ok is None or score > best_ok[0]:
                best_ok = (score, plan)
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
            # Cuts and heuristics off: same optimum (tested against brute force), but the
            # CVaR model (1,000 tail rows) solves ~40% faster without them.
            return pulp.PULP_CBC_CMD(msg=0, options=["cuts off", "heuristics off"])
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
        obj = pulp.lpSum(by[i].exp_npv * v for i, v in x.items())
        if p.risk_lambda > 0 and x:
            k = p.risk_npv.shape[1]
            eta = m.add_variable("eta")                                       # free
            u = [m.add_variable(f"u_{j}", lowBound=0) for j in range(k)]
            for j in range(k):
                m += u[j] >= eta - pulp.lpSum(float(p.risk_npv[i, j]) * v for i, v in x.items()), f"tail_{j}"
            obj = obj + p.risk_lambda * (eta - pulp.lpSum(u) / (ALPHA * k))
        m += obj
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


def _solve_indices(p: Problem) -> tuple[list[int], str]:
    selected = _run(*_model(p, "npv"))
    if selected is not None:
        return selected, "ok"
    closest = _run(*_model(p, "tonnes"))
    if closest is None:
        raise RuntimeError("solver failed on the max-tonnes model, which is always feasible")
    return closest, "infeasible"


def solve(p: Problem) -> dict:
    """PuLP model; same result format as brute_force()."""
    selected, status = _solve_indices(p)
    return _result(p, selected, status=status)


# --- minimum chance of hitting the target ------------------------------------------------

P_HIT_STEP_PCT = 2.0        # raise the internal target by 2 percentage points per retry
MAX_P_HIT_RETRIES = 10


def _p_hit(p: Problem, selected: list[int]) -> float:
    if not selected:
        return float(p.tonnes_needed <= EPS_TONNES)
    tonnes = p.sim.tonnes_per_year[sorted(selected)].sum(axis=0)
    return float((tonnes >= p.tonnes_needed - EPS_TONNES).mean())


def solve_with_min_p_hit(sim: SimulationResult, upgrades: list[FeasibleUpgrade], *,
                         baseline_tonnes_per_year: float, target_pct: float,
                         min_p_hit: float = 0.8, budget_usd: float | None = None,
                         exclusions: Iterable[str] = (), risk_lambda: float = 0.0,
                         n_risk_scenarios: int = 1000) -> dict:
    """Solve, then make the plan likely (not just expected) to hit the owner's target.

    The constraint uses EXPECTED tonnes, so a plan that only just clears the target
    hits it in about half the scenarios. If p_hit_target < min_p_hit, raise the
    internal target by 2 percentage points and re-solve, at most 10 times. Every
    result is still judged against the owner's real target: tonnes_needed,
    p_hit_target and shortfall all use target_pct, not the internal one.

    Returns the first plan that reaches min_p_hit; if none does (the raised target
    becomes unreachable, or 10 retries run out), the plan with the highest p_hit.
    Extra fields: internal_target_pct, min_p_hit, met_min_p_hit, p_hit_retries.
    """
    if not 0 <= min_p_hit <= 1:
        raise ValueError("min_p_hit is a probability 0-1, e.g. 0.8")
    kw = dict(baseline_tonnes_per_year=baseline_tonnes_per_year, budget_usd=budget_usd,
              exclusions=exclusions, risk_lambda=risk_lambda, n_risk_scenarios=n_risk_scenarios)
    user = build_problem(sim, upgrades, target_pct=target_pct, **kw)
    id_extra = {"min_p_hit": min_p_hit}

    best_sel, status = _solve_indices(user)
    best_internal, best_p, retries = target_pct, _p_hit(user, best_sel), 0
    internal = target_pct
    if status == "ok":
        while best_p < min_p_hit and retries < MAX_P_HIT_RETRIES and internal < 100:
            internal = min(internal + P_HIT_STEP_PCT, 100.0)
            retries += 1
            sel, st = _solve_indices(build_problem(sim, upgrades, target_pct=internal, **kw))
            if st != "ok":
                break                      # raised target unreachable: keep the best so far
            ph = _p_hit(user, sel)
            if ph > best_p:
                best_sel, best_internal, best_p = sel, internal, ph

    out = _result(user, best_sel, status=status, id_extra=id_extra)
    out.update(internal_target_pct=best_internal, min_p_hit=min_p_hit,
               met_min_p_hit=out["p_hit_target"] >= min_p_hit, p_hit_retries=retries)
    return out


# --- shared result -----------------------------------------------------------------------

def plan_id(p: Problem, **extra) -> str:
    """Same inputs -> same ID. Hashes the simulated NPVs too, so changed assumptions change it.
    extra: other request settings that change the answer (risk_lambda, min_p_hit)."""
    h = hashlib.sha256()
    h.update(json.dumps({
        "upgrades": p.sim.upgrade_ids, "seed": p.sim.seed, "k": p.sim.n_scenarios,
        "target_pct": p.target_pct, "budget_usd": p.budget_usd, "exclusions": p.exclusions,
        "risk_lambda": p.risk_lambda, "k_risk": int(p.risk_npv.shape[1]),
        **extra,
    }, sort_keys=True).encode())
    h.update(np.ascontiguousarray(p.sim.npv).tobytes())
    return h.hexdigest()[:12]


def _bar(c: Candidate) -> dict:
    return {"upgrade_id": c.upgrade_id, "building_id": c.building_id, "type": c.type,
            "tonnes_per_year": c.tonnes_per_year, "cost_per_tonne": c.cost_per_tonne}


def _result(p: Problem, selected: list[int], *, status: str, id_extra: dict | None = None) -> dict:
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
        in_slot = {(c.building_id, c.category): c for c in p.candidates if c.index in chosen}
        # Candidates: eligible but unselected, owner-excluded, AND unverified (include_in_optimizer
        # False) ones, flagged verified: False so the UI can offer "include unverified".
        extras = [c for c in p.candidates
                  if c.index not in chosen
                  and np.isfinite(c.cost_per_tonne)
                  and c.tonnes_per_year > (in_slot[(c.building_id, c.category)].tonnes_per_year
                                           if (c.building_id, c.category) in in_slot else 0.0)]
        extras.sort(key=lambda c: (c.cost_per_tonne, c.upgrade_id))
        plan_upfront = sum(sim.inputs[i].upfront_usd for i in sel)

        def fits(c: Candidate) -> bool:
            # Adding c (and dropping whatever it replaces in its slot) stays within budget.
            if p.budget_usd is None:
                return True
            replaced = in_slot.get((c.building_id, c.category))
            new_total = plan_upfront - (replaced.upfront_usd if replaced else 0.0) + c.upfront_usd
            return new_total <= p.budget_usd + 1e-6

        cheapest_extra = [{**_bar(c), "verified": c.verified, "fits_budget": fits(c)}
                          for c in extras[:N_CHEAPEST_EXTRA]]
    else:
        shortfall, cheapest_extra = 0.0, []

    return {
        "plan_id": plan_id(p, **(id_extra or {})),
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
