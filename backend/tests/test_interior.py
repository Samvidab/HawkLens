import json

import pytest
from PIL import Image

from app.adapters.types import ImageRef, MatterPakPaths, PanoramaRef
from app.agents import interior
from app.agents.aerial import Box
from app.config import get_settings
from app.events import load_events, reset_run
from tests.test_aerial import profile

MODEL = "hu9"


def panos(n=9):
    return [PanoramaRef(pano_id=f"p{i}", model_id=MODEL, label=str(i), xyz=(float(i % 3) * 3, float(i // 3) * 3, 1.5),
                        skybox_urls=[f"https://x/{i}/{f}" for f in range(6)]) for i in range(n)]


ROOMS = {"floors": [{"id": "f", "label": "Floor 1", "vertices": [], "edges": []}],
         "rooms": [{"id": "r1", "classifications": [], "dimensions": {"areaFloor": 73.6, "height": 2.74}},
                   {"id": "r2", "classifications": [{"label": "Office", "confidence": 1}],
                    "dimensions": {"areaFloor": 10.4, "height": 2.73}}],
         "assets": {"floorplans": [{"format": "jpg", "flags": ["photogramy"], "width": 10, "height": 10,
                                    "resolution": 100.0, "origin": {"x": 0, "y": 0}, "url": "https://signed"}]}}


def obs():
    return interior.InteriorObservation(
        lighting=interior.LightingObs(value="fluorescent", confidence=0.8, marks=[
            Box(image_id=interior.image_id(MODEL, "p4", 0), label="2x4 fluorescent troffer", x0=.4, y0=.4, x1=.6, y1=.6),
            Box(image_id=interior.image_id(MODEL, "p0", 0), label="troffer", x0=.1, y0=.1, x1=.3, y1=.3)]),
        hvac=interior.HvacObs(items=["vav_diffuser", "vav_diffuser", "thermostat"], confidence=0.7, marks=[
            Box(image_id=interior.image_id(MODEL, "p8", 0), label="ceiling diffuser", x0=.2, y0=.2, x1=.3, y1=.3)]),
        window=interior.WindowObs(value="unknown", confidence=0.1))


def test_sample_panos_spreads_and_is_deterministic():
    ps = panos(9)
    a = interior.sample_panos(ps, 5)
    assert len(a) == 5 and a == interior.sample_panos(list(reversed(ps)), 5)
    assert a[0].pano_id == "p4"  # nearest the centre first
    assert {"p0", "p2", "p6", "p8"} <= {p.pano_id for p in a}  # then the corners
    assert interior.sample_panos(ps[:3], 5) == ps[:3]


def test_scan_areas_and_coverage_rule():
    p = profile()  # rba 105,717 sf
    scan = interior.scan_areas(ROOMS, p)
    assert scan["scanned_floor_area_sqft"] == pytest.approx((73.6 + 10.4) * 10.7639, abs=0.2)
    assert scan["coverage_of_rba"] < 0.01 and scan["wall_edges"] == 0
    ps = interior.sample_panos(panos(9), 5)
    imgs = [ImageRef(image_id=interior.image_id(MODEL, x.pano_id, f), source="matterport_pano", local_path="x")
            for x in ps for f in interior.FACES]
    f, claims = interior.build_findings(p, MODEL, obs(), imgs, ps, scan)
    assert f.floor_area_sqft is None and f.envelope_area_sqft is None  # one suite of a big building
    big = interior.scan_areas(ROOMS, p.model_copy(update={"rba_sqft": 1000.0}))
    f2, _ = interior.build_findings(p, MODEL, obs(), imgs, ps, big)
    assert f2.floor_area_sqft == big["scanned_floor_area_sqft"]


def test_claims_and_pins():
    p = profile()
    ps = interior.sample_panos(panos(9), 5)
    imgs = [ImageRef(image_id=interior.image_id(MODEL, x.pano_id, f), source="matterport_pano", local_path="x")
            for x in ps for f in interior.FACES]
    f, claims = interior.build_findings(p, MODEL, obs(), imgs, ps, interior.scan_areas(ROOMS, p))
    by = {c.field: c for c in claims}
    assert by["interior.lighting"].value == "fluorescent" and len(by["interior.lighting"].evidence_ids) == 2
    assert by["interior.hvac"].value == "thermostat, vav_diffuser" and f.hvac_visible == ["thermostat", "vav_diffuser"]
    assert by["interior.window"].value == "unknown"
    assert len(f.pins) == 3  # 2 lighting panos + 1 hvac
    pin = next(x for x in f.pins if x.label == "ceiling diffuser")
    assert pin.xyz == (6.0, 6.0, 1.5) and pin.status == "pending"
    by_id = {c.claim_id: c.model_copy(update={"status": "verified"}) for c in claims}
    res = interior.InteriorResult(model_id=MODEL, images=imgs, panos=ps, obs=obs(), findings=f, claims=claims, scan={})
    assert all(x.status == "verified" for x in interior.with_statuses(res, by_id).findings.pins)


async def test_inspect_with_fakes(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    img = tmp_path / "face.jpg"
    Image.new("RGB", (64, 64), "grey").save(img)
    p = profile().model_copy(update={"matterport_model_id": MODEL})

    async def fake_rooms(m):
        return ROOMS

    async def fake_panos(m):
        return panos(9)

    async def fake_face(pano, face):
        return img

    async def fake_vision(prompt, images, schema):
        assert len(images) == 15 and "{{" not in prompt
        return obs()

    async def no_mesh(m):
        raise interior.mp.MatterportError("MatterPak unavailable")

    monkeypatch.setattr(interior.mp, "rooms", fake_rooms)
    monkeypatch.setattr(interior.mp, "panoramas", fake_panos)
    monkeypatch.setattr(interior.mp, "pano_face", fake_face)
    monkeypatch.setattr(interior.mp, "matterpak", no_mesh)
    monkeypatch.setattr(interior.llm, "vision_json", fake_vision)
    reset_run("in1")
    try:
        res = await interior.inspect(p, "in1")
        interior.save(p, res)
        d = tmp_path / "data" / "buildings" / "23551"
        assert json.loads((d / "interior.json").read_text())["lighting_type"] == "fluorescent"
        scan = json.loads((d / "interior_scan.json").read_text())
        assert scan["mesh_url"] is None and scan["model_id"] == MODEL
        assert interior.image_id(MODEL, "p4", 0) in json.loads((d / "images.json").read_text())
        msgs = [e.message for e in load_events("in1")]
        assert msgs[0] == "Matterport scan: 2 rooms, 9 panoramas; inspecting 5"
        assert "3D mesh not available from Matterport yet" in msgs

        async def mesh(m):
            return MatterPakPaths(model_id=m, dir="d", obj="d/abc.obj", mtl="d/abc.mtl")
        monkeypatch.setattr(interior.mp, "matterpak", mesh)
        res = await interior.inspect(p, None)
        interior.save(p, res)
        assert json.loads((d / "interior_scan.json").read_text())["mesh_url"] == f"/media/mesh/{MODEL}/abc.obj"
    finally:
        get_settings.cache_clear()
