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
