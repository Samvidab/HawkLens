"""optimize min_p_hit (raise internal target until the plan is LIKELY to hit) and fits_budget."""
from pathlib import Path

import pytest

from app.engine import optimizer
from app.engine.buildings import baseline_tonnes_per_year, load_building
from app.engine.models import load_assumptions, load_feasibility
from app.engine.monte_carlo import simulate
from app.engine.optimizer import build_problem, solve, solve_with_min_p_hit

FIXTURES = Path(__file__).parent / "fixtures"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]


@pytest.fixture(scope="module")
def setup():
    a = load_assumptions()
    buildings = {b: load_building(b, root=FIXTURES, assumptions=a) for b in BUILDING_IDS}
    upgrades = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    sim = simulate(upgrades, buildings, a, n_scenarios=10_000)
    base = sum(baseline_tonnes_per_year(b, a) for b in buildings.values())
    return sim, upgrades, base


def run(setup, **kw):
    sim, upgrades, base = setup
    return solve_with_min_p_hit(sim, upgrades, baseline_tonnes_per_year=base, **kw)


def real_p_hit(setup, r):
    """Recompute p_hit against the OWNER's target from the raw scenarios."""
    sim, _, base = setup
    rows = [sim.index(u) for u in r["selected"]]
    tonnes = sim.tonnes_per_year[rows].sum(axis=0)
    return float((tonnes >= r["tonnes_needed"] - 1e-6).mean())


# --- min_p_hit -----------------------------------------------------------------------------

def test_raises_internal_target_until_p_hit_met(setup):
    """25%: the plain plan hits 25% in only ~57% of scenarios; one 2-point raise (27%) gets >= 0.8."""
    plain = solve(build_problem(setup[0], setup[1], baseline_tonnes_per_year=setup[2], target_pct=25))
    assert plain["p_hit_target"] < 0.8
    r = run(setup, target_pct=25, min_p_hit=0.8)
    assert r["met_min_p_hit"] and r["p_hit_target"] >= 0.8
    assert r["internal_target_pct"] > 25 and (r["internal_target_pct"] - 25) % 2 == 0
    assert r["p_hit_retries"] == (r["internal_target_pct"] - 25) / 2


def test_reported_numbers_use_the_owners_target_not_the_internal_one(setup):
    _, _, base = setup
    r = run(setup, target_pct=25, min_p_hit=0.8)
    assert r["tonnes_needed"] == pytest.approx(0.25 * base)          # not 27%
    assert r["p_hit_target"] == pytest.approx(real_p_hit(setup, r))
    assert r["status"] == "ok" and r["shortfall_tonnes"] == 0


def test_already_met_needs_no_retry(setup):
    r = run(setup, target_pct=10, min_p_hit=0.8)
    assert r["internal_target_pct"] == 10 and r["p_hit_retries"] == 0 and r["met_min_p_hit"]


def test_min_p_hit_zero_matches_plain_solve(setup):
    sim, upgrades, base = setup
    r = run(setup, target_pct=25, min_p_hit=0)
    plain = solve(build_problem(sim, upgrades, baseline_tonnes_per_year=base, target_pct=25))
    assert r["selected"] == plain["selected"] and r["internal_target_pct"] == 25


def test_stops_when_raised_target_is_unreachable_and_returns_best(setup):
    """40%: 42% is reachable (580.8 t max = 42.1%), 44% is not -> stop after 2 retries.
    Best plan hits 40% in ~72% of scenarios: below 0.8, so met_min_p_hit is False."""
    r = run(setup, target_pct=40, min_p_hit=0.8)
    assert r["status"] == "ok"
    assert r["internal_target_pct"] == 42 and r["p_hit_retries"] == 2
    assert not r["met_min_p_hit"] and r["p_hit_target"] < 0.8
    assert r["p_hit_target"] == pytest.approx(real_p_hit(setup, r))


def test_never_more_than_10_retries(setup, monkeypatch):
    """Force p_hit to look 0 every time: the loop must stop after 10 re-solves (+20 points)."""
    monkeypatch.setattr(optimizer, "_p_hit", lambda p, sel: 0.0)
    r = run(setup, target_pct=5, min_p_hit=0.8)
    assert r["p_hit_retries"] == 10
    assert r["internal_target_pct"] == 5      # nothing beat p_hit 0, so the first plan is kept


def test_infeasible_target_skips_the_loop(setup):
    r = run(setup, target_pct=60, min_p_hit=0.8)
    assert r["status"] == "infeasible" and r["p_hit_retries"] == 0
    assert r["internal_target_pct"] == 60 and not r["met_min_p_hit"]


def test_min_p_hit_must_be_a_probability(setup):
    with pytest.raises(ValueError, match="probability"):
        run(setup, target_pct=25, min_p_hit=80)


def test_min_p_hit_is_part_of_plan_id(setup):
    assert run(setup, target_pct=10, min_p_hit=0.8)["plan_id"] != \
           run(setup, target_pct=10, min_p_hit=0.5)["plan_id"]


# --- fits_budget -------------------------------------------------------------------------------

def test_fits_budget_false_when_extra_would_break_the_budget(setup):
    """$200k budget, 40%: each solar costs $279k-$768k on its own -> none fits."""
    r = run(setup, target_pct=40, budget_usd=200_000, min_p_hit=0)
    assert r["status"] == "infeasible"
    assert [e["fits_budget"] for e in r["cheapest_extra"]] == [False] * len(r["cheapest_extra"])
    assert all(e["upgrade_id"].endswith("rooftop_solar") for e in r["cheapest_extra"])


def test_fits_budget_true_when_room_or_no_budget(setup):
    """Excluding hou-002 solar makes 40% unreachable; with no budget, or a big one, it fits."""
    for budget in (None, 10_000_000):
        r = run(setup, target_pct=40, budget_usd=budget, exclusions=["hou-002-rooftop_solar"],
                min_p_hit=0)
        first = r["cheapest_extra"][0]
        assert first["upgrade_id"] == "hou-002-rooftop_solar" and first["fits_budget"] is True


def test_fits_budget_rule_matches_hand_computation(setup):
    """fits_budget == (plan spend - cost of the slot-mate it replaces + its own cost <= budget),
    checked for every suggestion across several budgets."""
    sim, upgrades, _ = setup
    slot = {u.upgrade_id: (u.building_id, u.category) for u in upgrades}
    cost = {uid: sim.inputs[i].upfront_usd for i, uid in enumerate(sim.upgrade_ids)}
    checked = 0
    for budget in (200_000, 400_000, 1_000_000, 2_500_000):
        r = run(setup, target_pct=40, budget_usd=budget, min_p_hit=0)
        for e in r["cheapest_extra"]:
            replaced = sum(cost[s] for s in r["selected"] if slot[s] == slot[e["upgrade_id"]])
            expected = r["total_upfront"] - replaced + cost[e["upgrade_id"]] <= budget + 1e-6
            assert e["fits_budget"] is expected, (budget, e["upgrade_id"])
            checked += 1
    assert checked >= 6
