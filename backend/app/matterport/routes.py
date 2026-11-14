"""FastAPI routes for the Matterport property platform (read-only, Phase 2 subset)."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.matterport import service

router = APIRouter(prefix="/properties", tags=["properties"])


@router.get("")
def list_properties(
    q: str | None = Query(default=None, description="search by name or city"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> dict:
    return service.list_properties(q=q, limit=limit, offset=offset)


@router.get("/{model_id}")
def get_property(model_id: str) -> dict:
    prop = service.get_property(model_id)
    if prop is None:
        raise HTTPException(status_code=404, detail=f"No stored model {model_id}")
    return prop
