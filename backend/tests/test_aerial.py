import json

import pytest
from PIL import Image

from app.adapters.geometry import area_m2, square_wkt
from app.adapters.types import ImageRef
from app.agents import aerial
from app.config import get_settings
from app.events import load_events, reset_run
from app.schemas.profile import BuildingProfile

LAT, LON = 29.7164302, -95.5148383


def profile() -> BuildingProfile:
    return BuildingProfile(
        building_id="23551", costar_id="23551", name="Harwin Plaza II Bldg", address="7457 Harwin Dr",
        city="Houston", lat=LAT, lon=LON, footprint_wkt=square_wkt(LAT, LON, 50, "Houston"),
        footprint_source="estimated", property_type="Office", stories=3, rba_sqft=105717.0,
        year_built=1983, source_fields={})


def overhead(tmp_path) -> ImageRef:
    p = tmp_path / "ov.jpg"
    Image.new("RGB", (200, 200), "white").save(p)
    return ImageRef(image_id="vxo_1", source="vexcel_overhead", local_path=str(p), gsd_m=0.1,
                    bounds_wkt=square_wkt(LAT, LON, 100, "Houston"))


def obs(**over) -> aerial.AerialObservation:
    box = aerial.Box(image_id="vxo_1", label="roof", x0=0.8, y0=0.1, x1=0.2, y1=1.4)  # unordered + out of range
    base = dict(
        roof_type=aerial.RoofTypeObs(value="flat", confidence=0.9, marks=[box]),
        roof_color=aerial.RoofColorObs(value="dark", confidence=0.8),
        usable_roof_fraction=aerial.FractionObs(value=0.6, confidence=0.7),
        shading=aerial.ShadingObs(value="none", confidence=0.9),
        existing_solar=aerial.SolarObs(value="no", confidence=0.95),
    )
    return aerial.AerialObservation(**(base | over))


def test_build_findings_computes_area_in_code(tmp_path):
    p = profile()
    f, claims = aerial.build_findings(p, obs(), [overhead(tmp_path)])
    assert f.usable_roof_m2 == pytest.approx(area_m2(p.footprint_wkt, "Houston") * 0.6, abs=0.1)
    assert (f.roof_type, f.roof_color, f.shading, f.existing_solar) == ("flat", "dark", "none", False)
    assert [c.field for c in claims] == ["roof.type", "roof.color", "roof.usable_fraction", "roof.shading",
                                         "roof.existing_solar"]
    assert all(c.evidence_ids == ["vxo_1"] and c.status == "pending" for c in claims)
    assert claims[0].marks[0].bbox == (0.2, 0.1, 0.8, 1.0)  # sorted + clipped
    assert f.claim_ids == [c.claim_id for c in claims] and f.facades == {}


def test_build_findings_unknowns_and_bad_ids(tmp_path):
    fake = aerial.Box(image_id="invented", label="x", x0=0, y0=0, x1=1, y1=1)
    o = obs(usable_roof_fraction=aerial.FractionObs(value=None, confidence=0.6),
            shading=aerial.ShadingObs(value="unknown", confidence=0.2, marks=[fake]),
            existing_solar=aerial.SolarObs(value="unknown", confidence=0.1),
            facades=[aerial.FacadeObs(orientation="S", glazing_ratio=0.5, window_count=40, confidence=0.8)])
    f, claims = aerial.build_findings(profile(), o, [overhead(tmp_path)])
    by = {c.field: c for c in claims}
    assert f.usable_roof_m2 == 0 and by["roof.usable_fraction"].value == "unknown"
    assert by["roof.usable_fraction"].confidence == 0
    assert f.shading == "partial" and by["roof.shading"].value == "unknown" and by["roof.shading"].marks == []
    assert by["roof.existing_solar"].value == "unknown" and f.existing_solar is False
    assert f.facades == {} and not any(c.field.startswith("facade") for c in claims)  # no S oblique given


def test_facade_claims_with_oblique(tmp_path):
    obl = ImageRef(image_id="vxq_S", source="vexcel_oblique", orientation="S", local_path="x")
    o = obs(facades=[aerial.FacadeObs(orientation="S", glazing_ratio=0.55, window_count=42, confidence=0.7)])
    f, claims = aerial.build_findings(profile(), o, [overhead(tmp_path), obl])
    assert f.facades["S"].glazing_ratio == 0.55 and f.facades["S"].window_count_est == 42
    assert {c.field for c in claims} >= {"facade.S.glazing", "facade.S.window_count"}


def test_prompt_has_no_unfilled_placeholders(tmp_path):
    text = aerial.prompt_for(profile(), [overhead(tmp_path)], question="Is the north edge shaded?")
    assert "{{" not in text and "vxo_1" in text and "Is the north edge shaded?" in text


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    yield tmp_path / "data"
    get_settings.cache_clear()


@pytest.mark.parametrize("llm_fails", [False, True])
async def test_run_writes_files_events_and_falls_back(data_dir, tmp_path, monkeypatch, llm_fails):
    ov = overhead(tmp_path)

    async def fake_images(p):
        return [ov]

    async def fake_vision(prompt, images, schema):
        if llm_fails:
            raise RuntimeError("boom")
        return obs()

    monkeypatch.setattr(aerial, "fetch_images", fake_images)
    monkeypatch.setattr(aerial.llm, "vision_json", fake_vision)
    reset_run("ra")
    f, claims = await aerial.run(profile(), run_id="ra")

    d = data_dir / "buildings" / "23551"
    assert json.loads((d / "aerial.json").read_text())["building_id"] == "23551"
    assert len(json.loads((d / "claims.json").read_text())) == 5
    assert "vxo_1" in json.loads((d / "images.json").read_text())
    assert (d / "aerial_debug.png").exists()
    kinds = [e.kind for e in load_events("ra")]
    assert kinds[0] == "fetch" and kinds.count("observe") == 2 and (("error" in kinds) == llm_fails)
    if llm_fails:
        assert f.roof_type == "unknown" and all(c.confidence == 0 for c in claims)
