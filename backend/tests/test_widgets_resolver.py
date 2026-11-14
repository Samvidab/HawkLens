import json

import pytest

from app.adapters.geometry import square_wkt
from app.schemas import (AerialFindings, BuildingProfile, Claim, FacadeFinding, FeasibleUpgrade,
                         InteriorFindings, Mark, Pin)
from app.schemas.layout import WidgetSpec
from app.widgets.resolver import ResolveContext, ResolveError, resolve_layout, resolve_widget
from app.widgets.templates import template_for


def write(p, obj):
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(obj, list):
        obj = [o.model_dump(mode="json") if hasattr(o, "model_dump") else o for o in obj]
    elif hasattr(obj, "model_dump"):
        obj = obj.model_dump(mode="json")
    p.write_text(json.dumps(obj))


def upgrade(bid, typ, kind, size, unit, verified="verified", claims=()):
    return FeasibleUpgrade(upgrade_id=f"{bid}:{typ}", building_id=bid, category=kind, type=typ, size_value=size,
                           size_unit=unit, reason="r", confidence=0.8, claim_ids=list(claims),
                           evidence_ids=["img1"] if claims else [], verified=verified,
                           include_in_optimizer=verified != "unverified")


@pytest.fixture
def data(tmp_path):
    for bid, name, mp in [("b1", "Allen Center", "m1"), ("b2", "Harbor Lofts", None)]:
        write(tmp_path / f"buildings/{bid}/profile.json", BuildingProfile(
            building_id=bid, costar_id=f"c{bid}", name=name, address="x", city="Houston", lat=29.7, lon=-95.3,
            footprint_wkt=square_wkt(29.7, -95.3, 50, "Houston"), footprint_source="costar",
            property_type="Office", stories=10, matterport_model_id=mp, source_fields={}))
        write(tmp_path / f"buildings/{bid}/aerial.json", AerialFindings(
            building_id=bid, roof_type="flat", roof_color="dark", usable_roof_fraction=0.5, shading="none",
            existing_solar=False, usable_roof_m2=500.0, claim_ids=["k1"], evidence_ids=["img1"],
            facades={"S": FacadeFinding(glazing_ratio=0.55, window_count_est=40)}))
    write(tmp_path / "buildings/b1/interior.json", InteriorFindings(
        building_id="b1", model_id="m1", lighting_type="LED", hvac_visible=[], window_type="double",
        claim_ids=[], evidence_ids=[], pins=[Pin(claim_id="k1", label="solar roof", xyz=(1, 2, 3), status="verified")]))
    write(tmp_path / "buildings/b1/interior_scan.json", {"model_id": "m1", "mesh_url": "/media/mesh/m1/model.obj",
                                                         "mtl_url": "/media/mesh/m1/model.mtl", "rooms": [{"room_id": "r1", "type": "office", "area_sqft": 500.0}]})
    write(tmp_path / "buildings/b1/feasibility.json", [
        upgrade("b1", "rooftop_solar", "solar", 75, "kW", claims=["k1"]),
        upgrade("b1", "window_upgrade", "envelope", 9000, "sqft", verified="unverified", claims=["k2"])])
    write(tmp_path / "buildings/b2/feasibility.json", [upgrade("b2", "led_retrofit", "lighting", 120000, "sqft", "assumed")])
    write(tmp_path / "buildings/b1/verification.json", [
        Claim(claim_id="k1", building_id="b1", agent="aerial", field="roof.existing_solar", value=False, confidence=0.9,
              evidence_ids=["img1"], status="verified", marks=[Mark(image_id="img1", label="roof", bbox=(0, 0, 1, 1))]),
        Claim(claim_id="k2", building_id="b1", agent="aerial", field="facade.S.glazing", value=0.55, confidence=0.5,
              evidence_ids=["img1", "img2"], status="rejected", verifier_note="mostly spandrel")])
    write(tmp_path / "plans/current.json", {
        "plan_id": "p1", "goal": {"target_pct": 40, "budget_usd": None, "risk_lambda": 0.5},
        "selected": ["b1:rooftop_solar", "b2:led_retrofit"], "excluded_building_ids": ["b2"],
        "owner_included": ["b2:led_retrofit"], "exp_npv": 1234.5, "cvar5": -50.0, "p_loss": 0.1, "p_hit_target": 0.82,
        "total_upfront": 90000.0, "tonnes_per_year": 700.0, "tonnes_needed": 1000.0, "stub": True,
        "hist_bins": [{"x0": 0, "x1": 1, "count": 3}],
        "macc": {"bars": [
            {"upgrade_id": "b1:rooftop_solar", "building_id": "b1", "type": "rooftop_solar", "tonnes_per_year": 500.0, "cost_per_tonne": -20.0},
            {"upgrade_id": "b2:led_retrofit", "building_id": "b2", "type": "led_retrofit", "tonnes_per_year": 200.0, "cost_per_tonne": -5.0},
            {"upgrade_id": "b1:window_upgrade", "building_id": "b1", "type": "window_upgrade", "tonnes_per_year": 80.0, "cost_per_tonne": 40.0}]},
        "simulate": {"b1:rooftop_solar": {"exp_npv": 900.0, "upfront_usd": 60000.0},
                     "b2:led_retrofit": {"exp_npv": 334.5, "upfront_usd": 30000.0}},
        "by_building": {"b1": {"exp_npv": 900.0, "cvar5": -10.0, "p_loss": 0.05, "hist_bins": [{"x0": 0, "x1": 2, "count": 1}]}}})
    (tmp_path / "memo").mkdir()
    (tmp_path / "memo/p1.md").write_text("Memo body")
    return tmp_path


def widgets(layout):
    return {w.type: w for w in layout.widgets}


def test_portfolio_overview(data):
    ctx = ResolveContext.load(data, "r1")
    lay = resolve_layout(ctx, "portfolio_overview")
    w = widgets(lay)
    assert [x.type for x in lay.widgets][-1] == "activity_feed" and w["activity_feed"].props == {"run_id": "r1"}
    assert w["target_control"].props["p_hit_target"] == 0.82 and w["target_control"].props["tonnes_needed"] == 1000.0
    b = {x["building_id"]: x for x in w["portfolio_3d"].props["buildings"]}
    assert b["b1"]["height_m"] == 40.0 and b["b1"]["color_value"] == 500.0 and not b["b1"]["excluded"]
    assert b["b2"]["excluded"] is True
    assert b["b1"]["overlays"] == [{"type": "solar", "polygon_wkt": b["b1"]["footprint_wkt"], "facade": None}]
    assert [x["in_plan"] for x in w["abatement_curve"].props["bars"]] == [True, True, False]
    pt = w["plan_table"].props
    assert [r["size"] for r in pt["rows"]] == ["75 kW", "120,000 sqft"]
    assert pt["rows"][0]["upfront_usd"] == 60000.0 and pt["rows"][0]["cost_per_tonne"] == -20.0
    assert pt["rows"][1]["owner_included"] and pt["sample_pricing"] is True
    assert pt["totals"] == {"upfront_usd": 90000.0, "exp_npv": 1234.5, "tonnes_per_year": 700.0}
    assert w["risk_histogram"].props["scope"] == "plan"
    fc = w["financing_card"].props
    assert fc["state"] == "proposed" and fc["total_upfront_usd"] == 90000.0
    assert {x["contractor"]: x["amount"] for x in fc["bills"]} == {"Solar installer": 60000.0, "Electrical contractor": 30000.0}
    assert w["abatement_curve"].data_ref == "plans/current.json#/macc"


def test_target_gap(data):
    ctx = ResolveContext.load(data, "r1")
    w = widgets(resolve_layout(ctx, "target_gap"))
    gap = w["target_gap_card"].props
    assert gap["shortfall_tonnes"] == 300.0
    assert gap["cheapest_extra"] == [{"upgrade_id": "b1:window_upgrade", "cost_per_tonne": 40.0, "tonnes_per_year": 80.0}]


def test_building_detail_with_and_without_matterport(data):
    ctx = ResolveContext.load(data, "r1", focus_building_id="b1", selected_upgrade_ids=["b1:rooftop_solar"])
    lay = resolve_layout(ctx, "building_detail")
    w = widgets(lay)
    assert lay.focus_building_id == "b1" and len(lay.widgets) == 8
    assert w["hero_3d"].props["mesh_url"] == "/media/mesh/m1/model.obj"
    assert w["hero_3d"].props["pins"][0]["xyz"] == [1.0, 2.0, 3.0]
    assert w["building_header"].props["profile"]["name"] == "Allen Center"
    assert w["facade_compass"].props["facades"]["S"]["window_count_est"] == 40
    ul = w["upgrade_list"].props["upgrades"]
    assert [u["highlighted"] for u in ul] == [True, False] and ul[0]["in_plan"]
    assert w["risk_histogram"].props["scope"] == "building"
    ev = {i["image_id"]: i for i in w["evidence_gallery"].props["items"]}
    assert ev["img1"]["status"] == "rejected" and ev["img1"]["claim_ids"] == ["k1", "k2"]
    assert ev["img2"]["verifier_notes"] == ["mostly spandrel"] and ev["img1"]["url"] == "/media/img1"
    assert ev["img1"]["marks"][0]["label"] == "roof"

    ctx2 = ResolveContext.load(data, "r1", focus_building_id="b2")
    lay2 = resolve_layout(ctx2, "building_detail")
    assert {"hero_3d", "floor_plan"}.isdisjoint(widgets(lay2)) and "portfolio_3d" in widgets(lay2)
    assert widgets(lay2)["risk_histogram"].props["scope"] == "plan"  # no per-building risk available


def test_building_detail_requires_focus(data):
    with pytest.raises(ResolveError):
        resolve_layout(ResolveContext.load(data, "r1"), "building_detail")


def test_verification_issue_puts_problems_first_and_filters_upgrades(data):
    ctx = ResolveContext.load(data, "r1")
    w = widgets(resolve_layout(ctx, "verification_issue"))
    items = w["evidence_gallery"].props["items"]
    assert items[0]["status"] == "rejected"
    assert [u["upgrade"]["upgrade_id"] for u in w["upgrade_list"].props["upgrades"]] == ["b1:window_upgrade"]


def test_approved_state(data):
    plan = json.loads((data / "plans/current.json").read_text())
    plan["financing"] = {"state": "executed", "nessie_ids": {"account": "a91f"}}
    write(data / "plans/current.json", plan)
    w = widgets(resolve_layout(ResolveContext.load(data, "r1"), "approved"))
    assert w["financing_card"].props["state"] == "executed" and w["financing_card"].props["nessie_ids"] == {"account": "a91f"}
    assert w["memo"].props["markdown"] == "Memo body"


def test_props_never_come_from_the_composer(data):
    ctx = ResolveContext.load(data, "r1")
    sk = template_for("approved")
    sk[1] = sk[1].model_copy(update={"props": {"markdown": "INJECTED"}})
    assert widgets(resolve_layout(ctx, "approved", sk))["memo"].props["markdown"] == "Memo body"


def test_unknown_type_and_missing_plan(data):
    ctx = ResolveContext.load(data, "r1")
    with pytest.raises(ResolveError):
        resolve_widget(WidgetSpec(id="w", type="chatbot", title="t", why="w", size="half"), ctx)
    # no plan yet: still resolvable where fields are optional; target_gap needs numbers
    (data / "plans/current.json").unlink()
    empty = ResolveContext.load(data, "r1")
    assert resolve_layout(empty, "portfolio_overview").widgets
    with pytest.raises(ResolveError):
        resolve_layout(empty, "target_gap")
