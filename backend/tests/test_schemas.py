import pytest
from pydantic import ValidationError

from app.schemas import (ActivityEvent, AerialFindings, BuildingProfile, Claim, FacadeFinding,
                         FeasibleUpgrade, Goal, InteriorFindings, Layout, Mark, OwnerAction, Pin,
                         WidgetSpec)


def roundtrip(m):
    again = type(m).model_validate_json(m.model_dump_json())
    assert again == m
    return again


def test_profile():
    roundtrip(BuildingProfile(building_id="b1", costar_id="c1", name="N", address="A", city="Houston",
                              lat=29.7, lon=-95.3, footprint_source="estimated", property_type="Office",
                              source_fields={"stories": "NumberOfStories"}))


def test_claim_and_marks():
    c = roundtrip(Claim(building_id="b1", claim_id="k1", agent="aerial", field="roof.existing_solar",
                        value=False, confidence=0.8, evidence_ids=["i1"],
                        marks=[Mark(image_id="i1", label="roof", bbox=(0.1, 0.1, 0.5, 0.5),
                                    polygon=[(0, 0), (1, 0), (1, 1)])]))
    assert c.status == "pending" and c.loops == 0


def test_aerial_interior_upgrade():
    a = roundtrip(AerialFindings(building_id="b1", roof_type="flat", roof_color="dark",
                                 usable_roof_fraction=0.6, shading="none", existing_solar=False,
                                 usable_roof_m2=500.0, facades={"S": FacadeFinding(glazing_ratio=0.5)},
                                 claim_ids=["k1"], evidence_ids=["i1"]))
    assert a.facades["S"].glazing_ratio == 0.5
    roundtrip(InteriorFindings(building_id="b1", model_id="m", lighting_type="LED", hvac_visible=[],
                               window_type="double", claim_ids=[], evidence_ids=[],
                               pins=[Pin(claim_id="k1", label="x", xyz=(1, 2, 3), status="verified")]))
    roundtrip(FeasibleUpgrade(upgrade_id="u1", building_id="b1", category="solar", type="rooftop_solar",
                              size_value=100, size_unit="kW", reason="r", confidence=0.7, claim_ids=[],
                              evidence_ids=[], verified="verified", include_in_optimizer=True))


def test_event_goal_action():
    roundtrip(ActivityEvent(ts="t", run_id="r", seq=0, agent="Records", kind="fetch", message="m"))
    roundtrip(Goal(city="Houston", target_pct=40))
    roundtrip(OwnerAction(run_id="r", type="set_target", payload={"target_pct": 50}))
    with pytest.raises(ValidationError):
        OwnerAction(run_id="r", type="chat", payload={})
    with pytest.raises(ValidationError):
        Goal(city="Paris", target_pct=1)


def _w(i, t="plan_table", size="wide", why="ok"):
    return WidgetSpec(id=i, type=t, title="T", why=why, size=size, data_ref="plans/current.json#/x",
                      props={"a": 1})


def _layout(widgets):
    return Layout(layout_id="l", run_id="r", situation="portfolio_overview", generated_at="t",
                  widgets=widgets)


def test_layout_roundtrip_and_rules():
    roundtrip(_layout([_w("w1"), _w("w2", "activity_feed", "side")]))
    with pytest.raises(ValidationError):
        _layout([_w("w1")])  # no feed
    with pytest.raises(ValidationError):
        _layout([_w("w1"), _w("f", "activity_feed", "wide")])  # feed not side
    with pytest.raises(ValidationError):
        _layout([_w("w1", why="x" * 91), _w("f", "activity_feed", "side")])
    with pytest.raises(ValidationError):
        _layout([_w(f"w{i}") for i in range(8)] + [_w("f", "activity_feed", "side")])  # 9 widgets
    with pytest.raises(ValidationError):
        _w("w1", size="huge")
