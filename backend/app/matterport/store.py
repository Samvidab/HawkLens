"""Atomic JSON persistence for Matterport records under data/matterport/.

No database (repo rule): one JSON file per model, plus small index files. All writes
are atomic (temp file + rename) and idempotent.
"""
from __future__ import annotations

import json
from pathlib import Path

from app.config import get_settings
from app.matterport.models import MpModel


def mp_dir() -> Path:
    return get_settings().data_dir / "matterport"


def models_dir() -> Path:
    return mp_dir() / "models"


def _atomic_write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")
    tmp.replace(path)


def save_model(model: MpModel) -> Path:
    path = models_dir() / f"{model.id}.json"
    _atomic_write_json(path, model.model_dump())
    return path


def load_model(model_id: str) -> MpModel | None:
    path = models_dir() / f"{model_id}.json"
    if not path.exists():
        return None
    return MpModel.model_validate_json(path.read_text())


def media_dir() -> Path:
    return get_settings().cache_dir / "media" / "mp"


def save_thumbnail(model_id: str, data: bytes) -> Path:
    """Persist thumbnail bytes under cache/media/mp/<id>/thumb.jpg and return the path."""
    path = media_dir() / model_id / "thumb.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)
    return path


def thumbnail_path(model_id: str) -> Path | None:
    path = media_dir() / model_id / "thumb.jpg"
    return path if path.exists() else None


def list_models() -> list[MpModel]:
    d = models_dir()
    if not d.exists():
        return []
    out: list[MpModel] = []
    for p in sorted(d.glob("*.json")):
        try:
            out.append(MpModel.model_validate_json(p.read_text()))
        except Exception:
            continue
    return out
