"""Add OUR surveyed Matterport scans to THEIR store (data/matterport/models/), so their site lists them.

Their stock backfill (scripts.mp_backfill_slice) takes the first Houston models from Matterport search, which are not our
8 office buildings, so the verified CO2 tags would never match. This script uses THEIR client, parsers and store code
unchanged (it only decides which model ids to store): the ids come from OUR backend (the scans with verified items).

Run from backend/ with their environment (MP_TOKEN_ID / MP_TOKEN_SECRET, DATA_DIR / CACHE_DIR of their store):
    python ../frontend/co2-demo/backfill_our_scans.py [--api http://localhost:8000] [--ids ID1 ID2 ...]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.getcwd())

from app.matterport import store  # noqa: E402
from app.matterport.client import MatterportClient  # noqa: E402
from app.matterport.parsers import merge_model_detail, parse_search_result  # noqa: E402
from app.matterport.queries import MODEL_BY_ID  # noqa: E402


def get(api: str, path: str):
    with urllib.request.urlopen(f"{api}{path}", timeout=30) as r:
        return json.load(r)


def our_scan_ids(api: str) -> list[str]:
    ids = []
    for b in get(api, "/portfolio")["buildings"]:
        d = get(api, f"/co2_equipment/{b['building_id']}")
        if d.get("model_id") and d.get("items"):
            ids.append(d["model_id"])
    return ids


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--api", default="http://localhost:8000", help="OUR backend (GET /portfolio, /co2_equipment)")
    ap.add_argument("--ids", nargs="*", help="model ids to store instead of asking our backend")
    args = ap.parse_args()
    ids = args.ids or our_scan_ids(args.api)
    client = MatterportClient()
    try:
        for mid in ids:
            detail = (await client.graphql(MODEL_BY_ID, {"id": mid}, op_name=f"model_{mid}"))["model"]
            full = merge_model_detail(parse_search_result(detail), detail)
            if full.thumbnail_url:
                try:
                    path = store.save_thumbnail(mid, await client.get_bytes(full.thumbnail_url, op_name=f"thumb_{mid}"))
                    full = full.model_copy(update={"thumbnail_path": str(path)})
                except Exception:  # noqa: BLE001 - keep the record without a thumbnail
                    pass
            store.save_model(full)
            print(f"stored {mid}  {full.name!r}  city={full.city!r}  published={full.published}")
    finally:
        await client.aclose()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
