"""Backfill a thin slice of Houston models (thumbnail + Showcase embed) into data/.

Usage (from backend/):
    python -m scripts.mp_backfill_slice [--limit N] [--any]

--limit N : how many models (default 8)
--any     : don't prefer building-like names; take the first published Houston models
"""
from __future__ import annotations

import argparse
import asyncio
import sys

from app.matterport.backfill import backfill_slice
from app.matterport.client import MatterportAuthError


async def _main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--any", action="store_true", help="do not prefer building-like names")
    args = ap.parse_args()

    try:
        models = await backfill_slice(limit=args.limit, prefer_buildings=not args.any)
    except MatterportAuthError as exc:
        print(f"AUTH ERROR: {exc}", file=sys.stderr)
        return 2

    print(f"Stored {len(models)} Houston models to data/matterport/models/:\n")
    for m in models:
        print(f"  {m.id}  {m.name!r}")
        print(f"      city={m.city!r}  thumb={bool(m.thumbnail_url)}  embed={bool(m.embed_html)}  show={m.show_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
