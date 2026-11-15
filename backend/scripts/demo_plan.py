"""Make the 7-building demo plan (no survey, no investigator): price the surveyed buildings minus 7900 Fannin.

  ENGINE_MODE=live CACHE_MODE=read_write python scripts/demo_plan.py warm_full   # once: writes plan + memo, caches Gemini
  ENGINE_MODE=live CACHE_MODE=read_only  python scripts/demo_plan.py ro_seven    # offline check: same plan, memo, widgets

On run `run_id`: a `goal` action for the 7 buildings at 40% and risk_lambda 0.2 (so 40% is of the 7 buildings'
own baseline), then `exclude_building` 7900 Fannin (so the portfolio view marks it excluded), then the memo.
Writes data/plans/current.json, data/plans/<plan_id>.json, data/memo/<plan_id>.md and the run's state/events.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.agents.memo import write_memo  # noqa: E402
from app.agents.replan import replan  # noqa: E402
from app.schemas.goal import OwnerAction  # noqa: E402
from app.storage import data_path, read_json  # noqa: E402

DROPPED = "6550930"  # 7900 Fannin


async def main(run_id: str) -> None:
    portfolio = read_json(data_path("portfolio.json"))["buildings"]
    ids = [b["building_id"] for b in portfolio if b["building_id"] != DROPPED]
    goal = {"city": "Houston", "building_ids": ids, "target_pct": 40, "risk_lambda": 0.2, "budget_usd": None}
    await replan(OwnerAction(run_id=run_id, type="goal", payload=goal))
    await replan(OwnerAction(run_id=run_id, type="exclude_building", payload={"building_id": DROPPED}))
    plan = read_json(data_path("plans", "current.json"))
    memo = await write_memo(run_id, plan)
    keys = ("plan_id", "status", "tonnes_per_year", "tonnes_needed", "total_upfront", "exp_npv", "cvar5", "p_loss",
            "p_hit_target", "shortfall_tonnes", "excluded_building_ids")
    print(json.dumps({**{k: plan.get(k) for k in keys}, "n_selected": len(plan["selected"]),
                      "memo_sha256": hashlib.sha256(memo.encode()).hexdigest()[:12]}, indent=1))


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1] if len(sys.argv) > 1 else "warm_full"))
