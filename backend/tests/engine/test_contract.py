"""Step 6: contract functions (TRD §8.1 + engine/CLAUDE.md extras): keys, types, caching."""
import json
from pathlib import Path

import pytest

import app.engine as engine
from app.engine import state
from app.engine.models import load_feasibility

FIXTURES = Path(__file__).parent / "fixtures"
TEST_ASSUMPTIONS = FIXTURES / "assumptions.json"   # frozen placeholders
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
    engine.configure(buildings_root=FIXTURES, assumptions_path=TEST_ASSUMPTIONS)
    yield
    state.clear()


@pytest.fixture
def simulated(upgrades):
    return engine.simulate(upgrades, {})


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
    out = engine.simulate(as_dicts, {})
    assert len(out) == len(upgrades)
    assert state.has_simulation() and not state.is_stale()


def test_simulate_assumptions_arg_nested_and_dotted(upgrades):
    base = engine.simulate(upgrades, {})
    nested = engine.simulate(upgrades, {"upgrades": {"led_retrofit": {"unit_cost": 0.5}}})
    dotted = engine.simulate(upgrades, {"upgrades.led_retrofit.unit_cost": 0.5})
    led = "hou-001-led_retrofit"
    assert nested[led]["exp_npv"] > base[led]["exp_npv"]
    assert dotted[led]["exp_npv"] == pytest.approx(nested[led]["exp_npv"])
    assert dotted["hou-001-rooftop_solar"] == base["hou-001-rooftop_solar"]   # others untouched


def test_simulate_rejects_unknown_assumption(upgrades):
    with pytest.raises(KeyError):
        engine.simulate(upgrades, {"global.not_a_field": 1})


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
    engine.set_assumption("min_p_hit", 0)
    r = engine.optimize(40, 0, None, ["hou-002-rooftop_solar"])
    assert r["status"] == "infeasible" and r["shortfall_tonnes"] > 0
    assert r["cheapest_extra"]
    for e in r["cheapest_extra"]:
        assert set(e) == TRD_BAR_KEYS | {"verified", "fits_budget"}
        assert isinstance(e["verified"], bool) and isinstance(e["fits_budget"], bool)


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
    cheap = engine.simulate(upgrades, {})["hou-001-led_retrofit"]
    state.clear()
    engine.configure(buildings_root=FIXTURES, assumptions_path=TEST_ASSUMPTIONS)
    normal = engine.simulate(upgrades, {})["hou-001-led_retrofit"]
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


def test_baseline_without_simulation_uses_configured_root():
    r = engine.baseline("hou-002")
    assert r["annual_spend_usd"] == pytest.approx(14 * 45_000 * 0.12)


# --- agent-side integration (from STATUS-support.md) -------------------------------------------

def test_app_engine_macc_is_always_the_function():
    """curve.py, not macc.py: importing every engine module must never turn app.engine.macc
    into a module."""
    import importlib
    for mod in ("curve", "optimizer", "monte_carlo", "state", "risk", "npv", "buildings"):
        importlib.import_module(f"app.engine.{mod}")
    import app.engine
    assert callable(app.engine.macc) and app.engine.macc is engine.macc
    with pytest.raises(ModuleNotFoundError):
        importlib.import_module("app.engine.macc")
    for name in ("simulate", "macc", "optimize", "set_assumption", "baseline"):
        assert callable(getattr(app.engine, name)), name


def test_simulate_accepts_the_agents_own_pydantic_model(upgrades):
    """The agent passes app.schemas.upgrades.FeasibleUpgrade (a different class with the same
    fields, ids like 'hou-001:led_retrofit'); pydantic refuses foreign instances directly."""
    from pydantic import BaseModel

    class AgentFeasibleUpgrade(BaseModel):          # same fields as the agent branch's schema
        upgrade_id: str; building_id: str; category: str; type: str; size_value: float
        size_unit: str; reason: str; confidence: float; claim_ids: list[str]
        evidence_ids: list[str]; verified: str; include_in_optimizer: bool

    theirs = [AgentFeasibleUpgrade(**{**u.model_dump(),
                                      "upgrade_id": f"{u.building_id}:{u.type}"}) for u in upgrades]
    out = engine.simulate(theirs, {"discount_rate": 0.07})
    assert "hou-001:led_retrofit" in out and len(out) == len(upgrades)
    assert engine.optimize(25, 0.5, None, ["hou-002"])["status"] == "ok"


def test_simulate_assumptions_bare_discount_rate(upgrades):
    """The agent sends assumptions={'discount_rate': Goal.discount_rate}: a bare global key."""
    low = engine.simulate(upgrades, {"discount_rate": 0.03})
    high = engine.simulate(upgrades, {"discount_rate": 0.12})
    solar = "hou-002-rooftop_solar"
    assert low[solar]["exp_npv"] > high[solar]["exp_npv"]     # lower discount rate -> worth more


def test_excluded_building_stays_in_the_targets_denominator(simulated):
    """Target = X% of the WHOLE simulated portfolio (1,379.4 t/yr), even with hou-002 excluded."""
    engine.set_assumption("min_p_hit", 0)
    full = engine.optimize(25, 0, None, [])
    without = engine.optimize(25, 0, None, ["hou-002"])
    assert without["tonnes_needed"] == pytest.approx(full["tonnes_needed"])
    assert full["tonnes_needed"] == pytest.approx(0.25 * (684.0 + 239.4 + 456.0))


def test_cheapest_extra_includes_unverified_with_verified_false(simulated):
    """At 50% every verified slot is used; the unverified hou-003 window upgrade is suggested."""
    engine.set_assumption("min_p_hit", 0)
    r = engine.optimize(50, 0, None, [])
    assert r["status"] == "infeasible"
    unverified = [e for e in r["cheapest_extra"] if e["upgrade_id"] == "hou-003-window_upgrade"]
    assert unverified and unverified[0]["verified"] is False
    assert all(e["verified"] is True for e in r["cheapest_extra"] if e is not unverified[0])



TRD_SIGNATURES = {
    "simulate": ["upgrades", "assumptions"],
    "macc": ["exclusions"],
    "optimize": ["target_pct", "risk_lambda", "budget_usd", "exclusions"],
    "set_assumption": ["key", "value"],
    "baseline": ["building_id"],
}


def test_signatures_match_trd_exactly():
    """The agent's engine_client.live_contract_drift() compares parameter names exactly."""
    import inspect
    for name, want in TRD_SIGNATURES.items():
        assert list(inspect.signature(getattr(engine, name)).parameters) == want, name


def test_min_p_hit_is_an_assumption(simulated):
    assert engine.optimize(25, 0, None, [])["min_p_hit"] == 0.8          # assumptions.json default
    assert engine.set_assumption("min_p_hit", 0.5) == {"ok": True}
    assert engine.optimize(25, 0, None, [])["min_p_hit"] == 0.5
    bad = engine.set_assumption("min_p_hit", 80)
    assert bad["ok"] is False and "probability" in bad["error"]
