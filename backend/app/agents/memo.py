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
from app.guardrails import check_numbers, check_wording, fill_placeholders, guarded_text
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
    "n_upgrades": "number of individual upgrades in the plan (one per building and upgrade type): say \"upgrades\", never \"upgrade types\"",
    "n_upgrade_types": "number of distinct upgrade types (rooftop solar, LED retrofit, ...): say \"upgrade types\", never \"upgrades\"",
    "n_buildings": "number of buildings with upgrades",
    "return_summary": ("one finished sentence, written by code, stating plainly whether the plan pays back on average and which "
                       "upgrade types pay for themselves; include it exactly once, as its own sentence, and never soften or contradict it"),
}
STUB_NOTE = "_Sample pricing: figures come from placeholder stub values, not the quant engine._"


class MemoDraft(BaseModel):
    markdown: str


class DraftRejected(Exception):
    """The model's draft broke a memo rule (wording, counts, missing required sentence). The reason is fed back once."""


MAX_DRAFTS = 2
LABEL = {"rooftop_solar": "rooftop solar", "cool_roof": "cool roof", "window_upgrade": "window upgrade",
         "heat_pump": "heat pump", "insulation": "insulation", "led_retrofit": "LED retrofit"}
# "23 upgrade types" for 23 upgrades (or "3 upgrades" for 3 types): the counts must name what they count.
_WRONG_COUNT_WORDS = (
    (re.compile(r"\{\{\s*n_upgrades\s*\}\}\s+(?:[\w-]+\s+)?(?:upgrade\s+types|types\s+of\s+upgrades?|kinds\s+of\s+upgrades?|upgrade\s+categories)", re.I),
     "{{n_upgrades}} counts individual upgrades: write \"{{n_upgrades}} upgrades\", not \"upgrade types\""),
    (re.compile(r"\{\{\s*n_upgrade_types\s*\}\}\s+(?:[\w-]+\s+)?upgrades?\b(?!\s+types)", re.I),
     "{{n_upgrade_types}} counts upgrade types: write \"{{n_upgrade_types}} upgrade types\", not \"upgrades\""),
)


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
    n_types = len({upgrades[u]["type"] for u in sel if u in upgrades})
    raw = {"n_upgrades": len(sel), "n_buildings": n_buildings, "n_upgrade_types": n_types}
    budget = goal.get("budget_usd")
    values = {
        "target_pct": f"{goal.get('target_pct', 0):g}%", "tonnes_needed": tonnes(plan.get("tonnes_needed")),
        "tonnes_per_year": tonnes(plan.get("tonnes_per_year")), "shortfall_tonnes": tonnes(plan.get("shortfall_tonnes", 0)),
        "total_upfront": usd(plan.get("total_upfront")), "exp_npv": usd(plan.get("exp_npv")),
        "cvar5": usd(plan.get("cvar5")), "p_loss": pct(plan.get("p_loss")), "p_hit_target": pct(plan.get("p_hit_target")),
        "budget": "no budget cap" if budget is None else f"a budget cap of {usd(budget)}",
        "n_upgrades": str(raw["n_upgrades"]), "n_buildings": str(raw["n_buildings"]), "n_upgrade_types": str(n_types),
        "return_summary": return_summary(plan, upgrades),
    }
    return values, raw


def _join(items: list[str]) -> str:
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def return_summary(plan: dict, upgrades: dict[str, dict]) -> str:
    """A plain, neutral sentence about whether the plan pays back on average and which upgrade types do, from the plan's own
    expected NPVs (the plan's and each selected upgrade's). Written by code so the model cannot soften it."""
    npv = plan.get("exp_npv")
    if npv is None:
        return "The expected net present value of the plan is not available."
    by_type: dict[str, float] = {}
    for uid in plan.get("selected", []):
        v = plan.get("simulate", {}).get(uid, {}).get("exp_npv")
        if uid in upgrades and v is not None:
            by_type[upgrades[uid]["type"]] = by_type.get(upgrades[uid]["type"], 0.0) + v
    paying = sorted(LABEL.get(t, t) for t, v in by_type.items() if v > 0)
    losing = sorted(LABEL.get(t, t) for t, v in by_type.items() if v <= 0)
    if npv < 0:
        if paying:
            verb = "pays" if len(paying) == 1 else "pay"
            who = "itself" if len(paying) == 1 else "themselves"
            tail = f"the {_join(paying)} portion{'' if len(paying) == 1 else 's'} {verb} for {who}"
        else:
            tail = "no upgrade type pays for itself on average"
        return f"On average the plan costs more than it saves; {tail}."
    base = "On average the plan saves more than it costs" if npv > 0 else "On average the plan breaks even"
    if losing:
        verb = "costs" if len(losing) == 1 else "cost"
        return f"{base}; the {_join(losing)} portion{'' if len(losing) == 1 else 's'} {verb} more than {'it saves' if len(losing) == 1 else 'they save'}."
    return f"{base}."


FALLBACK = (
    "This plan cuts {{tonnes_per_year}} against a need of {{tonnes_needed}} for a {{target_pct}} reduction target, "
    "using {{n_upgrades}} upgrades across {{n_buildings}} buildings.\n\n"
    "It costs {{total_upfront}} upfront ({{budget}}), with an expected net present value of "
    "{{exp_npv}}. {{return_summary}} In the worst 5 percent of outcomes the value is {{cvar5}}, and the chance of a loss is {{p_loss}}.\n\n"
    "The probability of hitting the target is {{p_hit_target}}. Review recorded evidence and verification status; "
    "assumed upgrades are not observed findings."
)


def _placeholders(text: str) -> set[str]:
    return {m.strip() for m in re.findall(r"\{\{(.*?)\}\}", text)}


def check_draft(draft: str) -> None:
    """Raise DraftRejected if the model's draft breaks a memo rule; the message says what to fix."""
    if unknown := _placeholders(draft) - set(CATALOG):
        raise DraftRejected(f"it used unknown placeholders {sorted(unknown)}")
    if words := check_wording(draft):
        raise DraftRejected(f"it used evaluative or promotional wording ({', '.join(words)}); describe results neutrally")
    n = len(re.findall(r"\{\{\s*return_summary\s*\}\}", draft))
    if n != 1:
        raise DraftRejected(f"it must contain {{{{return_summary}}}} exactly once as its own sentence (found {n})")
    for pattern, message in _WRONG_COUNT_WORDS:
        if pattern.search(draft):
            raise DraftRejected(message)


def _prompt(plan: dict, profiles: dict[str, dict], upgrades: dict[str, dict], allow_numbers: bool, feedback: str | None = None) -> str:
    sel = [upgrades[u] for u in plan.get("selected", []) if u in upgrades]
    names = sorted({profiles[u["building_id"]]["name"] for u in sel if u["building_id"] in profiles})
    return PROMPT.format(
        catalog="\n".join(f"  {{{{{k}}}}} = {v}" for k, v in CATALOG.items()),
        outcome="target met" if plan.get("status") == "ok" else "target NOT met within limits",
        buildings=", ".join(names) or "none", types=", ".join(sorted({u["type"] for u in sel})) or "none",
        target_met="yes" if plan.get("status") == "ok" else "no",
        extra=("" if allow_numbers else "- Your previous draft contained a number. Use placeholders only.\n")
        + (f"- Your previous draft was rejected because {feedback}. Fix exactly that.\n" if feedback else ""))


def _appendix(plan: dict, profiles: dict[str, dict], upgrades: dict[str, dict]) -> str:
    """The table of selected upgrades. Every number comes from the plan JSON: costs and tonnes from `simulate`, sizes from
    `plan["upgrades"]` (written by the pricing node). Plans priced before that field existed show the size as not available."""
    sim = plan.get("simulate", {})
    details = plan.get("upgrades", {})
    names = plan.get("building_names", {})
    rows = ["| Building | Upgrade | Size | Upfront | Tonnes/yr |", "|---|---|---|---|---|"]
    for uid in plan.get("selected", []):
        d = details.get(uid) or {}
        bid = d.get("building_id") or (upgrades.get(uid) or {}).get("building_id") or uid.split(":")[0]
        typ = d.get("type") or (upgrades.get(uid) or {}).get("type") or uid.split(":")[-1]
        name = names.get(bid) or profiles.get(bid, {}).get("name", bid)
        size = f"{d['size_value']:,.0f} {d['size_unit']}" if d.get("size_value") is not None else "not available"
        s = sim.get(uid, {})
        t = s.get("tonnes_per_year")
        rows.append(f"| {name} | {LABEL.get(typ, typ)} | {size} | {usd(s.get('upfront_usd'))} | {'not available' if t is None else f'{t:,.0f}'} |")
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
    # Numbers may come only from the plan JSON and counts derived from it (`raw`). Digits that belong to a building's
    # name or address are not numbers about the plan ("7900 Fannin", "CityNorth 6"), so they are allowed too.
    sources = [plan, raw, [{"name": p.get("name"), "address": p.get("address")} for p in profiles.values()]]

    template, feedback = FALLBACK, None
    for attempt in range(MAX_DRAFTS):  # a draft that breaks a memo rule is regenerated once, told why; then the template
        async def generate(allow_numbers: bool) -> str:
            draft = (await text_json(_prompt(plan, profiles, upgrades, allow_numbers, feedback), MemoDraft)).markdown
            check_draft(draft)
            return draft

        try:
            template = await guarded_text(generate, sources, fallback=FALLBACK)
            break
        except DraftRejected as e:
            feedback = str(e)
            log.warning("memo draft %d rejected: %s", attempt + 1, feedback)
        except Exception as e:  # noqa: BLE001 - Gemini failure, cap hit: use the stock memo
            log.warning("memo LLM failed (%s); using template", e)
            break
    prose = fill_placeholders(template, values)
    if bad := check_numbers(prose, sources):  # defence in depth: substituted text must be explained
        log.warning("memo failed number check %s; using template", bad)
        prose = fill_placeholders(FALLBACK, values)
    appendix = _appendix(plan, profiles, upgrades)
    if bad := check_numbers(appendix, sources):  # the table too: only numbers from the plan (and names/addresses)
        raise ValueError(f"memo table has numbers that are not in the plan: {bad}")
    parts = [f"# Retrofit plan memo ({plan['plan_id']})", prose, "## Upgrades in the plan", appendix]
    if plan.get("stub"):
        parts.append(STUB_NOTE)
    md = "\n\n".join(parts) + "\n"
    path = data_path("memo", f"{plan['plan_id']}.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md)
    events.emit(run_id, "Memo", "compose", "investment memo written")
    return md
