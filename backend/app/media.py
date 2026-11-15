"""Media routes: evidence images and the hero's Matterport mesh.

GET /media/{image_id}                 image path from data/buildings/<id>/images.json (written by the
                                      aerial/interior inspectors: {image_id: ImageRef})
GET /media/mesh/{model_id}/{file}     OBJ / MTL / textures from cache/media/mesh/<model_id>/ (extracted by
                                      adapters.matterport.matterpak). `model.obj` / `model.mtl` alias the
                                      first .obj / .mtl in the folder, whatever the zip named them.
Only files under cache/ or data/ are served, and mesh files only with a whitelisted extension.
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.config import BACKEND_DIR, get_settings
from app.storage import read_json

router = APIRouter()

MESH_SUFFIXES = {".obj", ".mtl", ".jpg", ".jpeg", ".png"}
mimetypes.add_type("text/plain", ".obj")
mimetypes.add_type("text/plain", ".mtl")


def _inside(path: Path, *roots: Path) -> bool:
    p = path.resolve()
    return any(p.is_relative_to(Path(r).resolve()) for r in roots)


def find_image_path(image_id: str) -> Path | None:
    s = get_settings()
    for d in sorted(p for p in (Path(s.data_dir) / "buildings").glob("*") if p.is_dir()):
        entry = (read_json(d / "images.json", {}) or {}).get(image_id)
        if entry and entry.get("local_path"):
            p = Path(entry["local_path"])
            return p if p.is_absolute() else BACKEND_DIR / p
    return None


@router.get("/media/mesh/{model_id}/{file:path}")
def mesh_file(model_id: str, file: str):
    base = Path(get_settings().cache_dir) / "media" / "mesh" / model_id
    if not base.is_dir() or "/" in model_id or model_id.startswith("."):
        raise HTTPException(404, "no mesh for this model")
    target = base / file
    if not target.is_file() and file in ("model.obj", "model.mtl"):
        found = sorted(base.glob(f"*{Path(file).suffix}"))
        target = found[0] if found else target
    if (not target.is_file() or target.suffix.lower() not in MESH_SUFFIXES or target.name.startswith(".")
            or not _inside(target, base)):
        raise HTTPException(404, "file not found")
    return FileResponse(target)


@router.get("/media/{image_id}")
def image(image_id: str):
    s = get_settings()
    path = find_image_path(image_id)
    if path is None or not path.is_file() or not _inside(path, s.cache_dir, s.data_dir):
        raise HTTPException(404, f"image {image_id} not found")
    return FileResponse(path)
