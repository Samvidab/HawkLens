"""Default layout per situation (App Flow §6). The composer may drop/reorder/add <= 2 widgets;
stock `why` strings contain no numbers, so they pass the number guardrail untouched."""
from __future__ import annotations

from dataclasses import dataclass

from app.schemas.layout import MAX_WIDGETS, Situation, WidgetSpec
from app.widgets.registry import WIDGETS


@dataclass(frozen=True)
class Item:
    type: str
    title: str
    why: str
    size: str | None = None  # defaults to the registry's default size
    optional: str | None = None  # "matterport": include only if the building has a Matterport model


FEED = Item("activity_feed", "Agent activity", "Every agent step, as it happens.", "side")

TEMPLATES: dict[str, list[Item]] = {
    "portfolio_overview": [
        Item("target_control", "Your target", "Set the goal; agents re-plan on release."),
        Item("portfolio_3d", "Portfolio", "Where the planned upgrades sit across your buildings."),
        Item("abatement_curve", "Which cuts pay for themselves", "Bars below zero cut carbon and save money."),
        Item("plan_table", "Recommended plan", "The cheapest verified mix that meets the target."),
        Item("risk_histogram", "Risk", "How the plan's returns spread across outcomes."),
        Item("financing_card", "Financing", "What approval would set up."),
    ],
    "target_gap": [
        Item("target_control", "Your target", "The target is out of reach as set."),
        Item("target_gap_card", "Shortfall", "How far short the plan falls and the cheapest way to close it."),
        Item("abatement_curve", "Which cuts pay for themselves", "Unselected bars are the candidates to add."),
        Item("plan_table", "Best plan within limits", "The best verified mix inside your budget."),
        Item("portfolio_3d", "Portfolio", "Where the planned upgrades sit across your buildings."),
    ],
    "verification_issue": [
        Item("evidence_gallery", "Evidence to review", "Claims the verifier could not confirm come first."),
        Item("upgrade_list", "Affected upgrades", "Unverified upgrades stay out of the plan unless you include them."),
        Item("target_control", "Your target", "Excluded upgrades may change what is reachable."),
        Item("portfolio_3d", "Portfolio", "Where the planned upgrades sit across your buildings."),
    ],
    "building_detail": [
        Item("building_header", "Building", "Records from CoStar for this building."),
        Item("hero_3d", "Interior scan", "Findings pinned where the scanner saw them.", optional="matterport"),
        Item("portfolio_3d", "Building in 3D", "This building in context.", optional="no_matterport"),
        Item("evidence_gallery", "Evidence", "The images behind each finding, with verifier status."),
        Item("facade_compass", "Facades", "Glazing on each side drives window upgrades."),
        Item("floor_plan", "Floor plan", "Rooms and findings from the scan.", optional="matterport"),
        Item("upgrade_list", "Feasible upgrades", "What this building can take, and how sure we are."),
        Item("risk_histogram", "Building risk", "How this building's upgrades return across outcomes."),
    ],
    "approved": [
        Item("financing_card", "Financing", "Accounts and bills opened for the approved plan."),
        Item("memo", "Investment memo", "The plan in prose; every number comes from the engine."),
        Item("plan_table", "Approved plan", "The upgrades that were financed."),
    ],
}


def template_for(situation: Situation, *, has_matterport: bool = False) -> list[WidgetSpec]:
    """Widget skeletons (empty props) for a situation, ending with the always-present activity feed."""
    specs: list[WidgetSpec] = []
    for it in [*TEMPLATES[situation], FEED]:
        if it.optional == "matterport" and not has_matterport:
            continue
        if it.optional == "no_matterport" and has_matterport:
            continue
        specs.append(WidgetSpec(
            id=f"w{len(specs) + 1}", type=it.type, title=it.title, why=it.why,
            size=it.size or WIDGETS[it.type].default_size, props={}))
    assert len(specs) <= MAX_WIDGETS
    return specs


def stock_why(widget_type: str) -> str:
    """Fallback `why` for any widget type (composer fallback / added widgets)."""
    for items in TEMPLATES.values():
        for it in items:
            if it.type == widget_type:
                return it.why
    return FEED.why if widget_type == "activity_feed" else WIDGETS[widget_type].description


def stock_title(widget_type: str) -> str:
    for items in [*TEMPLATES.values(), [FEED]]:
        for it in items:
            if it.type == widget_type:
                return it.title
    return widget_type.replace("_", " ").title()
