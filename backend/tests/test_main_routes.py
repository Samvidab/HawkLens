import json

import pytest
from fastapi.testclient import TestClient

from app import events
from app.config import get_settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield TestClient(app), tmp_path
    get_settings.cache_clear()


def test_registry_route(client):
    c, _ = client
    body = c.get("/registry").json()
    assert "plan_table" in body["widgets"] and body["grid_columns"]["side"] == 4


def test_portfolio_route(client):
    c, d = client
    assert c.get("/portfolio").status_code == 404
    (d / "portfolio.json").write_text(json.dumps({"buildings": [{"id": "b1", "hero": True}]}))
    assert c.get("/portfolio").json()["buildings"][0]["id"] == "b1"


def test_events_router_mounted(client):
    c, d = client
    events._seq.clear()
    events.emit("rr", "A", "done", "x")
    r = c.get("/events/rr?replay=1&delay=0")
    assert r.status_code == 200 and '"kind":"done"' in r.text


def test_write_json_handles_models_and_lists_of_models(tmp_path):
    from app.schemas import Goal
    from app.storage import write_json
    write_json(tmp_path / "a.json", [Goal(city="Houston", target_pct=1), {"x": Goal(city="Houston", target_pct=2)}])
    got = json.loads((tmp_path / "a.json").read_text())
    assert got[0]["target_pct"] == 1 and got[1]["x"]["target_pct"] == 2
