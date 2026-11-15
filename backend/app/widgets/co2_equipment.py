"""Verified CO2-emitting equipment inside a building, for the 3D tour tags (GET /co2_equipment/{building_id}).

Only what the survey agents saw AND the verifier confirmed, nothing computed:
- lighting: interior pins of the verified `interior.lighting` claim (the fixture, with its type),
- ventilation / HVAC: interior pins of the verified `interior.hvac` claim that show an air diffuser / vent / grille.
A pin or claim that is rejected, unverified or "unknown" gives no item. Each item carries the claim, the verifier's result
and the panorama in which it was seen: the scan position whose coordinates equal the pin's (exact match, from the
Matterport panorama list), with the claim's evidence image from that panorama. No match -> panorama null ("not available").
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.adapters import matterport as mp
from app.agents import store

KINDS = {"interior.lighting": "lighting", "interior.hvac": "hvac"}
AIR_TERMINAL = re.compile(r"diffuser|vent|grille|register", re.I)  # "verified air diffusers" (not ducts, not thermostats)
UNKNOWN = {None, "", "unknown"}


def _read(path: Path, default: Any) -> Any:
    return json.loads(path.read_text()) if path.exists() else default


def _same(a, b) -> bool:
    return len(a) == 3 and len(b) == 3 and all(abs(float(x) - float(y)) < 1e-6 for x, y in zip(a, b))


def select(interior: dict, claims: dict[str, dict]) -> list[dict]:
    """Pure: the verified lighting / air-terminal pins with their claim (no panorama yet)."""
    out = []
    for pin in interior.get("pins") or []:
        cid = pin.get("claim_id", "")
        field = ".".join(cid.split(".")[1:])
        kind = KINDS.get(field)
        claim = claims.get(cid)
        if not kind or not claim or pin.get("status") != "verified" or claim.get("status") != "verified":
            continue
        if claim.get("value") in UNKNOWN or not pin.get("xyz"):
            continue
        label = str(pin.get("label") or "").strip()
        if not label or (kind == "hvac" and not AIR_TERMINAL.search(label)):
            continue
        value = str(claim["value"])
        if kind == "lighting" and value.replace("_", " ").lower() not in label.lower():
            label = f"{label} ({value.replace('_', ' ')})"  # the fixture type, from the verified claim
        out.append({"kind": kind, "equipment": label, "xyz": list(pin["xyz"]),
                    "claim": {"claim_id": cid, "field": field, "value": claim["value"], "confidence": claim.get("confidence"),
                              "evidence_ids": claim.get("evidence_ids") or []},
                    "verifier": {"status": claim["status"], "note": claim.get("verifier_note")}})
    return out


async def build(building_id: str) -> dict:
    d = store.building_dir(building_id)
    interior = _read(d / "interior.json", None) or {}
    model = interior.get("model_id")
    claims = {c["claim_id"]: c for c in _read(d / "claims.json", []) if isinstance(c, dict) and c.get("claim_id")}
    items = select(interior, claims) if model else []
    panos = []
    if items:
        try:
            panos = await mp.panoramas(model)
        except Exception:  # noqa: BLE001 - no panorama list: panorama "not available", never guessed
            panos = []
    for it in items:
        pano = next((p for p in panos if _same(p.xyz, it["xyz"])), None)
        image = next((e for e in it["claim"]["evidence_ids"] if pano and f"_{pano.pano_id}_" in e), None)
        it["pano_id"] = pano.pano_id if pano else None
        it["image_id"] = image
        it["image_url"] = f"/media/{image}" if image else None
        # Image marks are 2D evidence, not model coordinates. PanoramaRef records no
        # skybox extrinsics, so neither a bounding-box centre nor pin.xyz is a fixture.
        claim = claims[it["claim"]["claim_id"]]
        prefix = f"mpp_{model}_{pano.pano_id}_" if pano else None
        it["image_marks"] = [m for m in claim.get("marks", [])
                             if prefix and m.get("image_id", "").startswith(prefix)
                             and m.get("image_id") in it["claim"]["evidence_ids"]]
        it["placement"] = {"type": "observation", "label": "Photo taken here",
                           "reason": "No calibrated panorama-to-Showcase direction or verified fixture surface position recorded."}
    tour = _read(d / "tour.json", None) or {}
    viewable = bool(tour.get("available") and tour.get("showcase_url"))
    return {
        "building_id": building_id,
        "model_id": model,  # the scan the pins belong to
        "tour_model_id": tour.get("model_id") if viewable else None,
        "tour_url": tour.get("showcase_url") if viewable else None,  # tour.json: Matterport reports it public/unlisted
        "tour_basis": tour.get("basis"),
        # tags are placed only in the tour of the scan the pins were seen in
        "tags_in_tour": viewable and bool(model) and tour.get("model_id") == model,
        "items": items,
    }
