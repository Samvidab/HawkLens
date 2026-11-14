"""Step 6: contract functions (TRD §8.1 + engine/CLAUDE.md extras): keys, types, caching."""
import json
from pathlib import Path

import pytest

import app.engine as engine
from app.engine import state
from app.engine.models import load_feasibility

FIXTURES = Path(__file__).parent / "fixtures"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]

TRD_SIM_KEYS = {"exp_npv", "p_loss", "cvar5", "tonnes_lifetime", "cost_per_tonne", "hist_bins"}
EXTRA_SIM_KEYS = {"upfront_usd", "tonnes_per_year"}
TRD_BAR_KEYS = {"upgrade_id", "building_id", "type", "tonnes_per_year", "cost_per_tonne"}
TRD_PLAN_KEYS = {"plan_id", "selected", "exp_npv", "cvar5", "p_hit_target", "total_upfront",
                 "tonnes_per_year"}
EXTRA_PLAN_KEYS = {"status", "p_loss", "hist_bins", "tonnes_needed", "shortfall_tonnes",
                   "cheapest_extra", "internal_target_pct", "min_p_hit", "met_min_p_hit",
                   "p_hit_retries"}


@pytest.fixture
def upgrades():
    return [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]


@pytest.fixture(autouse=True)
def fresh_state():
    state.clear()
    yield
    state.clear()


@pytest.fixture
def simulated(upgrades):
    return engine.simulate(upgrades, {}, buildings_root=FIXTURES)


def is_num(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def assert_hist(bins):
    assert len(bins) == 30
    assert all(set(b) == {"x0", "x1", "count"} and isinstance(b["count"], int) for b in bins)


# --- simulate ------------------------------------------------------------------------------

def test_simulate_keys_and_types(simulated, upgrades):
    assert set(simulated) == {u.upgrade_id for u in upgrades}
    for uid, r in simulated.items():
        assert set(r) == TRD_SIM_KEYS | EXTRA_SIM_KEYS, uid
        for k in (TRD_SIM_KEYS | EXTRA_SIM_KEYS) - {"hist_bins"}:
            assert is_num(r[k]), (uid, k)
        assert 0 <= r["p_loss"] <= 1
        assert_hist(r["hist_bins"])
    json.dumps(simulated, allow_nan=False)            # plain JSON, no NaN/inf


def test_simulate_accepts_dicts_and_caches(upgrades):
    as_dicts = [u.model_dump() for u in upgrades]
    out = engine.simulate(as_dicts, {}, buildings_root=FIXTURES)
    assert len(out) == len(upgrades)
    assert state.has_simulation() and not state.is_stale()


def test_simulate_assumptions_arg_nested_and_dotted(upgrades):
    base = engine.simulate(upgrades, {}, buildings_root=FIXTURES)
    nested = engine.simulate(upgrades, {"upgrades": {"led_retrofit": {"unit_cost": 0.5}}},
                             buildings_root=FIXTURES)
    dotted = engine.simulate(upgrades, {"upgrades.led_retrofit.unit_cost": 0.5},
                             buildings_root=FIXTURES)
    led = "hou-001-led_retrofit"
    assert nested[led]["exp_npv"] > base[led]["exp_npv"]
    assert dotted[led]["exp_npv"] == pytest.approx(nested[led]["exp_npv"])
    assert dotted["hou-001-rooftop_solar"] == base["hou-001-rooftop_solar"]   # others untouched


def test_simulate_rejects_unknown_assumption(upgrades):
    with pytest.raises(KeyError):
        engine.simulate(upgrades, {"global.not_a_field": 1}, buildings_root=FIXTURES)


# --- macc ----------------------------------------------------------------------------------

def test_macc_keys_and_order(simulated):
    bars = engine.macc([])["bars"]
    assert all(set(b) == TRD_BAR_KEYS for b in bars)
    assert [b["cost_per_tonne"] for b in bars] == sorted(b["cost_per_tonne"] for b in bars)
    assert {b["upgrade_id"] for b in engine.macc(["hou-001"])["bars"]}.isdisjoint(
        {u for u in simulated if u.startswith("hou-001")})


def test_macc_and_optimize_need_a_simulation():
    with pytest.raises(state.NoSimulation):
        engine.macc([])
    with pytest.raises(state.NoSimulation):
        engine.optimize(25, 0, None, [])


# --- optimize ------------------------------------------------------------------------------

def test_optimize_keys_and_types(simulated):
    r = engine.optimize(25, 0.0, None, [])
    assert set(r) == TRD_PLAN_KEYS | EXTRA_PLAN_KEYS
    assert isinstance(r["plan_id"], str) and len(r["plan_id"]) == 12
    assert isinstance(r["selected"], list) and all(isinstance(s, str) for s in r["selected"])
    for k in ("exp_npv", "cvar5", "p_hit_target", "total_upfront", "tonnes_per_year",
              "p_loss", "tonnes_needed", "shortfall_tonnes", "internal_target_pct", "min_p_hit"):
        assert is_num(r[k]), k
    assert r["status"] in ("ok", "infeasible")
    assert isinstance(r["met_min_p_hit"], bool) and isinstance(r["p_hit_retries"], int)
    assert_hist(r["hist_bins"])
    json.dumps(r, allow_nan=False)


def test_optimize_positional_call_matches_trd_signature(simulated):
    """TRD: optimize(target_pct, risk_lambda, budget_usd, exclusions)."""
    a = engine.optimize(25, 0.0, None, ["hou-002"])
    assert not any(s.startswith("hou-002") for s in a["selected"])


def test_optimize_is_deterministic(simulated):
    assert engine.optimize(25, 0, None, []) == engine.optimize(25, 0, None, [])


def test_infeasible_has_cheapest_extra_with_fits_budget(simulated):
    r = engine.optimize(40, 0, None, ["hou-002-rooftop_solar"], min_p_hit=0)
    assert r["status"] == "infeasible" and r["shortfall_tonnes"] > 0
    assert r["cheapest_extra"]
    for e in r["cheapest_extra"]:
        assert set(e) == TRD_BAR_KEYS | {"fits_budget"}


# --- set_assumption --------------------------------------------------------------------------

def test_set_assumption_ok_marks_stale_and_next_call_resimulates(simulated):
    before = {b["upgrade_id"]: b["cost_per_tonne"] for b in engine.macc([])["bars"]}
    assert engine.set_assumption("upgrades.led_retrofit.unit_cost", 0.5) == {"ok": True}
    assert state.is_stale()
    after = {b["upgrade_id"]: b["cost_per_tonne"] for b in engine.macc([])["bars"]}
    assert not state.is_stale()
    assert after["hou-001-led_retrofit"] < before["hou-001-led_retrofit"]
    assert after["hou-001-rooftop_solar"] == before["hou-001-rooftop_solar"]


def test_set_assumption_bare_global_key(simulated):
    assert engine.set_assumption("discount_rate", 0.05)["ok"]
    assert state.overrides() == {"discount_rate": 0.05}


def test_set_assumption_survives_a_new_simulate(upgrades):
    engine.set_assumption("upgrades.led_retrofit.unit_cost", 0.5)     # before any simulate
    cheap = engine.simulate(upgrades, {}, buildings_root=FIXTURES)["hou-001-led_retrofit"]
    state.clear()
    normal = engine.simulate(upgrades, {}, buildings_root=FIXTURES)["hou-001-led_retrofit"]
    assert cheap["upfront_usd"] < normal["upfront_usd"]


@pytest.mark.parametrize("key,value,err", [
    ("global.not_a_field", 1, "KeyError"),
    ("upgrades.led_retrofit.unit_cost", "cheap", "TypeError"),
    ("discount_rate", 7, "ValueError"),            # 7 instead of 0.07
    ("global.max_savings_share", 50, "ValueError"),
])
def test_set_assumption_rejects_bad_input_and_changes_nothing(simulated, key, value, err):
    r = engine.set_assumption(key, value)
    assert r["ok"] is False and r["error"].startswith(err)
    assert state.overrides() == {} and not state.is_stale()


# --- baseline ------------------------------------------------------------------------------

def test_baseline_hand_check(simulated):
    """hou-001: 15 kWh/sqft (Office) x 120,000 sqft = 1,800,000 kWh.
    Spend = 1.8M x $0.12 = $216,000; CO2 = 1.8M x 0.38 / 1000 = 684.0 t/yr."""
    assert engine.baseline("hou-001") == pytest.approx({"annual_spend_usd": 216_000,
                                                         "tonnes_per_year": 684.0})


def test_baseline_without_simulation_uses_root():
    r = engine.baseline("hou-002", buildings_root=FIXTURES)
    assert r["annual_spend_usd"] == pytest.approx(14 * 45_000 * 0.12)
