"""T1.1: pick the demo portfolio from the CoStar kit and write data/portfolio.json.

Selection (deterministic):
  - demo city's research market, Office, Existing, named, 100k–600k sf RBA, 2–20 stories
    (big enough to matter, low enough that the roof is a real share of the building)
  - has year built, ≥1 Matterport model, ≥1 CoStar aerial attachment
  - rank by imagery (aerial attachments + Matterport models), then greedily keep buildings
    ≥ MIN_SPACING_M apart so the 3D view and imagery don't overlap
  - hero = most Matterport models among the picks (override with --hero)

Vexcel coverage is NOT checked yet (no Vexcel access, see adapters/README.md); each building
carries coverage.vexcel = "unchecked" until vexcel.py exists.

Usage: python scripts/pick_portfolio.py [--n 8] [--hero PROPERTY_ID] [--ids ID ID ...] [--dry-run]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters import costar  # noqa: E402
from app.config import get_settings  # noqa: E402

MIN_RBA, MAX_RBA = 100_000, 600_000
MIN_STORIES, MAX_STORIES = 2, 20
MIN_SPACING_M = 500


def haversine_m(a: dict, b: dict) -> float:
    r = 6_371_000
    p1, p2 = math.radians(a["lat"]), math.radians(b["lat"])
    dp, dl = p2 - p1, math.radians(b["lon"] - a["lon"])
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def eligible(h: dict) -> bool:
    return bool(
        h["name"] and h["lat"] is not None and h["lon"] is not None and h["year_built"]
        and h["matterport_model_ids"] and h["aerial_attachments"]
        and MIN_RBA <= (h["rba_sqft"] or 0) <= MAX_RBA
        and MIN_STORIES <= (h["stories"] or 0) <= MAX_STORIES
    )


def pick(cands: list[dict], n: int) -> list[dict]:
    ranked = sorted(cands, key=lambda h: (-(h["aerial_attachments"] + len(h["matterport_model_ids"])),
                                          -h["rba_sqft"], h["property_id"]))
    chosen: list[dict] = []
    for h in ranked:
        if all(haversine_m(h, c) >= MIN_SPACING_M for c in chosen):
            chosen.append(h)
        if len(chosen) == n:
            break
    return chosen


def entry(h: dict, hero_id: int, city: str) -> dict:
    return {
        "building_id": str(h["property_id"]),
        "costar_id": str(h["property_id"]),
        "name": h["name"],
        "address": h["address"],
        "city": city,
        "lat": h["lat"],
        "lon": h["lon"],
        "property_type": h["property_type"],
        "building_class": h["building_class"],
        "rba_sqft": h["rba_sqft"],
        "stories": h["stories"],
        "year_built": h["year_built"],
        "matterport_model_ids": h["matterport_model_ids"],
        "matterport_model_id": h["matterport_model_ids"][0] if h["matterport_model_ids"] else None,
        "hero": h["property_id"] == hero_id,
        "coverage": {"costar_aerial_photos": h["aerial_attachments"], "vexcel": "unchecked"},
    }


async def best_unlocked_model(model_ids: list[str]) -> dict | None:
    """Hero's model for interior work: MatterPak unlocked, then most panos, then most rooms."""
    from app.adapters import matterport

    best = None
    for mid in model_ids:
        ref = await matterport.model_ref(mid)
        if ref.matterpak != "unlocked":
            continue
        if best is None or (ref.panos, ref.rooms) > (best.panos, best.rooms):
            best = ref
    if best is None:
        print("WARNING: hero has no model with an unlocked MatterPak; pick another hero", file=sys.stderr)
        return None
    return {"model_id": best.model_id, "name": best.name, "panos": best.panos, "rooms": best.rooms,
            "matterpak": best.matterpak}


async def check_vexcel(buildings: list[dict], city: str) -> None:
    """Fetch (and cache) each building's overhead ortho; record coverage."""
    from app.adapters import geometry, vexcel

    for b in buildings:
        try:
            await vexcel.overhead(geometry.point_wkt(b["lat"], b["lon"]),
                                  vexcel.overhead_buffer_m(b["rba_sqft"], b["stories"]), city=city)
            b["coverage"]["vexcel"] = "overhead"
        except Exception as e:  # noqa: BLE001 - record and continue
            b["coverage"]["vexcel"] = f"none ({type(e).__name__})"


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--hero", type=int)
    ap.add_argument("--ids", type=int, nargs="*", help="use exactly these PropertyIds")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--offline", action="store_true", help="skip the Matterport hero-model check")
    args = ap.parse_args()
    if not 6 <= (len(args.ids) if args.ids else args.n) <= 10:
        ap.error("portfolio must have 6–10 buildings")

    s = get_settings()
    city = s.demo_city
    hits = await costar.search_properties(city, property_types=["Office"], min_sqft=MIN_RBA, limit=1000)
    if args.ids:
        by_id = {h["property_id"]: h for h in hits}
        missing = [i for i in args.ids if i not in by_id]
        if missing:
            ap.error(f"not found among {city} offices: {missing}")
        chosen = [by_id[i] for i in args.ids]
    else:
        chosen = pick([h for h in hits if eligible(h)], args.n)
    if len(chosen) < 6:
        print(f"only {len(chosen)} eligible buildings", file=sys.stderr)
        return 1

    hero_id = args.hero or max(chosen, key=lambda h: (len(h["matterport_model_ids"]), h["aerial_attachments"]))["property_id"]
    if hero_id not in {h["property_id"] for h in chosen}:
        ap.error(f"hero {hero_id} is not in the portfolio")

    hero_model = None if args.offline else await best_unlocked_model(
        next(h for h in chosen if h["property_id"] == hero_id)["matterport_model_ids"])

    doc = {
        "city": city,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "selection": {
            "property_type": "Office", "rba_sqft": [MIN_RBA, MAX_RBA], "stories": [MIN_STORIES, MAX_STORIES],
            "min_spacing_m": MIN_SPACING_M, "requires": ["year_built", "matterport_model", "costar_aerial_photo"],
            "vexcel_coverage": "overhead ortho fetched per building (obliques not yet available)",
        },
        "buildings": [entry(h, hero_id, city) for h in chosen],
    }
    if not args.offline:
        await check_vexcel(doc["buildings"], city)
    if hero_model:
        hb = next(b for b in doc["buildings"] if b["hero"])
        hb["matterport_model_id"] = hero_model["model_id"]
        hb["hero_model"] = hero_model

    for b in doc["buildings"]:
        print(f"{'★' if b['hero'] else ' '} {b['building_id']:>8}  {b['name'][:30]:30} {b['rba_sqft']:>9,.0f} sf "
              f"{b['stories']:>2} st  {b['year_built']}  class {b['building_class']}  "
              f"mp {len(b['matterport_model_ids'])}  aerial {b['coverage']['costar_aerial_photos']}")
    if args.dry_run:
        return 0

    out = s.data_dir / "portfolio.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=out.parent, prefix=".tmp-")
    with os.fdopen(fd, "w") as f:
        json.dump(doc, f, indent=2)
    os.replace(tmp, out)
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
