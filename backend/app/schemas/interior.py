from typing import Literal

from pydantic import BaseModel


class Pin(BaseModel):
    claim_id: str
    label: str
    xyz: tuple[float, float, float]
    status: str


RoomType = Literal["open_office", "private_office", "conference", "corridor", "lobby", "restroom",
                   "mechanical_it", "storage", "kitchen_break", "unknown"]


class RoomLabel(BaseModel):  # agentic annotation of a commercial interior (Lane A)
    room_id: str
    type: RoomType  # main use
    also_contains: list[RoomType] = []  # other spaces inside the same Matterport room (merged regions)
    confidence: float
    evidence_note: str | None = None  # inspector's short reason, from the panoramas
    claim_id: str
    status: str = "pending"  # verifier status of the claim
    area_sqft: float | None = None  # Matterport room dimensions (code)
    pano_ids: list[str] = []
    xyz: tuple[float, float, float] | None = None  # mean scan position of the room's panoramas
    matterport_tags: list[str] = []  # Matterport's own room tags, kept for comparison only


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
    rooms: list[RoomLabel] = []
