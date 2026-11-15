"""The plan every page reads is the engine's, and an empty / partial / infeasible plan never looks like success.

Regression for the empty current.json (selected [], baseline {}, simulate {}, status "ok", p_hit_target 1.0):
pricing ran with no surveyed buildings, the portfolio baseline was 0 t/yr, so 0 tonnes "met" the target.
"""
import json

import pytest
from fastapi.testclient import TestClient

from app import events
from app.agents import approval, replan
from app.agents.pricing import run_pricing
from app.config import get_settings
from app.engine import state as engine_state
from app.integrations import engine_client as eng
from app.integrations import nessie_client as nes
from app.main import app
from app.schemas.goal import Goal
from tests.test_compose_flow import put, upgrade
from tests.test_memo import data  # noqa: F401  (2 surveyed buildings b1, b2)

GOAL = {"city": "Houston", "target_pct": 10, "risk_lambda": 0.5}


@pytest.fixture
def live(data, monkeypatch):  # noqa: F811
    monkeypatch.setenv("ENGINE_MODE", "live"); monkeypatch.setenv("NESSIE_MODE", "stub")
    get_settings.cache_clear(); engine_state.clear(); nes.reset_stub()
    yield data
    get_settings.cache_clear()


@pytest.fixture
def empty(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); monkeypatch.setenv("ENGINE_MODE", "live")
    get_settings.cache_clear(); engine_state.clear(); events._seq.clear(); eng.reset_stub()
    put(tmp_path / "portfolio.json", {"buildings": [{"building_id": "b1", "name": "One"}, {"building_id": "b2", "name": "Two"}]})
    yield tmp_path
    get_settings.cache_clear()


async def test_no_survey_data_is_no_data_not_success(empty):
    plan = await run_pricing("r", Goal(**GOAL))
    assert plan["status"] == "no_data" and plan["p_hit_target"] is None
    assert plan["total_upfront"] is None and plan["exp_npv"] is None and plan["tonnes_needed"] is None
    assert plan["coverage"]["not_surveyed"] == ["b1", "b2"]
    v = approval.check(plan)
    assert v["approvable"] is False and any("not priced" in r for r in v["reasons"])
    ev = [json.loads(l) for l in (empty / "runs/r/events.jsonl").read_text().splitlines()]
    assert ev[-1]["kind"] == "error" and "not priced" in ev[-1]["message"]


@pytest.mark.parametrize("mode", ["live", "stub"])
def test_zero_baseline_raises_in_both_engines(empty, monkeypatch, mode):
    monkeypatch.setenv("ENGINE_MODE", mode); get_settings.cache_clear(); eng.reset_stub()
    eng.simulate([], {})
    with pytest.raises(ValueError, match="baseline is 0"):
        eng.optimize(10, 0.0, None, [])


async def test_surveyed_building_without_upgrades_still_counts_in_baseline(live):
    before = await run_pricing("r", Goal(**GOAL))
    p = json.loads((live / "buildings/b1/profile.json").read_text())
    put(live / "buildings/b3/profile.json", {**p, "building_id": "b3", "costar_id": "b3", "name": "No Upgrades"})
    put(live / "buildings/b3/feasibility.json", [])
    engine_state.clear(); eng.reset_stub()
    after = await run_pricing("r", Goal(**GOAL))
    assert "b3" in after["coverage"]["priced"] and "b3" in after["baseline"]
    assert after["tonnes_needed"] > before["tonnes_needed"]  # b3's CO2 is part of the 10 % target


async def test_unsurveyed_building_blocks_approval_until_excluded(live):
    put(live / "portfolio.json", {"buildings": [{"building_id": b, "name": b} for b in ("b1", "b2", "b9")]})
    plan = await run_pricing("r", Goal(**GOAL))
    assert plan["coverage"]["not_surveyed"] == ["b9"]
    assert not approval.check(plan)["approvable"]
    plan = await run_pricing("r", Goal(**GOAL), excluded_building_ids=["b9"])
    assert plan["coverage"]["not_surveyed"] == [] and plan["coverage"]["excluded"] == ["b9"]


async def test_line_items_and_bundles_reconcile_to_total(live):
    plan = await run_pricing("r", Goal(**GOAL))
    assert plan["status"] == "ok" and plan["selected"] and plan["stub"] is False
    assert [r["upgrade_id"] for r in plan["line_items"]] == plan["selected"]
    assert plan["reconciles"] is True
    assert sum(r["upfront_usd"] for r in plan["line_items"]) == pytest.approx(plan["total_upfront"], abs=0.01)
    assert sum(b["upfront_usd"] for b in plan["bundles"]) == pytest.approx(plan["total_upfront"], abs=0.01)
    assert all(r["building_name"] for r in plan["line_items"])
    assert approval.check(plan)["approvable"] is True


def test_plan_endpoint_and_controls_replan(live):
    c = TestClient(app)
    assert c.get("/plan").status_code == 404
    assert c.post("/compose", json={"run_id": "r", "type": "goal", "payload": GOAL}).status_code == 200
    p1 = c.get("/plan").json()
    assert "simulate" not in p1 and p1["approval"]["approvable"] is True
    assert p1["funding"] == {"mode": "stub", "simulated": True, "state": "proposed", "executed": False}

    for typ, key, val in [("set_target", "target_pct", 5), ("set_budget", "budget_usd", 10_000_000.0),
                          ("set_risk", "risk_lambda", 0.0)]:
        assert c.post("/compose", json={"run_id": "r", "type": typ, "payload": {key: val}}).status_code == 200
        p = c.get("/plan").json()
        assert p["goal"][key] == val  # the optimizer input changed ...
    assert p["plan_id"] != p1["plan_id"] and p["tonnes_needed"] < p1["tonnes_needed"]  # ... and the plan with it

    # unreachable target: infeasible, refused at approve
    assert c.post("/compose", json={"run_id": "r", "type": "set_target", "payload": {"target_pct": 95}}).status_code == 200
    p = c.get("/plan").json()
    assert p["status"] == "infeasible" and p["approval"]["approvable"] is False
    r = c.post("/compose", json={"run_id": "r", "type": "approve", "payload": {"plan_id": p["plan_id"]}})
    assert r.status_code == 409 and "carbon target" in r.json()["detail"]
    assert nes._ledger["transfers"] == []


def test_approve_labels_simulated_funding_and_uses_engine_total(live, monkeypatch):
    from app.agents import memo
    async def no_llm(*a, **k):
        raise RuntimeError("no LLM in tests")
    monkeypatch.setattr(memo, "text_json", no_llm)
    c = TestClient(app)
    c.post("/compose", json={"run_id": "r", "type": "goal", "payload": GOAL})
    p = c.get("/plan").json()
    assert c.post("/compose", json={"run_id": "r", "type": "approve", "payload": {"plan_id": p["plan_id"]}}).status_code == 200
    after = c.get("/plan").json()
    assert after["funding"]["executed"] is True and after["financing"]["simulated"] is True
    assert after["financing"]["amount"] == round(p["total_upfront"], 2)
    assert nes._ledger["transfers"][0]["amount"] == round(p["total_upfront"], 2)


def test_funding_account_never_invents_a_balance(live, monkeypatch):
    c = TestClient(app)
    r = c.get("/funding-account").json()
    assert r["simulated"] is True and r["balance"] is None
    monkeypatch.setenv("NESSIE_MODE", "live"); monkeypatch.setenv("NESSIE_SOURCE_ACCOUNT_ID", "acct123456")
    get_settings.cache_clear()
    monkeypatch.setattr(nes, "get_account", lambda a: {"account_id": a, "nickname": "Ops", "type": "Checking",
                                                        "balance": 2500.0, "simulated": False})
    r = c.get("/funding-account").json()
    assert r == {"mode": "live", "configured": True, "account_id": "…3456", "nickname": "Ops", "type": "Checking",
                 "balance": 2500.0, "simulated": False}


async def test_live_nessie_refuses_when_balance_does_not_cover(live, monkeypatch):
    from app.agents import finance
    plan = await run_pricing("r", Goal(**GOAL))
    monkeypatch.setenv("NESSIE_MODE", "live"); monkeypatch.setenv("NESSIE_CUSTOMER_ID", "c")
    monkeypatch.setenv("NESSIE_SOURCE_ACCOUNT_ID", "s"); get_settings.cache_clear()
    monkeypatch.setattr(nes, "get_account", lambda a: {"balance": 1.0})
    monkeypatch.setattr(nes, "create_account", lambda *a: pytest.fail("no write before the balance check"))
    with pytest.raises(finance.ApprovalError, match="does not cover"):
        await finance.run_finance("r", plan["plan_id"])


async def test_goal_without_building_ids_surveys_unsurveyed_portfolio_buildings(empty, monkeypatch):
    called = []

    async def runner(rid, goal, ids):
        called.append(ids)
    monkeypatch.setattr(replan, "_survey_runner", runner)
    from app.schemas.goal import OwnerAction
    await replan.replan(OwnerAction(run_id="r", type="goal", payload=GOAL))
    assert called == [["b1", "b2"]]
