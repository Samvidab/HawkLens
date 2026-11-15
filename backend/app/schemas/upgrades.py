from typing import Literal

from pydantic import BaseModel


class FeasibleUpgrade(BaseModel):  # feasibility.json = list[FeasibleUpgrade]
    upgrade_id: str
    building_id: str
    category: Literal["lighting", "hvac", "envelope", "solar", "roof"]
    type: Literal["rooftop_solar", "cool_roof", "window_upgrade", "heat_pump", "insulation", "led_retrofit"]
    size_value: float
    size_unit: Literal["kW", "sqft", "fixtures"]
    reason: str
    confidence: float
    claim_ids: list[str]
    evidence_ids: list[str]
    verified: Literal["verified", "unverified", "assumed"]  # led_retrofit default = "assumed"
    include_in_optimizer: bool  # False if unverified unless owner overrides
