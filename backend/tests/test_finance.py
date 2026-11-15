import json

import pytest
from fastapi.testclient import TestClient

from app import events
from app.agents import finance, memo
from app.agents.pricing import run_pricing
from app.config import get_settings
from app.integrations import engine_client as eng
from app.integrations import nessie_client as nes
from app.main import app
from app.schemas.goal import Goal
from tests.test_memo import data, fake_llm, GOOD  # noqa: F401  (fixtures/helpers)


@pytest.fixture(autouse=True)
def clean(data, monkeypatch):  # after `data`, which sets ENGINE_MODE=stub
    # Real engine: approval refuses stub (sample) pricing, so financing is tested on quant-engine numbers.
    monkeypatch.setenv("NESSIE_MODE", "stub"); monkeypatch.setenv("ENGINE_MODE", "live")
    get_settings.cache_clear(); nes.reset_stub()
    from app.engine import state as engine_state
    engine_state.clear()
    yield
    get_settings.cache_clear()


def ledger():
    return {k: len(v) for k, v in nes._ledger.items()}


async def priced(run="r"):
    plan = await run_pricing(run, Goal(city="Houston", target_pct=10))
    assert plan["selected"]
    return plan


async def test_gated_on_plan_id(data):
    with pytest.raises(finance.ApprovalError, match="no current plan"):
        await finance.run_finance("r", "plan_x")
    plan = await priced()
    for bad in (None, "plan_wrong", plan["plan_id"] + "x"):
        with pytest.raises(finance.ApprovalError):
            await finance.run_finance("r", bad)
    assert ledger() == {"accounts": 0, "transfers": 0, "bills": 0}  # nothing written without a match


async def test_books_reserve_transfer_and_bill_per_contractor(data):
    plan = await priced()
    st = await finance.run_finance("r", plan["plan_id"])
    types = {u["upgrade_id"]: u["type"] for u in [*json.loads((data / "buildings/b1/feasibility.json").read_text()),
                                                  *json.loads((data / "buildings/b2/feasibility.json").read_text())]}
    contractors = {finance.CONTRACTOR[types[u]] for u in plan["selected"]}
    assert st["state"] == "executed" and len(st["bills"]) == len(contractors)
    assert ledger() == {"accounts": 1, "transfers": 1, "bills": len(contractors)}
    assert nes._ledger["accounts"][0]["nickname"] == "Retrofit Reserve"
    assert nes._ledger["transfers"][0]["amount"] == round(plan["total_upfront"], 2)
    assert nes._ledger["transfers"][0]["to"] == st["account_id"]
    assert sum(b["amount"] for b in st["bills"]) == pytest.approx(plan["total_upfront"], abs=0.05)
    ev = [json.loads(l) for l in (data / "runs/r/events.jsonl").read_text().splitlines()]
    acts = [e for e in ev if e["kind"] == "act"]
    assert len(acts) == 2 + len(contractors) and all(e["agent"] == "Finance" for e in acts)
    assert st["account_id"][-4:] in acts[0]["message"] and all(len(e["message"]) <= 90 for e in acts)
    cur = json.loads((data / "plans/current.json").read_text())
    assert cur["financing"]["state"] == "executed" and cur["financing"]["nessie_ids"]["account"] == st["account_id"]


async def test_idempotent_by_plan_id(data):
    plan = await priced()
    a = await finance.run_finance("r", plan["plan_id"])
    before = ledger()
    b = await finance.run_finance("r", plan["plan_id"])
    assert a == b and ledger() == before


async def test_resume_after_partial_failure_never_double_books(data, monkeypatch):
    plan = await priced()
    real, n = nes.create_bill, {"c": 0}

    def flaky(*a, **k):
        n["c"] += 1
        if n["c"] == 2:
            raise RuntimeError("nessie 500")
        return real(*a, **k)
    monkeypatch.setattr(nes, "create_bill", flaky)
    with pytest.raises(RuntimeError):
        await finance.run_finance("r", plan["plan_id"])
    mid = ledger()
    assert mid["accounts"] == 1 and mid["transfers"] == 1 and mid["bills"] == 1
    st = await finance.run_finance("r", plan["plan_id"])
    assert st["state"] == "executed"
    assert ledger()["accounts"] == 1 and ledger()["transfers"] == 1 and ledger()["bills"] == len(st["bills"])
    assert any(json.loads(l)["kind"] == "error" for l in (data / "runs/r/events.jsonl").read_text().splitlines())


async def test_live_mode_needs_ids(data, monkeypatch):
    plan = await priced()
    monkeypatch.setenv("NESSIE_MODE", "live"); get_settings.cache_clear()
    monkeypatch.setattr(finance, "_env", lambda n: None)
    with pytest.raises(finance.ApprovalError, match="NESSIE_CUSTOMER_ID"):
        await finance.run_finance("r", plan["plan_id"])


def test_approve_endpoint_end_to_end(data, monkeypatch):
    calls = fake_llm(monkeypatch, [GOOD])
    c = TestClient(app)
    goal = {"city": "Houston", "target_pct": 10}
    lay = c.post("/compose", json={"run_id": "r", "type": "goal", "payload": goal}).json()
    pid = json.loads((data / "plans/current.json").read_text())["plan_id"]
    assert {w["type"]: w for w in lay["widgets"]}["financing_card"]["props"]["state"] == "proposed"

    assert c.post("/compose", json={"run_id": "r", "type": "approve", "payload": {"plan_id": "stale"}}).status_code == 409
    assert ledger()["accounts"] == 0

    r = c.post("/compose", json={"run_id": "r", "type": "approve", "payload": {"plan_id": pid}})
    assert r.status_code == 200
    lay = r.json()
    assert lay["situation"] == "approved"
    w = {x["type"]: x for x in lay["widgets"]}
    assert list(w) == ["financing_card", "memo", "plan_table", "activity_feed"]
    fc = w["financing_card"]["props"]
    assert fc["state"] == "executed" and fc["nessie_ids"]["account"] and fc["plan_id"] == pid
    assert "Retrofit plan memo" in w["memo"]["props"]["markdown"]
    snap, n_calls = ledger(), len(calls)

    again = c.post("/compose", json={"run_id": "r", "type": "approve", "payload": {"plan_id": pid}})
    assert again.status_code == 200 and again.json()["situation"] == "approved"
    assert ledger() == snap and len(calls) == n_calls  # no new Nessie writes, no new LLM call
    assert c.get("/state/r").json()["layout"]["situation"] == "approved"
