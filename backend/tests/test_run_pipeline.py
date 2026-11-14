"""POST /run pipeline: Lane A survey → Lane B goal replan (pricing → compose) → done."""
import json

from fastapi.testclient import TestClient

from app import events, main
from app.agents import graph
from app.integrations import engine_client as eng
from app.schemas.goal import Goal, OwnerAction
from tests.test_compose_flow import GOAL, client  # noqa: F401  (fixture: 2 surveyed buildings, stub engine)


async def test_run_full_survey_then_compose(client, monkeypatch):  # noqa: F811
    c, d = client
    surveyed = []

    async def fake_run(goal, run_id):
        surveyed.append(run_id)
        graph.write_state(run_id, status="surveyed")
        events.emit(run_id, "Orchestrator", "decide", "Survey complete: 2 of 2 buildings, 4 feasible upgrades")
        return {"run_id": run_id, "results": {"b1": {"status": "done"}, "b2": {"status": "done"}}}

    monkeypatch.setattr(graph, "run", fake_run)

    async def compose():
        await main.replan(OwnerAction(run_id="rp1", type="goal", payload=GOAL))

    await graph.run_full(Goal(**GOAL), "rp1", compose)
    st = json.loads((d / "runs/rp1/state.json").read_text())
    assert st["status"] == "ready" and st["layout"]["situation"] == "portfolio_overview"
    assert set(st["results"]) == {"b1", "b2"} and st["plan_id"]
    ev = events.load_events("rp1")
    kinds = [e.kind for e in ev]
    assert kinds[-1] == "done" and ev[-1].message == "Workspace ready"
    assert kinds.index("price") < kinds.index("compose") < len(kinds) - 1  # done only after compose
    assert c.get("/state/rp1").json()["layout"]["layout_id"] == st["layout"]["layout_id"]


async def test_run_full_reports_compose_failure_and_still_ends(client, monkeypatch):  # noqa: F811
    async def fake_run(goal, run_id):
        return {"run_id": run_id, "results": {}}

    async def boom():
        raise RuntimeError("engine down")

    monkeypatch.setattr(graph, "run", fake_run)
    await graph.run_full(Goal(**GOAL), "rp2", boom)
    ev = events.load_events("rp2")
    assert [e.kind for e in ev][-2:] == ["error", "done"]


def test_post_run_returns_run_id(client, monkeypatch):  # noqa: F811
    c, _ = client
    started = []

    async def fake_full(goal, run_id, compose):
        started.append((goal.city, run_id))

    monkeypatch.setattr(graph, "run_full", fake_full)
    r = c.post("/run", json=GOAL)
    assert r.status_code == 200 and r.json()["run_id"].startswith("run_")


def test_survey_runner_is_registered():
    """main.py registers Lane A's survey with replan at import (other tests may reset it)."""
    import importlib

    from app.agents import replan
    replan.register_survey_runner(None)
    importlib.reload(main)
    assert replan._survey_runner is graph.survey_runner
