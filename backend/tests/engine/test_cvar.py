"""Step 7: optimizer with the CVaR risk term (Rockafellar-Uryasev), checked against brute force."""
from pathlib import Path

import numpy as np
import pulp
import pytest

import app.engine as engine
from app.engine import optimizer, state
from app.engine.buildings import baseline_tonnes_per_year, load_building
from app.engine.models import load_assumptions, load_feasibility
from app.engine.monte_carlo import simulate
from app.engine.optimizer import brute_force, build_problem, solve
from app.engine.risk import cvar

FIXTURES = Path(__file__).parent / "fixtures"
TEST_ASSUMPTIONS = FIXTURES / "assumptions.json"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]
LAMBDAS = [0, 0.25, 0.5, 1, 2, 5]


@pytest.fixture(scope="module")
def setup():
    a = load_assumptions(TEST_ASSUMPTIONS)   # frozen placeholders: mechanics, not data
    buildings = {b: load_building(b, root=FIXTURES, assumptions=a) for b in BUILDING_IDS}
    upgrades = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    sim = simulate(upgrades, buildings, a, n_scenarios=10_000)
    base = sum(baseline_tonnes_per_year(b, a) for b in buildings.values())
    return sim, upgrades, base


def problem(setup, **kw):
    sim, upgrades, base = setup
    return build_problem(sim, upgrades, baseline_tonnes_per_year=base, n_risk_scenarios=1000, **kw)


# --- PuLP == brute force with the risk term -----------------------------------------------

@pytest.mark.parametrize("risk_lambda", [0.25, 0.5, 2])
@pytest.mark.parametrize("target_pct", [10, 25])
def test_pulp_matches_brute_force_with_cvar(setup, target_pct, risk_lambda):
    p = problem(setup, target_pct=target_pct, risk_lambda=risk_lambda)
    got, oracle = solve(p), brute_force(p)
    assert got["selected"] == oracle["selected"]
    sel = [c.index for c in p.candidates if c.upgrade_id in got["selected"]]
    assert p.score(sel) == pytest.approx(p.score([c.index for c in p.candidates
                                                  if c.upgrade_id in oracle["selected"]]))


def test_lambda_zero_is_plain_expected_npv(setup):
    """risk_lambda = 0 must give exactly the step-5 plan."""
    for target in (10, 25, 40):
        with_risk_arg = solve(problem(setup, target_pct=target, risk_lambda=0))
        sim, upgrades, base = setup
        plain = solve(build_problem(sim, upgrades, baseline_tonnes_per_year=base, target_pct=target))
        assert with_risk_arg["selected"] == plain["selected"]


def test_rockafellar_uryasev_term_equals_exact_worst_5_percent(setup):
    """At the optimum, eta - sum(u)/(alpha K) must equal the plan's exact worst-50-of-1000 mean."""
    p = problem(setup, target_pct=10, risk_lambda=0.5)
    m, x = optimizer._model(p, "npv")
    m.solve(optimizer._solver())
    assert m.status == pulp.LpStatusOptimal
    sel = sorted(i for i, v in x.items() if v.value() > 0.5)
    v = {var.name: var.value() for var in m.variables()}
    k = p.risk_npv.shape[1]
    ru = v["eta"] - sum(v[f"u_{j}"] for j in range(k)) / (0.05 * k)
    exact = float(cvar(p.risk_npv[sel].sum(axis=0), 0.05))
    assert ru == pytest.approx(exact, rel=1e-6, abs=1e-3)


# --- what raising lambda guarantees ---------------------------------------------------------

@pytest.mark.parametrize("target_pct", [0, 10, 25])
def test_raising_lambda_never_worsens_cvar_or_raises_expected_npv(setup, target_pct):
    """For optimal solutions: higher lambda -> CVaR (on the optimizer's scenarios) up or equal,
    E[NPV] down or equal. This is what the math guarantees; p_loss is NOT guaranteed to fall
    (see CLAUDE.md "Sanity checks")."""
    cvars, npvs = [], []
    for lam in LAMBDAS:
        p = problem(setup, target_pct=target_pct, risk_lambda=lam)
        r = solve(p)
        sel = [c.index for c in p.candidates if c.upgrade_id in r["selected"]]
        cvars.append(p.plan_cvar(sel))
        npvs.append(sum(c.exp_npv for c in p.candidates if c.index in sel))
    assert all(b >= a - 1e-6 for a, b in zip(cvars, cvars[1:])), cvars
    assert all(b <= a + 1e-6 for a, b in zip(npvs, npvs[1:])), npvs


def test_risk_term_changes_the_plan_on_the_fixtures(setup):
    """At 10%, lambda 0.5 swaps the 5-upgrade money-maker for a smaller, safer plan."""
    calm = solve(problem(setup, target_pct=10, risk_lambda=0))
    careful = solve(problem(setup, target_pct=10, risk_lambda=0.5))
    assert careful["selected"] != calm["selected"]
    assert careful["cvar5"] > calm["cvar5"]
    assert careful["tonnes_per_year"] >= careful["tonnes_needed"] - 1e-6


def test_high_lambda_with_no_target_does_nothing(setup):
    """Every upgrade's worst 5% is a loss, so with no target and enough risk aversion the
    best plan is to do nothing (score 0)."""
    r = solve(problem(setup, target_pct=0, risk_lambda=1))
    assert r["selected"] == [] and r["exp_npv"] == 0


# --- inputs and ids ------------------------------------------------------------------------

def test_negative_lambda_rejected(setup):
    with pytest.raises(ValueError, match="risk_lambda"):
        problem(setup, target_pct=10, risk_lambda=-0.5)


def test_plan_id_depends_on_lambda(setup):
    assert solve(problem(setup, target_pct=25, risk_lambda=0))["plan_id"] != \
           solve(problem(setup, target_pct=25, risk_lambda=0.5))["plan_id"]


def test_risk_scenarios_are_the_first_n_optimizer_scenarios(setup):
    p = problem(setup, target_pct=10, risk_lambda=0.5)
    assert p.risk_npv.shape == (len(setup[1]), 1000)
    assert np.array_equal(p.risk_npv, setup[0].npv[:, :1000])


# --- contract ------------------------------------------------------------------------------

def test_contract_risk_lambda_is_applied():
    state.clear()
    engine.configure(buildings_root=FIXTURES, assumptions_path=TEST_ASSUMPTIONS)
    try:
        ups = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
        engine.simulate(ups, {})
        engine.set_assumption("min_p_hit", 0)
        calm = engine.optimize(10, 0.0, None, [])
        careful = engine.optimize(10, 0.5, None, [])
        assert calm["selected"] != careful["selected"]
        assert careful["cvar5"] > calm["cvar5"]
        assert engine.optimize(10, 0.5, None, []) == careful        # deterministic
    finally:
        state.clear()
