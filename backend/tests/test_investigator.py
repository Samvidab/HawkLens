"""Investigator agent: decision loop, cap, required roof, fallback, and the no-invention rule
(no network, no Gemini)."""
import json

import pytest

from app.adapters.types import PanoramaRef
from app.agents import aerial, graph, interior, investigator
from app.agents.investigator import Investigation, Step
from app.config import get_settings
from app.events import load_events, reset_run
from app.guardrails import check_numbers
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


def S(tool, purpose="solar_evidence", **kw) -> Step:
    return Step(tool=tool, purpose=purpose, **kw)


def feed(run_id):
    return [e for e in load_events(run_id) if e.agent == "Investigator"]


async def test_tool_sequence_events_and_trace(env, monkeypatch):
    tmp_path, calls, vision = env
    prompts = scripted(monkeypatch, [
        S("inspect_roof", because=["built"]),
        S("get_vexcel_wider_context", "shading_check", because=["shading"]),
        S("inspect_roof", "shading_check", because=["wider_context"]),
        S("finish", "no_more_value", because=["built"]),
    ])
    reset_run("i1")
    out = await investigator.investigate(profile(), "i1", Goal(city="Houston", target_pct=40))
    assert [h["tool"] for h in out["investigation"]] == [
        "inspect_roof", "get_vexcel_wider_context", "inspect_roof", "finish"]
    assert out["interior"] is None and out["aerial"] is not None
    assert len(calls) == 2 and calls[1] == pytest.approx(calls[0] * investigator.WIDE_FACTOR)
    assert "wider overhead context" in vision.prompts[1] and "wider overhead context" not in vision.prompts[0]
    msgs = [e.message for e in feed("i1")]
    assert msgs[0] == "inspected roof: for solar, given built 1983"
    assert msgs[1].startswith("pulled wider Vexcel context (") and msgs[1].endswith("given shading none")
    assert msgs[2].startswith("re-inspected roof with context: to check shading, given wider view")
    assert msgs[3] == "finished: more evidence won't change an upgrade, given built 1983"
    assert all(len(m) <= 90 for m in msgs)
    assert "shading none" in prompts[1] and "Calls left: 7" in prompts[1]
    trace = json.loads((tmp_path / "data" / "buildings" / "23551" / "investigation.json").read_text())
    assert len(trace["steps"]) == 4 and trace["facts"]["shading"]["source"] == "roof inspection with wider context"


async def test_nothing_shown_is_invented(env, monkeypatch, tmp_path):
    """Every Investigator event (text, numbers, cited facts, image) comes from what a tool returned in
    this run; failed or empty tools show 'unknown'; the model's own words and invented ids never show."""
    async def no_basics(mid):
        raise RuntimeError("private model")

    async def failing_vision(prompt, images, schema):
        raise RuntimeError("gemini down")

    async def fake_fetch(mid, k):
        p = PanoramaRef(model_id=mid, pano_id="p1", xyz=(0, 0, 0), skybox_urls=[])
        img = overhead(tmp_path).model_copy(update={"image_id": "mpp_real", "source": "matterport_pano"})
        return [p], [img]

    async def room_panos(mid):
        return [{"room_id": "room1xyz", "pano_ids": [], "dimensions": {}}]

    async def panoramas(mid):
        return [PanoramaRef(model_id=mid, pano_id=f"q{i}", xyz=(i, 0, 0), skybox_urls=[]) for i in range(3)]

    async def rooms_fail(mid):
        raise RuntimeError("rooms query failed")

    async def no_room_imgs(mid, subset, all_panos):
        return {}, []

    async def no_mesh(mid):
        raise RuntimeError("unavailable")

    monkeypatch.setattr(investigator.mp, "basics", no_basics)
    monkeypatch.setattr(investigator.mp, "room_panos", room_panos)
    monkeypatch.setattr(investigator.mp, "panoramas", panoramas)
    monkeypatch.setattr(investigator.mp, "rooms", rooms_fail)
    monkeypatch.setattr(investigator.mp, "matterpak", no_mesh)
    monkeypatch.setattr(investigator.interior, "fetch_images", fake_fetch)
    monkeypatch.setattr(investigator.interior, "fetch_room_images", no_room_imgs)
    monkeypatch.setattr(investigator.llm, "vision_json", failing_vision)

    # The model tries to smuggle prose and cites facts no tool returned.
    smuggled = Step.model_validate({"tool": "inspect_roof", "purpose": "solar_evidence",
                                    "because": ["trees_everywhere", "built"],
                                    "reason": "roof is 73% covered by oak trees"})
    steps = [
        smuggled,
        S("find_matterport_scans", "find_interior_evidence", because=["scans_linked"]),  # every scan errors
        S("get_matterport_rooms", "lighting_for_led", model_id="hero1"),
        S("inspect_interior", "lighting_for_led", because=["lighting"]),  # vision fails
        S("label_rooms", "room_use", because=["hvac", "made_up"]),  # no room panoramas come back
        S("finish", "no_more_value"),
    ]
    scripted(monkeypatch, steps)
    reset_run("i9")
    inv = Investigation(profile().model_copy(update={"matterport_model_id": "hero1"}), "i9",
                        Goal(city="Houston", target_pct=40))
    await inv.run()
    inter = await inv.interior_result()
    events = feed("i9")
    assert [h["tool"] for h in inv.history] == [s.tool for s in steps]
    assert len(events) == len(inv.history)

    tool_returns = [h["result"] for h in inv.history]
    facts = {k: v["text"] for k, v in inv.facts.items()}
    for e, h in zip(events, inv.history):
        assert e.message == h["shown"]
        # 1. every number shown is in what tools returned (results, facts) or the CoStar profile
        assert check_numbers(e.message, [tool_returns, facts, inv.profile.model_dump(mode="json")]) == []
        # 2. every fact quoted was established by a tool, verbatim, and is in the line
        for fid, f in h["quoted"].items():
            assert f == inv.facts[fid] and f["text"] in e.message
        # 3. every image attached is one a tool returned
        assert e.evidence_id is None or e.evidence_id in inv.images_returned()
        # 4. nothing the model wrote is shown; invented fact ids are dropped
        assert "oak" not in e.message and "73" not in e.message
        assert not set(h["quoted"]) & {"trees_everywhere", "made_up"}

    by_tool = {h["tool"]: h for h in inv.history}
    # failures and empty returns are recorded as unknown, in the trace, the feed and the facts
    assert by_tool["find_matterport_scans"]["result"].startswith("unknown")
    assert by_tool["find_matterport_scans"]["shown"].startswith("Matterport scans unknown")
    assert facts["scans_found"] == "scans unknown"
    assert facts["lighting"] == "lighting unknown" and facts["hvac"] == "HVAC unknown"
    assert "vision model failed" in by_tool["inspect_interior"]["result"]
    assert by_tool["label_rooms"]["result"].startswith("unknown")
    assert by_tool["label_rooms"]["shown"].startswith("room labels unknown")
    assert by_tool["inspect_roof"]["shown"] == "inspected roof: for solar, given built 1983"
    # a failed rooms query leaves floor area unknown, not zero
    assert inter.scan["scanned_floor_area_sqft"] is None and inter.findings.floor_area_sqft is None
    assert any(e.message == "lighting unknown; HVAC unknown" for e in load_events("i9") if e.agent == "Interior")


async def test_failed_tool_is_unknown_and_run_goes_on(env, monkeypatch):
    scripted(monkeypatch, [S("inspect_roof"), S("get_vexcel_wider_context", "shading_check"),
                           S("finish", "no_more_value")])
    real, n = investigator.vexcel.overhead, [0]

    async def first_ok(*a, **k):
        n[0] += 1
        if n[0] > 1:
            raise TimeoutError("vexcel down")
        return await real(*a, **k)
    monkeypatch.setattr(investigator.vexcel, "overhead", first_ok)
    reset_run("i8")
    out = await investigator.investigate(profile(), "i8", None)
    wide = out["investigation"][1]
    assert wide["result"] == "unknown (failed: TimeoutError)"
    assert wide["shown"].startswith("wider Vexcel context unknown")
    assert any(e.kind == "error" and "failed (TimeoutError)" in e.message for e in load_events("i8"))
    assert out["investigation"][-1]["tool"] == "finish"


async def test_aerial_feed_says_unknown_not_zero(env, monkeypatch, tmp_path):
    async def vision(prompt, images, schema):
        return obs(usable_roof_fraction=aerial.FractionObs(value=None, confidence=0.0))
    monkeypatch.setattr(aerial.llm, "vision_json", vision)
    reset_run("i7")
    await aerial.inspect(profile(), "i7", images=[overhead(tmp_path)])
    msgs = [e.message for e in load_events("i7")]
    assert "usable roof unknown, shading none" in msgs and not any("0%" in m for m in msgs)


async def test_cap_and_required_roof(env, monkeypatch):
    scripted(monkeypatch, [S("get_costar_record", "record_details")] * 20)

    async def fake_prop(cid):
        return {"numStoriesAboveGrade": 3, "rentableBuildingAreaSquareFeet": 105717.0}
    monkeypatch.setattr(investigator.costar, "get_property", fake_prop)
    reset_run("i2")
    out = await investigator.investigate(profile(), "i2", None)
    tools = [h["tool"] for h in out["investigation"]]
    assert tools.count("get_costar_record") == investigator.MAX_CALLS
    assert tools[-1] == "inspect_roof" and out["aerial"] is not None  # required, run by code
    assert "year renovated: unknown" in out["investigation"][0]["result"]  # missing fields say so
    assert "call limit reached; finishing" in [e.message for e in feed("i2")]


async def test_refused_tool_goes_back_to_the_agent(env, monkeypatch):
    prompts = scripted(monkeypatch, [S("label_rooms", "room_use"), S("finish", "no_more_value")])
    out = await investigator.investigate(profile(), None, None)
    assert out["investigation"][0]["result"].startswith("unknown (refused: call inspect_interior")
    assert "call inspect_interior" in prompts[1]


def test_preferred_scan_first(env):
    inv = Investigation(profile().model_copy(update={"matterport_model_id": "hero1"}), None, None)
    assert inv.scan_ids() == ["hero1", "aaa", "bbb"]
    assert "Preferred scan" in inv.building_card()
    assert inv.facts["scans_linked"]["text"] == "3 scans linked"


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

    await inv.inspect_interior(S("inspect_interior", model_id="hero1"))
    assert pano_calls == [5]
    with pytest.raises(investigator.ToolError, match="already inspected"):
        await inv.inspect_interior(S("inspect_interior"))
    await inv.inspect_interior(S("inspect_interior", count=20))  # wider look, capped
    assert pano_calls == [5, investigator.MAX_PANOS]
    with pytest.raises(investigator.ToolError, match="one scan per building"):
        await inv.get_matterport_rooms(S("get_matterport_rooms", model_id="aaa"))


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
