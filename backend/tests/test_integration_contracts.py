"""Contract tests: stubs must match TRD §8.1 / §8.2 signatures and shapes."""
import inspect

import pytest

from app.config import get_settings
from app.integrations import engine_client as eng
from app.integrations import nessie_client as nes
from app.schemas.upgrades import FeasibleUpgrade


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.setenv("ENGINE_MODE", "stub"); monkeypatch.setenv("NESSIE_MODE", "stub")
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear(); eng.reset_stub(); nes.reset_stub()
    yield
    get_settings.cache_clear()


def up(bid, typ, cat, size, unit, ok=True):
    return FeasibleUpgrade(upgrade_id=f"{bid}:{typ}", building_id=bid, category=cat, type=typ, size_value=size,
                           size_unit=unit, reason="r", confidence=0.9, claim_ids=[], evidence_ids=[],
                           verified="verified" if ok else "unverified", include_in_optimizer=ok)


UPS = [up("b1", "rooftop_solar", "solar", 300, "kW"), up("b1", "led_retrofit", "lighting", 400_000, "sqft"),
       up("b2", "cool_roof", "roof", 50_000, "sqft"), up("b2", "heat_pump", "hvac", 200_000, "sqft"),
       up("b2", "window_upgrade", "envelope", 20_000, "sqft"), up("b3", "insulation", "envelope", 90_000, "sqft", ok=False)]


def params(fn):
    return list(inspect.signature(fn).parameters)


def test_engine_signatures_match_trd():
    assert params(eng.simulate) == ["upgrades", "assumptions"]
    assert params(eng.macc) == ["exclusions"]
    assert params(eng.optimize) == ["target_pct", "risk_lambda", "budget_usd", "exclusions"]
    assert params(eng.set_assumption) == ["key", "value"]
    assert params(eng.baseline) == ["building_id"]


def test_simulate_shape():
    sim = eng.simulate(UPS, {})
    assert set(sim) == {u.upgrade_id for u in UPS}
    keys = {"exp_npv", "p_loss", "cvar5", "tonnes_lifetime", "cost_per_tonne", "hist_bins", "upfront_usd", "tonnes_per_year"}
    for m in sim.values():
        assert keys <= set(m) and len(m["hist_bins"]) == 30
        assert set(m["hist_bins"][0]) == {"x0", "x1", "count"} and 0 <= m["p_loss"] <= 1
        assert m["cvar5"] <= m["exp_npv"]
    assert eng.simulate(UPS, {}) == sim  # deterministic


def test_macc_sorted_and_exclusions():
    eng.simulate(UPS, {})
    bars = eng.macc([])["bars"]
    assert {"upgrade_id", "building_id", "type", "tonnes_per_year", "cost_per_tonne"} == set(bars[0])
    assert [b["cost_per_tonne"] for b in bars] == sorted(b["cost_per_tonne"] for b in bars)
    assert "b3:insulation" not in {b["upgrade_id"] for b in bars}  # include_in_optimizer False
    assert all(b["building_id"] != "b2" for b in eng.macc(["b2"])["bars"])  # building id excludes all
    assert "b1:rooftop_solar" not in {b["upgrade_id"] for b in eng.macc(["b1:rooftop_solar"])["bars"]}


def test_optimize_shape_and_target():
    eng.simulate(UPS, {})
    plan = eng.optimize(10, 0.5, None, [])
    need = {"plan_id", "selected", "exp_npv", "cvar5", "p_hit_target", "total_upfront", "tonnes_per_year", "status",
            "p_loss", "hist_bins", "tonnes_needed", "shortfall_tonnes", "cheapest_extra"}
    assert need <= set(plan) and plan["stub"] is True
    assert plan["status"] == "ok" and plan["tonnes_per_year"] >= plan["tonnes_needed"] > 0
    assert plan["shortfall_tonnes"] == 0 and plan["cheapest_extra"] == []
    assert eng.optimize(10, 0.5, None, []) == plan  # same inputs, same plan_id
    assert eng.optimize(11, 0.5, None, [])["plan_id"] != plan["plan_id"]


def test_optimize_one_per_building_category_and_exclusion():
    eng.simulate(UPS, {})
    plan = eng.optimize(100, 0.5, None, ["b2"])
    assert all(not s.startswith("b2:") for s in plan["selected"]) and "b3:insulation" not in plan["selected"]
    cats = [(u.building_id, u.category) for u in UPS if u.upgrade_id in plan["selected"]]
    assert len(cats) == len(set(cats))


def test_optimize_infeasible_gives_gap_fields():
    eng.simulate(UPS, {})
    plan = eng.optimize(80, 0.5, 1.0, [])  # $1 budget
    assert plan["status"] == "infeasible" and plan["shortfall_tonnes"] == plan["tonnes_needed"] > 0
    assert 1 <= len(plan["cheapest_extra"]) <= 3
    assert set(plan["cheapest_extra"][0]) == {"upgrade_id", "cost_per_tonne", "tonnes_per_year"}
    assert plan["total_upfront"] <= 1.0


def test_set_assumption_changes_pricing():
    before = eng.simulate(UPS, {})["b1:rooftop_solar"]["upfront_usd"]
    assert eng.set_assumption("cost_multiplier", 2.0) == {"ok": True}
    assert eng.macc([]) and eng._state["models"]["b1:rooftop_solar"]["upfront_usd"] == pytest.approx(2 * before)


def test_baseline_shape():
    b = eng.baseline("nope")
    assert set(b) == {"annual_spend_usd", "tonnes_per_year"} and b["tonnes_per_year"] > 0


def test_live_mode_without_engine_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("ENGINE_MODE", "live"); get_settings.cache_clear()
    try:
        import app.engine  # noqa: F401
        pytest.skip("real engine present")
    except ImportError:
        with pytest.raises(ImportError):
            eng.macc([])


def test_nessie_signatures_and_ids():
    assert params(nes.get_bills) == ["building_id"]
    assert params(nes.create_account) == ["customer_id", "nickname"]
    assert params(nes.transfer) == ["from_account", "to_account", "amount", "description"]
    assert params(nes.create_bill) == ["account_id", "merchant_id", "amount", "description"]
    bills = nes.get_bills("b1")
    assert len(bills) == 12 and bills == nes.get_bills("b1") and bills != nes.get_bills("b2")
    acct = nes.create_account("cust", "Retrofit Reserve")
    reserve = nes.create_account("cust")
    assert acct != reserve and isinstance(nes.transfer("chk", reserve, 100.0, "upfront"), str)
    assert isinstance(nes.create_bill(reserve, "solar-co", 50.0, "bill"), str)
    with pytest.raises(ValueError):
        nes.transfer("a", "b", 0, "x")
