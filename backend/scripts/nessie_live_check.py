"""One real approve against the Nessie SANDBOX (NESSIE_MODE=live), then read the result back from Nessie.

  python scripts/nessie_live_check.py            # dry run: checks config and balance, prints what it WOULD do
  python scripts/nessie_live_check.py --yes      # does it: creates/reuses the reserve account, moves money, creates bills

Needs in backend/.env: NESSIE_API_KEY (the teammate's key from nessie/.env), NESSIE_CUSTOMER_ID, NESSIE_SOURCE_ACCOUNT_ID.
Prices a small synthetic portfolio with the stub engine (budget capped so the plan fits the account), so what is written
to Nessie is: 1 reserve account (reused if it exists), 1 transfer operating -> reserve, 1 bill per contractor type.
Prints every Nessie id it created and re-reads the reserve balance and bills from Nessie to confirm.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT)); sys.path.insert(0, str(ROOT / "scripts"))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--yes", action="store_true", help="really write to the Nessie sandbox")
    ap.add_argument("--max-usd", type=float, default=250_000.0, help="upper bound for the plan's upfront cost (default %(default)s)")
    a = ap.parse_args(argv)

    import make_samples as ms  # synthetic portfolio + temp data dir (sets stub engine/Nessie env; overridden below)
    os.environ["NESSIE_MODE"] = "live"
    from app.config import get_settings
    get_settings.cache_clear()
    from app.envutil import env_value
    from app.integrations import nessie_client as nes
    from app.schemas import OwnerAction

    cust, src = env_value("NESSIE_CUSTOMER_ID"), env_value("NESSIE_SOURCE_ACCOUNT_ID")
    missing = [n for n, v in (("NESSIE_API_KEY", env_value("NESSIE_API_KEY")), ("NESSIE_CUSTOMER_ID", cust), ("NESSIE_SOURCE_ACCOUNT_ID", src)) if not v]
    if missing:
        print("missing in backend/.env:", ", ".join(missing)); return 2
    source = nes._call("get", f"/accounts/{src}")
    balance = float(source["balance"])
    cap = min(a.max_usd, 0.5 * balance)
    print(f"source account '{source.get('nickname')}' balance ${balance:,.2f}; plan capped at ${cap:,.0f} upfront")
    if not a.yes:
        print("dry run: nothing written. Re-run with --yes to create the reserve account, one transfer and one bill per contractor.")
        return 0

    ms.build_world(ms.DATA, issue=False)
    from app.agents import composer, memo, replan
    async def _no_llm(*x, **k): raise RuntimeError("LLM off")
    composer.text_json = _no_llm; memo.text_json = _no_llm  # the check needs no Gemini

    async def go():
        await replan.replan(OwnerAction(run_id="nessie_check", type="goal", payload={**ms.GOAL, "budget_usd": cap}))
        plan = json.loads((ms.DATA / "plans/current.json").read_text())
        if not plan["selected"]:
            raise SystemExit("the capped plan selected nothing; raise --max-usd")
        lay = await replan.replan(OwnerAction(run_id="nessie_check", type="approve", payload={"plan_id": plan["plan_id"]}))
        return plan, lay
    plan, lay = asyncio.run(go())
    fc = next(w for w in lay.widgets if w.type == "financing_card").props
    reserve = fc["nessie_ids"]["account"]
    back = {"reserve_balance_usd": nes._call("get", f"/accounts/{reserve}")["balance"],
            "reserve_bills": [{"id": b["_id"], "payee": b["payee"], "amount": b["payment_amount"]} for b in nes._call("get", f"/accounts/{reserve}/bills")]}
    out = {"plan_id": plan["plan_id"], "total_upfront_usd": plan["total_upfront"], "state": fc["state"], "nessie_ids": fc["nessie_ids"], "read_back": back}
    print(json.dumps(out, indent=2))
    ok = abs(sum(b["amount"] for b in back["reserve_bills"] if b["id"] in fc["nessie_ids"].values()) - plan["total_upfront"]) < 0.06
    print("read-back matches the plan:" , ok)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
