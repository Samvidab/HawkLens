"""Live runs + cache warm-up (CACHE_MODE=read_write), in quota order.

  --probe   one tiny call to GEMINI_MODEL_VISION (uncached); exit 0 if it answers, 2 if the quota is
            spent (QuotaExhausted / 429), 1 on any other error.
  default   phase 1: survey the hero alone (aerial cached → verifier → reinspect → interior), so the
            scarce vision quota goes to the hero's interior + verifier first;
            phase 2: the full POST /run pipeline (survey all → pricing → compose → done); the hero's
            calls are cache hits. Prints and saves a summary (send_backs, claim statuses, interior).

Usage: GEMINI_RPM=4 CACHE_MODE=read_write python scripts/warm_cache.py [--probe]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402

from app.adapters.cache import write_json_atomic  # noqa: E402
from app.agents import graph, llm, records, store  # noqa: E402
from app.events import load_events  # noqa: E402
from app.schemas.goal import Goal, OwnerAction  # noqa: E402


class Pong(BaseModel):
    ok: bool


async def probe() -> int:
    from app.config import get_settings
    model = get_settings().gemini_model_vision
    try:
        await llm._call_with_retries(model, 'Reply with {"ok": true}.', [], Pong)
        print(f"gemini {model}: OK")
        return 0
    except llm.QuotaExhausted as e:
        print(f"gemini {model}: quota spent ({e})")
        return 2
    except Exception as e:  # noqa: BLE001
        code = getattr(e, "code", None)
        print(f"gemini {model}: error {type(e).__name__} {code}: {str(e)[:200]}")
        return 2 if code == 429 else 1


def summarize(run_id: str) -> dict:
    ev = load_events(run_id)
    out = {"run_id": run_id,
           "send_backs": [f"{e.building_name}: {e.message}" for e in ev if e.kind == "send_back"],
           "rechecks": [f"{e.building_name}: {e.message}" for e in ev if e.message.startswith("re-check")],
           "errors": [f"{e.agent} · {e.building_name}: {e.message}" for e in ev if e.kind == "error"],
           "done": next((e.message for e in ev if e.kind == "done"), None),
           "buildings": {}}
    for b in records.load_portfolio()["buildings"]:
        d = store.building_dir(b["building_id"])
        claims = json.loads((d / "claims.json").read_text()) if (d / "claims.json").exists() else []
        st: dict[str, int] = {}
        for c in claims:
            st[c["status"]] = st.get(c["status"], 0) + 1
        out["buildings"][b["building_id"]] = {"name": b["name"], "claims": st,
                                              "interior": (d / "interior.json").exists()}
    return out


async def warm() -> int:
    from app.agents.replan import replan

    port = records.load_portfolio()["buildings"]
    hero = next(b["building_id"] for b in port if b.get("hero"))
    city = records.load_portfolio().get("city", "Houston")

    print(f"phase 1: hero {hero}")
    await graph.run(Goal(city=city, target_pct=40, building_ids=[hero]), "warm_hero")

    print("phase 2: full pipeline")
    run_id = "warm_full"
    goal = Goal(city=city, target_pct=40)

    async def compose() -> None:
        await replan(OwnerAction(run_id=run_id, type="goal", payload=goal.model_dump(mode="json")))

    await graph.run_full(goal, run_id, compose)
    summary = {"hero_run": summarize("warm_hero"), "full_run": summarize(run_id)}
    write_json_atomic(store.run_dir(run_id) / "warm_summary.json", summary)
    print(json.dumps(summary, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--probe", action="store_true")
    args = ap.parse_args()
    return asyncio.run(probe() if args.probe else warm())


if __name__ == "__main__":
    sys.exit(main())
