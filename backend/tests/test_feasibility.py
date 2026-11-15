import pytest

from app.adapters.geometry import SQFT_PER_M2, square_wkt
from app.rules.feasibility import apply_verification, evaluate, load_rules
from app.schemas import (AerialFindings, BuildingProfile, Claim, FacadeFinding, InteriorFindings)

SQFT_100M = 100 * 100 * SQFT_PER_M2  # footprint of the 100 m square below
FP = square_wkt(29.76, -95.37, 100, "Houston")


def profile(**kw):
    base = dict(building_id="b1", costar_id="c1", name="Test Tower", address="1 Main", city="Houston",
                lat=29.76, lon=-95.37, footprint_wkt=FP, footprint_source="costar", property_type="Office",
                year_built=2010, stories=10, rba_sqft=500_000.0, source_fields={})
    return BuildingProfile(**{**base, **kw})


def aerial(**kw):
    base = dict(building_id="b1", roof_type="pitched", roof_color="light", usable_roof_fraction=0.5,
                shading="none", existing_solar=True, usable_roof_m2=0.0, facades={}, claim_ids=[],
                evidence_ids=[])
    return AerialFindings(**{**base, **kw})


def interior(**kw):
    base = dict(building_id="b1", model_id="m1", lighting_type="LED", hvac_visible=[], window_type="double",
                claim_ids=[], evidence_ids=[], pins=[])
    return InteriorFindings(**{**base, **kw})


def claim(cid, field, status="verified", conf=0.9, ev=("img1",)):
    return Claim(claim_id=cid, building_id="b1", agent="aerial", field=field, value=True,
                 confidence=conf, evidence_ids=list(ev), status=status)


def by_type(ups):
    return {u.type: u for u in ups}


def test_boring_building_only_gets_assumed_led():
    assert [u.type for u in evaluate(profile(), aerial())] == ["led_retrofit"]


# ---- rooftop_solar
def test_solar_size_and_derate():
    cl = [claim("k1", "roof.existing_solar"), claim("k2", "roof.shading", conf=0.7, ev=("img2",))]
    u = by_type(evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=1000), claims=cl))["rooftop_solar"]
    assert u.size_value == pytest.approx(1000 * 0.75 * 0.20)  # 150 kW
    assert u.size_unit == "kW" and u.category == "solar"
    assert u.confidence == 0.7  # min of its claims
    assert u.claim_ids == ["k1", "k2"] and u.evidence_ids == ["img1", "img2"]
    assert u.verified == "verified" and u.include_in_optimizer
    part = by_type(evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=1000, shading="partial"),
                            claims=cl))["rooftop_solar"]
    assert part.size_value == pytest.approx(150 * 0.7)


@pytest.mark.parametrize("kw", [dict(existing_solar=True, usable_roof_m2=1000),
                                dict(existing_solar=False, usable_roof_m2=99.9),
                                dict(existing_solar=False, usable_roof_m2=1000, shading="heavy")])
def test_solar_requirements(kw):
    assert "rooftop_solar" not in by_type(evaluate(profile(), aerial(**kw)))


def test_solar_boundary_100m2_included():
    assert "rooftop_solar" in by_type(evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=100)))


# ---- cool_roof
@pytest.mark.parametrize("rtype,ok", [("flat", True), ("mixed", True), ("pitched", False)])
def test_cool_roof_types(rtype, ok):
    ups = by_type(evaluate(profile(), aerial(roof_color="dark", roof_type=rtype)))
    assert ("cool_roof" in ups) is ok
    if ok:
        assert ups["cool_roof"].size_value == pytest.approx(SQFT_100M, rel=0.01)
        assert ups["cool_roof"].category == "roof"


def test_cool_roof_needs_dark():
    assert "cool_roof" not in by_type(evaluate(profile(), aerial(roof_color="light", roof_type="flat")))


# ---- window_upgrade
def test_window_upgrade_area():
    fac = {"S": FacadeFinding(glazing_ratio=0.5), "W": FacadeFinding(glazing_ratio=0.2),
           "N": FacadeFinding(glazing_ratio=0.9)}  # N never counts
    cl = [claim("k1", "facade.S.glazing"), claim("k2", "facade.N.glazing")]
    u = by_type(evaluate(profile(), aerial(facades=fac), claims=cl))["window_upgrade"]
    # 100 m facades x (10 stories x 4 m) x (0.5 + 0.2) -> m2 -> sqft
    assert u.size_value == pytest.approx(100 * 40 * 0.7 * SQFT_PER_M2, rel=0.01)
    assert u.claim_ids == ["k1"]  # N-facade claim is not evidence for this upgrade
    assert u.category == "envelope"


def test_window_upgrade_thresholds_and_missing_imagery():
    low = {"S": FacadeFinding(glazing_ratio=0.34), "W": FacadeFinding(glazing_ratio=0.1)}
    assert "window_upgrade" not in by_type(evaluate(profile(), aerial(facades=low)))
    assert "window_upgrade" in by_type(evaluate(profile(), aerial(facades={"W": FacadeFinding(glazing_ratio=0.35)})))
    only_n = {"N": FacadeFinding(glazing_ratio=0.9), "S": FacadeFinding(glazing_ratio=None)}
    assert "window_upgrade" not in by_type(evaluate(profile(), aerial(facades=only_n)))
    assert "window_upgrade" not in by_type(evaluate(profile(), aerial(facades={})))  # no oblique imagery


# ---- heat_pump
def test_heat_pump_by_year_is_record_based():
    u = by_type(evaluate(profile(year_built=1995), aerial()))["heat_pump"]
    assert u.size_value == 500_000 and u.size_unit == "sqft" and u.category == "hvac"
    assert u.verified == "verified" and u.include_in_optimizer and u.confidence == 1.0
    assert "heat_pump" not in by_type(evaluate(profile(year_built=1996), aerial()))
    assert "heat_pump" not in by_type(evaluate(profile(year_built=None), aerial()))


def test_heat_pump_by_visible_hvac_prefers_floor_area():
    cl = [claim("h1", "interior.hvac.visible", conf=0.6)]
    ups = by_type(evaluate(profile(), aerial(), interior(hvac_visible=["Rooftop_Unit_old", "vav"],
                                                         floor_area_sqft=420_000.0), claims=cl))
    u = ups["heat_pump"]
    assert u.size_value == 420_000 and u.claim_ids == ["h1"] and u.confidence == 0.6
    assert "heat_pump" not in by_type(evaluate(profile(), aerial(), interior(hvac_visible=["vav"])))


def test_heat_pump_visible_hvac_without_claim_is_unverified():
    u = by_type(evaluate(profile(), aerial(), interior(hvac_visible=["boiler"])))["heat_pump"]
    assert u.verified == "unverified" and not u.include_in_optimizer


# ---- insulation
def test_insulation_needs_envelope_area():
    assert "insulation" not in by_type(evaluate(profile(), aerial(), interior()))
    assert "insulation" not in by_type(evaluate(profile(), aerial()))
    u = by_type(evaluate(profile(), aerial(), interior(envelope_area_sqft=88_000.0),
                         claims=[claim("e1", "interior.envelope")]))["insulation"]
    assert u.size_value == 88_000 and u.category == "envelope" and u.verified == "verified"


# ---- led_retrofit
def test_led_assumed_by_default():
    u = by_type(evaluate(profile(), aerial()))["led_retrofit"]
    assert u.verified == "assumed" and u.confidence == 0.5 and u.include_in_optimizer
    assert u.size_value == 500_000 and u.category == "lighting"


def test_led_skipped_when_already_led_and_uses_floor_area():
    assert "led_retrofit" not in by_type(evaluate(profile(), aerial(), interior(lighting_type="LED")))
    u = by_type(evaluate(profile(), aerial(), interior(lighting_type="fluorescent", floor_area_sqft=400_000.0)))["led_retrofit"]
    assert u.size_value == 400_000 and u.verified == "assumed"  # no claim yet
    v = by_type(evaluate(profile(), aerial(), interior(lighting_type="fluorescent"),
                         claims=[claim("l1", "interior.lighting_type", conf=0.8)]))["led_retrofit"]
    assert v.verified == "verified" and v.confidence == 0.8


# ---- verification states
def test_unverified_claims_exclude_from_optimizer():
    for st in ("unverified", "rejected", "pending", "sent_back"):
        cl = [claim("k1", "roof.existing_solar", status=st)]
        u = by_type(evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=500), claims=cl))["rooftop_solar"]
        assert u.verified == "unverified" and not u.include_in_optimizer, st


def test_image_upgrade_without_any_claim_is_not_optimized():
    u = by_type(evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=500)))["rooftop_solar"]
    assert u.verified == "unverified" and not u.include_in_optimizer and u.evidence_ids == []


def test_apply_verification_and_owner_override():
    pend = [claim("k1", "roof.existing_solar", status="pending")]
    ups = evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=500), claims=pend)
    done = [claim("k1", "roof.existing_solar", status="verified", conf=0.95)]
    solar = by_type(apply_verification(ups, done))["rooftop_solar"]
    assert solar.verified == "verified" and solar.include_in_optimizer and solar.confidence == 0.95
    bad = [claim("k1", "roof.existing_solar", status="unverified")]
    solar = by_type(apply_verification(ups, bad))["rooftop_solar"]
    assert not solar.include_in_optimizer
    forced = by_type(apply_verification(ups, bad, owner_included={"b1:rooftop_solar"}))["rooftop_solar"]
    assert forced.include_in_optimizer and forced.verified == "unverified"
    led = by_type(apply_verification(ups, bad))["led_retrofit"]
    assert led.verified == "assumed" and led.include_in_optimizer  # untouched


def test_deterministic_and_yaml_constants_drive_output():
    a = evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=1000))
    assert a == evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=1000))
    rules = {**load_rules(), "rooftop_solar": {**load_rules()["rooftop_solar"], "packing_factor": 0.5}}
    u = by_type(evaluate(profile(), aerial(existing_solar=False, usable_roof_m2=1000), rules=rules))["rooftop_solar"]
    assert u.size_value == pytest.approx(100.0)


def test_estimated_footprint_used_when_costar_has_none():
    p = profile(footprint_wkt=None, footprint_source="estimated", stories=10, rba_sqft=1_076_391.0)
    u = by_type(evaluate(p, aerial(roof_color="dark", roof_type="flat")))["cool_roof"]
    assert u.size_value == pytest.approx(1_076_391.0 / 10, rel=0.01)
