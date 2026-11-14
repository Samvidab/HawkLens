"""UI composer v1 (T3.2, App Flow §6).

Code detects the situation and builds the template; Gemini FAST may only drop (<=2), reorder, add (<=2)
widgets and write `why` lines (with {{placeholders}} for figures). The resolver fills every prop from
data. Any invalid / slow / failed LLM answer falls back to the template with stock `why` strings.
A widget whose data is not ready is dropped with an `error` event rather than blanking the page.
"""
from __future__ import annotations

import asyncio
import logging
import statistics
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel

from app import events
from app.agents.llm import text_json
from app.guardrails import check_numbers, fill_placeholders
from app.schemas.claims import Claim
from app.schemas.layout import MAX_WHY, MAX_WIDGETS, Layout, Situation, WidgetSpec
from app.storage import data_path, read_json, write_json
from app.widgets.registry import WIDGETS, RegistryError
from app.widgets.resolver import ResolveContext, ResolveError, resolve_layout, resolve_widget
from app.widgets.templates import stock_title, stock_why, template_for

log = logging.getLogger(__name__)
PROMPT = (Path(__file__).parent / "prompts" / "composer.md").read_text()

COMPOSER_LLM_TIMEOUT_S = 1.5  # owner actions must feel instant; a late answer still warms the cache
MAX_DROPS, MAX_ADDS = 2, 2
BAD_CLAIM_STATES = {"unverified", "rejected"}
PINNED: dict[str, set[str]] = {
    "portfolio_overview": {"target_control", "plan_table"},
    "target_gap": {"target_control", "target_gap_card"},
    "verification_issue": {"evidence_gallery", "upgrade_list"},
    "building_detail": {"building_header", "upgrade_list"},
    "approved": {"financing_card", "memo"},
}
PLACEHOLDERS = {
    "target_pct": "the CO2 target percent",
    "shortfall": "annual tonnes the plan falls short",
    "p_hit": "probability of hitting the target",
    "n_selected": "number of upgrades in the plan",
    "n_negative_bars": "number of upgrades that pay for themselves (negative cost per tonne)",
    "n_bars": "number of upgrades on the abatement curve",
    "n_issues": "number of unverified or rejected findings",
    "n_extra": "number of extra cuts suggested to close the gap",
    "building": "name of the building being viewed",
}


# ---- situation detection (pure code) ----------------------------------------------------------
def issue_claims(ctx: ResolveContext) -> list[Claim]:
    """Unverified/rejected claims backing an upgrade the owner has neither included nor switched off."""
    excluded_u = set(ctx.plan.get("excluded_upgrade_ids", []))
    out: dict[str, Claim] = {}
    for bid, claims in ctx.claims.items():
        if bid in ctx.excluded:
            continue
        backed = {cid for u in ctx.upgrades.get(bid, []) if u.upgrade_id not in excluded_u
                  and u.upgrade_id not in ctx.owner_included for cid in u.claim_ids}
        for c in claims:
            if c.status in BAD_CLAIM_STATES and c.claim_id in backed:
                out[c.claim_id] = c
    return list(out.values())


def detect_situation(ctx: ResolveContext, action_type: str, view: "View") -> Situation:
    """Priority: approved > building_detail > verification_issue (new findings only) > target_gap > overview."""
    if action_type == "approve" and ctx.plan.get("financing", {}).get("state") == "executed":
        return "approved"
    if view.focus_building_id:
        return "building_detail"
    if any(c.claim_id not in view.issues_shown for c in issue_claims(ctx)):
        return "verification_issue"
    if ctx.plan.get("status") == "infeasible":
        return "target_gap"
    return "portfolio_overview"


def situation_facts(ctx: ResolveContext, n_issues: int) -> tuple[dict[str, str], dict[str, float]]:
    """(placeholder strings, raw numbers) computed by code from plan data."""
    p = ctx.plan
    bars = p.get("macc", {}).get("bars", [])
    raw = {"n_selected": len(p.get("selected", [])), "n_bars": len(bars),
           "n_negative_bars": sum(b["cost_per_tonne"] < 0 for b in bars), "n_issues": n_issues,
           "n_extra": len(p.get("cheapest_extra", []))}
    shortfall = p.get("shortfall_tonnes") or 0.0
    strings = {k: str(v) for k, v in raw.items()}
    strings.update(target_pct=f"{p.get('goal', {}).get('target_pct', 0):g}%", shortfall=f"{shortfall:,.0f} t/yr",
                   p_hit="n/a" if p.get("p_hit_target") is None else f"{p['p_hit_target'] * 100:.0f}%",
                   building=ctx.name(ctx.focus_building_id) if ctx.focus_building_id in ctx.profiles else "")
    raw["shortfall"] = shortfall
    return strings, raw


# ---- LLM refinement ---------------------------------------------------------------------------
class WhyItem(BaseModel):
    type: str
    why: str = ""


class Selection(BaseModel):
    widgets: list[WhyItem]


# Widgets the LLM may add per situation (only ones that make sense there; never a gap card when the
# target is met, never focus-only widgets outside a detail view, never the memo).
ADDABLE: dict[str, list[str]] = {
    "portfolio_overview": ["evidence_gallery", "upgrade_list"],
    "target_gap": ["risk_histogram", "upgrade_list"],
    "verification_issue": ["plan_table", "abatement_curve"],
    "building_detail": ["plan_table", "abatement_curve", "portfolio_3d"],
    "approved": ["risk_histogram", "abatement_curve"],
}


def _addable(situation: str, template_types: set[str], ctx: ResolveContext) -> list[str]:
    return sorted(t for t in ADDABLE[situation] if t not in template_types)


def _prompt(situation: str, template: list[WidgetSpec], addable: list[str]) -> str:
    return PROMPT.replace("{situation}", situation).replace(
        "{template}", "\n".join(f"- {w.type}: {w.why}" for w in template if w.type != "activity_feed")).replace(
        "{addable}", "\n".join(f"- {t}: {WIDGETS[t].description}" for t in addable) or "(none)").replace(
        "{pinned}", ", ".join(sorted(PINNED[situation]))).replace("{max_widgets}", str(MAX_WIDGETS - 1)).replace(
        "{placeholders}", "\n".join(f"  {{{{{k}}}}} = {v}" for k, v in PLACEHOLDERS.items()))


async def _ask_llm(prompt: str) -> Selection:
    task = asyncio.ensure_future(text_json(prompt, Selection))
    task.add_done_callback(lambda t: t.cancelled() or t.exception())  # never "exception was never retrieved"
    return await asyncio.wait_for(asyncio.shield(task), COMPOSER_LLM_TIMEOUT_S)


def validate_selection(sel: Selection, situation: str, template: list[WidgetSpec], addable: list[str]) -> list[WhyItem]:
    """The LLM's order/drops/adds if they respect the limits, else raises ValueError."""
    items = [w for w in sel.widgets if w.type != "activity_feed"]
    types = [w.type for w in items]
    base = [w.type for w in template if w.type != "activity_feed"]
    if len(set(types)) != len(types):
        raise ValueError("duplicate widget types")
    if unknown := [t for t in types if t not in base and t not in addable]:
        raise ValueError(f"widgets not allowed here: {unknown}")
    if len(set(base) - set(types)) > MAX_DROPS:
        raise ValueError("too many drops")
    if len(set(types) - set(base)) > MAX_ADDS:
        raise ValueError("too many additions")
    if PINNED[situation] - set(types):
        raise ValueError("dropped a pinned widget")
    if len(types) + 1 > MAX_WIDGETS:
        raise ValueError("too many widgets")
    return items


async def refine(situation: str, template: list[WidgetSpec], ctx: ResolveContext) -> list[WhyItem] | None:
    addable = _addable(situation, {w.type for w in template}, ctx)
    try:
        return validate_selection(await _ask_llm(_prompt(situation, template, addable)), situation, template, addable)
    except Exception as e:  # noqa: BLE001 - timeout, CacheMiss, bad JSON, limit violations: all mean 'use the template'
        log.info("composer LLM unavailable (%s: %s); using the template", type(e).__name__, str(e)[:80])
        return None


# ---- assembly ---------------------------------------------------------------------------------
def _large_unshaded_roof(ctx: ResolveContext) -> bool:
    bid = ctx.focus_building_id
    a = ctx.aerial.get(bid) if bid else None
    if not a or len(ctx.aerial) < 1:
        return False
    return a.shading == "none" and a.usable_roof_m2 > statistics.median(x.usable_roof_m2 for x in ctx.aerial.values())


def _upgrade_list_first(specs: list[WidgetSpec]) -> list[WidgetSpec]:
    """App Flow §6: for a large unshaded roof, upgrade_list leads the widgets below the top group."""
    lower = {"evidence_gallery", "facade_compass", "floor_plan", "risk_histogram"}
    ul = next((w for w in specs if w.type == "upgrade_list"), None)
    first = next((i for i, w in enumerate(specs) if w.type in lower), None)
    if ul is None or first is None:
        return specs
    rest = [w for w in specs if w is not ul]
    first = next(i for i, w in enumerate(rest) if w.type in lower)
    return rest[:first] + [ul] + rest[first:]


async def compose(run_id: str, action_type: str, view: "View") -> tuple[Layout, "View"]:
    ctx = ResolveContext.load(data_path(), run_id, focus_building_id=view.focus_building_id,
                              selected_upgrade_ids=list(view.selected_upgrade_ids))
    situation = detect_situation(ctx, action_type, view)
    ctx.situation = situation
    fresh_issues = [c for c in issue_claims(ctx) if c.claim_id not in view.issues_shown]
    roof_rule = situation == "building_detail" and _large_unshaded_roof(ctx)
    if roof_rule:  # highlight the solar overlay + upgrade
        solar = next((u.upgrade_id for u in ctx.upgrades.get(ctx.focus_building_id, []) if u.type == "rooftop_solar"), None)
        if solar and solar not in ctx.selected_upgrade_ids:
            ctx.selected_upgrade_ids = [*ctx.selected_upgrade_ids, solar]

    fid = ctx.focus_building_id
    template = template_for(situation, has_hero=ctx.hero_source(fid) is not None, has_floor_plan=bool(ctx.floor_rooms(fid)))
    strings, raw = situation_facts(ctx, len(issue_claims(ctx)))
    chosen = await refine(situation, template, ctx)

    by_type = {w.type: w for w in template}
    specs: list[WidgetSpec] = []
    templ_why: dict[str, str] = {}
    for item in chosen if chosen is not None else [WhyItem(type=w.type) for w in template if w.type != "activity_feed"]:
        w = by_type.get(item.type) or WidgetSpec(id="", type=item.type, title=stock_title(item.type),
                                                 why=stock_why(item.type)[:MAX_WHY], size=WIDGETS[item.type].default_size)
        specs.append(w.model_copy())
        if item.why:
            templ_why[item.type] = item.why
    specs.append(by_type["activity_feed"].model_copy())
    if roof_rule:
        specs = _upgrade_list_first(specs)

    kept: list[WidgetSpec] = []
    for spec in specs:
        try:
            resolved = resolve_widget(spec, ctx)
        except (ResolveError, RegistryError) as e:
            events.emit(run_id, "Composer", "error", f"dropped {spec.type}: {str(e)[:60]}")
            continue
        spec = spec.model_copy(update={"id": f"w{len(kept) + 1}"})
        if (draft := templ_why.get(spec.type)) is not None:
            try:
                why = " ".join(fill_placeholders(draft, strings).split())
                if len(why) <= MAX_WHY and why and not check_numbers(why, [raw, resolved.props]):
                    spec = spec.model_copy(update={"why": why})
            except KeyError:
                pass  # unknown placeholder: keep the stock why
        kept.append(spec)
    layout = resolve_layout(ctx, situation, kept)

    view = view.model_copy(update={"issues_shown": sorted({*view.issues_shown, *(c.claim_id for c in fresh_issues)})})
    write_json(data_path("layout.json"), layout)
    msg = {"target_gap": f"showing target gap: {strings['shortfall']} short",
           "building_detail": f"showing {strings['building'] or 'building'} detail",
           "verification_issue": f"showing {len(fresh_issues)} findings needing review"}.get(
        situation, f"showing {situation.replace('_', ' ')}, {len(layout.widgets)} widgets")
    events.emit(run_id, "Composer", "compose", msg)
    return layout, view


def save_state(run_id: str, layout: Layout, goal: dict | None, plan_id: str | None, view: dict | None = None) -> dict:
    """Merge the composer's fields into runs/<id>/state.json (graph.py writes survey status/results there too)."""
    path = data_path("runs", run_id, "state.json")
    state = read_json(path, {}) or {}
    state.update({"run_id": run_id, "goal": goal, "plan_id": plan_id, "view": view or {},
                  "layout": layout.model_dump(mode="json"),
                  "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds")})
    write_json(path, state)
    return state


class View(BaseModel):
    """Per-run view state persisted in runs/<id>/state.json."""
    focus_building_id: str | None = None
    selected_upgrade_ids: list[str] = []
    issues_shown: list[str] = []  # claim ids already surfaced as verification_issue
