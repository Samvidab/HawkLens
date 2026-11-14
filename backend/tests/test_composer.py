import asyncio
import json
import time

import pytest

from app.adapters.geometry import square_wkt
from app.agents import composer
from app.agents.composer import Selection, View, WhyItem, compose, detect_situation
from app.config import get_settings
from app.widgets.resolver import ResolveContext


def put(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(obj))


def prof(bid, name, mp=None):
    return dict(building_id=bid, costar_id=bid, name=name, address="a", city="Houston", lat=29.7, lon=-95.3,
                footprint_wkt=square_wkt(29.7, -95.3, 60, "Houston"), footprint_source="costar", property_type="Office",
                stories=8, rba_sqft=400_000.0, matterport_model_id=mp, source_fields={})


def aer(bid, m2, shading="none"):
    return dict(building_id=bid, roof_type="flat", roof_color="dark", usable_roof_fraction=0.5, shading=shading,
                existing_solar=False, usable_roof_m2=m2, facades={"S": {"glazing_ratio": 0.5, "window_count_est": 30}},
                claim_ids=[], evidence_ids=["img1"])


def up(bid, typ, cat, size, unit, claims=(), verified="verified"):
    return dict(upgrade_id=f"{bid}:{typ}", building_id=bid, category=cat, type=typ, size_value=size, size_unit=unit,
                reason="r", confidence=0.9, claim_ids=list(claims), evidence_ids=["img1"] if claims else [],
                verified=verified, include_in_optimizer=verified != "unverified")


def claim(cid, bid, status="verified"):
    return dict(claim_id=cid, building_id=bid, agent="aerial", field="roof.shading", value="none", confidence=0.8,
                evidence_ids=["img1"], status=status, verifier_note="shaded by the tower" if status == "rejected" else None)


BASE_PLAN = {
    "plan_id": "p1", "status": "ok", "goal": {"target_pct": 40, "budget_usd": None, "risk_lambda": 0.5},
    "selected": ["b1:rooftop_solar", "b2:cool_roof"], "excluded_building_ids": [], "owner_included": [],
    "exp_npv": 1000.0, "cvar5": -10.0, "p_loss": 0.1, "p_hit_target": 0.82, "total_upfront": 90000.0,
    "tonnes_per_year": 700.0, "tonnes_needed": 600.0, "shortfall_tonnes": 0.0, "cheapest_extra": [],
    "hist_bins": [{"x0": 0, "x1": 1, "count": 2}],
    "macc": {"bars": [
        {"upgrade_id": "b1:rooftop_solar", "building_id": "b1", "type": "rooftop_solar", "tonnes_per_year": 500.0, "cost_per_tonne": -20.0},
        {"upgrade_id": "b2:cool_roof", "building_id": "b2", "type": "cool_roof", "tonnes_per_year": 200.0, "cost_per_tonne": 15.0},
        {"upgrade_id": "b2:window_upgrade", "building_id": "b2", "type": "window_upgrade", "tonnes_per_year": 80.0, "cost_per_tonne": 40.0}]},
    "simulate": {"b1:rooftop_solar": {"upfront_usd": 60000.0, "exp_npv": 900.0}, "b2:cool_roof": {"upfront_usd": 30000.0, "exp_npv": 100.0}},
}


SCAN_B1 = {"model_id": "m1", "mesh_url": "/media/mesh/m1/Suite.obj", "mtl_url": "/media/mesh/m1/Suite.mtl",
           "rooms": [{"room_id": "r1", "type": "office", "area_sqft": 500.0}]}


@pytest.fixture
def world(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); get_settings.cache_clear()
    from app import events
    events._seq.clear(); events._subs.clear()

    def build(plan=None, claims_b1=(), claims_b2=(), upgrades_b2=None, b1_roof=900.0, b2_roof=200.0):
        put(tmp_path / "plans/current.json", {**BASE_PLAN, **(plan or {})})
        for bid, name, mp, roof, cl in [("b1", "Allen Center", "m1", b1_roof, claims_b1), ("b2", "Harbor Lofts", None, b2_roof, claims_b2)]:
            put(tmp_path / f"buildings/{bid}/profile.json", prof(bid, name, mp))
            put(tmp_path / f"buildings/{bid}/aerial.json", aer(bid, roof))
            put(tmp_path / f"buildings/{bid}/verification.json", list(cl))
        put(tmp_path / "buildings/b1/interior_scan.json", SCAN_B1)
        put(tmp_path / "buildings/b1/feasibility.json", [up("b1", "rooftop_solar", "solar", 150, "kW", claims=["k1"])])
        put(tmp_path / "buildings/b2/feasibility.json", upgrades_b2 or [
            up("b2", "cool_roof", "roof", 50000, "sqft", claims=["k2"]), up("b2", "window_upgrade", "envelope", 20000, "sqft", claims=["k3"], verified="unverified")])
        return tmp_path
    yield build
    get_settings.cache_clear()


def types(lay):
    return [w.type for w in lay.widgets]


def ctx_for(d, focus=None):
    return ResolveContext.load(d, "r", focus_building_id=focus)


# ---------------------------------------------------------------- situation detection (code only)
async def test_default_is_portfolio_overview(world):
    d = world(claims_b1=[claim("k1", "b1")], claims_b2=[claim("k2", "b2"), claim("k3", "b2", "verified")])
    lay, _ = await compose("r", "goal", View())
    assert lay.situation == "portfolio_overview"
    assert types(lay) == ["target_control", "portfolio_3d", "abatement_curve", "plan_table", "risk_histogram", "financing_card", "activity_feed"]


async def test_target_gap_when_target_unreachable(world):
    world(plan={"status": "infeasible", "tonnes_per_year": 300.0, "shortfall_tonnes": 300.0,
                "cheapest_extra": [{"upgrade_id": "b2:window_upgrade", "cost_per_tonne": 40.0, "tonnes_per_year": 80.0}]})
    lay, _ = await compose("r", "set_target", View())
    assert lay.situation == "target_gap"
    assert types(lay) == ["target_control", "target_gap_card", "abatement_curve", "plan_table", "portfolio_3d", "activity_feed"]
    gap = {w.type: w for w in lay.widgets}["target_gap_card"].props
    assert gap["shortfall_tonnes"] == 300.0 and gap["cheapest_extra"][0]["upgrade_id"] == "b2:window_upgrade"
    ev = [json.loads(l) for l in (get_settings().data_dir / "runs/r/events.jsonl").read_text().splitlines()]
    assert ev[-1]["message"] == "showing target gap: 300 t/yr short"


async def test_building_detail_for_hero_and_non_hero(world):
    world()
    lay, _ = await compose("r", "open_building", View(focus_building_id="b1"))
    assert lay.situation == "building_detail" and lay.focus_building_id == "b1"
    # b1 has the large unshaded roof, so upgrade_list leads the lower widgets (App Flow §6)
    assert types(lay) == ["building_header", "hero_3d", "upgrade_list", "evidence_gallery", "facade_compass",
                          "floor_plan", "risk_histogram", "activity_feed"]
    lay2, _ = await compose("r", "open_building", View(focus_building_id="b2"))
    assert lay2.situation == "building_detail" and "hero_3d" not in types(lay2) and "floor_plan" not in types(lay2)
    assert "portfolio_3d" in types(lay2) and types(lay2)[0] == "building_header"


async def test_verification_issue_for_rejected_claim_then_overview(world):
    world(claims_b2=[claim("k2", "b2"), claim("k3", "b2", "rejected")])
    lay, view = await compose("r", "goal", View())
    assert lay.situation == "verification_issue"
    assert types(lay) == ["evidence_gallery", "upgrade_list", "target_control", "portfolio_3d", "activity_feed"]
    items = {w.type: w for w in lay.widgets}["evidence_gallery"].props["items"]
    assert items[0]["status"] == "rejected" and items[0]["verifier_notes"] == ["shaded by the tower"]
    assert view.issues_shown == ["k3"]
    again, _ = await compose("r", "set_target", view)  # owner moved on: findings were shown once
    assert again.situation == "portfolio_overview"
    new_run, _ = await compose("r", "goal", View())  # a new goal/run re-surfaces them
    assert new_run.situation == "verification_issue"


@pytest.mark.parametrize("resolution", [{"owner_included": ["b2:window_upgrade"]},
                                        {"excluded_upgrade_ids": ["b2:window_upgrade"]},
                                        {"excluded_building_ids": ["b2"]}])
async def test_owner_decision_resolves_the_issue(world, resolution):
    world(plan=resolution, claims_b2=[claim("k3", "b2", "unverified")])
    assert detect_situation(ctx_for(get_settings().data_dir), "goal", View()) == "portfolio_overview"


async def test_claims_not_backing_any_upgrade_are_not_issues(world):
    world(claims_b2=[claim("orphan", "b2", "rejected")])
    assert detect_situation(ctx_for(get_settings().data_dir), "goal", View()) == "portfolio_overview"


async def test_approved_after_finance(world):
    world(plan={"financing": {"state": "executed", "nessie_ids": {"account": "a1"}}, "bills": [{"contractor": "Solar installer", "amount": 60000.0}]})
    d = get_settings().data_dir
    (d / "memo").mkdir(); (d / "memo/p1.md").write_text("memo")
    lay, _ = await compose("r", "approve", View())
    assert lay.situation == "approved" and types(lay) == ["financing_card", "memo", "plan_table", "activity_feed"]
    # approve before finance succeeded does not claim the approved screen
    world()
    lay, _ = await compose("r", "approve", View())
    assert lay.situation == "portfolio_overview"


async def test_priority_detail_beats_issue_beats_gap(world):
    d = world(plan={"status": "infeasible", "shortfall_tonnes": 5.0}, claims_b2=[claim("k3", "b2", "rejected")])
    assert detect_situation(ctx_for(d), "goal", View()) == "verification_issue"
    assert detect_situation(ctx_for(d, "b1"), "open_building", View(focus_building_id="b1")) == "building_detail"
    assert detect_situation(ctx_for(d), "goal", View(issues_shown=["k3"])) == "target_gap"


async def test_large_unshaded_roof_puts_upgrade_list_first_and_highlights_solar(world):
    world(b1_roof=900.0, b2_roof=200.0)
    lay, _ = await compose("r", "open_building", View(focus_building_id="b1"))
    t = types(lay)
    assert t.index("upgrade_list") < t.index("evidence_gallery") and t.index("upgrade_list") < t.index("facade_compass")
    ul = {w.type: w for w in lay.widgets}["upgrade_list"].props["upgrades"]
    assert [u["highlighted"] for u in ul] == [True]
    small, _ = await compose("r", "open_building", View(focus_building_id="b2"))
    t2 = types(small)
    assert t2.index("evidence_gallery") < t2.index("upgrade_list")  # default order: roof is not large
    assert not any(u["highlighted"] for u in {w.type: w for w in small.widgets}["upgrade_list"].props["upgrades"])


# ---------------------------------------------------------------- Gemini FAST refinement
def llm(monkeypatch, selection=None, exc=None, delay=0.0, calls=None):
    async def _t(prompt, schema, **kw):
        if calls is not None:
            calls.append((prompt, kw))
        if delay:
            await asyncio.sleep(delay)
        if exc:
            raise exc
        return selection
    monkeypatch.setattr(composer, "text_json", _t)


def sel(*items):
    return Selection(widgets=[WhyItem(type=t, why=w) for t, w in items])


OV = ["target_control", "portfolio_3d", "abatement_curve", "plan_table", "risk_histogram", "financing_card"]


async def test_llm_can_reorder_drop_add_and_write_why(world, monkeypatch):
    world()
    calls = []
    llm(monkeypatch, sel(("plan_table", "Start with the plan: {{n_selected}} upgrades chosen."),
                         ("abatement_curve", "{{n_negative_bars}} of {{n_bars}} cuts pay for themselves."),
                         ("target_control", "Target {{target_pct}}, hit chance {{p_hit}}."),
                         ("portfolio_3d", ""), ("upgrade_list", "All feasible upgrades with their status."),
                         ("financing_card", "")), calls=calls)  # drops risk_histogram, adds upgrade_list
    lay, _ = await compose("r", "set_target", View())
    w = {x.type: x for x in lay.widgets}
    assert types(lay) == ["plan_table", "abatement_curve", "target_control", "portfolio_3d", "upgrade_list", "financing_card", "activity_feed"]
    assert w["plan_table"].why == "Start with the plan: 2 upgrades chosen."
    assert w["abatement_curve"].why == "1 of 3 cuts pay for themselves."
    assert w["target_control"].why == "Target 40%, hit chance 82%."
    assert w["upgrade_list"].why == "All feasible upgrades with their status."
    assert w["portfolio_3d"].why == "Where the planned upgrades sit across your buildings."  # empty -> stock
    assert [x.id for x in lay.widgets] == [f"w{i}" for i in range(1, 8)] and lay.widgets[-1].size == "side"
    prompt, kw = calls[0]
    assert "NEVER write digits" in prompt and "{{n_selected}}" in prompt and "risk_histogram" in prompt
    assert "700" not in prompt and "90000" not in prompt  # no plan figures reach the model
    assert kw == {}  # text_json default = Gemini FAST


BAD = {
    "pinned dropped": sel(*[(t, "") for t in OV if t != "plan_table"]),
    "three drops": sel(("target_control", ""), ("plan_table", ""), ("portfolio_3d", "")),
    "three adds": sel(*[(t, "") for t in OV], ("upgrade_list", ""), ("evidence_gallery", ""), ("target_gap_card", "")),
    "unknown type": sel(*[(t, "") for t in OV], ("chatbot", "")),
    "focus-only in overview": sel(*[(t, "") for t in OV], ("hero_3d", "")),
    "gap card when target is met": sel(*[(t, "") for t in OV], ("target_gap_card", "")),
    "memo outside approval": sel(*[(t, "") for t in OV], ("memo", "")),
    "duplicates": sel(*[(t, "") for t in OV], ("plan_table", "")),
    "empty": sel(),
}


@pytest.mark.parametrize("name", list(BAD))
async def test_invalid_selection_falls_back_to_template(world, monkeypatch, name):
    world()
    llm(monkeypatch, BAD[name])
    lay, _ = await compose("r", "goal", View())
    assert types(lay) == OV + ["activity_feed"]
    assert {w.type: w for w in lay.widgets}["plan_table"].why == "The cheapest verified mix that meets the target."


async def test_llm_failure_and_timeout_fall_back_fast(world, monkeypatch):
    world()
    llm(monkeypatch, exc=RuntimeError("503"))
    lay, _ = await compose("r", "goal", View())
    assert types(lay) == OV + ["activity_feed"]
    monkeypatch.setattr(composer, "COMPOSER_LLM_TIMEOUT_S", 0.1)
    llm(monkeypatch, sel(*[(t, "late") for t in OV]), delay=0.4)
    t0 = time.perf_counter()
    lay, _ = await compose("r", "goal", View())
    assert time.perf_counter() - t0 < 0.35 and types(lay) == OV + ["activity_feed"]
    await asyncio.sleep(0.5)  # the late call finishes in the background (cache warm) without error


async def test_bad_why_lines_fall_back_per_widget(world, monkeypatch):
    world()
    llm(monkeypatch, sel(("target_control", "Saves 4,242 tonnes a year."),            # invented number
                         ("portfolio_3d", "x" * 100),                                    # too long
                         ("abatement_curve", "Uses {{secret}} here."),                   # unknown placeholder
                         ("plan_table", "Plan has {{n_selected}} upgrades."),            # fine
                         ("risk_histogram", "Plain words only."),                        # fine
                         ("financing_card", "Costs 99 dollars.")))                       # invented number
    lay, _ = await compose("r", "goal", View())
    w = {x.type: x for x in lay.widgets}
    assert w["target_control"].why == "Set the goal; agents re-plan on release."
    assert w["portfolio_3d"].why == "Where the planned upgrades sit across your buildings."
    assert w["abatement_curve"].why == "Bars below zero cut carbon and save money."
    assert w["financing_card"].why == "What approval would set up."
    assert w["plan_table"].why == "Plan has 2 upgrades." and w["risk_histogram"].why == "Plain words only."
    assert all(len(x.why) <= 90 for x in lay.widgets)


async def test_llm_pinned_widgets_per_situation_and_no_hero_without_matterport(world, monkeypatch):
    world()
    # b2 has no Matterport: its template has no hero_3d, and the LLM cannot add one (not in the whitelist)
    llm(monkeypatch, sel(("building_header", ""), ("upgrade_list", ""), ("evidence_gallery", ""), ("facade_compass", ""),
                         ("risk_histogram", ""), ("hero_3d", "")))
    lay, _ = await compose("r", "open_building", View(focus_building_id="b2"))
    assert types(lay) == ["building_header", "portfolio_3d", "evidence_gallery", "facade_compass", "upgrade_list",
                          "risk_histogram", "activity_feed"]  # invalid selection -> template (b2 has no Matterport)


async def test_widget_without_data_is_dropped_not_blank(world, monkeypatch):
    d = world()
    (d / "plans/current.json").write_text(json.dumps({**BASE_PLAN, "tonnes_needed": None, "status": "ok"}))
    llm(monkeypatch, sel(*[(t, "") for t in OV], ("upgrade_list", "")))
    lay, _ = await compose("r", "goal", View())
    assert lay.widgets[-1].type == "activity_feed" and "upgrade_list" in types(lay)


async def test_compose_keeps_the_surveys_state_fields(world):
    """graph.py writes status/results into the same state.json; the composer must merge, not overwrite."""
    d = world()
    st = d / "runs/r/state.json"
    put(st, {"run_id": "r", "status": "surveyed", "results": {"b1": {"status": "done"}}, "plan": ["step 1"]})
    lay, view = await compose("r", "goal", View())
    composer.save_state("r", lay, {"target_pct": 40}, "p1", view.model_dump())
    got = json.loads(st.read_text())
    assert got["status"] == "surveyed" and got["results"] == {"b1": {"status": "done"}} and got["plan"] == ["step 1"]
    assert got["layout"]["situation"] == lay.situation and got["plan_id"] == "p1"


# ---------------------------------------------------------------- hero_3d / floor_plan visibility (App Flow §6)
async def open_b1(world, scan=..., interior=None, rooms=None, mesh_on_disk=None):
    d = world()
    for name in ("interior_scan.json", "interior.json", "rooms.json"):
        (d / "buildings/b1" / name).unlink(missing_ok=True)
    if scan is not ...:
        if scan is not None:
            put(d / "buildings/b1/interior_scan.json", scan)
    if rooms is not None:
        put(d / "buildings/b1/rooms.json", rooms)
    if interior is not None:
        put(d / "buildings/b1/interior.json", interior)
    import shutil
    md = get_settings().cache_dir / "media" / "mesh" / "m1"
    shutil.rmtree(md, ignore_errors=True)
    if mesh_on_disk:
        md.mkdir(parents=True, exist_ok=True)
        for f in mesh_on_disk:
            (md / f).write_text("x")
    lay, _ = await compose("r", "open_building", View(focus_building_id="b1"))
    return lay, {w.type: w for w in lay.widgets}


async def test_matterport_model_without_mesh_or_interior_data_hides_hero_and_floor_plan(world, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache")); get_settings.cache_clear()
    lay, w = await open_b1(world, scan=None)
    assert "hero_3d" not in w and "floor_plan" not in w and "portfolio_3d" in w  # b1 still has matterport_model_id
    assert lay.widgets[-1].type == "activity_feed"


async def test_mesh_without_rooms_shows_hero_but_no_floor_plan(world, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache")); get_settings.cache_clear()
    lay, w = await open_b1(world, scan={"model_id": "m1", "mesh_url": "/media/mesh/m1/Suite.obj", "mtl_url": None, "rooms": []})
    assert "hero_3d" in w and "floor_plan" not in w and "portfolio_3d" not in w
    p = w["hero_3d"].props
    assert p["mode"] == "mesh" and p["mesh_url"] == "/media/mesh/m1/Suite.obj" and p["mtl_url"] is None and p["showcase_url"] is None


async def test_interior_rooms_without_mesh_show_floor_plan_but_no_hero(world, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache")); get_settings.cache_clear()
    lay, w = await open_b1(world, scan={"model_id": "m1", "mesh_url": None, "rooms": [{"room_id": "r1", "type": None, "area_sqft": 900.0}]})
    assert "hero_3d" not in w and "floor_plan" in w and "portfolio_3d" in w
    rooms = w["floor_plan"].props["rooms"]
    assert rooms == [{"room_id": "r1", "type": None, "polygon": [], "area_sqft": 900.0}]


async def test_showcase_url_replaces_the_mesh(world, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache")); get_settings.cache_clear()
    url = "https://my.matterport.com/show/?m=abc"
    lay, w = await open_b1(world, scan={**SCAN_B1, "showcase_url": url})
    p = w["hero_3d"].props
    assert p["mode"] == "showcase" and p["showcase_url"] == url and p["mesh_url"] is None and p["mtl_url"] is None
    assert "floor_plan" in w
    # showcase alone is enough to show the hero, with no rooms and no mesh
    lay, w = await open_b1(world, scan={"model_id": "m1", "mesh_url": None, "showcase_url": url})
    assert w["hero_3d"].props["mode"] == "showcase" and "floor_plan" not in w


async def test_mesh_found_on_disk_without_a_scan_file(world, tmp_path, monkeypatch):
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache")); get_settings.cache_clear()
    lay, w = await open_b1(world, scan=None, mesh_on_disk=["Suite.obj", "Suite.mtl", "tex.jpg"])
    p = w["hero_3d"].props
    assert p["mode"] == "mesh" and p["mesh_url"] == "/media/mesh/m1/model.obj" and p["mtl_url"] == "/media/mesh/m1/model.mtl"
    assert "floor_plan" not in w  # no interior data
    lay, w = await open_b1(world, scan=None, mesh_on_disk=["tex.jpg", "matterpak.zip"])  # no obj: nothing to show
    assert "hero_3d" not in w
