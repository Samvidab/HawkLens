from typing import Literal

from pydantic import BaseModel


class FacadeFinding(BaseModel):
    glazing_ratio: float | None = None
    window_count_est: int | None = None
    notes: str | None = None


class AerialFindings(BaseModel):  # aerial.json
    building_id: str
    roof_type: Literal["flat", "pitched", "mixed", "unknown"]
    roof_color: Literal["dark", "light", "mixed", "unknown"]
    usable_roof_fraction: float  # of footprint, from Gemini, 0-1
    shading: Literal["none", "partial", "heavy"]
    existing_solar: bool
    usable_roof_m2: float  # computed in code = footprint_area x fraction
    facades: dict[Literal["N", "E", "S", "W"], FacadeFinding] = {}
    claim_ids: list[str]
    evidence_ids: list[str]
