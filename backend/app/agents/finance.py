"""Finance agent (T3.4): writes to Nessie only after an `approve` action carrying the current plan_id.

Steps: create "Retrofit Reserve" account -> transfer the plan's upfront cost into it -> one bill per
contractor type. One `act` event per call with the returned ID. Idempotent by plan_id: progress is
persisted after every call to data/finance/<plan_id>.json, so a repeat approve returns the stored
result and a retry after a mid-way failure resumes without double-booking.
"""
from __future__ import annotations

import asyncio
import re

from app import events
from app.agents.llm import _env
from app.config import get_settings
from app.integrations import nessie_client as nessie
from app.storage import data_path, read_json, write_json
from app.widgets.resolver import CONTRACTOR

RESERVE_NICKNAME = "Hawk Lens Retrofit Reserve"  # the reserve account the Nessie teammate already seeded (get-or-create)
STUB_CUSTOMER, STUB_SOURCE = "demo-customer", "demo-operating-account"


class ApprovalError(Exception):
    """approve rejected: no plan, plan_id mismatch, or the plan has nothing to finance."""


def _ids() -> tuple[str, str]:
    """(customer_id, source account id) from NESSIE_CUSTOMER_ID / NESSIE_SOURCE_ACCOUNT_ID.
    Stub mode always uses fixed ids, so stub output (tests, samples) never depends on a machine's .env."""
    if get_settings().nessie_mode == "stub":
        return STUB_CUSTOMER, STUB_SOURCE
    cust, src = _env("NESSIE_CUSTOMER_ID"), _env("NESSIE_SOURCE_ACCOUNT_ID")
    if not (cust and src):
        raise ApprovalError("NESSIE_CUSTOMER_ID and NESSIE_SOURCE_ACCOUNT_ID must be set for live Nessie")
    return cust, src


def plan_bills(plan: dict) -> list[dict]:
    """One bill per contractor type: sum of the selected upgrades' upfront cost (from the engine)."""
    types = {u["upgrade_id"]: u["type"]
             for d in data_path("buildings").glob("*") if d.is_dir()
             for u in read_json(d / "feasibility.json", [])}
    acc: dict[str, float] = {}
    for uid in plan.get("selected", []):
        up = plan.get("simulate", {}).get(uid, {}).get("upfront_usd")
        if uid not in types or up is None:
            raise ApprovalError(f"no upfront cost for {uid}; cannot bill")
        c = CONTRACTOR[types[uid]]
        acc[c] = acc.get(c, 0.0) + up
    return [{"contractor": c, "amount": round(a, 2)} for c, a in sorted(acc.items())]


def _short(i: str) -> str:
    return "…" + i[-4:]


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def result_path(plan_id: str):
    return data_path("finance", f"{plan_id}.json")


async def run_finance(run_id: str, plan_id: str | None) -> dict:
    """Execute (or return the stored result of) the financing for `plan_id`."""
    plan = read_json(data_path("plans", "current.json"))
    if not plan or not plan.get("plan_id"):
        raise ApprovalError("no current plan to approve")
    if plan_id != plan["plan_id"]:
        raise ApprovalError(f"plan_id {plan_id!r} is not the current plan {plan['plan_id']!r}")
    if not plan.get("selected"):
        raise ApprovalError("plan has no upgrades to finance")

    done = read_json(result_path(plan_id), {})
    if done.get("state") == "executed":
        if plan.get("financing", {}).get("state") != "executed":
            _publish(plan, done)  # e.g. plan re-priced to the same id after approval
        return done  # idempotent: second approve books nothing
    bills = plan_bills(plan)
    total = plan.get("total_upfront")
    if total is None or total <= 0:
        raise ApprovalError("plan has no upfront cost")
    customer, source = _ids()
    st = {"plan_id": plan_id, "state": "proposed", "account_id": None, "transfer_id": None,
          "bills": [{**b, "bill_id": None} for b in bills], **done}

    def save() -> None:
        write_json(result_path(plan_id), st)

    try:
        if not st["account_id"]:
            st["account_id"] = await asyncio.to_thread(nessie.create_account, customer, RESERVE_NICKNAME)
            save()
            events.emit(run_id, "Finance", "act", f"opened {RESERVE_NICKNAME} (acct {_short(st['account_id'])})")
        if not st["transfer_id"]:
            st["transfer_id"] = await asyncio.to_thread(
                nessie.transfer, source, st["account_id"], round(total, 2), f"Upfront for plan {plan_id}")
            save()
            events.emit(run_id, "Finance", "act", f"transferred ${total:,.0f} upfront (xfer {_short(st['transfer_id'])})")
        for b in st["bills"]:
            if b["bill_id"]:
                continue
            b["bill_id"] = await asyncio.to_thread(
                nessie.create_bill, st["account_id"], b["contractor"], b["amount"],  # live: the bill's payee, a readable name

                f"{b['contractor']} for plan {plan_id}")
            save()
            events.emit(run_id, "Finance", "act", f"billed {b['contractor']} ${b['amount']:,.0f} (bill {_short(b['bill_id'])})")
    except Exception as e:  # noqa: BLE001 - progress is already saved; a retry resumes
        events.emit(run_id, "Finance", "error", f"finance stopped: {str(e)[:60]}")
        raise
    st["state"] = "executed"
    save()
    _publish(plan, st)
    return st


def _publish(plan: dict, st: dict) -> None:
    """Expose the result to the resolver/financing_card via plans/current.json."""
    nessie_ids = {"account": st["account_id"], "transfer": st["transfer_id"],
                  **{f"bill: {b['contractor']}": b["bill_id"] for b in st["bills"]}}
    plan = {**plan, "bills": [{"contractor": b["contractor"], "amount": b["amount"]} for b in st["bills"]],
            "financing": {"state": st["state"], "nessie_ids": nessie_ids}}
    write_json(data_path("plans", "current.json"), plan)
    write_json(data_path("plans", f"{plan['plan_id']}.json"), plan)
