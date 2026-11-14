from typing import Literal

from pydantic import BaseModel


class Pin(BaseModel):
    claim_id: str
    label: str
    xyz: tuple[float, float, float]
    status: str


class InteriorFindings(BaseModel):  # interior.json (hero only for MVP)
    building_id: str
    model_id: str
    lighting_type: Literal["LED", "fluorescent", "incandescent", "mixed", "unknown"]
    hvac_visible: list[str]
    window_type: Literal["single", "double", "unknown"]
    floor_area_sqft: float | None = None  # from room boundaries (code)
    envelope_area_sqft: float | None = None  # exterior wall length x floor height x stories (code)
    claim_ids: list[str]
    evidence_ids: list[str]
    pins: list[Pin]
