"""T1.8: survey one building end to end: records → aerial → site engineer.

Writes data/buildings/<id>/{profile,aerial,claims,images,feasibility}.json + aerial_debug.png,
emits activity events to data/runs/<run_id>/events.jsonl, and prints the feasible upgrades JSON.
Every external call is cached, so a second run is fully cached and prints identical JSON
(and works with CACHE_MODE=read_only and no network).

Usage: python scripts/survey_one.py <building_id> [--run-id RUN] [--events]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.adapters.cache import write_json_atomic  # noqa: E402
from app.agents import aerial, records  # noqa: E402
from app.events import emit, load_events  # noqa: E402
from app.rules import feasibility  # noqa: E402
from app.schemas.upgrades import FeasibleUpgrade  # noqa: E402

SIZE_LABEL = {"rooftop_solar": "solar", "cool_roof": "cool roof", "heat_pump": "heat pump",
              "led_retrofit": "LED", "window_upgrade": "windows", "insulation": "insulation"}


def decide_message(ups: list[FeasibleUpgrade]) -> str:
    msg = f"{len(ups)} feasible upgrade{'s' if len(ups) != 1 else ''}"
    solar = next((u for u in ups if u.type == "rooftop_solar"), None)
    if solar:
        msg += f" (solar {solar.size_value:,.0f} kW)"
    return msg


async def survey(building_id: str, run_id: str) -> list[FeasibleUpgrade]:
    profile = await records.run(building_id, run_id)
    findings, claims = await aerial.run(profile, run_id)
    upgrades = feasibility.evaluate(profile, findings, None, claims)
    write_json_atomic(aerial.building_dir(building_id) / "feasibility.json",
                      [u.model_dump(mode="json") for u in upgrades])
    emit(run_id, "Site engineer", "decide", decide_message(upgrades), building_id, building_name=profile.name)
    return upgrades


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("building_id")
    ap.add_argument("--run-id")
    ap.add_argument("--events", action="store_true", help="print this run's activity feed to stderr")
    args = ap.parse_args()
    run_id = args.run_id or f"survey-{args.building_id}"

    upgrades = asyncio.run(survey(args.building_id, run_id))
    if args.events:
        for e in load_events(run_id):
            print(f"{e.agent} · {e.building_name or '-'} · {e.message}", file=sys.stderr)
    print(json.dumps([u.model_dump(mode="json") for u in upgrades], indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
