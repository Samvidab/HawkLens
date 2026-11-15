"""Investigator agent: decision loop, cap, required roof, reasons, fallback (no network, no Gemini)."""
import json

import pytest

from app.agents import aerial, graph, investigator
from app.agents.investigator import Investigation, Step
from app.config import get_settings
from app.events import load_events, reset_run
from app.schemas.goal import Goal
from tests.test_aerial import obs, overhead, profile


@pytest.fixture
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    d = tmp_path / "data"
    d.mkdir()
    (d / "portfolio.json").write_text(json.dumps({"buildings": [
        {"building_id": "23551", "costar_id": "23551", "name": "Harwin Plaza II Bldg", "hero": True,
         "matterport_model_ids": ["aaa", "hero1", "bbb"], "matterport_model_id": "hero1"}]}))
    ov, wide = overhead(tmp_path), overhead(tmp_path).model_copy(update={"image_id": "vxo_wide", "gsd_m": 0.3})
    calls = []

    async def fake_overhead(point, buffer_m, *, px=1400, city=None):
        calls.append(buffer_m)
        return [ov if len(calls) == 1 else wide]

    async def fake_vision(prompt, images, schema):
        assert schema is aerial.AerialObservation
        fake_vision.prompts.append(prompt)
        return obs()
    fake_vision.prompts = []
    monkeypatch.setattr(investigator.vexcel, "overhead", fake_overhead)
    monkeypatch.setattr(aerial.llm, "vision_json", fake_vision)
    yield tmp_path, calls, fake_vision
    get_settings.cache_clear()


def scripted(monkeypatch, steps):
    seq = iter(steps)
    prompts = []

    async def decide(self):
        prompts.append(self.prompt())
        return next(seq)
    monkeypatch.setattr(Investigation, "decide", decide)
    return prompts


async def test_tool_sequence_events_and_trace(env, monkeypatch):
    tmp_path, calls, vision = env
    prompts = scripted(monkeypatch, [
        Step(reason="need the roof for solar", tool="inspect_roof"),
        Step(reason="roof open but trees nearby", tool="get_vexcel_wider_context"),
        Step(reason="check shading with neighbours", tool="inspect_roof"),
        Step(reason="no scan worth the cost here", tool="finish"),
    ])
    reset_run("i1")
    out = await investigator.investigate(profile(), "i1", Goal(city="Houston", target_pct=40))
    assert [h["tool"] for h in out["investigation"]] == [
        "inspect_roof", "get_vexcel_wider_context", "inspect_roof", "finish"]
    assert out["interior"] is None and out["aerial"] is not None
    assert len(calls) == 2 and calls[1] == pytest.approx(calls[0] * investigator.WIDE_FACTOR)
    # the second roof inspection saw both images, the wide one labelled as context
    assert "wider overhead context" in vision.prompts[1] and "wider overhead context" not in vision.prompts[0]
    msgs = [e.message for e in load_events("i1") if e.agent == "Investigator"]
    assert msgs[0] == "inspecting roof: need the roof for solar"
    assert msgs[2].startswith("re-inspecting roof with context")
    assert msgs[-1] == "finishing: no scan worth the cost here"
    assert all(len(m) <= 90 for m in msgs)
    # later prompts carry earlier results
    assert "shading none" in prompts[1] and "Calls left: 7" in prompts[1]
    trace = json.loads((tmp_path / "data" / "buildings" / "23551" / "investigation.json").read_text())
    assert len(trace["steps"]) == 4


async def test_cap_and_required_roof(env, monkeypatch):
    scripted(monkeypatch, [Step(reason="checking", tool="get_costar_record")] * 20)

    async def fake_prop(cid):
        return {"numStoriesAboveGrade": 3, "rentableBuildingAreaSquareFeet": 105717.0}
    monkeypatch.setattr(investigator.costar, "get_property", fake_prop)
    reset_run("i2")
    out = await investigator.investigate(profile(), "i2", None)
    tools = [h["tool"] for h in out["investigation"]]
    assert tools.count("get_costar_record") == investigator.MAX_CALLS
    assert tools[-1] == "inspect_roof" and out["aerial"] is not None  # required, run by code
    msgs = [e.message for e in load_events("i2") if e.agent == "Investigator"]
    assert "call limit reached; finishing" in msgs


async def test_tool_errors_go_back_to_the_agent(env, monkeypatch):
    prompts = scripted(monkeypatch, [
        Step(reason="label the rooms", tool="label_rooms"),
        Step(reason="done", tool="finish"),
    ])
    out = await investigator.investigate(profile(), None, None)
    assert out["investigation"][0]["result"].startswith("error: call inspect_interior")
    assert "error: call inspect_interior" in prompts[1]


def test_reason_with_invented_number_falls_back_to_template(env):
    inv = Investigation(profile(), None, Goal(city="Houston", target_pct=40))
    assert inv.feed_reason(Step(reason="roof covers 73% open area", tool="inspect_roof")) == \
        investigator.DEFAULT_REASON["inspect_roof"]
    # numbers from the record are allowed; long reasons are cut at a word
    r = inv.feed_reason(Step(reason="Built 1983 so " + "original lighting likely " * 10, tool="inspect_interior"))
    assert r.startswith("built 1983") and len("inspecting interior: " + r) <= 90


def test_preferred_scan_first(env):
    p = profile().model_copy(update={"matterport_model_id": "hero1"})
    inv = Investigation(p, None, None)
    assert inv.scan_ids() == ["hero1", "aaa", "bbb"]
    assert "Preferred scan" in inv.building_card()


async def test_inspect_node_falls_back_to_fixed_pipeline(env, monkeypatch):
    async def boom(*a, **k):
        raise RuntimeError("investigator broke")

    async def fixed(s):
        return {"fixed": True}
    monkeypatch.setattr(investigator, "investigate", boom)
    monkeypatch.setattr(graph, "fixed_inspect", fixed)
    reset_run("i3")
    out = await graph.inspect_node({"run_id": "i3", "building_id": "23551", "profile": profile()})
    assert out == {"fixed": True}
    assert any("running the fixed survey" in e.message for e in load_events("i3"))

    monkeypatch.setenv("AGENTIC_SURVEY", "false")
    assert not investigator.enabled()


async def test_one_scan_per_building_and_no_identical_reinspection(env, monkeypatch, tmp_path):
    from app.adapters.types import PanoramaRef
    from app.agents import interior
    inv = Investigation(profile().model_copy(update={"matterport_model_id": "hero1"}), None, None)
    pano_calls = []

    async def fake_room_panos(mid):
        return [{"room_id": f"r{mid}", "pano_ids": [], "dimensions": {}}]

    async def fake_panoramas(mid):
        return [PanoramaRef(model_id=mid, pano_id=f"q{i}", xyz=(i, 0, 0), skybox_urls=[]) for i in range(20)]

    async def fake_fetch(mid, k):
        pano_calls.append(k)
        p = PanoramaRef(model_id=mid, pano_id=f"p{k}", xyz=(0, 0, 0), skybox_urls=[])
        img = overhead(tmp_path).model_copy(update={"image_id": f"mpp_{k}", "source": "matterport_pano"})
        return [p] * k, [img]

    async def fake_vision(prompt, images, schema):
        return interior.unknown_observation()
    monkeypatch.setattr(investigator.mp, "room_panos", fake_room_panos)
    monkeypatch.setattr(investigator.mp, "panoramas", fake_panoramas)
    monkeypatch.setattr(investigator.interior, "fetch_images", fake_fetch)
    monkeypatch.setattr(investigator.llm, "vision_json", fake_vision)

    await inv.inspect_interior(Step(reason="", tool="inspect_interior", model_id="hero1"))
    assert pano_calls == [5]
    with pytest.raises(investigator.ToolError, match="already inspected"):
        await inv.inspect_interior(Step(reason="", tool="inspect_interior"))
    await inv.inspect_interior(Step(reason="", tool="inspect_interior", count=20))  # wider look, capped
    assert pano_calls == [5, investigator.MAX_PANOS]
    with pytest.raises(investigator.ToolError, match="one scan per building"):
        await inv.get_matterport_rooms(Step(reason="", tool="get_matterport_rooms", model_id="aaa"))


def test_reason_keeps_acronyms(env):
    inv = Investigation(profile(), None, None)
    assert inv.feed_reason(Step(reason="HVAC unclear, need more panoramas", tool="inspect_interior")) == \
        "HVAC unclear, need more panoramas"


def test_finalize_clears_stale_interior_files(env):
    from app.agents import store
    p = profile().model_copy(update={"building_id": "x1", "showcase_url": None})
    d = store.building_dir("x1")
    d.mkdir(parents=True, exist_ok=True)
    for n in ("interior.json", "rooms.json", "interior_scan.json"):
        (d / n).write_text("{}")
    graph.clear_interior(p)
    assert not any((d / n).exists() for n in ("interior.json", "rooms.json", "interior_scan.json"))
    graph.clear_interior(p.model_copy(update={"showcase_url": "https://my.matterport.com/show/?m=x"}))
    assert json.loads((d / "interior_scan.json").read_text())["showcase_url"].endswith("m=x")
