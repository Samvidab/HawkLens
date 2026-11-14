"""Model backfill: page Houston models, pick a slice, fetch embed, store.

Idempotent and cache-backed. For the thin vertical slice this selects a small number
of published Houston models that look like whole buildings (not per-unit floorplans),
fetches each full model(id) for the Showcase embed, and stores one JSON per model.

Houston filter = query:"Houston" to narrow, then verify address.locality == "Houston".
"""
from __future__ import annotations

import re

from app.matterport.client import MatterportClient
from app.matterport.models import MpModel
from app.matterport.parsers import merge_model_detail, parse_search_result
from app.matterport.queries import MODEL_BY_ID, MODELS_SEARCH
from app.matterport import store

# Name tokens that suggest a single apartment unit / floorplan rather than a building.
_UNIT_HINTS = re.compile(
    r"\b(studio|\d+\s*bed|sq\s*ft|unit|/\s*\d|apt|apartment|floor\s*plan)\b",
    re.IGNORECASE,
)


def looks_like_building(name: str | None) -> bool:
    if not name:
        return False
    return not _UNIT_HINTS.search(name)


async def _iter_houston(client: MatterportClient, *, page_size: int = 100):
    """Yield parsed Houston search results (locality == Houston, published, has thumb)."""
    async for page in client.paginate(
        MODELS_SEARCH,
        {"query": "Houston"},
        connection_path=["models"],
        op_name="models_houston",
        page_size=page_size,
    ):
        for r in page:
            m = parse_search_result(r)
            if (m.city or "").strip().lower() != "houston":
                continue
            if not m.published or not m.thumbnail_url:
                continue
            yield m


async def select_slice(
    client: MatterportClient,
    *,
    limit: int = 8,
    prefer_buildings: bool = True,
    max_scan_pages: int = 10,
) -> list[MpModel]:
    """Pick up to `limit` Houston models, preferring building-like names."""
    buildings: list[MpModel] = []
    others: list[MpModel] = []
    pages = 0
    async for m in _iter_houston(client):
        (buildings if looks_like_building(m.name) else others).append(m)
        if prefer_buildings and len(buildings) >= limit:
            break
        pages = len(buildings) + len(others)
        if pages >= max_scan_pages * 100:
            break

    chosen = (buildings + others) if prefer_buildings else (buildings + others)
    return chosen[:limit]


async def backfill_slice(
    *,
    limit: int = 8,
    prefer_buildings: bool = True,
    client: MatterportClient | None = None,
) -> list[MpModel]:
    """Select a slice, fetch each full model for its embed, store, and return them."""
    own = client is None
    client = client or MatterportClient()
    stored: list[MpModel] = []
    try:
        chosen = await select_slice(client, limit=limit, prefer_buildings=prefer_buildings)
        for m in chosen:
            detail = await client.graphql(MODEL_BY_ID, {"id": m.id}, op_name=f"model_{m.id}")
            full = merge_model_detail(m, detail["model"])
            # Matterport image URLs are short-lived signed URLs; download the bytes now
            # and serve our own durable copy (R5). Use the freshly-signed URL from the
            # full-model response.
            if full.thumbnail_url:
                try:
                    data = await client.get_bytes(full.thumbnail_url, op_name=f"thumb_{m.id}")
                    path = store.save_thumbnail(m.id, data)
                    full = full.model_copy(update={"thumbnail_path": str(path)})
                except Exception:
                    pass  # keep the record even if the thumbnail fetch fails
            store.save_model(full)
            stored.append(full)
    finally:
        if own:
            await client.aclose()
    return stored
