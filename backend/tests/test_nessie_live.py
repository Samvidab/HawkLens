"""NESSIE_MODE=live: our wrapper around the Nessie teammate's scripts, against a fake Nessie API."""
import json

import pytest
from fastapi.testclient import TestClient

from app.agents import finance
from app.config import get_settings
from app.integrations import nessie_client as nes
from app.main import app
from tests.fake_nessie import CUSTOMER, OPERATING, RESERVE, FakeNessie
from tests.test_memo import data, fake_llm, GOOD  # noqa: F401
from tests.test_replan import post, plan, events_of  # noqa: F401

KEY = "test-key-not-real"


@pytest.fixture
def api(monkeypatch):
    monkeypatch.setenv("NESSIE_MODE", "live"); monkeypatch.setenv("NESSIE_API_KEY", KEY)
    monkeypatch.setenv("NESSIE_CUSTOMER_ID", CUSTOMER); monkeypatch.setenv("NESSIE_SOURCE_ACCOUNT_ID", OPERATING)
    get_settings.cache_clear(); nes.reset_live(); nes.reset_stub()
    fake = FakeNessie(); fake.seed_utility_bills(); fake.install(monkeypatch)
    yield fake
    nes.reset_live(); get_settings.cache_clear()


def test_her_scripts_are_loaded_from_the_repo_and_unmodified(api):
    mods = nes._her()
    assert mods["client"].BASE_URL == "https://api.nessieisreal.com" and mods["client"].API_KEY == KEY
    assert (nes.HER_DIR / "get_bills.py").is_file() and callable(mods["get_bills"].get_bills)


def test_get_bills_follows_the_configured_source_account(api, monkeypatch):
    other = "other-operating-acct"
    api.accounts[other] = {"_id": other, "customer_id": CUSTOMER, "nickname": "Other", "balance": 0}
    api.bills[other] = [{"_id": "x1", "nickname": "99_gas_05", "payment_amount": 3.0, "payment_date": "2026-05-15"}]
    monkeypatch.setenv("NESSIE_SOURCE_ACCOUNT_ID", other); nes.reset_live()
    assert [b.bill_id for b in nes.get_bills("99")] == ["x1"]  # not her hardcoded operating account


def test_missing_key_is_a_clear_error(monkeypatch):
    monkeypatch.setenv("NESSIE_MODE", "live"); get_settings.cache_clear(); nes.reset_live()
    monkeypatch.delenv("NESSIE_API_KEY", raising=False)
    import app.integrations.nessie_client as mod
    monkeypatch.setattr(mod, "env_value", lambda n: None)
    with pytest.raises(nes.NessieError, match="NESSIE_API_KEY is not set"):
        nes.get_bills("23551")
    get_settings.cache_clear()


def test_get_bills_maps_her_bills_to_ours(api):
    bills = nes.get_bills("23551")
    assert [(b.month, b.utility, b.amount_usd, b.building_id) for b in bills] == [
        ("2026-01", "electricity", 12000.5, "23551"), ("2026-01", "gas", 900.0, "23551")]  # not sample_001, not malformed/negative
    assert bills[0].bill_id == "u-23551_electricity_01" and bills[0].kwh is None
    assert [b.month for b in nes.get_bills("a_b_c")] == ["2026-02"]  # building ids may contain underscores
    assert nes.get_bills("nope") == [] and api.keys == {KEY}


def test_create_account_is_get_or_create(api):
    assert nes.create_account(CUSTOMER, "Hawk Lens Retrofit Reserve") == RESERVE  # her seeded reserve is reused
    assert api.writes == []
    new = nes.create_account(CUSTOMER, "Another Reserve")
    assert new != RESERVE and nes.create_account(CUSTOMER, "Another Reserve") == new
    assert [w[1] for w in api.writes] == [f"/customers/{CUSTOMER}/accounts"] and api.writes[0][2]["nickname"] == "Another Reserve"


def test_transfer_moves_money_with_medium_and_payee(api):
    tid = nes.transfer(OPERATING, RESERVE, 1234.567, "Upfront for plan p1")
    body = api.writes[-1][2]
    assert body["medium"] == "balance" and body["payee_id"] == RESERVE and body["amount"] == 1234.57 and body["description"] == "Upfront for plan p1"
    assert tid == "xfer-0" and api.accounts[OPERATING]["balance"] == pytest.approx(50_000_000 - 1234.57) and api.accounts[RESERVE]["balance"] == pytest.approx(1234.57)


def test_transfer_errors_are_clear_and_leak_no_key(api):
    with pytest.raises(nes.NessieError, match="insufficient funds") as e:
        nes.transfer(OPERATING, RESERVE, 99_999_999, "too much")
    assert KEY not in str(e.value) and "HTTP 400" in str(e.value)
    with pytest.raises(ValueError):
        nes.transfer(OPERATING, RESERVE, 0, "x")


def test_create_bill_payload_and_dedupe_by_description(api):
    b1 = nes.create_bill(RESERVE, "Solar installer", 5000.0, "plan p1: Solar installer")
    body = api.writes[-1][2]
    assert body["payee"] == "Solar installer" and body["payment_amount"] == 5000.0 and body["nickname"] == "plan p1: Solar installer" and body["status"] == "pending"
    assert nes.create_bill(RESERVE, "Solar installer", 5000.0, "plan p1: Solar installer") == b1  # a retry never double-bills
    assert len([w for w in api.writes if w[1].endswith("/bills")]) == 1
    assert nes.create_bill(RESERVE, "Roofing contractor", 10.0, "plan p1: Roofing contractor") != b1


def test_http_failures_become_nessie_errors(api):
    api.fail_on[rf"/accounts/{RESERVE}/bills"] = 500
    with pytest.raises(nes.NessieError, match="HTTP 500"):
        nes.create_bill(RESERVE, "x", 1.0, "n1")
    assert nes.create_bill(RESERVE, "x", 1.0, "n1")  # works once Nessie recovers


# ---- approve end to end through finance + API, live Nessie (fake server) -------------------------
@pytest.fixture
def c(data, api, monkeypatch):
    fake_llm(monkeypatch, [GOOD])
    return TestClient(app)


def small_goal(c):
    assert post(c, "goal", {"city": "Houston", "target_pct": 3, "risk_lambda": 0.5}).status_code == 200


def test_approve_end_to_end_live_nessie(c, data, api):
    small_goal(c)
    p = plan(data)
    r = post(c, "approve", {"plan_id": p["plan_id"]})
    assert r.status_code == 200 and r.json()["situation"] == "approved"
    fc = {w["type"]: w["props"] for w in r.json()["widgets"]}["financing_card"]
    assert fc["state"] == "executed"
    assert api.accounts[RESERVE]["balance"] == pytest.approx(p["total_upfront"], abs=0.01)  # money actually moved
    assert api.accounts[OPERATING]["balance"] == pytest.approx(50_000_000 - p["total_upfront"], abs=0.01)
    assert sum(b["payment_amount"] for b in api.bills[RESERVE]) == pytest.approx(p["total_upfront"], abs=0.05)
    ids = fc["nessie_ids"]
    assert ids["account"] == RESERVE and ids["transfer"] == "xfer-0"
    assert {ids[k] for k in ids if k.startswith("bill:")} == {b["_id"] for b in api.bills[RESERVE]}
    assert all(w[1] in (f"/accounts/{OPERATING}/transfers", f"/accounts/{RESERVE}/bills") for w in api.writes)
    n = len(api.writes)
    assert post(c, "approve", {"plan_id": p["plan_id"]}).status_code == 200
    assert len(api.writes) == n  # idempotent: second approve posts nothing


def test_nessie_failure_gives_502_and_the_retry_resumes_without_double_booking(c, data, api):
    small_goal(c)
    pid = plan(data)["plan_id"]
    api.fail_on[rf"/accounts/{RESERVE}/bills"] = 500  # the first bill POST fails once... (the GET dedupe call hits it first)
    r = post(c, "approve", {"plan_id": pid})
    assert r.status_code == 502 and "Nessie could not complete" in r.text and KEY not in r.text
    assert len(api.transfers) == 1  # the transfer already happened and is remembered
    assert any(e["kind"] == "error" and e["agent"] == "Finance" for e in events_of(data))
    assert post(c, "approve", {"plan_id": pid}).status_code == 200
    assert len(api.transfers) == 1 and api.accounts[RESERVE]["balance"] == pytest.approx(plan(data)["total_upfront"], abs=0.01)


def test_insufficient_funds_is_a_502_with_the_reason(c, data, api):
    small_goal(c)
    api.accounts[OPERATING]["balance"] = 10.0
    r = post(c, "approve", {"plan_id": plan(data)["plan_id"]})
    assert r.status_code == 502 and "insufficient funds" in r.text
    assert api.transfers == [] and api.bills[RESERVE] == []
