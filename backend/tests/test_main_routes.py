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


def test_cors_origins_from_env(monkeypatch):
    from app import main
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setattr(main, "env_value", lambda n: None)
    assert main.cors_origins() == ["http://localhost:5173", "http://localhost:3000"]
    monkeypatch.setattr(main, "env_value", lambda n: {"CORS_ORIGINS": " https://a.example.com/ ,https://b.example.com,"}.get(n))
    assert main.cors_origins() == ["https://a.example.com", "https://b.example.com"]


def _cors_client(monkeypatch, origins, regex=None):
    from fastapi import FastAPI
    from app import events, main
    monkeypatch.setattr(main, "env_value", lambda n: {"CORS_ORIGINS": origins, "CORS_ORIGIN_REGEX": regex}.get(n))
    a = FastAPI(); main.configure_cors(a); a.include_router(events.router)

    @a.post("/compose")
    def compose():
        return {"ok": True}
    return TestClient(a)


def test_cors_preflight_and_headers(monkeypatch):
    c = _cors_client(monkeypatch, "https://app.example.com")
    ok = c.options("/compose", headers={"Origin": "https://app.example.com", "Access-Control-Request-Method": "POST",
                                        "Access-Control-Request-Headers": "content-type"})
    assert ok.status_code == 200 and ok.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "POST" in ok.headers["access-control-allow-methods"]
    bad = c.options("/compose", headers={"Origin": "https://evil.example.com", "Access-Control-Request-Method": "POST"})
    assert bad.status_code == 400 and "access-control-allow-origin" not in bad.headers
    r = c.post("/compose", headers={"Origin": "https://app.example.com"})
    assert r.headers["access-control-allow-origin"] == "https://app.example.com"
    assert "access-control-allow-origin" not in c.post("/compose", headers={"Origin": "https://evil.example.com"}).headers


def test_cors_covers_the_sse_stream_and_regex(monkeypatch, tmp_path):
    from app import events
    from app.config import get_settings
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); get_settings.cache_clear(); events._seq.clear()
    events.emit("cr", "A", "done", "x")
    c = _cors_client(monkeypatch, "https://app.example.com", regex=r"https://.*\.vercel\.app")
    r = c.get("/events/cr?replay=1&delay=0", headers={"Origin": "https://app.example.com"})
    assert r.status_code == 200 and r.headers["access-control-allow-origin"] == "https://app.example.com"
    r = c.get("/events/cr?replay=1&delay=0", headers={"Origin": "https://pr-12-retroalpha.vercel.app"})
    assert r.headers["access-control-allow-origin"] == "https://pr-12-retroalpha.vercel.app"
    get_settings.cache_clear()


def test_assumptions_route_serves_the_engine_file():
    """The Assumptions screen shows the engine's real, sourced values: the route returns them as stored."""
    from app.engine.models import ASSUMPTIONS_PATH
    stored = json.loads(ASSUMPTIONS_PATH.read_text())
    c = TestClient(app)
    r = c.get("/assumptions?city=houston").json()
    assert r["city"] == "Houston" and r["city_values"] == stored["cities"]["Houston"] and r["global"] == stored["global"]
    assert c.get("/assumptions?city=Nowhere").json()["city_values"] is None


def test_portfolio_cards_from_recorded_data_only(tmp_path, monkeypatch):
    """GET /portfolio: card fields from portfolio.json / profile.json / tour.json; missing -> null; files untouched."""
    from app.main import CARD_FIELDS
    data = tmp_path / "data"
    (data / "buildings" / "b1").mkdir(parents=True)
    (data / "buildings" / "b2").mkdir(parents=True)
    pf = {"city": "Houston", "buildings": [
        {"building_id": "b1", "name": "One", "address": "1 Main St", "lat": 29.7, "lon": -95.3, "rba_sqft": 1000.0,
         "stories": 3, "year_built": None, "matterport_model_id": "COSTAR1", "hero": True},
        {"building_id": "b2", "name": "Two", "address": None, "lat": None, "lon": None, "rba_sqft": None,
         "matterport_model_id": None}]}
    (data / "portfolio.json").write_text(json.dumps(pf))
    (data / "buildings" / "b1" / "tour.json").write_text(json.dumps(
        {"model_id": "SCAN1", "available": True, "showcase_url": "https://my.matterport.com/show/?m=SCAN1"}))
    (data / "buildings" / "b1" / "profile.json").write_text(json.dumps({"year_built": 1984}))
    (data / "buildings" / "b2" / "tour.json").write_text(json.dumps({"model_id": "PRIV", "available": False, "showcase_url": None}))
    monkeypatch.setenv("DATA_DIR", str(data))
    get_settings.cache_clear()
    try:
        before = (data / "portfolio.json").read_text()
        b1, b2 = TestClient(app).get("/portfolio").json()["buildings"]
        assert all(set(CARD_FIELDS) <= set(b) for b in (b1, b2))
        # the tour's scan (tour.json) is the card's model; the CoStar record's own model is kept separately
        assert b1["matterport_model_id"] == "SCAN1" and b1["costar_matterport_model_id"] == "COSTAR1"
        assert b1["showcase_url"] == "https://my.matterport.com/show/?m=SCAN1" and b1["sqft"] == 1000.0
        assert b1["year_built"] == 1984 and b1["hero"] is True  # profile.json fills a missing value; other fields kept
        assert b2["showcase_url"] is None and b2["matterport_model_id"] == "PRIV"  # not viewable: no link, never guessed
        assert b2["address"] is None and b2["lat"] is None and b2["sqft"] is None and b2["stories"] is None
        assert (data / "portfolio.json").read_text() == before
    finally:
        get_settings.cache_clear()


def test_state_serves_plan_documents_without_regenerating_them(client):
    """Synthetic files prove documents survive a view change and GET is read-only."""
    c, d = client
    from app.storage import write_json
    write_json(d / "runs" / "doc-run" / "state.json", {"plan_id": "doc-plan", "layout": {"widgets": []}})
    plan = {"plan_id": "doc-plan", "financing": {"state": "executed", "nessie_ids": {"account": "stub-account"}}}
    write_json(d / "plans" / "doc-plan.json", plan)
    (d / "memo").mkdir(); (d / "memo" / "doc-plan.md").write_text("Recorded synthetic test memo")
    before = {str(p.relative_to(d)): p.read_bytes() for p in d.rglob('*') if p.is_file()}
    state = c.get('/state/doc-run').json()
    assert state['plan'] == plan
    assert state['memo_markdown'] == 'Recorded synthetic test memo'
    assert {str(p.relative_to(d)): p.read_bytes() for p in d.rglob('*') if p.is_file()} == before


def test_invalid_optimization_inputs_return_validation_errors(client):
    c, _ = client
    for extra in ({'target_pct': -1}, {'target_pct': 101}, {'budget_usd': -1}, {'risk_lambda': -1}):
        assert c.post('/run', json={'city': 'Houston', 'target_pct': 40, **extra}).status_code == 422
