import json
import time

import pytest
from fastapi.testclient import TestClient

from app.agents import memo, replan
from app.config import get_settings
from app.integrations import nessie_client as nes
from app.main import app
from tests.test_memo import data, fake_llm, GOOD  # noqa: F401
from tests.test_finance import clean as _clean  # noqa: F401

GOAL = {"city": "Houston", "target_pct": 10, "risk_lambda": 0.5}


@pytest.fixture
def c(data):
    from tests.test_compose_flow import upgrade
    f = data / "buildings/b2/feasibility.json"  # add an unverified upgrade to the shared fixture
    f.write_text(json.dumps([*json.loads(f.read_text()), upgrade("b2", "window_upgrade", "envelope", 20_000, "sqft", ok=False)]))
    return TestClient(app)


def post(c, type_, payload=None, run="r"):
    return c.post("/compose", json={"run_id": run, "type": type_, "payload": payload or {}})


def plan(d):
    return json.loads((d / "plans/current.json").read_text())


def events_of(d, run="r"):
    return [json.loads(l) for l in (d / f"runs/{run}/events.jsonl").read_text().splitlines()]


def widget(lay, t):
    return {w["type"]: w for w in lay["widgets"]}[t]["props"]


def test_goal_then_every_pricing_action(c, data):
    assert post(c, "goal", GOAL).status_code == 200
    p0 = plan(data)
    first = p0["selected"][0]
    bid = first.split(":")[0]

    r = post(c, "exclude_building", {"building_id": bid}); assert r.status_code == 200
    p1 = plan(data)
    assert p1["excluded_building_ids"] == [bid] and not any(s.startswith(bid) for s in p1["selected"])
    b3d = {b["building_id"]: b for b in widget(r.json(), "portfolio_3d")["buildings"]}
    assert b3d[bid]["excluded"] is True

    r = post(c, "include_building", {"building_id": bid}); assert plan(data)["excluded_building_ids"] == []
    assert plan(data)["selected"] == p0["selected"]  # same inputs, same plan

    uid = p0["selected"][0]
    post(c, "toggle_upgrade", {"upgrade_id": uid, "on": False})
    assert uid not in plan(data)["selected"] and plan(data)["excluded_upgrade_ids"] == [uid]
    post(c, "toggle_upgrade", {"upgrade_id": uid, "on": True})
    assert plan(data)["excluded_upgrade_ids"] == [] and uid in plan(data)["selected"]

    bars = lambda: {b["upgrade_id"] for b in plan(data)["macc"]["bars"]}
    assert "b2:window_upgrade" not in bars()  # unverified: out of the optimizer
    post(c, "include_unverified", {"upgrade_id": "b2:window_upgrade"})
    assert plan(data)["owner_included"] == ["b2:window_upgrade"] and "b2:window_upgrade" in bars()
    post(c, "set_target", {"target_pct": 10})
    assert plan(data)["owner_included"] == ["b2:window_upgrade"] and "b2:window_upgrade" in bars()  # sticky

    post(c, "set_target", {"target_pct": 30}); assert plan(data)["goal"]["target_pct"] == 30
    post(c, "set_budget", {"budget_usd": 5e5}); assert plan(data)["goal"]["budget_usd"] == 5e5
    post(c, "set_risk", {"risk_lambda": 0.1}); assert plan(data)["goal"]["risk_lambda"] == 0.1
    assert plan(data)["goal"]["target_pct"] == 30  # edits accumulate


def test_new_goal_resets_owner_decisions(c, data):
    post(c, "goal", GOAL)
    post(c, "exclude_building", {"building_id": "b1"})
    post(c, "goal", GOAL)
    assert plan(data)["excluded_building_ids"] == [] and plan(data)["owner_included"] == []


def test_compose_only_actions_do_not_reprice(c, data):
    post(c, "goal", GOAL)
    pid = plan(data)["plan_id"]
    n = len(events_of(data))
    r = post(c, "open_building", {"building_id": "b1"})
    assert r.json()["situation"] == "building_detail" and r.json()["focus_building_id"] == "b1"
    assert plan(data)["plan_id"] == pid
    assert not any(e["agent"] == "Pricing" for e in events_of(data)[n:])
    r = post(c, "select_bar", {"upgrade_id": "b2:cool_roof"}).json()
    assert r["focus_building_id"] == "b2"
    assert widget(r, "upgrade_list")["upgrades"] and any(u["highlighted"] for u in widget(r, "upgrade_list")["upgrades"])
    # view state persists and is cleared by open_building(None)
    assert c.get("/state/r").json()["view"]["focus_building_id"] == "b2"
    back = post(c, "open_building", {"building_id": None}).json()
    assert back["situation"] == "portfolio_overview" and back["focus_building_id"] is None


def test_one_to_three_events_per_action_with_orchestrator_first(c, data):
    post(c, "goal", GOAL)
    uid = plan(data)["selected"][0]
    for t, payload in [("set_target", {"target_pct": 12}), ("exclude_building", {"building_id": "b1"}),
                       ("toggle_upgrade", {"upgrade_id": uid, "on": False}), ("include_unverified", {"upgrade_id": "b2:window_upgrade"}),
                       ("open_building", {"building_id": "b2"}), ("select_bar", {"upgrade_id": "b2:cool_roof"})]:
        n = len(events_of(data)); post(c, t, payload)
        new = events_of(data)[n:]
        assert 1 <= len(new) <= 3, (t, [e["message"] for e in new])
        assert new[0]["agent"] == "Orchestrator" and new[0]["kind"] == "plan" and new[-1]["agent"] == "Composer"
        assert all(len(e["message"]) <= 90 for e in new)


def test_event_messages_are_human(c, data):
    post(c, "goal", GOAL)
    n = len(events_of(data)); post(c, "exclude_building", {"building_id": "b2"})
    assert events_of(data)[n]["message"] == "re-plan: Harbor Lofts excluded"
    n = len(events_of(data)); post(c, "set_target", {"target_pct": 25})
    assert events_of(data)[n]["message"] == "re-plan: target 25%"


def test_actions_need_a_goal_and_valid_ids(c, data):
    for t, pl in [("set_target", {"target_pct": 5}), ("exclude_building", {"building_id": "b1"}),
                  ("toggle_upgrade", {"upgrade_id": "b1:rooftop_solar", "on": False})]:
        assert post(c, t, pl).status_code in (409, 422), t
    assert post(c, "set_target", {"target_pct": 5}).status_code == 409
    post(c, "goal", GOAL)
    assert post(c, "exclude_building", {"building_id": "nope"}).status_code == 422
    assert post(c, "toggle_upgrade", {"upgrade_id": "nope", "on": False}).status_code == 422
    assert post(c, "select_bar", {"upgrade_id": "nope"}).status_code == 422
    assert post(c, "open_building", {"building_id": "nope"}).status_code == 422
    assert post(c, "set_target", {"target_pct": "lots"}).status_code == 422
    assert post(c, "goal", {"city": "Paris"}).status_code == 422


def test_approve_routes_through_finance_memo(c, data, monkeypatch):
    fake_llm(monkeypatch, [GOOD]); nes.reset_stub()
    post(c, "goal", GOAL)
    pid = plan(data)["plan_id"]
    assert post(c, "approve", {"plan_id": "stale"}).status_code == 409
    r = post(c, "approve", {"plan_id": pid})
    assert r.status_code == 200 and r.json()["situation"] == "approved"
    assert any(e["agent"] == "Finance" for e in events_of(data))


def test_goal_with_unsurveyed_buildings_uses_registered_survey_runner(c, data):
    seen = []

    async def runner(run_id, goal, missing):
        seen.append(missing)
    replan.register_survey_runner(runner)
    try:
        post(c, "goal", {**GOAL, "building_ids": ["b1", "ghost"]})
    finally:
        replan.register_survey_runner(None)
    assert seen == [["ghost"]]
    post(c, "goal", {**GOAL, "building_ids": ["b1", "ghost"]}, run="r9")  # no runner: warns, prices the rest
    assert any(e["kind"] == "error" and "not surveyed" in e["message"] for e in events_of(data, "r9"))


def test_replan_is_fast_with_stub_engine(c, data):
    post(c, "goal", GOAL)
    t0 = time.perf_counter()
    for t, pl in [("set_target", {"target_pct": 40}), ("exclude_building", {"building_id": "b1"}),
                  ("include_building", {"building_id": "b1"}), ("set_risk", {"risk_lambda": 0.9}),
                  ("open_building", {"building_id": "b1"})]:
        t1 = time.perf_counter(); assert post(c, t, pl).status_code == 200
        assert time.perf_counter() - t1 < 3.0, t
    assert time.perf_counter() - t0 < 5 * 3.0


def test_compose_actions_never_erase_the_surveys_state_fields(c, data):
    """Lane A's graph writes status/results/plan into runs/<id>/state.json; every action must merge into it."""
    (data / "runs/r").mkdir(parents=True)
    (data / "runs/r/state.json").write_text(json.dumps({"run_id": "r", "status": "surveyed", "plan": ["Survey 2 buildings"],
                                                         "results": {"b1": {"status": "done", "upgrades": 2}}}))
    for t, pl in [("goal", GOAL), ("set_target", {"target_pct": 20}), ("open_building", {"building_id": "b1"}),
                  ("open_building", {"building_id": None})]:
        assert post(c, t, pl).status_code == 200
        st = json.loads((data / "runs/r/state.json").read_text())
        assert st["status"] == "surveyed" and st["plan"] == ["Survey 2 buildings"] and st["results"]["b1"]["upgrades"] == 2, t
        assert st["layout"]["widgets"] and st["plan_id"] and "view" in st
    assert c.get("/state/r").json()["status"] == "surveyed"
