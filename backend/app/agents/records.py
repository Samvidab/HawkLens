"""Records agent (T1.5): CoStar record → BuildingProfile → data/buildings/<id>/profile.json.

No LLM. Every value is copied or derived in code, and `source_fields` names the CoStar field(s)
behind it. CoStar records carry no building footprint, so the footprint is always an estimated
square centred on the geocoded point (adapters/README.md).
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

from app.adapters import costar
from app.adapters.cache import write_json_atomic
from app.adapters.geometry import SQFT_PER_M2, square_wkt
from app.config import get_settings
from app.events import emit
from app.schemas.profile import BuildingProfile

AGENT = "Records"
MARKET_CITY = {v: k for k, v in costar.MARKET_ID.items()}


def profile_path(building_id: str) -> Path:
    return Path(get_settings().data_dir) / "buildings" / building_id / "profile.json"


def load_portfolio() -> dict[str, Any]:
    p = Path(get_settings().data_dir) / "portfolio.json"
    return json.loads(p.read_text()) if p.exists() else {"buildings": []}


def portfolio_entry(building_id: str) -> dict[str, Any] | None:
    return next((b for b in load_portfolio()["buildings"] if b["building_id"] == building_id), None)


def footprint_sqft(rec: dict[str, Any]) -> tuple[float | None, str | None]:
    """Best per-floor area for the footprint estimate, and the CoStar field it came from."""
    typical = rec.get("grossTypicalFloorSquareFeet")
    if typical:
        return float(typical), "grossTypicalFloorSquareFeet"
    stories = rec.get("numStoriesAboveGrade") or 1
    for field in ("grossBuildingAreaSquareFeet", "rentableBuildingAreaSquareFeet"):
        if rec.get(field):
            return float(rec[field]) / stories, f"{field} / numStoriesAboveGrade"
    return None, None


def map_record(rec: dict[str, Any], *, building_id: str | None = None,
               matterport_model_id: str | None = None) -> BuildingProfile:
    pa = rec.get("primaryAddress") or {}
    market = pa.get("researchMarketId")
    if market not in MARKET_CITY:
        raise ValueError(f"CoStar {rec.get('id')}: research market {market} is not Houston (14) or LA (20)")
    city = MARKET_CITY[market]
    lat, lon = pa.get("latitude"), pa.get("longitude")
    if lat is None or lon is None:
        raise ValueError(f"CoStar {rec.get('id')}: primaryAddress has no coordinates")

    address = costar.format_address(pa)
    src: dict[str, str] = {
        "costar_id": "id",
        "address": "primaryAddress.{streetNumber,streetDirection,streetName,streetType,streetSuffix,city,state,postcode}",
        "city": "primaryAddress.researchMarketId",
        "lat": "primaryAddress.latitude",
        "lon": "primaryAddress.longitude",
        "property_type": "propertyType",
    }

    name = rec.get("buildingName")
    src["name"] = "buildingName" if name else "primaryAddress (no buildingName)"
    name = name or address.split(",")[0]

    building_class = costar.BUILDING_CLASS.get(rec.get("buildingClass"))
    if building_class:
        src["building_class"] = "buildingClass"
    yb = costar.year_built(rec)
    if yb:
        src["year_built"] = "constructionEvents[eventType=2 ConstructionComplete].year"
    stories = rec.get("numStoriesAboveGrade")
    if stories:
        src["stories"] = "numStoriesAboveGrade"
    rba = rec.get("rentableBuildingAreaSquareFeet")
    if rba:
        src["rba_sqft"] = "rentableBuildingAreaSquareFeet"

    fp_sqft, fp_field = footprint_sqft(rec)
    footprint = None
    if fp_sqft:
        footprint = square_wkt(lat, lon, math.sqrt(fp_sqft / SQFT_PER_M2), city)
        src["footprint_wkt"] = f"estimated: square of {fp_field} at primaryAddress lat/lon"
    if matterport_model_id:
        src["matterport_model_id"] = "commercial-properties.csv MatterportModelId (portfolio hero model)"

    return BuildingProfile(
        building_id=building_id or str(rec["id"]),
        costar_id=str(rec["id"]),
        name=name,
        address=address,
        city=city,
        lat=float(lat),
        lon=float(lon),
        footprint_wkt=footprint,
        footprint_source="estimated",
        property_type=costar.PROPERTY_TYPE.get(rec.get("propertyType"), "Unknown"),
        building_class=building_class,
        year_built=yb,
        stories=stories,
        rba_sqft=float(rba) if rba else None,
        occupancy_pct=None,  # not on the property record (would need location-occupancy.jsonl)
        matterport_model_id=matterport_model_id,
        source_fields=src,
    )


def summary(p: BuildingProfile) -> str:
    parts = []
    if p.stories:
        parts.append(f"{p.stories} stories")
    if p.rba_sqft:
        parts.append(f"{p.rba_sqft:,.0f} sq ft")
    if p.year_built:
        parts.append(f"built {p.year_built}")
    if p.building_class:
        parts.append(f"class {p.building_class}")
    return ", ".join(parts) or p.property_type


async def run(building_id: str, run_id: str | None = None) -> BuildingProfile:
    """Build and write profile.json for one portfolio building (CoStar PropertyId)."""
    entry = portfolio_entry(building_id) or {}
    costar_id = entry.get("costar_id", building_id)
    model_id = entry.get("matterport_model_id") if entry.get("hero") else None

    rec = await costar.get_property(costar_id)
    profile = map_record(rec, building_id=building_id, matterport_model_id=model_id)
    write_json_atomic(profile_path(building_id), profile.model_dump(mode="json"))
    if run_id:
        emit(run_id, AGENT, "fetch", summary(profile), building_id, building_name=profile.name)
    return profile
