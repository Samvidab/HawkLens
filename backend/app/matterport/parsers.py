"""Parse raw Matterport GraphQL responses into Pydantic models.

Search results and full-model results carry overlapping-but-different fields, so we
merge them: the search gives name/address/thumbnail/published; the full model(id)
query adds the Showcase embed + show URL. `raw` keeps the full source for traceability.
"""
from __future__ import annotations

from app.matterport.models import MpAddress, MpGeo, MpModel


def parse_search_result(r: dict) -> MpModel:
    """Parse one entry from models.results[] into an MpModel (no embed yet)."""
    pub = r.get("publication") or {}
    return MpModel(
        id=r["id"],
        name=r.get("name"),
        created=r.get("created"),
        modified=r.get("modified"),
        address=MpAddress.from_api(r.get("address")),
        geo=MpGeo.from_api(r.get("geolocation")),
        thumbnail_url=(r.get("image") or {}).get("url"),
        published=bool(pub.get("published")),
        raw={"search": r},
    )


def merge_model_detail(model: MpModel, detail: dict) -> MpModel:
    """Overlay full model(id) fields (embed, show URL, better thumbnail) onto a model."""
    pub = detail.get("publication") or {}
    geo = detail.get("geocoordinates") or {}
    thumb = (detail.get("image") or {}).get("url") or model.thumbnail_url
    merged_geo = model.geo
    if geo.get("latitude") is not None or geo.get("longitude") is not None:
        merged_geo = MpGeo(lat=geo.get("latitude"), lon=geo.get("longitude"))
    raw = dict(model.raw)
    raw["model"] = detail
    return model.model_copy(
        update={
            "name": detail.get("name") or model.name,
            "created": detail.get("created") or model.created,
            "modified": detail.get("modified") or model.modified,
            "address": MpAddress.from_api(detail.get("address")) if detail.get("address") else model.address,
            "geo": merged_geo,
            "thumbnail_url": thumb,
            "embed_html": pub.get("embed"),
            "show_url": pub.get("url"),
            "published": bool(pub.get("published")) or model.published,
            "raw": raw,
        }
    )
