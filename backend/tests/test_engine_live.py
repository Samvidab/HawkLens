"""ENGINE_MODE=live against the real quant engine (app.engine, from the quant-engine branch)."""
import json
import time

import pytest

pytest.importorskip("numpy"); pytest.importorskip("pulp")
from fastapi.testclient import TestClient  # noqa: E402

from app import engine as real_engine  # noqa: E402
from app.agents.pricing import load_upgrades  # noqa: E402
from app.config import get_settings  # noqa: E402
from app.engine import state as engine_state  # noqa: E402
from app.integrations import engine_client as ec  # noqa: E402
from app.integrations import nessie_client as nes  # noqa: E402
from app.main import app  # noqa: E402
from tests.test_memo import data, fake_llm, GOOD  # noqa: E402,F401
from tests.test_replan import post, plan, events_of, widget  # noqa: E402,F401

GOAL = {"city": "Houston", "target_pct": 5, "risk_lambda": 0.5}


@pytest.fixture(autouse=True)
def live(monkeypatch, data):
    monkeypatch.setenv("ENGINE_MODE", "live"); monkeypatch.setenv("NESSIE_MODE", "stub")
    get_settings.cache_clear(); ec.reset_stub(); nes.reset_stub(); engine_state.clear()
    yield
    engine_state.clear(); get_settings.cache_clear()


@pytest.fixture
def c(data):
    from tests.test_compose_flow import upgrade
    f = data / "buildings/b2/feasibility.json"  # add one unverified upgrade
    f.write_text(json.dumps([*json.loads(f.read_text()), upgrade("b2", "window_upgrade", "envelope", 20_000, "sqft", ok=False)]))
    return TestClient(app)


def test_the_real_engine_matches_the_contract():
    assert ec.live_contract_drift() == []
    assert callable(real_engine.macc)  # the function, not the macc submodule


def test_outputs_conform_and_carry_the_extras(data):
    ups = [u for lst in load_upgrades().values() for u in lst]
    sim = ec.simulate(ups, {"discount_rate": 0.07})
    bars, opt = ec.macc([]), ec.optimize(5, 0.5, None, [])
    base = {b: ec.baseline(b) for b in {u.building_id for u in ups}}
    assert ec.check_outputs(sim, bars, opt, base) == []
    m = next(iter(sim.values()))
    assert m["upfront_usd"] > 0 and m["tonnes_per_year"] > 0 and len(m["hist_bins"]) == 30
    assert opt["status"] in ("ok", "infeasible") and opt["risk_supported"] is True  # the final engine applies risk_lambda (CVaR)
    assert all(b["annual_spend_usd"] > 0 and b["tonnes_per_year"] > 0 for b in base.values())
    assert ec.optimize(5, 0.5, None, []) == opt  # deterministic


def test_goal_end_to_end_with_real_pricing(c, data):
    r = post(c, "goal", GOAL)
    assert r.status_code == 200, r.text
    lay = r.json()
    p = plan(data)
    assert p["stub"] is False and p["risk_supported"] is True and p["selected"]
    w = {x["type"]: x["props"] for x in lay["widgets"]}
    assert w["plan_table"]["sample_pricing"] is False  # no "sample pricing" badge with the real engine
    assert w["target_control"]["risk_supported"] is True and w["target_control"]["p_hit_target"] is not None
    rows = w["plan_table"]["rows"]
    assert rows and all(r["upfront_usd"] and r["tonnes_per_year"] and r["exp_npv"] is not None for r in rows)
    assert w["plan_table"]["totals"]["upfront_usd"] == pytest.approx(sum(r["upfront_usd"] for r in rows))
    assert w["risk_histogram"]["bins"] and len(w["risk_histogram"]["bins"]) == 30
    assert w["abatement_curve"]["bars"]
    assert not any(e["kind"] == "error" for e in events_of(data))  # no contract-drift event


def test_risk_slider_is_applied_by_the_engine(c, data):
    """The final engine applies risk_lambda (E[NPV] + lambda x CVaR5): the flag is true and the slider's action re-plans."""
    post(c, "goal", {**GOAL, "target_pct": 5, "risk_lambda": 0.0})
    plans = {0.0: plan(data)}
    for lam in (0.2, 0.5, 2.0):
        n = len(events_of(data))
        r = post(c, "set_risk", {"risk_lambda": lam})
        assert r.status_code == 200
        plans[lam] = plan(data)
        assert plans[lam]["goal"]["risk_lambda"] == lam and plans[lam]["risk_supported"] is True
        assert events_of(data)[n]["message"] == f"re-plan: risk appetite {lam:g}"  # no "(not modelled yet)"
        assert {x["type"]: x for x in r.json()["widgets"]}["target_control"]["props"]["risk_supported"] is True
    assert len({p["plan_id"] for p in plans.values()}) == 4  # lambda is part of the plan id
    # what raising lambda guarantees (engine docs): worst-5% mean never worse, expected NPV never higher
    lams = sorted(plans)
    for lo, hi in zip(lams, lams[1:]):
        assert plans[hi]["cvar5"] >= plans[lo]["cvar5"] - 1e-6, (lo, hi)
        assert plans[hi]["exp_npv"] <= plans[lo]["exp_npv"] + 1e-6, (lo, hi)


def test_exclusions_budget_and_unverified(c, data):
    post(c, "goal", GOAL)
    base = plan(data)
    needed = base["tonnes_needed"]
    post(c, "exclude_building", {"building_id": "b1"})
    p = plan(data)
    assert not any(s.startswith("b1:") for s in p["selected"])
    assert p["tonnes_needed"] == needed  # an excluded building still counts in the target's denominator
    post(c, "include_building", {"building_id": "b1"})
    assert "b2:window_upgrade" not in {b["upgrade_id"] for b in plan(data)["macc"]["bars"]}
    post(c, "include_unverified", {"upgrade_id": "b2:window_upgrade"})
    assert "b2:window_upgrade" in {b["upgrade_id"] for b in plan(data)["macc"]["bars"]}
    post(c, "set_budget", {"budget_usd": 1000.0})
    q = plan(data)
    assert q["total_upfront"] <= 1000.0 and q["status"] == "infeasible" and q["shortfall_tonnes"] > 0


def test_unreachable_target_gives_the_target_gap_screen(c, data):
    r = post(c, "goal", {**GOAL, "target_pct": 95})
    assert r.status_code == 200 and r.json()["situation"] == "target_gap"
    p = plan(data)
    gap = {x["type"]: x["props"] for x in r.json()["widgets"]}["target_gap_card"]
    assert p["status"] == "infeasible" and gap["shortfall_tonnes"] == pytest.approx(p["shortfall_tonnes"], rel=1e-3)
    assert [e["upgrade_id"] for e in gap["cheapest_extra"]] == [e["upgrade_id"] for e in p["cheapest_extra"]][:3]


def test_approve_books_the_engines_upfront_costs(c, data, monkeypatch):
    fake_llm(monkeypatch, [GOOD])
    post(c, "goal", GOAL)
    p = plan(data)
    r = post(c, "approve", {"plan_id": p["plan_id"]})
    assert r.status_code == 200 and r.json()["situation"] == "approved"
    booked = sum(b["amount"] for b in nes._ledger["bills"])
    assert booked == pytest.approx(p["total_upfront"], rel=1e-3)
    assert nes._ledger["transfers"][0]["amount"] == pytest.approx(p["total_upfront"], abs=0.01)


def test_actions_stay_under_three_seconds(c, data):
    post(c, "goal", GOAL)
    for t, pl in [("set_target", {"target_pct": 8}), ("exclude_building", {"building_id": "b2"}),
                  ("include_building", {"building_id": "b2"}), ("set_budget", {"budget_usd": 5e6}),
                  ("set_risk", {"risk_lambda": 0.2}), ("open_building", {"building_id": "b1"})]:
        t0 = time.perf_counter(); assert post(c, t, pl).status_code == 200
        assert time.perf_counter() - t0 < 3.0, t
