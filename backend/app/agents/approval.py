"""Approval rules for a plan: one place, used by GET /plan (to show the owner why the button is off) and by
the finance agent (to refuse the approve action). The frontend's button state is advisory; this is the gate.

A plan can be funded only when every one of these holds:
  - it was priced (status is not "no_data") and the optimizer met the target (status "ok")
  - it selects at least one upgrade, with a positive upfront cost
  - it was priced by the live engine, not the stub's sample pricing
  - every requested building was surveyed (or explicitly excluded by the owner) and has a baseline
  - the selected line items' upfront costs add up to total_upfront
  - total_upfront is within the owner's budget, if one is set
Warnings do not block: a chance of hitting the target below min_p_hit, owner-included unverified upgrades.
"""
from __future__ import annotations

BUDGET_TOLERANCE_USD = 0.01


def check(plan: dict | None) -> dict:
    """{approvable, reasons: [str], warnings: [str]} for `plan` (current.json)."""
    if not plan or not plan.get("plan_id"):
        return {"approvable": False, "reasons": ["there is no plan yet; run the survey"], "warnings": []}
    reasons: list[str] = []
    warnings: list[str] = []
    status = plan.get("status")
    if status == "no_data":
        reasons.append(f"the plan was not priced: {plan.get('reason') or 'no survey data'}")
    elif status == "infeasible":
        short = plan.get("shortfall_tonnes")
        reasons.append("the plan does not reach the carbon target"
                       + (f" ({short:,.0f} t/yr short)" if isinstance(short, (int, float)) else ""))
    elif status != "ok":
        reasons.append(f"unknown plan status {status!r}")

    if status != "no_data":
        if not plan.get("selected"):
            reasons.append("the plan has no upgrades to fund")
        total = plan.get("total_upfront")
        if not isinstance(total, (int, float)) or total <= 0:
            reasons.append("the plan has no upfront cost")
        if plan.get("stub"):
            reasons.append("the plan uses sample (stub) pricing, not the quant engine")
        if plan.get("reconciles") is not True:
            reasons.append("the upgrade costs do not add up to the total investment")
        budget = (plan.get("goal") or {}).get("budget_usd")
        if isinstance(budget, (int, float)) and isinstance(total, (int, float)) and total > budget + BUDGET_TOLERANCE_USD:
            reasons.append("the investment is over your budget")

    cov = plan.get("coverage") or {}
    if cov.get("not_surveyed"):
        n = len(cov["not_surveyed"])
        reasons.append(f"{n} building{'s' if n != 1 else ''} not surveyed; survey or exclude {'them' if n != 1 else 'it'}")
    if cov.get("baseline_missing"):
        n = len(cov["baseline_missing"])
        reasons.append(f"{n} building{'s' if n != 1 else ''} without a CO2 baseline")

    p_hit, min_p = plan.get("p_hit_target"), plan.get("min_p_hit")
    if status == "ok" and isinstance(p_hit, (int, float)) and isinstance(min_p, (int, float)) and p_hit < min_p:
        warnings.append(f"the plan hits the target in {p_hit:.0%} of scenarios (aim: {min_p:.0%})")
    unverified = [r["upgrade_id"] for r in plan.get("line_items", []) if r.get("verified") == "unverified"]
    if unverified:
        warnings.append(f"{len(unverified)} owner-included upgrade{'s' if len(unverified) != 1 else ''} not verified")
    return {"approvable": not reasons, "reasons": reasons, "warnings": warnings}
