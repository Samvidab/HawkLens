"""Read API over the stored Matterport records in data/matterport/.

Pure reads, no network. Returns trimmed dicts suitable for the frontend (we do not
ship the big `raw` blob to clients).
"""
from __future__ import annotations

from app.matterport import store
from app.matterport.models import MpModel


def _public(m: MpModel) -> dict:
    # Prefer our durable, self-hosted thumbnail; the raw CDN URL expires quickly.
    thumb = f"/properties/{m.id}/thumbnail" if m.thumbnail_path else None
    return {
        "id": m.id,
        "name": m.name,
        "city": m.city,
        "address": m.address.formatted,
        "thumbnail_url": thumb,
        "show_url": m.show_url,
        "embed_html": m.embed_html,
        "published": m.published,
        "lat": m.geo.lat,
        "lon": m.geo.lon,
    }


def list_properties(*, q: str | None = None, limit: int = 100, offset: int = 0) -> dict:
    items = store.list_models()
    if q:
        ql = q.lower()
        items = [m for m in items if (m.name or "").lower().find(ql) >= 0 or (m.city or "").lower().find(ql) >= 0]
    total = len(items)
    window = items[offset : offset + limit]
    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "results": [_public(m) for m in window],
    }


def get_property(model_id: str) -> dict | None:
    m = store.load_model(model_id)
    return _public(m) if m else None
