"""Adapter return types (TRD §4)."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

Orientation = Literal["N", "E", "S", "W"]


class ImageRef(BaseModel):
    image_id: str
    source: Literal["vexcel_overhead", "vexcel_oblique", "matterport_pano"]
    orientation: Orientation | None = None
    local_path: str  # cached file served at /media/{image_id}
    gsd_m: float | None = None  # ground sample distance (m/px) if known
    bounds_wkt: str | None = None
    captured_at: str | None = None


class PanoramaRef(BaseModel):
    pano_id: str
    model_id: str
    label: str | None = None
    xyz: tuple[float, float, float]  # metres, model frame, z up
    skybox_urls: list[str]  # signed, expiring; faces 0 up, 1–4 horizon, 5 down
    room_id: str | None = None


class MatterportModelRef(BaseModel):
    model_id: str
    name: str | None = None
    address: str | None = None
    lat: float | None = None
    lon: float | None = None
    rooms: int = 0
    panos: int = 0
    matterpak: Literal["unlocked", "locked", "unknown"] = "unknown"


class MatterPakPaths(BaseModel):
    model_id: str
    dir: str
    obj: str | None = None
    mtl: str | None = None
    textures: list[str] = []
    floorplan: str | None = None
    pointcloud: str | None = None  # not extracted by default (≈400 MB)
