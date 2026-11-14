import json

import pytest
from fastapi.testclient import TestClient

from app import events
from app.adapters.geometry import square_wkt
from app.config import get_settings
from app.integrations import engine_client as eng
from app.main import app
from app.widgets.registry import validate_layout
from app.schemas.layout import Layout


def put(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def upgrade(bid, typ, cat, size, unit, ok=True):
    return dict(upgrade_id=f"{bid}:{typ}", building_id=bid, category=cat, type=typ, size_value=size, size_unit=unit,
                reason="r", confidence=0.9, claim_ids=[], evidence_ids=[],
                verified="verified" if ok else "unverified", include_in_optimizer=ok)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); monkeypatch.setenv("ENGINE_MODE", "stub")
    get_settings.cache_clear(); eng.reset_stub(); events._seq.clear(); events._subs.clear()
    for bid, name, ups in [
        ("b1", "Allen Center", [upgrade("b1", "rooftop_solar", "solar", 300, "kW"), upgrade("b1", "led_retrofit", "lighting", 400_000, "sqft")]),
        ("b2", "Harbor Lofts", [upgrade("b2", "cool_roof", "roof", 50_000, "sqft"), upgrade("b2", "window_upgrade", "envelope", 20_000, "sqft", ok=False)])]:
        put(tmp_path / f"buildings/{bid}/profile.json", dict(
            building_id=bid, costar_id=bid, name=name, address="a", city="Houston", lat=29.7, lon=-95.3,
            footprint_wkt=square_wkt(29.7, -95.3, 60, "Houston"), footprint_source="costar", property_type="Office",
            stories=8, rba_sqft=400_000.0, source_fields={}))
        put(tmp_path / f"buildings/{bid}/feasibility.json", ups)
    yield TestClient(app), tmp_path
    get_settings.cache_clear()


GOAL = {"city": "Houston", "target_pct": 10, "risk_lambda": 0.5}


def test_goal_in_layout_out(client):
    c, d = client
    r = c.post("/compose", json={"run_id": "r1", "type": "goal", "payload": GOAL})
    assert r.status_code == 200, r.text
    lay = r.json()
    validate_layout(Layout.model_validate(lay))
    assert lay["situation"] == "portfolio_overview" and lay["widgets"][-1]["type"] == "activity_feed"
    types = [w["type"] for w in lay["widgets"]]
    assert types == ["target_control", "portfolio_3d", "abatement_curve", "plan_table", "risk_histogram",
                     "financing_card", "activity_feed"]
    w = {x["type"]: x for x in lay["widgets"]}
    plan = json.loads((d / "plans/current.json").read_text())
    assert plan["selected"] and plan["stub"] is True and plan["goal"]["target_pct"] == 10
    assert [r["upgrade_id"] for r in w["plan_table"]["props"]["rows"]] == plan["selected"]
    assert w["plan_table"]["props"]["sample_pricing"] is True
    assert w["plan_table"]["props"]["totals"]["upfront_usd"] == plan["total_upfront"]
    assert w["target_control"]["props"]["p_hit_target"] == plan["p_hit_target"]
    assert (d / "layout.json").exists() and (d / f"plans/{plan['plan_id']}.json").exists()


def test_state_endpoint_and_events(client):
    c, d = client
    assert c.get("/state/r1").status_code == 404
    c.post("/compose", json={"run_id": "r1", "type": "goal", "payload": GOAL})
    st = c.get("/state/r1").json()
    assert st["run_id"] == "r1" and st["layout"]["situation"] == "portfolio_overview" and st["goal"]["target_pct"] == 10
    ev = [json.loads(l) for l in (d / "runs/r1/events.jsonl").read_text().splitlines()]
    assert [(e["agent"], e["kind"]) for e in ev] == [("Pricing", "price"), ("Composer", "compose")]
    assert "p(hit)" in ev[0]["message"]


def test_set_target_reprices_and_recomposes(client):
    c, d = client
    a = c.post("/compose", json={"run_id": "r1", "type": "goal", "payload": GOAL}).json()
    b = c.post("/compose", json={"run_id": "r1", "type": "set_target", "payload": {"target_pct": 60}}).json()
    tc = {w["type"]: w for w in b["widgets"]}["target_control"]["props"]
    assert tc["target_pct"] == 60 and tc["tonnes_needed"] > \
        {w["type"]: w for w in a["widgets"]}["target_control"]["props"]["tonnes_needed"]
    c.post("/compose", json={"run_id": "r1", "type": "set_budget", "payload": {"budget_usd": 1000.0}})
    assert json.loads((d / "plans/current.json").read_text())["goal"]["budget_usd"] == 1000.0
    c.post("/compose", json={"run_id": "r1", "type": "set_risk", "payload": {"risk_lambda": 0.9}})
    assert json.loads((d / "plans/current.json").read_text())["goal"]["risk_lambda"] == 0.9


def test_bad_inputs(client):
    c, d = client
    assert c.post("/compose", json={"run_id": "r1", "type": "set_target", "payload": {"target_pct": 5}}).status_code == 409
    assert c.post("/compose", json={"run_id": "r1", "type": "goal", "payload": {"city": "Paris"}}).status_code == 422
    assert c.post("/compose", json={"run_id": "r1", "type": "chat", "payload": {}}).status_code == 422


def test_compose_without_any_plan_drops_unready_widgets(client):
    c, d = client
    r = c.post("/compose", json={"run_id": "r2", "type": "open_building", "payload": {"building_id": "b1"}})
    assert r.status_code == 200
    lay = r.json()
    assert lay["widgets"][-1]["type"] == "activity_feed"  # never blank
    tc = {w["type"]: w for w in lay["widgets"]}
    assert tc["target_control"]["props"]["p_hit_target"] is None  # no plan yet: empty but present
    assert tc["plan_table"]["props"]["rows"] == []
