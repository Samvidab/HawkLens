"""Replan router (T3.1): OwnerAction -> nodes, per TRD §9.

  exclude/include building, toggle_upgrade, include_unverified,
  set_target / set_budget / set_risk   -> pricing (macc + optimize) -> compose
  select_bar, open_building            -> compose only
  approve                              -> finance -> memo -> compose
  goal                                 -> (survey, if some buildings are unsurveyed) -> pricing -> compose

Owner-decision state lives in plans/current.json (excluded_*, owner_included, goal); view state
(focus building, highlighted upgrades) in runs/<run_id>/state.json under "view".
Each action emits an Orchestrator `plan` event, plus the Pricing and Composer events from those nodes
(1-3 per action; `approve` also emits the Finance `act` events and the memo event).
"""
from __future__ import annotations

from typing import Awaitable, Callable

from pydantic import ValidationError

from app import events
from app.agents import composer
from app.agents.composer import View
from app.agents.finance import ApprovalError, run_finance
from app.agents.memo import write_memo
from app.agents.pricing import load_upgrades, requested_ids, run_pricing
from app.schemas.goal import Goal, OwnerAction
from app.schemas.layout import Layout
from app.storage import data_path, read_json

SurveyRunner = Callable[[str, Goal, list[str]], Awaitable[None]]
_survey_runner: SurveyRunner | None = None  # Lane A's graph registers its survey here


def register_survey_runner(fn: SurveyRunner | None) -> None:
    global _survey_runner
    _survey_runner = fn


class ReplanError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def _load_view(run_id: str) -> View:
    return View.model_validate((read_json(data_path("runs", run_id, "state.json"), {}) or {}).get("view", {}))


def _names() -> tuple[dict[str, str], dict]:
    names = {}
    for d in data_path("buildings").glob("*"):
        prof = read_json(d / "profile.json") if d.is_dir() else None
        if prof:
            names[d.name] = prof["name"]
    ups = {u.upgrade_id: u for lst in load_upgrades().values() for u in lst}
    return names, ups


def _require(cond: bool, status: int, msg: str) -> None:
    if not cond:
        raise ReplanError(status, msg)


async def replan(action: OwnerAction) -> Layout:
    """Execute one owner action and return the new layout. Raises ReplanError(status, message)."""
    rid, p = action.run_id, action.payload
    if action.type == "approve":
        return await _approve(action)

    plan = read_json(data_path("plans", "current.json")) or {}
    view = _load_view(rid)
    names, ups = _names()
    excl_b, excl_u = set(plan.get("excluded_building_ids", [])), set(plan.get("excluded_upgrade_ids", []))
    owner_inc = set(plan.get("owner_included", []))
    goal_d = plan.get("goal")

    def bid() -> str:
        b = p.get("building_id")
        _require(b in names, 422, f"unknown building_id {b!r}")
        return b

    def uid() -> str:
        u = p.get("upgrade_id")
        _require(u in ups, 422, f"unknown upgrade_id {u!r}")
        return u

    def need_goal() -> dict:
        _require(bool(goal_d), 409, "no current goal; send a `goal` action first")
        return goal_d

    price = True
    t = action.type
    if t == "goal":
        try:
            goal = Goal.model_validate(p)
        except ValidationError as e:
            raise ReplanError(422, str(e)) from e
        excl_b, excl_u, owner_inc = set(), set(), set()  # a new goal is a fresh run
        view = View()
        # No explicit list means the whole portfolio: survey any portfolio building without results, so a goal sent
        # straight to /compose never prices an empty portfolio.
        wanted = requested_ids(goal)
        have = load_upgrades(wanted)
        tried = (read_json(data_path("runs", rid, "state.json"), {}) or {}).get("results", {})  # this run's survey
        missing = [b for b in wanted if b not in have and b not in tried]
        n = len(wanted)
        events.emit(rid, "Orchestrator", "plan", f"Plan: price {n} buildings at {goal.target_pct:g}% target")
        if missing and _survey_runner is not None:
            await _survey_runner(rid, goal, missing)
        elif missing:
            events.emit(rid, "Orchestrator", "error", f"{len(missing)} buildings not surveyed; pricing the rest")
    elif t in ("set_target", "set_budget", "set_risk"):
        key = {"set_target": "target_pct", "set_budget": "budget_usd", "set_risk": "risk_lambda"}[t]
        try:
            goal = Goal.model_validate({**need_goal(), key: p.get(key)})
        except ValidationError as e:
            raise ReplanError(422, str(e)) from e
        risk = f"risk appetite {goal.risk_lambda:g}" + ("" if plan.get("risk_supported", True) else " (not modelled yet)")
        label = {"target_pct": f"target {goal.target_pct:g}%", "budget_usd": f"budget {goal.budget_usd or 'cleared'}",
                 "risk_lambda": risk}[key]
        events.emit(rid, "Orchestrator", "plan", f"re-plan: {label}")
        view = View(issues_shown=view.issues_shown)
    elif t in ("exclude_building", "include_building"):
        need_goal(); b = bid(); goal = Goal.model_validate(goal_d)
        (excl_b.add if t == "exclude_building" else excl_b.discard)(b)
        events.emit(rid, "Orchestrator", "plan", f"re-plan: {names[b]} {'excluded' if t == 'exclude_building' else 'included'}",
                    building_id=b, building_name=names[b])
        view = View(issues_shown=view.issues_shown)
    elif t == "toggle_upgrade":
        need_goal(); u = uid(); goal = Goal.model_validate(goal_d)
        on = bool(p.get("on", False))
        (excl_u.discard if on else excl_u.add)(u)
        events.emit(rid, "Orchestrator", "plan",
                    f"re-plan: {ups[u].type} at {names[ups[u].building_id]} {'on' if on else 'off'}",
                    building_id=ups[u].building_id)
        view = view.model_copy(update={"selected_upgrade_ids": []})
    elif t == "include_unverified":
        need_goal(); u = uid(); goal = Goal.model_validate(goal_d)
        owner_inc.add(u); excl_u.discard(u)
        events.emit(rid, "Orchestrator", "plan",
                    f"re-plan: owner includes unverified {ups[u].type} at {names[ups[u].building_id]}",
                    building_id=ups[u].building_id)
    elif t in ("select_bar", "open_building"):
        price = False
        if t == "select_bar":
            u = uid()
            view = view.model_copy(update={"focus_building_id": ups[u].building_id, "selected_upgrade_ids": [u]})
            events.emit(rid, "Orchestrator", "plan",
                        f"opening {names[ups[u].building_id]}, highlighting {ups[u].type}", building_id=ups[u].building_id)
        else:
            b = p.get("building_id")
            if b is None:  # back to the portfolio
                view = View(issues_shown=view.issues_shown)
                events.emit(rid, "Orchestrator", "plan", "back to portfolio overview")
            else:
                bid_ = bid()
                view = View(focus_building_id=bid_, issues_shown=view.issues_shown)
                events.emit(rid, "Orchestrator", "plan", f"opening {names[bid_]}", building_id=bid_, building_name=names[bid_])
    else:  # pragma: no cover - OwnerAction.type is a closed Literal
        raise ReplanError(422, f"unsupported action {t}")

    if price:
        plan = await run_pricing(rid, goal, excluded_building_ids=excl_b, excluded_upgrade_ids=excl_u, owner_included=owner_inc)
    layout, view = await composer.compose(rid, t, view)
    composer.save_state(rid, layout, plan.get("goal"), plan.get("plan_id"), view.model_dump())
    return layout


async def _approve(action: OwnerAction) -> Layout:
    """finance -> memo -> `approved` layout; gated on the current plan_id; repeat approve books nothing."""
    rid = action.run_id
    events.emit(rid, "Orchestrator", "plan", "approval received; opening financing")
    try:
        await run_finance(rid, action.payload.get("plan_id"))
    except ApprovalError as e:
        raise ReplanError(409, str(e)) from e
    plan = read_json(data_path("plans", "current.json"))
    if not data_path("memo", f"{plan['plan_id']}.md").exists():
        await write_memo(rid, plan)
    view = _load_view(rid).model_copy(update={"focus_building_id": None, "selected_upgrade_ids": []})
    layout, view = await composer.compose(rid, "approve", view)
    composer.save_state(rid, layout, plan.get("goal"), plan["plan_id"], view.model_dump())
    return layout
