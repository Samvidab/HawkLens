from typing import Literal

from pydantic import BaseModel


class BuildingProfile(BaseModel):  # data/buildings/<id>/profile.json
    building_id: str
    costar_id: str
    name: str
    address: str
    city: Literal["Houston", "Los Angeles"]
    lat: float
    lon: float
    footprint_wkt: str | None = None
    footprint_source: Literal["costar", "estimated"]
    property_type: str
    building_class: str | None = None
    year_built: int | None = None
    stories: int | None = None
    rba_sqft: float | None = None
    occupancy_pct: float | None = None
    matterport_model_id: str | None = None
    source_fields: dict[str, str]  # which CoStar fields fed each value
