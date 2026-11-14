"""Step 5: optimizer (max expected NPV), PuLP checked against brute force."""
from pathlib import Path

import pulp
import pytest

from app.engine import optimizer
from app.engine.buildings import baseline_tonnes_per_year, load_building
from app.engine.models import load_assumptions, load_feasibility
from app.engine.monte_carlo import simulate
from app.engine.optimizer import brute_force, build_problem, solve

FIXTURES = Path(__file__).parent / "fixtures"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]
RESULT_KEYS = {"plan_id", "selected", "exp_npv", "cvar5", "p_hit_target", "total_upfront",
               "tonnes_per_year", "status", "p_loss", "hist_bins", "tonnes_needed",
               "shortfall_tonnes", "cheapest_extra"}


@pytest.fixture(scope="module")
def setup():
    a = load_assumptions()
    buildings = {b: load_building(b, root=FIXTURES, assumptions=a) for b in BUILDING_IDS}
    upgrades = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    sim = simulate(upgrades, buildings, a, n_scenarios=10_000)
    base = sum(baseline_tonnes_per_year(b, a) for b in buildings.values())   # 1,379.4 t/yr
    return sim, upgrades, base


def problem(setup, **kw):
    sim, upgrades, base = setup
    return build_problem(sim, upgrades, baseline_tonnes_per_year=base, **kw)


def assert_same(a, b):
    assert a["status"] == b["status"]
    assert a["selected"] == b["selected"]
    assert a["exp_npv"] == pytest.approx(b["exp_npv"])
    assert a["tonnes_per_year"] == pytest.approx(b["tonnes_per_year"])


# --- requested: PuLP == brute force at 3 targets ------------------------------------------

@pytest.mark.parametrize("target_pct", [10, 25, 40])
def test_pulp_matches_brute_force(setup, target_pct):
    p = problem(setup, target_pct=target_pct)
    got = solve(p)
    assert got["status"] == "ok"
    assert got["tonnes_per_year"] >= got["tonnes_needed"] - 1e-6
    assert_same(got, brute_force(p))


# --- more cross-checks with the oracle -----------------------------------------------------

@pytest.mark.parametrize("kw", [
    {"target_pct": 25, "budget_usd": 1_500_000},
    {"target_pct": 20, "exclusions": ["hou-002"]},
    {"target_pct": 30, "exclusions": ["hou-001-heat_pump", "hou-003-rooftop_solar"]},
    {"target_pct": 0},
])
def test_pulp_matches_brute_force_with_budget_and_exclusions(setup, kw):
    p = problem(setup, **kw)
    assert_same(solve(p), brute_force(p))


def test_infeasible_target_matches_brute_force_and_reports_shortfall(setup):
    """Max reachable = 580.8 t/yr (42% of 1,379.4); 50% needs 689.7 -> short by ~108.9."""
    p = problem(setup, target_pct=50)
    got = solve(p)
    assert_same(got, brute_force(p))
    assert got["status"] == "infeasible"
    assert got["shortfall_tonnes"] == pytest.approx(got["tonnes_needed"] - got["tonnes_per_year"])
    assert got["shortfall_tonnes"] > 100
    # Every eligible upgrade is used or would only replace a bigger slot-mate; the one thing
    # left that adds tonnes is the unverified hou-003 window upgrade (22.9 t/yr).
    extras = got["cheapest_extra"]
    assert [e["upgrade_id"] for e in extras] == ["hou-003-window_upgrade"]
    assert extras[0]["verified"] is False and extras[0]["fits_budget"] is True


def test_cheapest_extra_suggests_excluded_upgrades_that_add_tonnes(setup):
    """Excluding hou-002 solar (160.5 t/yr) makes 40% unreachable; it's the cheapest fix."""
    got = solve(problem(setup, target_pct=40, exclusions=["hou-002-rooftop_solar"]))
    assert got["status"] == "infeasible"
    extra_ids = [e["upgrade_id"] for e in got["cheapest_extra"]]
    assert extra_ids[0] == "hou-002-rooftop_solar"
    assert len(extra_ids) <= 3
    costs = [e["cost_per_tonne"] for e in got["cheapest_extra"]]
    assert costs == sorted(costs)


# --- constraints ---------------------------------------------------------------------------

def test_one_upgrade_per_building_per_category(setup):
    sim, upgrades, _ = setup
    cat = {u.upgrade_id: (u.building_id, u.category) for u in upgrades}
    for target in (10, 25, 40, 50):
        slots = [cat[s] for s in solve(problem(setup, target_pct=target))["selected"]]
        assert len(slots) == len(set(slots)), target


def test_budget_is_respected(setup):
    got = solve(problem(setup, target_pct=10, budget_usd=400_000))
    assert got["total_upfront"] <= 400_000


def test_excluded_building_and_unverified_upgrade_never_selected(setup):
    for target in (10, 25, 40, 50):
        sel = solve(problem(setup, target_pct=target, exclusions=["hou-002"]))["selected"]
        assert not any(s.startswith("hou-002") for s in sel)
        assert "hou-003-window_upgrade" not in sel


def test_result_has_contract_keys_and_valid_ranges(setup):
    got = solve(problem(setup, target_pct=25))
    assert set(got) == RESULT_KEYS
    assert 0 <= got["p_loss"] <= 1 and 0 <= got["p_hit_target"] <= 1
    assert len(got["hist_bins"]) == 30
    assert got["tonnes_needed"] == pytest.approx(0.25 * setup[2])


def test_plan_id_is_stable_and_input_sensitive(setup):
    a = solve(problem(setup, target_pct=25))["plan_id"]
    assert a == solve(problem(setup, target_pct=25))["plan_id"]
    assert a != solve(problem(setup, target_pct=26))["plan_id"]
    assert a != solve(problem(setup, target_pct=25, exclusions=["hou-001"]))["plan_id"]


def test_target_pct_must_be_a_percentage(setup):
    with pytest.raises(ValueError, match="percentage"):
        problem(setup, target_pct=140)


# --- solver selection ----------------------------------------------------------------------

def test_falls_back_to_highs_then_errors(monkeypatch):
    optimizer._solver_name.cache_clear()
    monkeypatch.setattr(pulp, "listSolvers", lambda onlyAvailable=False: ["HiGHS"])
    assert optimizer._solver_name() == "HiGHS"
    optimizer._solver_name.cache_clear()
    monkeypatch.setattr(pulp, "listSolvers", lambda onlyAvailable=False: [])
    with pytest.raises(RuntimeError, match="no MILP solver"):
        optimizer._solver_name()
    optimizer._solver_name.cache_clear()


def test_prefers_cbc_when_available():
    optimizer._solver_name.cache_clear()
    assert optimizer._solver_name() == "PULP_CBC_CMD"
