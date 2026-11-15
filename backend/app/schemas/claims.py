from typing import Literal

from pydantic import BaseModel


class Mark(BaseModel):
    image_id: str
    label: str
    bbox: tuple[float, float, float, float] | None = None  # normalized 0-1 (x0,y0,x1,y1)
    polygon: list[tuple[float, float]] | None = None  # normalized


class Claim(BaseModel):  # every observation an inspector makes
    claim_id: str
    building_id: str
    agent: Literal["aerial", "interior"]
    field: str  # e.g. "roof.existing_solar", "facade.S.glazing"
    value: str | float | bool
    confidence: float  # inspector's own 0-1
    evidence_ids: list[str]
    marks: list[Mark] = []
    status: Literal["pending", "verified", "sent_back", "unverified", "rejected"] = "pending"
    verifier_score: float | None = None
    loops: int = 0
    verifier_note: str | None = None
