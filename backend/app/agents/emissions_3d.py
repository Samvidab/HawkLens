"""Emissions in 3D (EMISSIONS_3D, default off): where a building's CO2 comes from, shown where observed.

Per building, two files (new; no frozen file is changed):
- tour.json: the building's Matterport model, its visibility from the Matterport `basics` query
  and the Showcase link when the tour is viewable (public/unlisted); otherwise "unknown"/None.
- emissions_breakdown.json: the engine's baseline tonnes/yr x a cited end-use split for Houston
  offices. The top 3 end uses, each with tonnes/yr and % of the building total (both marked
  "estimate", with their basis), the citation, the verified claims that link the end use to THIS
  building, and 3D positions (interior pins and labelled rooms where that equipment was seen).
  No verified evidence or no position → "unknown", never guessed. Every breakdown is labelled
  LABEL: the split is building-wide, the positions only show where its equipment was observed.

Numbers: tonnes = baseline x share (rounded), % = share x 100. Nothing else is computed.
The split comes from a source file the owner of the data provides (`source_path()`); until it
exists, build() refuses and only the tour part runs.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.adapters import matterport as mp
from app.adapters.cache import write_json_atomic
from app.agents import records, store

LABEL = "building-wide estimate, shown where observed"
UNKNOWN = "unknown"
TOP_N = 3
POSITION_NOTE = "scan position of a panorama in which it was seen (not the equipment's exact location)"
ROOM_POSITION_NOTE = "centre of the panoramas captured in a room labelled as this kind of space"


def enabled() -> bool:
    return os.getenv("EMISSIONS_3D", "false").strip().lower() in ("1", "true", "yes", "on")


def source_path() -> Path:
    """The cited end-use split (not in the repo until provided)."""
    return Path(os.getenv("EMISSIONS_SPLIT_PATH") or Path(__file__).parent / "sources" / "houston_office_end_use.json")


# --------------------------------------------------------------------------- the cited split

# Canonical end uses → which observed evidence can link them to a building. Only these are linked;
# any other end use in the source gets evidence/positions "unknown".
EVIDENCE = {
    "lighting": {"claims": ["interior.lighting"], "rooms": []},
    "cooling": {"claims": ["interior.hvac"], "rooms": []},
    "heating": {"claims": ["interior.hvac"], "rooms": []},
    "ventilation": {"claims": ["interior.hvac"], "rooms": []},
    "office_equipment": {"claims": [], "rooms": ["open_office", "private_office", "conference"]},
    "computing": {"claims": [], "rooms": ["mechanical_it"]},
    "refrigeration": {"claims": [], "rooms": ["kitchen_break"]},
    "cooking": {"claims": [], "rooms": ["kitchen_break"]},
    "water_heating": {"claims": [], "rooms": ["kitchen_break", "restroom"]},
    "other": {"claims": [], "rooms": []},
}


class EndUse(BaseModel):
    model_config = ConfigDict(extra="allow")  # research provenance: column, value_text, quote, verified
    name: str  # as the source names it, e.g. "Space cooling"
    category: str  # one of EVIDENCE
    share: float = Field(ge=0, le=1)  # share of the building's energy CO2, from the source

    @field_validator("category")
    @classmethod
    def _known(cls, v: str) -> str:
        if v not in EVIDENCE:
            raise ValueError(f"category must be one of {sorted(EVIDENCE)}")
        return v


class Split(BaseModel):
    model_config = ConfigDict(extra="allow")  # research provenance: table, row, quotes, verification
    citation: str
    url: str | None = None
    scope: str  # e.g. "Houston offices" / "CBECS West South Central, office"
    basis: str  # what the share measures, e.g. "share of site electricity"
    end_uses: list[EndUse]

    @field_validator("end_uses")
    @classmethod
    def _sums(cls, v: list[EndUse]) -> list[EndUse]:
        if not v:
            raise ValueError("end_uses is empty")
        if sum(e.share for e in v) > 1.0001:
            raise ValueError("shares add up to more than 1")
        return v


def load_split(path: Path | None = None) -> Split:
    p = path or source_path()
    if not p.exists():
        raise FileNotFoundError(f"end-use split source not provided yet ({p})")
    split = Split.model_validate_json(p.read_text())
    status = (getattr(split, "verification", None) or {}).get("status")
    unverified = [e.name for e in split.end_uses if getattr(e, "verified", None) is False]
    if status is not None and (status != "verified" or unverified):
        raise ValueError(f"end-use split is not verified (status {status}; unverified {unverified})")
    return split


# --------------------------------------------------------------------------- tour (part 1)

def tour_model(building_id: str) -> str | None:
    """The scan the survey inspected (interior.json), else the portfolio's linked model."""
    d = store.building_dir(building_id)
    inter = d / "interior.json"
    if inter.exists() and (mid := json.loads(inter.read_text()).get("model_id")):
        return mid
    entry = records.portfolio_entry(building_id) or {}
    return entry.get("matterport_model_id") or next(iter(entry.get("matterport_model_ids") or []), None)


async def tour_status(building_id: str) -> dict:
    mid = tour_model(building_id)
    if not mid:
        return {"building_id": building_id, "model_id": None, "visibility": UNKNOWN, "available": False,
                "showcase_url": None, "basis": "no Matterport model linked in CoStar"}
    try:
        vis = (await mp.basics(mid)).get("visibility") or UNKNOWN
    except Exception as e:  # noqa: BLE001 - recorded, not guessed
        return {"building_id": building_id, "model_id": mid, "visibility": UNKNOWN, "available": False,
                "showcase_url": None, "basis": f"Matterport basics query failed ({type(e).__name__})"}
    ok = vis in ("public", "unlisted")
    return {"building_id": building_id, "model_id": mid, "visibility": vis, "available": ok,
            "showcase_url": records.SHOWCASE.format(model_id=mid) if ok else None,
            "basis": "Matterport GraphQL basics query: model.visibility"}


async def save_tour(building_id: str) -> dict:
    t = await tour_status(building_id)
    write_json_atomic(store.building_dir(building_id) / "tour.json", t)
    return t


# --------------------------------------------------------------------------- breakdown (part 2)

def _read(path: Path, default: Any) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def evidence_for(building_id: str, category: str) -> tuple[list[dict] | str, list[dict] | str]:
    """Verified claims and positions linking an end use to this building, or 'unknown'."""
    d = store.building_dir(building_id)
    claims = {c["claim_id"]: c for c in _read(d / "verification.json", [])}
    inter = _read(d / "interior.json", {}) or {}
    rule = EVIDENCE[category]
    ev, pos = [], []
    for field in rule["claims"]:
        cid = f"{building_id}.{field}"
        c = claims.get(cid)
        if c and c["status"] == "verified" and c["value"] not in (UNKNOWN, None, ""):
            ev.append({"claim_id": cid, "value": c["value"], "status": "verified", "evidence_ids": c["evidence_ids"]})
            for p in inter.get("pins") or []:
                if p["claim_id"] == cid and p["status"] == "verified":
                    pos.append({"xyz": p["xyz"], "label": p["label"], "claim_id": cid, "kind": "pin",
                                "note": POSITION_NOTE})
    for r in inter.get("rooms") or []:
        kinds = {r["type"], *(r.get("also_contains") or [])}
        if r.get("status") == "verified" and kinds & set(rule["rooms"]):
            ev.append({"claim_id": r["claim_id"], "value": r["type"], "status": "verified",
                       "also_contains": r.get("also_contains") or [], "evidence_note": r.get("evidence_note")})
            if r.get("xyz"):
                pos.append({"xyz": r["xyz"], "label": r["type"].replace("_", " "), "claim_id": r["claim_id"],
                            "kind": "room", "note": ROOM_POSITION_NOTE})
    return (ev or UNKNOWN), (pos or UNKNOWN)


def build(building_id: str, baseline_tonnes: float | None, split: Split, tour: dict | None = None) -> dict:
    """The breakdown for one building. Pure: every number is baseline x share or share x 100."""
    top = sorted(split.end_uses, key=lambda e: (-e.share, e.name))[:TOP_N]
    cite = {"citation": split.citation, "url": split.url, "scope": split.scope, "basis": split.basis,
            **{k: getattr(split, k) for k in ("table", "row", "measures") if getattr(split, k, None)}}
    rows = []
    for e in top:
        ev, pos = evidence_for(building_id, e.category)
        tonnes = UNKNOWN if baseline_tonnes is None else round(baseline_tonnes * e.share, 1)
        rows.append({
            "end_use": e.name, "category": e.category,
            "tonnes_per_year": {"value": tonnes, "estimate": True,
                                "basis": f"engine baseline tonnes/yr x share {e.share:.4f} ({split.citation})"
                                if tonnes != UNKNOWN else "engine baseline unknown"},
            "pct_of_building": {"value": round(e.share * 100, 1), "estimate": True,
                                "basis": f"{split.scope} end-use share, {split.basis} ({split.citation})"},
            "citation": {**cite, "column": getattr(e, "column", e.name), "value_text": getattr(e, "value_text", None),
                         "quote": getattr(e, "quote", None)},
            "evidence": ev, "positions": pos,
        })
    return {"building_id": building_id, "label": LABEL,
            "baseline": {"tonnes_per_year": baseline_tonnes if baseline_tonnes is not None else UNKNOWN,
                         "basis": "quant engine baseline(building_id)"},
            "source": cite, "tour": tour or _read(store.building_dir(building_id) / "tour.json", None),
            "top": rows}


def write(building_id: str, baseline_tonnes: float | None, split: Split) -> dict:
    out = build(building_id, baseline_tonnes, split)
    write_json_atomic(store.building_dir(building_id) / "emissions_breakdown.json", out)
    return out


def load(building_id: str) -> dict | None:
    """emissions_3d for a building (for the widget/API layer), or None when off or not built."""
    if not enabled():
        return None
    return _read(store.building_dir(building_id) / "emissions_breakdown.json", None)
