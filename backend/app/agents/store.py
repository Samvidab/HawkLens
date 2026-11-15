"""data/buildings/<id>/ file helpers shared by the survey agents (atomic writes, TRD §5)."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from app.adapters.cache import write_json_atomic
from app.adapters.types import ImageRef
from app.config import get_settings
from app.schemas.claims import Claim


def building_dir(building_id: str) -> Path:
    return Path(get_settings().data_dir) / "buildings" / building_id


def run_dir(run_id: str) -> Path:
    return Path(get_settings().data_dir) / "runs" / run_id


def save_claims(building_id: str, claims: Iterable[Claim]) -> None:
    write_json_atomic(building_dir(building_id) / "claims.json", [c.model_dump(mode="json") for c in claims])


def add_images(building_id: str, images: Iterable[ImageRef]) -> None:
    """Merge into images.json (image_id → ImageRef); the /media route resolves ids through it."""
    p = building_dir(building_id) / "images.json"
    index = json.loads(p.read_text()) if p.exists() else {}
    index.update({i.image_id: i.model_dump(mode="json") for i in images})
    write_json_atomic(p, index)


def find_image(image_id: str) -> ImageRef | None:
    root = Path(get_settings().data_dir) / "buildings"
    for p in root.glob("*/images.json"):
        entry = json.loads(p.read_text()).get(image_id)
        if entry:
            return ImageRef.model_validate(entry)
    return None
