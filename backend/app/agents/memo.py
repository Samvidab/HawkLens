"""Memo writer (T3.5): Gemini writes prose with {{placeholders}} only; code substitutes the numbers.

The LLM never sees or produces a figure. guardrails.guarded_text rejects drafts containing numbers
no source explains and regenerates without numbers; after that a template memo is the fallback.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

from pydantic import BaseModel

from app import events
from app.agents.llm import text_json
from app.guardrails import check_numbers, fill_placeholders, guarded_text
from app.storage import data_path, read_json

log = logging.getLogger(__name__)
PROMPT = (Path(__file__).parent / "prompts" / "memo.md").read_text()

CATALOG = {
    "target_pct": "CO2 reduction target, percent",
    "tonnes_needed": "annual tonnes needed to hit the target (already includes the unit t/yr)",
    "tonnes_per_year": "annual tonnes the plan cuts (already includes the unit t/yr)",
    "shortfall_tonnes": "annual shortfall (already includes the unit t/yr; zero when the target is met)",
    "total_upfront": "total upfront cost",
    "exp_npv": "expected net present value",
    "cvar5": "net present value in the worst 5 percent of outcomes",
    "p_loss": "probability the plan loses money",
    "p_hit_target": "probability the plan hits the target",
    "budget": "a complete phrase about the budget, e.g. 'no budget cap' or 'a budget cap of $X'; do not add words around it",
    "n_upgrades": "number of upgrades in the plan",
    "n_buildings": "number of buildings with upgrades",
}
STUB_NOTE = "_Sample pricing: figures come from placeholder stub values, not the quant engine._"


class MemoDraft(BaseModel):
    markdown: str


def usd(v: float | None) -> str:
    if v is None:
        return "n/a"
    sign, a = ("-" if v < 0 else ""), abs(v)
    if a >= 1e6:
        return f"{sign}${a / 1e6:.1f}M"
    return f"{sign}${a:,.0f}"


def pct(p: float | None) -> str:
    return "n/a" if p is None else f"{p * 100:.0f}%"


def tonnes(v: float | None) -> str:
    return "n/a" if v is None else f"{v:,.0f} t/yr"


def build_values(plan: dict, upgrades: dict[str, dict]) -> tuple[dict[str, str], dict[str, float]]:
    """(display strings for placeholders, raw derived numbers to add to the check sources)"""
    sel = plan.get("selected", [])
    n_buildings = len({upgrades[u]["building_id"] for u in sel if u in upgrades})
    goal = plan.get("goal", {})
    raw = {"n_upgrades": len(sel), "n_buildings": n_buildings}
    budget = goal.get("budget_usd")
    values = {
        "target_pct": f"{goal.get('target_pct', 0):g}%", "tonnes_needed": tonnes(plan.get("tonnes_needed")),
        "tonnes_per_year": tonnes(plan.get("tonnes_per_year")), "shortfall_tonnes": tonnes(plan.get("shortfall_tonnes", 0)),
        "total_upfront": usd(plan.get("total_upfront")), "exp_npv": usd(plan.get("exp_npv")),
        "cvar5": usd(plan.get("cvar5")), "p_loss": pct(plan.get("p_loss")), "p_hit_target": pct(plan.get("p_hit_target")),
        "budget": "no budget cap" if budget is None else f"a budget cap of {usd(budget)}",
        "n_upgrades": str(raw["n_upgrades"]), "n_buildings": str(raw["n_buildings"]),
    }
    return values, raw


FALLBACK = (
    "This plan cuts {{tonnes_per_year}} against a need of {{tonnes_needed}} for a {{target_pct}} reduction target, "
    "using {{n_upgrades}} upgrades across {{n_buildings}} buildings.\n\n"
    "It costs {{total_upfront}} upfront ({{budget}}), with an expected net present value of "
    "{{exp_npv}}. In the worst 5 percent of outcomes the value is {{cvar5}}, and the chance of a loss is {{p_loss}}.\n\n"
    "The probability of hitting the target is {{p_hit_target}}. Every upgrade is backed by images the agents inspected "
    "and checked."
)


def _placeholders(text: str) -> set[str]:
    return {m.strip() for m in re.findall(r"\{\{(.*?)\}\}", text)}


def _prompt(plan: dict, profiles: dict[str, dict], upgrades: dict[str, dict], allow_numbers: bool) -> str:
    sel = [upgrades[u] for u in plan.get("selected", []) if u in upgrades]
    names = sorted({profiles[u["building_id"]]["name"] for u in sel if u["building_id"] in profiles})
    return PROMPT.format(
        catalog="\n".join(f"  {{{{{k}}}}} = {v}" for k, v in CATALOG.items()),
        outcome="target met" if plan.get("status") == "ok" else "target NOT met within limits",
        buildings=", ".join(names) or "none", types=", ".join(sorted({u["type"] for u in sel})) or "none",
        target_met="yes" if plan.get("status") == "ok" else "no",
        extra="" if allow_numbers else "- Your previous draft contained a number. Use placeholders only.")


def _appendix(plan: dict, profiles: dict[str, dict], upgrades: dict[str, dict]) -> str:
    sim = plan.get("simulate", {})
    rows = ["| Building | Upgrade | Size | Upfront | Tonnes/yr |", "|---|---|---|---|---|"]
    for uid in plan.get("selected", []):
        u = upgrades.get(uid)
        if not u:
            continue
        s = sim.get(uid, {})
        rows.append(f"| {profiles.get(u['building_id'], {}).get('name', u['building_id'])} | {u['type']} | "
                    f"{u['size_value']:,.0f} {u['size_unit']} | {usd(s.get('upfront_usd'))} | "
                    f"{tonnes(s.get('tonnes_per_year')).replace(' t/yr', '')} |")
    return "\n".join(rows)


def _load() -> tuple[dict, dict[str, dict], dict[str, dict]]:
    plan = read_json(data_path("plans", "current.json"), {})
    profiles, upgrades = {}, {}
    for d in sorted(p for p in data_path("buildings").glob("*") if p.is_dir()):
        if (prof := read_json(d / "profile.json")) is not None:
            profiles[d.name] = prof
        for u in read_json(d / "feasibility.json", []):
            upgrades[u["upgrade_id"]] = u
    return plan, profiles, upgrades


async def write_memo(run_id: str, plan: dict | None = None) -> str:
    """Write memo/<plan_id>.md and return its markdown."""
    loaded, profiles, upgrades = _load()
    plan = plan or loaded
    if not plan.get("plan_id"):
        raise ValueError("no plan to write a memo for")
    values, raw = build_values(plan, upgrades)
    # Digits that belong to a building's name or address are not invented numbers ("7900 Fannin", "CityNorth 6").
    sources = [plan, raw, [{"name": p.get("name"), "address": p.get("address")} for p in profiles.values()]]

    async def generate(allow_numbers: bool) -> str:
        draft = (await text_json(_prompt(plan, profiles, upgrades, allow_numbers), MemoDraft)).markdown
        unknown = _placeholders(draft) - set(CATALOG)
        if unknown:
            raise ValueError(f"unknown placeholders {sorted(unknown)}")
        return draft

    try:
        template = await guarded_text(generate, sources, fallback=FALLBACK)
    except Exception as e:  # noqa: BLE001 - Gemini failure, bad placeholders, cap hit: use the stock memo
        log.warning("memo LLM failed (%s); using template", e)
        template = FALLBACK
    prose = fill_placeholders(template, values)
    if bad := check_numbers(prose, sources):  # defence in depth: substituted text must be explained
        log.warning("memo failed number check %s; using template", bad)
        prose = fill_placeholders(FALLBACK, values)
    parts = [f"# Retrofit plan memo ({plan['plan_id']})", prose, "## Upgrades in the plan", _appendix(plan, profiles, upgrades)]
    if plan.get("stub"):
        parts.append(STUB_NOTE)
    md = "\n\n".join(parts) + "\n"
    path = data_path("memo", f"{plan['plan_id']}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md)
    events.emit(run_id, "Memo", "compose", "investment memo written")
    return md
