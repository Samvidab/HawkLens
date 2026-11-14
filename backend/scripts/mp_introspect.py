"""Run Matterport GraphQL introspection and print a capability report.

Usage (from backend/):
    python -m scripts.mp_introspect

Requires MP_TOKEN_ID / MP_TOKEN_SECRET in backend/.env (or the environment).
Never prints the secret. Writes:
    data/matterport/schema.json
    data/matterport/schema-report.md
"""
from __future__ import annotations

import asyncio
import sys

from app.config import get_settings
from app.matterport.client import MatterportAuthError
from app.matterport.schema import introspect_and_report


async def _main() -> int:
    s = get_settings()
    if not s.mp_token_id or not s.mp_token_secret:
        print(
            "ERROR: MP_TOKEN_ID and MP_TOKEN_SECRET are not set.\n"
            "Copy backend/.env.example to backend/.env and fill them in.",
            file=sys.stderr,
        )
        return 2
    try:
        report, pi_available = await introspect_and_report()
    except MatterportAuthError as exc:
        print(f"AUTH ERROR: {exc}", file=sys.stderr)
        return 2

    print(report)
    print(f"\nSaved: data/matterport/schema.json and data/matterport/schema-report.md")
    print(f"pi_available (heuristic): {pi_available}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
