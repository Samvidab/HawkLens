from fastapi.testclient import TestClient

from app.main import app


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_health_reports_the_e2e_sandbox_only_when_set(monkeypatch):
    """The Playwright guard trusts `sandbox`: it is true only for scripts/e2e_backend.sh (E2E_SANDBOX=1)."""
    monkeypatch.delenv("E2E_SANDBOX", raising=False)
    monkeypatch.setenv("RETROALPHA_ENV_FILE", "/nonexistent")
    assert TestClient(app).get("/health").json()["sandbox"] is False
    monkeypatch.setenv("E2E_SANDBOX", "1")
    assert TestClient(app).get("/health").json()["sandbox"] is True
