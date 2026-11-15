"""Emissions in 3D: every number traces to the engine baseline or the cited split; no evidence or
position is invented (missing → "unknown"); the label is always present; off by default."""
import json

import pytest

from app.agents import emissions_3d as e3
from app.config import get_settings
from app.guardrails import source_numbers

# A stand-in split for the tests only (NOT the real source; that one is provided separately).
SPLIT = {"citation": "TEST SOURCE (not real data)", "url": None, "scope": "test offices",
         "basis": "share of energy CO2",
         "end_uses": [{"name": "Lighting", "category": "lighting", "share": 0.25},
                      {"name": "Space cooling", "category": "cooling", "share": 0.3},
                      {"name": "Office equipment", "category": "office_equipment", "share": 0.2},
                      {"name": "Refrigeration", "category": "refrigeration", "share": 0.05},
                      {"name": "Other", "category": "other", "share": 0.2}]}


@pytest.fixture
def bdir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    d = tmp_path / "data" / "buildings" / "b1"
    d.mkdir(parents=True)
    (tmp_path / "data" / "portfolio.json").write_text(json.dumps({"buildings": [
        {"building_id": "b1", "matterport_model_ids": ["m1"], "matterport_model_id": "m1"}]}))
    yield d
    get_settings.cache_clear()


def claim(cid, value, status="verified"):
    return {"claim_id": cid, "value": value, "status": status, "evidence_ids": ["img1"]}


def numbers(obj, skip=("xyz", "url", "evidence_ids", "claim_id", "building_id", "model_id")):
    """Every number in the output except identifiers and 3D coordinates (checked separately)."""
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k not in skip:
                out += numbers(v, skip)
    elif isinstance(obj, list):
        for v in obj:
            out += numbers(v, skip)
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        out.append(float(obj))
    return out


def test_every_number_traces_to_baseline_or_source(bdir):
    (bdir / "verification.json").write_text(json.dumps([
        claim("b1.interior.lighting", "fluorescent"), claim("b1.interior.hvac", "vav_diffuser", "rejected"),
        claim("b1.interior.room.r1", "open_office")]))
    pins = [{"claim_id": "b1.interior.lighting", "label": "troffer", "xyz": [1.0, 2.0, 1.5], "status": "verified"},
            {"claim_id": "b1.interior.hvac", "label": "diffuser", "xyz": [3.0, 4.0, 1.5], "status": "rejected"}]
    rooms = [{"room_id": "r1", "type": "open_office", "also_contains": [], "claim_id": "b1.interior.room.r1",
              "status": "verified", "xyz": [5.0, 6.0, 1.4], "evidence_note": "Rows of desks."}]
    (bdir / "interior.json").write_text(json.dumps({"pins": pins, "rooms": rooms}))
    split = e3.Split.model_validate(SPLIT)
    out = e3.build("b1", 536.7, split, tour={"available": True})

    # top 3 by share, labelled, every value an estimate with a basis
    assert [r["end_use"] for r in out["top"]] == ["Space cooling", "Lighting", "Office equipment"]
    assert out["label"] == "building-wide estimate, shown where observed"
    for r in out["top"]:
        for k in ("tonnes_per_year", "pct_of_building"):
            assert r[k]["estimate"] is True and r[k]["basis"]
        share = next(e.share for e in split.end_uses if e.name == r["end_use"])
        assert r["tonnes_per_year"]["value"] == round(536.7 * share, 1)
        assert r["pct_of_building"]["value"] == round(share * 100, 1)
        assert r["citation"]["citation"] == split.citation

    # every number in the file is the baseline, a share from the source, or baseline x share / share x 100
    shares = [e.share for e in split.end_uses]
    allowed = {536.7, *shares, *(round(536.7 * s, 1) for s in shares), *(round(s * 100, 1) for s in shares)}
    allowed |= source_numbers(SPLIT)  # numbers inside the citation text itself
    for n in numbers(out):
        assert any(abs(n - a) < 1e-9 for a in allowed), n

    # positions only where a verified claim or verified room put them, copied verbatim
    by = {r["end_use"]: r for r in out["top"]}
    assert by["Lighting"]["positions"] == [{"xyz": [1.0, 2.0, 1.5], "label": "troffer", "claim_id":
                                            "b1.interior.lighting", "kind": "pin", "note": e3.POSITION_NOTE}]
    assert by["Office equipment"]["positions"][0]["xyz"] == [5.0, 6.0, 1.4]
    # HVAC claim was rejected: no evidence, no position, said so
    assert by["Space cooling"]["evidence"] == "unknown" and by["Space cooling"]["positions"] == "unknown"


def test_no_interior_means_unknown_not_invented(bdir):
    (bdir / "verification.json").write_text(json.dumps([claim("b1.aerial.roof.type", "flat")]))
    out = e3.build("b1", None, e3.Split.model_validate(SPLIT))
    for r in out["top"]:
        assert r["evidence"] == "unknown" and r["positions"] == "unknown"
        assert r["tonnes_per_year"]["value"] == "unknown"  # no baseline → no tonnes
    assert out["baseline"]["tonnes_per_year"] == "unknown"


def test_unknown_claim_value_is_not_evidence(bdir):
    (bdir / "verification.json").write_text(json.dumps([claim("b1.interior.lighting", "unknown")]))
    (bdir / "interior.json").write_text(json.dumps({"pins": [], "rooms": []}))
    ev, pos = e3.evidence_for("b1", "lighting")
    assert ev == "unknown" and pos == "unknown"


def test_split_must_be_cited_and_sane(tmp_path):
    with pytest.raises(FileNotFoundError, match="not provided"):
        e3.load_split(tmp_path / "missing.json")
    bad = dict(SPLIT, end_uses=[{"name": "x", "category": "lighting", "share": 0.8},
                                {"name": "y", "category": "cooling", "share": 0.5}])
    with pytest.raises(ValueError, match="more than 1"):
        e3.Split.model_validate(bad)
    with pytest.raises(ValueError):
        e3.Split.model_validate(dict(SPLIT, end_uses=[{"name": "x", "category": "plasma", "share": 0.1}]))
    with pytest.raises(ValueError):
        e3.Split.model_validate({k: v for k, v in SPLIT.items() if k != "citation"})


async def test_tour_from_visibility_and_unknown_on_failure(bdir, monkeypatch):
    async def public(mid):
        return {"visibility": "public"}
    monkeypatch.setattr(e3.mp, "basics", public)
    t = await e3.tour_status("b1")
    assert t["available"] and t["showcase_url"].endswith("m=m1") and t["visibility"] == "public"

    async def private(mid):
        return {"visibility": "private"}
    monkeypatch.setattr(e3.mp, "basics", private)
    t = await e3.tour_status("b1")
    assert not t["available"] and t["showcase_url"] is None

    async def boom(mid):
        raise RuntimeError("api down")
    monkeypatch.setattr(e3.mp, "basics", boom)
    t = await e3.tour_status("b1")
    assert t["visibility"] == "unknown" and not t["available"] and "failed" in t["basis"]


def test_flag_off_by_default(bdir, monkeypatch):
    (bdir / "emissions_3d.json").write_text("{}")
    monkeypatch.delenv("EMISSIONS_3D", raising=False)
    assert e3.load("b1") is None
    monkeypatch.setenv("EMISSIONS_3D", "true")
    assert e3.load("b1") == {}


# --------------------------------------------------------------------------- UI path: verified positions only

def _ref(pid, xyz):
    from app.adapters.types import PanoramaRef
    return PanoramaRef(model_id="m1", pano_id=pid, xyz=xyz, skybox_urls=[])


def _interior(bdir, monkeypatch, panos):
    claims = [
        {**claim("b1.interior.lighting", "fluorescent"), "evidence_ids": ["mpp_m1_p1_0", "mpp_m1_p2_1"],
         "verifier_score": 0.95, "verifier_note": "Troffers visible.", "loops": 0},
        {**claim("b1.interior.hvac", "vav_diffuser", "rejected"), "evidence_ids": ["mpp_m1_p3_0"]},
        claim("b1.interior.room.r1", "open_office"),
    ]
    pins = [{"claim_id": "b1.interior.lighting", "label": "troffer", "xyz": [1.0, 2.0, 1.5], "status": "verified"},
            {"claim_id": "b1.interior.lighting", "label": "troffer", "xyz": [9.0, 9.0, 1.5], "status": "verified"},
            {"claim_id": "b1.interior.hvac", "label": "diffuser", "xyz": [3.0, 4.0, 1.5], "status": "rejected"},
            {"claim_id": "b1.interior.room.r1", "label": "Open office", "xyz": [5.0, 6.0, 1.4], "status": "verified"}]
    (bdir / "verification.json").write_text(json.dumps(claims))
    (bdir / "interior.json").write_text(json.dumps({"model_id": "m1", "pins": pins, "rooms": []}))

    async def fake_panos(mid):
        return panos
    monkeypatch.setattr(e3.mp, "panoramas", fake_panos)


async def test_positions_are_verified_equipment_only_with_pano_and_verifier(bdir, monkeypatch):
    _interior(bdir, monkeypatch, [_ref("p1", (1.0, 2.0, 1.5)), _ref("p2", (7.0, 7.0, 1.5)), _ref("p3", (3.0, 4.0, 1.5))])
    out = await e3.positions("b1")
    pos = out["positions"]
    assert [p["claim_id"] for p in pos] == ["b1.interior.lighting", "b1.interior.lighting"]  # no rejected HVAC, no room
    first = pos[0]
    assert first == {"xyz": [1.0, 2.0, 1.5], "equipment": "lighting", "equipment_type": "fluorescent",
                     "seen_as": "troffer", "claim_id": "b1.interior.lighting",
                     "verifier": {"status": "verified", "score": 0.95, "note": "Troffers visible.", "loops": 0},
                     "pano_id": "p1", "model_id": "m1"}
    assert pos[1]["pano_id"] == "unknown"  # no evidence panorama sits at that position: not guessed


async def test_ui_payload_has_no_shares_and_needs_no_source(bdir, monkeypatch):
    monkeypatch.setenv("EMISSIONS_SPLIT_PATH", str(bdir / "no_such_source.json"))  # the split is absent
    _interior(bdir, monkeypatch, [_ref("p1", (1.0, 2.0, 1.5))])
    await e3.save_positions("b1")
    monkeypatch.setenv("EMISSIONS_3D", "true")
    out = e3.load("b1")
    text = json.dumps(out)
    for word in ("share", "pct", "tonnes", "baseline", "citation", "end_use"):
        assert word not in text
    assert out["positions"][0]["pano_id"] == "p1"


async def test_no_verified_equipment_or_no_interior_is_unknown(bdir, monkeypatch):
    out = await e3.positions("b1")  # no interior at all
    assert out["positions"] == "unknown" and out["model_id"] == "unknown"

    async def boom(mid):
        raise RuntimeError("api down")
    _interior(bdir, monkeypatch, [])
    monkeypatch.setattr(e3.mp, "panoramas", boom)
    out = await e3.positions("b1")
    assert {p["pano_id"] for p in out["positions"]} == {"unknown"}  # can't confirm → unknown
