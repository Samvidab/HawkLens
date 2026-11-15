"""Verified CO2 equipment for the 3D tags: only verified pins of verified lighting / air-terminal claims; the panorama is
the one at exactly the pin's position; nothing is filled in when missing."""
import json

import pytest
from fastapi.testclient import TestClient

from app.adapters import matterport as mp
from app.config import get_settings
from app.adapters.types import PanoramaRef
from app.widgets import co2_equipment as co2

PIN = lambda cid, label, xyz, status="verified": {"claim_id": cid, "label": label, "xyz": xyz, "status": status}
CLAIM = lambda cid, value, status="verified", ev=(): {"claim_id": cid, "field": cid.split(".", 1)[1], "value": value, "status": status,
                                                       "confidence": 0.9, "evidence_ids": list(ev), "verifier_note": f"note {cid}"}


@pytest.fixture
def bdir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    d = tmp_path / "buildings" / "b1"
    d.mkdir(parents=True)
    (d / "profile.json").write_text("{}")
    yield d
    get_settings.cache_clear()


def write(d, interior, claims, tour=None):
    (d / "interior.json").write_text(json.dumps(interior))
    (d / "claims.json").write_text(json.dumps(claims))
    if tour:
        (d / "tour.json").write_text(json.dumps(tour))


def test_select_keeps_only_verified_lighting_and_air_terminals():
    interior = {"pins": [
        PIN("b1.interior.lighting", "fluorescent troffer", [1, 2, 3]),
        PIN("b1.interior.lighting", "recessed fixture", [4, 5, 6]),                 # type comes from the claim
        PIN("b1.interior.hvac", "ceiling supply diffuser", [7, 8, 9]),
        PIN("b1.interior.hvac", "thermostat", [7, 8, 9]),                           # not an air terminal
        PIN("b1.interior.hvac", "exposed ductwork", [7, 8, 9]),                     # not an air terminal
        PIN("b1.interior.hvac", "return air grille", [1, 1, 1], status="rejected"),  # rejected pin
        PIN("b1.interior.window", "double glazed window", [0, 0, 0]),               # not a CO2 source here
        PIN("b1.interior.room.r1", "open office", [0, 0, 0]),
    ]}
    claims = {c["claim_id"]: c for c in [CLAIM("b1.interior.lighting", "fluorescent"), CLAIM("b1.interior.hvac", "vav_diffuser"),
                                         CLAIM("b1.interior.window", "double"), CLAIM("b1.interior.room.r1", "open_office")]}
    got = co2.select(interior, claims)
    assert [(g["kind"], g["equipment"]) for g in got] == [
        ("lighting", "fluorescent troffer"), ("lighting", "recessed fixture (fluorescent)"), ("hvac", "ceiling supply diffuser")]
    assert got[2]["verifier"] == {"status": "verified", "note": "note b1.interior.hvac"}


@pytest.mark.parametrize("status,value", [("rejected", "fluorescent"), ("unverified", "fluorescent"), ("verified", "unknown")])
def test_claim_not_verified_or_unknown_gives_no_tag(status, value):
    interior = {"pins": [PIN("b1.interior.lighting", "fluorescent troffer", [1, 2, 3])]}
    assert co2.select(interior, {"b1.interior.lighting": CLAIM("b1.interior.lighting", value, status)}) == []


async def test_build_matches_the_panorama_by_exact_position(bdir, monkeypatch):
    write(bdir, {"model_id": "M1", "pins": [PIN("b1.interior.hvac", "ceiling air vent", [-3.03, 4.23, 1.49]),
                                            PIN("b1.interior.lighting", "fluorescent troffer", [9.0, 9.0, 1.5])]},
          [CLAIM("b1.interior.hvac", "vav_diffuser", ev=["mpp_M1_pA_3", "mpp_M1_pB_0"]),
           CLAIM("b1.interior.lighting", "fluorescent", ev=["mpp_M1_pB_0"])],
          tour={"model_id": "M1", "available": True, "showcase_url": "https://my.matterport.com/show/?m=M1", "basis": "basics"})

    async def panos(model_id):
        assert model_id == "M1"
        return [PanoramaRef(pano_id="pA", model_id="M1", label="1", xyz=(-3.03, 4.23, 1.49), skybox_urls=[]),
                PanoramaRef(pano_id="pB", model_id="M1", label="2", xyz=(0.0, 0.0, 1.5), skybox_urls=[])]
    monkeypatch.setattr(mp, "panoramas", panos)
    out = await co2.build("b1")
    assert out["model_id"] == "M1" and out["tour_url"] == "https://my.matterport.com/show/?m=M1" and out["tags_in_tour"] is True
    hvac, light = out["items"]
    assert (hvac["pano_id"], hvac["image_id"], hvac["image_url"]) == ("pA", "mpp_M1_pA_3", "/media/mpp_M1_pA_3")
    assert (light["pano_id"], light["image_id"], light["image_url"]) == (None, None, None)  # no panorama there: not guessed


async def test_tour_of_another_scan_is_shown_but_gets_no_tags(bdir, monkeypatch):
    write(bdir, {"model_id": "M1", "pins": []}, [], tour={"model_id": "OTHER", "available": True, "showcase_url": "https://x/?m=OTHER"})
    out = await co2.build("b1")
    assert out["tour_url"] == "https://x/?m=OTHER" and out["tags_in_tour"] is False and out["items"] == []
    write(bdir, {"model_id": "M1", "pins": []}, [], tour={"model_id": "M1", "available": False, "showcase_url": None, "visibility": "private"})
    assert (await co2.build("b1"))["tour_url"] is None


def test_route(bdir, monkeypatch):
    write(bdir, {"model_id": None, "pins": []}, [])
    from app.main import app
    c = TestClient(app)
    assert c.get("/co2_equipment/b1").json() == {"building_id": "b1", "model_id": None, "tour_model_id": None, "tour_url": None,
                                                  "tour_basis": None, "tags_in_tour": False, "items": []}
    assert c.get("/co2_equipment/nope").status_code == 404
