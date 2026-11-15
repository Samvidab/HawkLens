"""Emissions in 3D for every portfolio building (EMISSIONS_3D).

    python scripts/build_emissions_3d.py --tours     # part 1: tour.json (Matterport visibility)
    python scripts/build_emissions_3d.py --research  # find + verify the end-use split (Gemini + EIA PDF)
    python scripts/build_emissions_3d.py             # part 2: emissions_breakdown.json (needs the source)

Writes only new files (tour.json, emissions_breakdown.json); never profile/plan/cache entries that
exist. Run with CACHE_MODE=read_only to stay on cached Matterport answers.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from app.agents import emissions_3d, records  # noqa: E402
from app.integrations import engine_client  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tours", action="store_true", help="only part 1 (tour availability)")
    ap.add_argument("--research", action="store_true", help="research and verify the end-use split, then stop")
    args = ap.parse_args()
    if args.research:
        from app.agents import end_use_research
        from app.events import load_events
        split = await end_use_research.research()
        for e in load_events(end_use_research.RUN_ID):
            print(f"{e.agent} · {e.kind}: {e.message}")
        print(json.dumps({k: split[k] for k in ("citation", "url", "table", "row", "scope", "measures")}, indent=1))
        return 0
    ids = [b["building_id"] for b in records.load_portfolio()["buildings"]]
    tours = {b: await emissions_3d.save_tour(b) for b in ids}
    if args.tours:
        print(json.dumps(tours, indent=1))
        return 0
    split = emissions_3d.load_split()
    for b in ids:
        base = engine_client.baseline(b).get("tonnes_per_year")
        out = emissions_3d.write(b, base, split)
        print(b, [(r["end_use"], r["tonnes_per_year"]["value"], r["pct_of_building"]["value"],
                   "positions" if r["positions"] != "unknown" else "unknown") for r in out["top"]])
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
