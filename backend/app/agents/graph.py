"""LangGraph wiring (T2.1): orchestrator → Send fan-out → per-building survey subgraph → collect.

Survey subgraph:
    records → inspect (aerial ∥ interior on the hero) → site_engineer → verify ─┬─► finalize
                                                          ▲                     │ claims sent back
                                                          └──── reinspect ◄─────┘
inspect: with AGENTIC_SURVEY (default on) the investigator agent (agents/investigator.py) chooses
which evidence to pull per building; the fixed aerial ∥ interior pipeline is its fallback.
Graph edges are fixed; inside `inspect` the investigator (Gemini) chooses each tool call. Gemini
also writes the orchestrator's plan lines (checked for invented numbers, template fallback) and
does the inspectors'/verifier's vision work.
Concurrency: at most MAX_CONCURRENT_BUILDINGS surveys at once (semaphore per run).
"""
from __future__ import annotations

import asyncio
import logging
import operator
import uuid
from datetime import datetime, timezone
from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send
from pydantic import BaseModel

from app.adapters.cache import write_json_atomic
from app.agents import aerial, llm, records, store
from app.config import get_settings
from app.events import emit
from app.guardrails import check_numbers
from app.rules import feasibility
from app.schemas.claims import Claim
from app.schemas.goal import Goal
from app.schemas.profile import BuildingProfile
from app.schemas.upgrades import FeasibleUpgrade

log = logging.getLogger(__name__)
ORCH = "Orchestrator"


def _merge(a: dict, b: dict) -> dict:
    return {**a, **b}


# --------------------------------------------------------------------------- survey subgraph

class SurveyState(TypedDict, total=False):
    run_id: str
    building_id: str
    hero: bool
    profile: BuildingProfile
    aerial: Any  # aerial.AerialResult
    interior: Any  # interior.InteriorResult | None (T2.3)
    claims: list[Claim]
    upgrades: list[FeasibleUpgrade]
    sent_back: dict[str, str]  # claim_id → verifier question (T2.2)
    _verify_round: int
    goal: Goal  # optional: the owner's goal, for the investigator
    investigation: list[dict]  # investigator tool calls (AGENTIC_SURVEY)


async def records_node(s: SurveyState) -> dict:
    return {"profile": await records.run(s["building_id"], s["run_id"])}


async def inspect_node(s: SurveyState) -> dict:
    from app.agents import investigator
    if investigator.enabled():
        try:
            return await investigator.investigate(s["profile"], s["run_id"], s.get("goal"), bool(s.get("hero")))
        except Exception as e:  # noqa: BLE001 - the fixed pipeline below is the fallback
            log.exception("investigator failed for %s", s["building_id"])
            emit(s["run_id"], "Investigator", "error",
                 f"investigator failed ({type(e).__name__}); running the fixed survey", s["building_id"],
                 building_name=s["profile"].name)
    return await fixed_inspect(s)


async def fixed_inspect(s: SurveyState) -> dict:
    """The fixed pipeline: aerial always, interior on the hero's scan."""
    profile = s["profile"]
    tasks = [aerial.inspect(profile, s["run_id"])]
    interior_mod = _interior()
    if interior_mod and s.get("hero") and profile.matterport_model_id:
        tasks.append(interior_mod.inspect(profile, s["run_id"]))
    results = await asyncio.gather(*tasks, return_exceptions=True)
    aer = results[0]
    if isinstance(aer, BaseException):
        raise aer
    inter = results[1] if len(results) > 1 else None
    if isinstance(inter, BaseException):  # interior is optional: keep the building, report the error
        log.warning("interior failed for %s: %s", profile.building_id, inter)
        emit(s["run_id"], "Interior", "error", f"interior survey failed ({type(inter).__name__})",
             profile.building_id, building_name=profile.name)
        inter = None
    claims = list(aer.claims) + (list(inter.claims) if inter else [])
    return {"aerial": aer, "interior": inter, "claims": claims}


def _evaluate(s: SurveyState) -> list[FeasibleUpgrade]:
    inter = s.get("interior")
    return feasibility.evaluate(s["profile"], s["aerial"].findings, inter.findings if inter else None, s["claims"])


def decide_message(ups: list[FeasibleUpgrade]) -> str:
    msg = f"{len(ups)} feasible upgrade{'s' if len(ups) != 1 else ''}"
    solar = next((u for u in ups if u.type == "rooftop_solar"), None)
    return msg + (f" (solar {solar.size_value:,.0f} kW)" if solar else "")


async def site_engineer_node(s: SurveyState) -> dict:
    ups = _evaluate(s)
    emit(s["run_id"], "Site engineer", "decide", decide_message(ups), s["building_id"],
         building_name=s["profile"].name)
    return {"upgrades": ups}


async def verify_node(s: SurveyState) -> dict:
    v = _verifier()
    if not v:
        return {"sent_back": {}}
    return await v.verify(s)


async def reinspect_node(s: SurveyState) -> dict:
    return await _verifier().reinspect(s)


def after_verify(s: SurveyState) -> str:
    return "reinspect" if s.get("sent_back") else "finalize"


async def finalize_node(s: SurveyState) -> dict:
    """Re-derive findings/upgrades from the final claims and write every building file."""
    profile, bid = s["profile"], s["building_id"]
    v = _verifier()
    state = dict(s)
    if v:
        state = {**state, **v.refresh_findings(state)}
    ups = feasibility.apply_verification(_evaluate(state), state["claims"])
    aerial.save(profile, state["aerial"])
    if state.get("interior"):
        _interior().save(profile, state["interior"])
    store.save_claims(bid, state["claims"])
    # Contract with widgets/resolver.py: verification.json = list[Claim] with final statuses.
    write_json_atomic(store.building_dir(bid) / "verification.json",
                      [c.model_dump(mode="json") for c in state["claims"]])
    write_json_atomic(store.building_dir(bid) / "feasibility.json", [u.model_dump(mode="json") for u in ups])
    return {"upgrades": ups, "claims": state["claims"], "aerial": state["aerial"]}


def _interior():
    try:
        from app.agents import interior
        return interior
    except ImportError:
        return None


def _verifier():
    try:
        from app.agents import verifier
        return verifier
    except ImportError:
        return None


def build_survey_graph():
    g = StateGraph(SurveyState)
    g.add_node("records", records_node)
    g.add_node("inspect", inspect_node)
    g.add_node("site_engineer", site_engineer_node)
    g.add_node("verify", verify_node)
    g.add_node("reinspect", reinspect_node)
    g.add_node("finalize", finalize_node)
    g.add_edge(START, "records")
    g.add_edge("records", "inspect")
    g.add_edge("inspect", "site_engineer")
    g.add_edge("site_engineer", "verify")
    g.add_conditional_edges("verify", after_verify, {"reinspect": "reinspect", "finalize": "finalize"})
    g.add_edge("reinspect", "verify")
    g.add_edge("finalize", END)
    return g.compile()


# --------------------------------------------------------------------------- run graph

class RunState(TypedDict, total=False):
    run_id: str
    goal: Goal
    building_ids: list[str]
    hero_id: str | None
    results: Annotated[dict[str, dict], _merge]
    plan: list[str]


class PlanSteps(BaseModel):
    steps: list[str]


_semaphores: dict[str, asyncio.Semaphore] = {}
_survey_graph = None


def survey_graph():
    global _survey_graph
    if _survey_graph is None:
        _survey_graph = build_survey_graph()
    return _survey_graph


def template_plan(n: int, city: str, k: int, hero_name: str | None) -> list[str]:
    steps = [f"Plan: survey {n} {city} buildings, {k} at a time",
             "Each: CoStar records, Vexcel roof inspection, site engineer rules, verifier"]
    if hero_name:
        steps.append(f"Interior scan of {hero_name} from Matterport")
    return steps


async def write_plan(goal: Goal, names: list[str], k: int, hero_name: str | None) -> list[str]:
    fallback = template_plan(len(names), goal.city, k, hero_name)
    sources = {"n": len(names), "k": k, "target_pct": goal.target_pct, "budget": goal.budget_usd,
               "fallback": fallback}
    prompt = (
        "You are the orchestrator of a building-retrofit survey team. Write 2 to 4 plan steps for a live activity "
        "feed, each one short factual line under 80 characters, present tense, no filler.\n"
        f"City: {goal.city}. Buildings to survey ({len(names)}): {', '.join(names)}. At most {k} surveyed at once. "
        f"Interior (Matterport) survey: {hero_name or 'none'}. Owner target: cut CO2 {goal.target_pct:g}%.\n"
        "Steps per building: CoStar records, Vexcel aerial roof inspection, site-engineer feasibility rules, "
        "verifier checks each claim against its image and sends doubtful ones back. "
        "Use only numbers given here.")
    try:
        out = await llm.text_json(prompt, PlanSteps)
        steps = [" ".join(x.split()) for x in out.steps[:4]]
        steps = [x for x in steps if x and len(x) <= 90 and not check_numbers(x, sources)]
        return steps if len(steps) >= 2 else fallback
    except Exception as e:  # noqa: BLE001
        log.warning("orchestrator plan fell back to template: %s", e)
        return fallback


def write_state(run_id: str, **fields) -> None:
    p = store.run_dir(run_id) / "state.json"
    import json
    cur = json.loads(p.read_text()) if p.exists() else {}
    cur.update(fields)
    cur["run_id"] = run_id
    cur["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    write_json_atomic(p, cur)


async def orchestrator_plan(s: RunState) -> dict:
    run_id, goal = s["run_id"], s["goal"]
    portfolio = records.load_portfolio()["buildings"]
    by_id = {b["building_id"]: b for b in portfolio}
    ids = [i for i in (goal.building_ids or list(by_id)) if i in by_id]
    hero = next((b for b in portfolio if b.get("hero") and b["building_id"] in ids), None)
    k = get_settings().max_concurrent_buildings
    _semaphores[run_id] = asyncio.Semaphore(k)

    plan = await write_plan(goal, [by_id[i]["name"] for i in ids], k, hero["name"] if hero else None)
    for line in plan:
        emit(run_id, ORCH, "plan", line)
    write_state(run_id, status="surveying", goal=goal.model_dump(mode="json"),
                building_ids=ids, hero_id=hero["building_id"] if hero else None, plan=plan,
                results={i: {"status": "queued"} for i in ids})
    return {"building_ids": ids, "hero_id": hero["building_id"] if hero else None, "plan": plan, "results": {}}


def fan_out(s: RunState) -> list[Send]:
    return [Send("survey", {"run_id": s["run_id"], "building_id": b, "hero": b == s.get("hero_id"),
                            "goal": s.get("goal")})
            for b in s["building_ids"]]


async def survey_node(payload: dict) -> dict:
    run_id, bid = payload["run_id"], payload["building_id"]
    async with _semaphores.setdefault(run_id, asyncio.Semaphore(get_settings().max_concurrent_buildings)):
        try:
            out = await survey_graph().ainvoke(payload)
            ups = out.get("upgrades", [])
            claims = out.get("claims", [])
            res = {"status": "done", "name": out["profile"].name, "upgrades": len(ups),
                   "included": sum(u.include_in_optimizer for u in ups),
                   "claims": {st: sum(c.status == st for c in claims)
                              for st in ("verified", "unverified", "rejected", "pending")},
                   "interior": bool(out.get("interior"))}
        except Exception as e:  # noqa: BLE001 - one building failing must not stop the run
            log.exception("survey failed for %s", bid)
            emit(run_id, ORCH, "error", f"survey of {bid} failed ({type(e).__name__}); continuing", bid)
            res = {"status": "error", "error": f"{type(e).__name__}: {e}"[:300]}
    write_state(run_id, **{"results": {**_read_results(run_id), bid: res}})
    return {"results": {bid: res}}


def _read_results(run_id: str) -> dict:
    import json
    p = store.run_dir(run_id) / "state.json"
    return json.loads(p.read_text()).get("results", {}) if p.exists() else {}


async def collect(s: RunState) -> dict:
    res = s.get("results", {})
    done = [r for r in res.values() if r.get("status") == "done"]
    n_up = sum(r.get("upgrades", 0) for r in done)
    write_state(s["run_id"], status="surveyed", results=res)
    # Not `done`: the frontend reads /state on `done`, which needs pricing + compose first (run_full).
    emit(s["run_id"], ORCH, "decide",
         f"Survey complete: {len(done)} of {len(res)} buildings, {n_up} feasible upgrades")
    _semaphores.pop(s["run_id"], None)
    return {}


def build_run_graph():
    g = StateGraph(RunState)
    g.add_node("orchestrator_plan", orchestrator_plan)
    g.add_node("survey", survey_node)
    g.add_node("collect", collect)
    g.add_edge(START, "orchestrator_plan")
    g.add_conditional_edges("orchestrator_plan", fan_out, ["survey"])
    g.add_edge("survey", "collect")
    g.add_edge("collect", END)
    return g.compile()


def new_run_id() -> str:
    return "run_" + uuid.uuid4().hex[:8]


async def run(goal: Goal, run_id: str | None = None) -> dict:
    run_id = run_id or new_run_id()
    try:
        out = await build_run_graph().ainvoke({"run_id": run_id, "goal": goal, "results": {}})
        return {"run_id": run_id, "results": out.get("results", {})}
    except Exception as e:  # noqa: BLE001
        log.exception("run %s failed", run_id)
        emit(run_id, ORCH, "error", f"run failed ({type(e).__name__})")
        write_state(run_id, status="error", error=str(e)[:300])
        raise


async def survey_runner(run_id: str, goal: Goal, building_ids: list[str]) -> None:
    """Registered with agents.replan: survey buildings a `goal` action finds unsurveyed."""
    await run(goal.model_copy(update={"building_ids": building_ids}), run_id)


async def run_full(goal: Goal, run_id: str, compose) -> None:
    """POST /run pipeline: survey every goal building → `compose()` (Lane B: pricing → composer →
    state.json with the layout) → `done`. Errors still end with `done` so the UI never hangs."""
    try:
        out = await run(goal, run_id)
    except Exception:  # noqa: BLE001 - already reported by run()
        emit(run_id, ORCH, "done", "Run stopped: survey failed")
        return
    try:
        await compose()
    except Exception as e:  # noqa: BLE001
        log.exception("pricing/compose failed for %s", run_id)
        emit(run_id, ORCH, "error", f"pricing/compose failed ({type(e).__name__})")
        write_state(run_id, status="error", error=str(e)[:300], results=out["results"])
        emit(run_id, ORCH, "done", "Run finished without a workspace")
        return
    write_state(run_id, status="ready", results=out["results"])  # merges into composer's state.json
    emit(run_id, ORCH, "done", "Workspace ready")
