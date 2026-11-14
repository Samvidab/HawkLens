"""CoStar adapter over the local hackathon kit (see adapters/README.md).

The kit has no API: records are JSON Lines at $COSTAR_KIT_DIR/data/commercial-property.jsonl
(193 MB, streamed line by line, never loaded whole) and the Matterport model ids are in
$COSTAR_KIT_DIR/commercial-properties.csv. Every read goes through adapters/cache.py, so the
demo runs with CACHE_MODE=read_only and no kit.
"""
from __future__ import annotations

import csv
import json
import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Literal

from app.adapters.cache import cached
from app.config import BACKEND_DIR

City = Literal["Houston", "Los Angeles"]

# primaryAddress.researchMarketId (kit index.md "Scope")
MARKET_ID: dict[str, int] = {"Houston": 14, "Los Angeles": 20}

# Enums from models/commercial-property.md "Allowed values"
PROPERTY_TYPE: dict[int, str] = {
    0: "Unknown", 1: "Hospitality", 2: "Industrial", 3: "Land", 5: "Office", 6: "GeneralRetail",
    7: "Flex", 8: "SportsAndEntertainment", 9: "MixedUse", 10: "Specialty", 11: "Multifamily",
    13: "Healthcare", 14: "PropertyTypeUnknown", 15: "Residential", 16: "Homes",
}
PROPERTY_TYPE_ID: dict[str, int] = {v: k for k, v in PROPERTY_TYPE.items()}
BUILDING_CLASS: dict[int, str | None] = {0: None, 1: "A", 2: "B", 3: "C", 4: "F"}
CONSTRUCTION_EXISTING = 1
EVENT_CONSTRUCTION_COMPLETE = 2
ATTACHMENT_AERIAL = 1
MATTERPORT_REF_TYPES = {36, 234}  # MatterportScan, MatterportStreamingKey


def kit_dir() -> Path:
    raw = os.environ.get("COSTAR_KIT_DIR")
    if not raw:
        try:
            from dotenv import dotenv_values

            raw = dotenv_values(BACKEND_DIR / ".env").get("COSTAR_KIT_DIR")
        except ImportError:  # pragma: no cover
            raw = None
    return Path(raw or "~/costar-kit").expanduser()


def _jsonl() -> Path:
    return kit_dir() / "data" / "commercial-property.jsonl"


def _iter_records() -> Iterator[dict[str, Any]]:
    with _jsonl().open(encoding="utf-8") as f:
        for line in f:
            if line.strip():
                yield json.loads(line)


def _find_record(property_id: int) -> dict[str, Any]:
    needle = f'"id":{property_id},'
    with _jsonl().open(encoding="utf-8") as f:
        for line in f:
            if needle in line[:40].replace(" ", ""):  # cheap check before parsing ~60 KB
                rec = json.loads(line)
                if rec.get("id") == property_id:
                    return rec
    raise KeyError(f"CoStar property {property_id} not in kit")


def _model_index() -> dict[int, list[str]]:
    out: dict[int, list[str]] = {}
    with (kit_dir() / "commercial-properties.csv").open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            ids = out.setdefault(int(row["PropertyId"]), [])
            if row["MatterportModelId"] and row["MatterportModelId"] not in ids:
                ids.append(row["MatterportModelId"])
    return out


def year_built(rec: dict[str, Any]) -> int | None:
    years = [e["year"] for e in rec.get("constructionEvents") or []
             if e.get("eventType") == EVENT_CONSTRUCTION_COMPLETE and e.get("year")]
    return min(years) if years else None


def matterport_keys(rec: dict[str, Any]) -> list[str]:
    """Matterport model ids on the record's own attachments (index.md 'How the datasets connect')."""
    return sorted({a["videoKey"] for a in rec.get("attachments") or []
                   if a.get("videoExternalReferenceType") in MATTERPORT_REF_TYPES and a.get("videoKey")})


def summarize(rec: dict[str, Any], model_ids: list[str] | None = None) -> dict[str, Any]:
    """Small search-result dict (full records are ~60 KB; don't cache thousands of them)."""
    pa = rec.get("primaryAddress") or {}
    return {
        "property_id": rec["id"],
        "name": rec.get("buildingName"),
        "address": format_address(pa),
        "market_id": pa.get("researchMarketId"),
        "lat": pa.get("latitude"),
        "lon": pa.get("longitude"),
        "property_type": PROPERTY_TYPE.get(rec.get("propertyType"), str(rec.get("propertyType"))),
        "building_class": BUILDING_CLASS.get(rec.get("buildingClass")),
        "rba_sqft": rec.get("rentableBuildingAreaSquareFeet"),
        "stories": rec.get("numStoriesAboveGrade"),
        "year_built": year_built(rec),
        "construction_status": rec.get("constructionStatus"),
        "aerial_attachments": sum(1 for a in rec.get("attachments") or []
                                  if a.get("attachmentType") == ATTACHMENT_AERIAL and a.get("attachmentUri")),
        "matterport_model_ids": model_ids if model_ids is not None else matterport_keys(rec),
    }


def format_address(pa: dict[str, Any]) -> str:
    street = " ".join(str(pa[k]) for k in ("streetNumber", "streetDirection", "streetName", "streetType", "streetSuffix")
                      if pa.get(k))
    tail = ", ".join(x for x in (pa.get("city"), " ".join(filter(None, [pa.get("state"), (pa.get("postcode") or "")[:5]])))
                     if x)
    return ", ".join(x for x in (street, tail) if x)


async def search_properties(
    city: City,
    *,
    property_types: list[str] | None = None,
    min_sqft: int | None = None,
    limit: int = 50,
    existing_only: bool = True,
) -> list[dict]:
    """Properties in the city's research market, largest RBA first. Returns summaries, not full records."""
    market = MARKET_ID[city]
    type_ids = sorted(PROPERTY_TYPE_ID[t] for t in property_types) if property_types else None
    params = {"city": city, "property_types": type_ids, "min_sqft": min_sqft, "limit": limit,
              "existing_only": existing_only}

    def run() -> list[dict]:
        models = _model_index()
        hits = []
        for rec in _iter_records():
            pa = rec.get("primaryAddress") or {}
            if pa.get("researchMarketId") != market:
                continue
            if type_ids and rec.get("propertyType") not in type_ids:
                continue
            if existing_only and rec.get("constructionStatus") != CONSTRUCTION_EXISTING:
                continue
            rba = rec.get("rentableBuildingAreaSquareFeet") or 0
            if min_sqft and rba < min_sqft:
                continue
            hits.append(summarize(rec, models.get(rec["id"], [])))
        hits.sort(key=lambda h: -(h["rba_sqft"] or 0))
        return hits[:limit]

    return await cached("costar.search_properties", params, run)


async def get_property(property_id: str | int) -> dict:
    """Raw CoStar record (records agent maps it to BuildingProfile)."""
    pid = int(property_id)
    return await cached("costar.property", {"property_id": pid}, lambda: _find_record(pid))


async def matterport_model_ids(property_id: str | int) -> list[str]:
    """Matterport model ids for a property, from commercial-properties.csv (kit's join table)."""
    pid = int(property_id)
    return await cached("costar.matterport_models", {"property_id": pid}, lambda: _model_index().get(pid, []))
