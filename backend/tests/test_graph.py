import asyncio
import json

import pytest

from app.agents import aerial, graph, records
from app.config import get_settings
from app.events import load_events, reset_run
from app.schemas.goal import Goal
from tests.test_aerial import obs, overhead, profile


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("MAX_CONCURRENT_BUILDINGS", "2")
    get_settings.cache_clear()
    d = tmp_path / "data"
    d.mkdir()
    ids = ["b1", "b2", "b3", "b4", "b5"]
    (d / "portfolio.json").write_text(json.dumps({"buildings": [
        {"building_id": i, "costar_id": i, "name": f"Bldg {i}", "hero": i == "b1"} for i in ids]}))
    yield tmp_path, ids
    get_settings.cache_clear()


def patch_agents(monkeypatch, tmp_path, fail: str | None = None):
    active, peak = [0], [0]
    ov = overhead(tmp_path)

    async def fake_records(bid, run_id=None):
        if bid == fail:
            raise RuntimeError("costar down")
        return profile().model_copy(update={"building_id": bid, "name": f"Bldg {bid}"})

    async def fake_inspect(p, run_id=None):
        active[0] += 1
        peak[0] = max(peak[0], active[0])
        await asyncio.sleep(0.02)
        active[0] -= 1
        f, c = aerial.build_findings(p, obs(), [ov])
        return aerial.AerialResult(images=[ov], obs=obs(), findings=f, claims=c)

    async def fake_plan(*a, **k):
        raise RuntimeError("no gemini in tests")

    monkeypatch.setattr(records, "run", fake_records)
    monkeypatch.setattr(aerial, "inspect", fake_inspect)
    monkeypatch.setattr(graph.llm, "text_json", fake_plan)
    monkeypatch.setattr(graph, "_verifier", lambda: None)
    monkeypatch.setattr(graph, "_interior", lambda: None)
    return peak


async def test_run_surveys_all_in_parallel_with_cap(env, monkeypatch):
    tmp_path, ids = env
    peak = patch_agents(monkeypatch, tmp_path)
    reset_run("g1")
    out = await graph.run(Goal(city="Houston", target_pct=40), "g1")

    assert set(out["results"]) == set(ids) and all(r["status"] == "done" for r in out["results"].values())
    assert 1 < peak[0] <= 2  # parallel, capped by MAX_CONCURRENT_BUILDINGS
    data = tmp_path / "data"
    for i in ids:
        assert json.loads((data / "buildings" / i / "feasibility.json").read_text())
    state = json.loads((data / "runs" / "g1" / "state.json").read_text())
    assert state["status"] == "surveyed" and state["hero_id"] == "b1" and set(state["results"]) == set(ids)
    ev = load_events("g1")
    assert ev[0].kind == "plan" and ev[-1].kind == "done"
    assert sum(e.kind == "decide" for e in ev) == len(ids)
    assert ev[0].message.startswith("Plan: survey 5 Houston buildings, 2 at a time")  # template fallback


async def test_one_failing_building_does_not_stop_the_run(env, monkeypatch):
    tmp_path, ids = env
    patch_agents(monkeypatch, tmp_path, fail="b3")
    reset_run("g2")
    out = await graph.run(Goal(city="Houston", target_pct=40, building_ids=["b2", "b3"]), "g2")
    assert out["results"]["b2"]["status"] == "done" and out["results"]["b3"]["status"] == "error"
    kinds = [e.kind for e in load_events("g2")]
    assert "error" in kinds and kinds[-1] == "done"


async def test_plan_drops_lines_with_invented_numbers(monkeypatch):
    class Out:
        steps = ["Survey 8 Houston offices, 4 at a time", "Expect 12,000 t saved", "Verify every roof claim"]

    async def fake(prompt, schema):
        return Out()

    monkeypatch.setattr(graph.llm, "text_json", fake)
    steps = await graph.write_plan(Goal(city="Houston", target_pct=40), [f"B{i}" for i in range(8)], 4, None)
    assert steps == ["Survey 8 Houston offices, 4 at a time", "Verify every roof claim"]
