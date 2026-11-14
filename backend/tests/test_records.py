import json

import pytest

from app.adapters.geometry import SQFT_PER_M2, area_m2
from app.agents import records
from app.config import get_settings
from app.events import load_events, reset_run

REC = {
    "id": 23347, "buildingName": "333 Northbelt", "propertyType": 5, "buildingClass": 2,
    "rentableBuildingAreaSquareFeet": 213281.0, "grossBuildingAreaSquareFeet": 213281.0,
    "grossTypicalFloorSquareFeet": 17773.0, "numStoriesAboveGrade": 12,
    "constructionEvents": [{"eventType": 2, "year": 1980}, {"eventType": 4, "year": 2024, "month": 4}],
    "primaryAddress": {"streetNumber": "333", "streetName": "Sam Houston", "streetType": "Pky", "city": "Houston",
                       "state": "TX", "postcode": "770602414", "latitude": 29.9407608, "longitude": -95.3982479,
                       "researchMarketId": 14},
}


def test_map_record_fields_and_sources():
    p = records.map_record(REC)
    assert (p.building_id, p.costar_id, p.name, p.city) == ("23347", "23347", "333 Northbelt", "Houston")
    assert p.address == "333 Sam Houston Pky, Houston, TX 77060"
    assert (p.property_type, p.building_class, p.year_built, p.stories, p.rba_sqft) == ("Office", "B", 1980, 12, 213281.0)
    assert p.footprint_source == "estimated" and p.occupancy_pct is None and p.matterport_model_id is None
    # footprint uses the typical floor plate
    assert area_m2(p.footprint_wkt, "Houston") == pytest.approx(17773.0 / SQFT_PER_M2, rel=0.01)
    for f in ("name", "address", "city", "lat", "lon", "property_type", "building_class", "year_built",
              "stories", "rba_sqft", "footprint_wkt"):
        assert f in p.source_fields, f


def test_map_record_fallbacks():
    rec = dict(REC, buildingName=None, grossTypicalFloorSquareFeet=None, buildingClass=0, constructionEvents=[])
    p = records.map_record(rec, matterport_model_id="abc")
    assert p.name == "333 Sam Houston Pky"
    assert p.building_class is None and p.year_built is None and "year_built" not in p.source_fields
    assert area_m2(p.footprint_wkt, "Houston") == pytest.approx(213281.0 / 12 / SQFT_PER_M2, rel=0.01)
    assert p.matterport_model_id == "abc" and "matterport_model_id" in p.source_fields


def test_map_record_rejects_other_markets():
    with pytest.raises(ValueError):
        records.map_record(dict(REC, primaryAddress=dict(REC["primaryAddress"], researchMarketId=99)))


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    (tmp_path / "data").mkdir()
    yield tmp_path / "data"
    get_settings.cache_clear()


async def test_run_writes_profile_and_event(data_dir, monkeypatch):
    (data_dir / "portfolio.json").write_text(json.dumps({"buildings": [
        {"building_id": "23347", "costar_id": "23347", "hero": True, "matterport_model_id": "hu9"}]}))

    async def fake_get(pid):
        assert str(pid) == "23347"
        return REC

    monkeypatch.setattr(records.costar, "get_property", fake_get)
    reset_run("r1")
    p = await records.run("23347", run_id="r1")
    saved = json.loads((data_dir / "buildings" / "23347" / "profile.json").read_text())
    assert saved["matterport_model_id"] == "hu9" and saved == p.model_dump(mode="json")
    [ev] = load_events("r1")
    assert ev.agent == "Records" and ev.kind == "fetch" and ev.building_name == "333 Northbelt"
    assert ev.message == "12 stories, 213,281 sq ft, built 1980, class B"
