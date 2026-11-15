"""Investigator: one Gemini agent per building that decides which data to pull, in what order,
and when to stop (AGENTIC_SURVEY, default on).

Loop: Gemini sees the owner's goal, the CoStar record, the tool list, every tool result so far and
a numbered list of facts those results established. It returns one validated tool call
{tool, purpose, because, args}. Code runs that tool through the existing adapters and inspectors
(every external call cached and replayable) and appends the result to the next prompt. At most
MAX_CALLS calls per building (`finish` included); temperature 0 (llm.py).

Nothing shown is invented. Gemini writes no text that is shown: `purpose` is one of a fixed set
of intents and `because` cites fact ids. Each activity event is composed by code AFTER the tool
ran, from what it actually returned: counts are counted, facts are quoted from tool results (an
uncited or unknown fact id is dropped), images are the ones the tool returned. A tool that fails
or returns nothing is recorded as "unknown", in the feed, the trace and the facts, never guessed.
The trace (investigation.json) records, per step, what was shown and which facts it quoted.

Outputs are the fixed pipeline's: profile, aerial.AerialResult, interior.InteriorResult | None
and claims, so the site engineer, verifier loop, pricing, composer and frontend don't change.
The roof is required: if the agent finishes without inspecting it, code inspects it anyway.
graph.inspect_node falls back to the fixed pipeline if this module raises.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel

from app.adapters import costar, geometry, vexcel
from app.adapters import matterport as mp
from app.adapters.cache import write_json_atomic
from app.adapters.types import ImageRef, PanoramaRef
from app.agents import aerial, interior, llm, records
from app.events import emit
from app.schemas.claims import Claim
from app.schemas.goal import Goal
from app.schemas.profile import BuildingProfile

log = logging.getLogger(__name__)
AGENT = "Investigator"
PROMPT_PATH = Path(__file__).parent / "prompts" / "investigator.md"
MAX_CALLS = 8
MAX_ROOMS = 4
MAX_SCANS_LISTED = 4
MAX_PANOS = 8  # a second, wider look when the first 5 (interior.MAX_PANOS) were unclear
MAX_FEED = 90  # events.MAX_MESSAGE
WIDE_FACTOR = 3.0  # wider context: 3x the building's own crop (neighbours, trees)
UNKNOWN = "unknown"

ToolName = Literal["get_costar_record", "get_vexcel_overhead", "get_vexcel_wider_context",
                   "find_matterport_scans", "get_matterport_rooms", "get_panoramas", "inspect_roof",
                   "inspect_interior", "label_rooms", "finish"]
Purpose = Literal["solar_evidence", "shading_check", "find_interior_evidence", "lighting_for_led",
                  "hvac_for_heat_pump", "room_use", "settle_unclear_result", "record_details",
                  "no_more_value"]
PURPOSE_TEXT = {  # fixed intents; the facts after them come from tool results
    "solar_evidence": "for solar", "shading_check": "to check shading", "find_interior_evidence":
    "for interior evidence", "lighting_for_led": "for LED evidence", "hvac_for_heat_pump": "for HVAC evidence",
    "room_use": "for room use", "settle_unclear_result": "to settle an unclear result",
    "record_details": "for record details", "no_more_value": "more evidence won't change an upgrade",
}
TOOL_TEXT = {
    "get_costar_record": "CoStar record", "get_vexcel_overhead": "Vexcel overhead",
    "get_vexcel_wider_context": "wider Vexcel context", "find_matterport_scans": "Matterport scans",
    "get_matterport_rooms": "scan rooms", "get_panoramas": "panoramas", "inspect_roof": "roof inspection",
    "inspect_interior": "interior inspection", "label_rooms": "room labels", "finish": "finished",
}


def enabled() -> bool:
    return os.getenv("AGENTIC_SURVEY", "true").strip().lower() not in ("0", "false", "no", "off")


class Step(BaseModel):
    """One tool call chosen by Gemini. No free text: nothing the model writes is shown."""
    tool: ToolName
    purpose: Purpose
    because: list[str] = []  # fact ids from "Facts so far"
    model_id: str | None = None
    room_ids: list[str] = []
    count: int | None = None


class ToolError(ValueError):
    """A tool call the agent can fix (wrong order, unknown id): returned to it as the result."""


class Outcome(BaseModel):
    """What a tool actually returned: `result` goes to the next prompt, `done` to the feed."""
    result: str
    done: str
    evidence: str | None = None  # an image the tool returned


def _unknown(tool: str, why: str) -> Outcome:
    return Outcome(result=f"{UNKNOWN} ({why})", done=f"{TOOL_TEXT[tool]} {UNKNOWN}")


def _c(x: float) -> str:
    return f"{x:.2f}"


class Investigation:
    """State of one building's investigation; each tool is a method returning an Outcome."""

    def __init__(self, profile: BuildingProfile, run_id: str | None, goal: Goal | None, hero: bool = False):
        self.profile, self.run_id, self.goal, self.hero = profile, run_id, goal, hero
        self.history: list[dict] = []  # {tool, args, purpose, because, result, shown, quoted}
        self.facts: dict[str, dict] = {}  # id -> {text, source}; set only from tool returns
        self.record: dict | None = None
        self.overhead: ImageRef | None = None
        self.wide: ImageRef | None = None
        self.scans: list[dict] = []
        self.model_id: str | None = None
        self.room_info: list[dict] = []
        self.all_panos: list[PanoramaRef] = []
        self.base_panos: list[PanoramaRef] = []
        self.base_images: list[ImageRef] = []
        self.room_images: dict[str, list[str]] = {}
        self.room_imgs: list[ImageRef] = []
        self.aerial: aerial.AerialResult | None = None
        self.interior_obs: interior.InteriorObservation | None = None
        self.room_obs: interior.RoomLabelsObservation | None = None
        self.labelled: list[str] = []
        self._profile_facts()

    # ----------------------------------------------------------------- facts

    def fact(self, fid: str, text: str, source: str) -> None:
        self.facts[fid] = {"text": text, "source": source}

    def _profile_facts(self) -> None:
        """From the records agent's CoStar profile and the kit's scan index (tool returns of the survey)."""
        p, src = self.profile, "CoStar record"
        self.fact("built", f"built {p.year_built}" if p.year_built else f"year built {UNKNOWN}", src)
        self.fact("stories", f"{p.stories} stories" if p.stories else f"stories {UNKNOWN}", src)
        n = len(self.scan_ids())
        self.fact("scans_linked", f"{n} scan{'s' if n != 1 else ''} linked" if n else "no scans linked",
                  "CoStar models index")

    # ----------------------------------------------------------------- events

    def emit(self, kind: str, msg: str, agent: str = AGENT, evidence: str | None = None) -> None:
        if self.run_id:
            emit(self.run_id, agent, kind, msg, self.profile.building_id, evidence,
                 building_name=self.profile.name)

    def compose(self, step: Step, outcome: Outcome) -> tuple[str, list[str]]:
        """Feed line from the tool's actual outcome + the cited facts that exist (whole facts that fit)."""
        msg = f"{outcome.done}: {PURPOSE_TEXT[step.purpose]}"
        quoted: list[str] = []
        for fid in dict.fromkeys(step.because):  # de-duplicated, in order
            f = self.facts.get(fid)
            if f is None:
                continue  # cited a fact no tool returned: not shown
            add = f"{'; ' if quoted else ', given '}{f['text']}"
            if len(msg) + len(add) > MAX_FEED:
                break
            msg += add
            quoted.append(fid)
        return msg[:MAX_FEED], quoted

    # ----------------------------------------------------------------- prompt

    def building_card(self) -> str:
        p = self.profile
        lines = [f"- Name: {p.name}", f"- Type: {p.property_type}" + (f", class {p.building_class}" if p.building_class else "")]
        if p.rba_sqft:
            lines.append(f"- Rentable area: {p.rba_sqft:,.0f} sq ft")
        if self.profile.matterport_model_id:
            lines.append(f"- Preferred scan (the portfolio's 3D tour): `{self.profile.matterport_model_id}`")
        return "\n".join(lines)

    def goal_text(self) -> str:
        if not self.goal:
            return "- Cut the portfolio's operational CO2; no budget given."
        g = self.goal
        return (f"- Cut the portfolio's operational CO2 by {g.target_pct:g}%\n"
                f"- Budget: {'none given' if g.budget_usd is None else f'${g.budget_usd:,.0f}'}")

    def prompt(self) -> str:
        hist = "\n".join(f"{n}. `{h['tool']}`{_args_text(h['args'])} ({h['purpose']})\n   → {h['result']}"
                         for n, h in enumerate(self.history, start=1)) or "Nothing yet."
        facts = "\n".join(f"- `{k}`: {v['text']} ({v['source']})" for k, v in self.facts.items())
        return (PROMPT_PATH.read_text()
                .replace("{{goal}}", self.goal_text())
                .replace("{{building}}", self.building_card())
                .replace("{{facts}}", facts)
                .replace("{{history}}", hist)
                .replace("{{purposes}}", ", ".join(f"`{k}`" for k in PURPOSE_TEXT))
                .replace("{{max_calls}}", str(MAX_CALLS))
                .replace("{{max_panos}}", str(MAX_PANOS))
                .replace("{{default_panos}}", str(interior.MAX_PANOS))
                .replace("{{max_rooms}}", str(MAX_ROOMS))
                .replace("{{calls_left}}", str(MAX_CALLS - len(self.history))))

    # ----------------------------------------------------------------- helpers

    def scan_ids(self) -> list[str]:
        entry = records.portfolio_entry(self.profile.building_id) or {}
        ids = list(entry.get("matterport_model_ids") or [])
        if pref := self.profile.matterport_model_id:  # the portfolio's chosen scan (hero tour) first
            ids = [pref] + [i for i in ids if i != pref]
        return ids

    async def _ensure_model(self, model_id: str | None) -> str:
        model_id = model_id or self.model_id or (self.scans[0]["model_id"] if self.scans else None)
        if not model_id:
            raise ToolError("no scan chosen yet: call find_matterport_scans and get_matterport_rooms first")
        if model_id not in self.scan_ids():
            raise ToolError(f"unknown model_id {model_id}: use one from find_matterport_scans")
        if model_id != self.model_id and self.interior_obs is not None:
            raise ToolError(f"scan `{self.model_id}` is already inspected; one scan per building")
        if model_id != self.model_id:
            self.model_id = model_id
            self.room_info = await mp.room_panos(model_id)
            self.all_panos = await mp.panoramas(model_id)
            self.base_panos, self.base_images, self.room_images, self.room_imgs = [], [], {}, []
            self.interior_obs = self.room_obs = None
            self.labelled = []
        return model_id

    def _room_ids(self, ids: list[str]) -> list[str]:
        known = {r["room_id"]: r["room_id"] for r in self.room_info}
        known.update({interior.short_id(r): r for r in list(known)})
        out = []
        for i in ids:
            rid = known.get(i) or next((r for r in known.values() if r.startswith(i)), None)
            if rid and rid not in out:
                out.append(rid)
        return out[:MAX_ROOMS]

    # ----------------------------------------------------------------- tools

    async def get_costar_record(self, step: Step) -> Outcome:
        rec = await costar.get_property(self.profile.costar_id)
        if not rec:
            return _unknown("get_costar_record", "record empty")
        office = rec.get("propertyOffice") or {}
        fields = {
            "year built": rec.get("yearBuilt") or rec.get("yearBuiltDate"),
            "year renovated": rec.get("yearRenovated") or rec.get("renovatedYear"),
            "stories": rec.get("numStoriesAboveGrade"),
            "typical floor sq ft": rec.get("grossTypicalFloorSquareFeet"),
            "rentable sq ft": rec.get("rentableBuildingAreaSquareFeet"),
            "slab-to-slab height ft": (office.get("structural") or {}).get("slabToSlabHeightFeet"),
        }
        self.record = {k: (UNKNOWN if v in (None, "") else v) for k, v in fields.items()}
        renov = self.record["year renovated"]
        self.fact("renovated", f"renovated {renov}" if renov != UNKNOWN else f"renovation {UNKNOWN}", "CoStar record")
        return Outcome(result="; ".join(f"{k}: {v}" for k, v in self.record.items()), done="read CoStar record")

    async def get_vexcel_overhead(self, step: Step) -> Outcome:
        imgs = await vexcel.overhead(geometry.point_wkt(self.profile.lat, self.profile.lon),
                                     vexcel.overhead_buffer_m(self.profile.rba_sqft, self.profile.stories),
                                     city=self.profile.city)
        if not imgs:
            return _unknown("get_vexcel_overhead", "no image returned")
        self.overhead = imgs[0]
        cm = f"{self.overhead.gsd_m * 100:.0f} cm/px" if self.overhead.gsd_m else f"resolution {UNKNOWN}"
        self.emit("fetch", f"overhead image ({cm})", "Aerial", self.overhead.image_id)
        return Outcome(result=f"overhead image `{self.overhead.image_id}`, {cm}, roof at the centre",
                       done="pulled Vexcel overhead", evidence=self.overhead.image_id)

    async def get_vexcel_wider_context(self, step: Step) -> Outcome:
        buf = vexcel.overhead_buffer_m(self.profile.rba_sqft, self.profile.stories) * WIDE_FACTOR
        imgs = await vexcel.overhead(geometry.point_wkt(self.profile.lat, self.profile.lon), buf,
                                     city=self.profile.city)
        if not imgs:
            self.fact("wider_context", f"wider context {UNKNOWN}", "Vexcel")
            return _unknown("get_vexcel_wider_context", "no image returned")
        self.wide = imgs[0]
        across = f"{2 * buf:,.0f} m"
        self.fact("wider_context", f"wider view {across} across", "Vexcel")
        self.emit("fetch", f"wider overhead context ({across} across) for shading", "Aerial", self.wide.image_id)
        return Outcome(result=f"wider overhead `{self.wide.image_id}`, {across} across; inspect_roof will now "
                              "also see neighbours and trees",
                       done=f"pulled wider Vexcel context ({across})", evidence=self.wide.image_id)

    async def find_matterport_scans(self, step: Step) -> Outcome:
        ids = self.scan_ids()
        if not ids:
            self.fact("scans_found", "no scans", "CoStar models index")
            return Outcome(result="no Matterport scans are linked to this building in CoStar",
                           done="no Matterport scans linked")
        out, rows = [], []
        for mid in ids[:MAX_SCANS_LISTED]:
            try:
                b = await mp.basics(mid)
            except Exception as e:  # noqa: BLE001 - recorded as unknown, never skipped silently
                rows.append(f"`{mid}`: {UNKNOWN} (Matterport {type(e).__name__})")
                continue
            s = {"model_id": mid, "name": b.get("name") or UNKNOWN, "rooms": len(b.get("rooms") or []),
                 "panoramas": len(b.get("panoLocations") or [])}
            out.append(s)
            rows.append(f"`{mid}` \"{s['name']}\": {s['rooms']} rooms, {s['panoramas']} panoramas")
        hero = self.profile.matterport_model_id
        self.scans = sorted((s for s in out if s["panoramas"]), key=lambda s: (s["model_id"] != hero, -s["panoramas"]))
        more = f" ({len(ids) - MAX_SCANS_LISTED} more not listed)" if len(ids) > MAX_SCANS_LISTED else ""
        n = len(self.scans)
        self.fact("scans_found", f"{n} scan{'s' if n != 1 else ''} with panoramas" if out else f"scans {UNKNOWN}",
                  "Matterport")
        if not out:
            return _unknown("find_matterport_scans", "; ".join(rows))
        return Outcome(result=f"{len(ids)} scans linked{more}: " + "; ".join(rows),
                       done=f"found {n} scan{'s' if n != 1 else ''} with panoramas")

    async def get_matterport_rooms(self, step: Step) -> Outcome:
        mid = await self._ensure_model(step.model_id)
        rows = []
        for r in self.room_info:
            area = (r.get("dimensions") or {}).get("areaFloor")
            tags = ", ".join((r.get("tags") or []) + (r.get("keywords") or [])) or "none"
            rows.append(f"`{interior.short_id(r['room_id'])}` "
                        f"{'%.0f sq ft' % (area * 10.7639) if area else f'size {UNKNOWN}'}, "
                        f"{len(r['pano_ids'])} panoramas, Matterport tags: {tags}")
        n, k = len(self.room_info), len(self.all_panos)
        self.fact("scan_rooms", f"scan has {n} room{'s' if n != 1 else ''}", "Matterport")
        self.emit("fetch", f"Matterport scan: {n} rooms, {k} panoramas", interior.AGENT)
        return Outcome(result=f"scan `{mid}`: {n} rooms, {k} panoramas. Rooms: " + ("; ".join(rows) or "none"),
                       done=f"listed {n} room{'s' if n != 1 else ''}, {k} panoramas")

    async def get_panoramas(self, step: Step) -> Outcome:
        mid = await self._ensure_model(step.model_id)
        if step.room_ids:
            return await self._room_panoramas(mid, step.room_ids)
        k = max(1, min(MAX_PANOS, step.count or interior.MAX_PANOS))
        if self.base_panos and k == len(self.base_panos):
            raise ToolError(f"those {k} panoramas are already pulled; ask for more (up to {MAX_PANOS}) or move on")
        if k > len(self.all_panos) and self.base_panos and len(self.base_panos) >= len(self.all_panos):
            raise ToolError("every panorama of this scan is already pulled")
        self.base_panos, self.base_images = await interior.fetch_images(mid, k)
        self.interior_obs = None
        n = len(self.base_panos)
        if not n:
            return _unknown("get_panoramas", "no panoramas returned")
        return Outcome(result=f"{n} panoramas spread across the scan, {len(self.base_images)} views "
                              "(ceiling + two horizon faces each), ready for inspect_interior",
                       done=f"pulled {n} panorama{'s' if n != 1 else ''}", evidence=self.base_images[0].image_id)

    async def _room_panoramas(self, mid: str, ids: list[str]) -> Outcome:
        rids = [r for r in self._room_ids(ids) if r not in self.room_images]
        if not rids and not self._room_ids(ids):
            raise ToolError("unknown room_ids: use the ids from get_matterport_rooms")
        subset = [r for r in self.room_info if r["room_id"] in rids]
        imgs_by_room, imgs = await interior.fetch_room_images(mid, subset, self.all_panos)
        self.room_images.update(imgs_by_room)
        have = {i.image_id for i in self.room_imgs}
        self.room_imgs += [i for i in imgs if i.image_id not in have and not have.add(i.image_id)]
        got = sum(1 for r in subset if imgs_by_room.get(r["room_id"]))
        if subset and not imgs:
            return _unknown("get_panoramas", "no room panoramas returned")
        return Outcome(result=f"{len(imgs)} views from {got} rooms ready for label_rooms" if subset else "already pulled",
                       done=f"pulled panoramas of {got} room{'s' if got != 1 else ''}",
                       evidence=imgs[0].image_id if imgs else None)

    async def inspect_roof(self, step: Step) -> Outcome:
        if self.overhead is None:
            got = await self.get_vexcel_overhead(step)
            if self.overhead is None:
                return got
        images = [self.overhead] + ([self.wide] if self.wide else [])
        self.aerial = await aerial.inspect(self.profile, self.run_id, images=images)
        o = self.aerial.obs
        frac = UNKNOWN if o.usable_roof_fraction.value is None else _c(o.usable_roof_fraction.value)
        src = "roof inspection" + (" with wider context" if self.wide else "")
        self.fact("roof", f"roof {o.roof_type.value}, {o.roof_color.value}", src)
        self.fact("usable_roof", f"usable roof {UNKNOWN}" if frac == UNKNOWN else
                  f"usable roof {o.usable_roof_fraction.value:.0%}", src)
        self.fact("shading", f"shading {o.shading.value}", src)
        self.fact("existing_solar", f"existing solar {o.existing_solar.value}", src)
        return Outcome(result=(f"roof {o.roof_type.value} ({_c(o.roof_type.confidence)}), {o.roof_color.value} "
                               f"({_c(o.roof_color.confidence)}); usable fraction {frac} "
                               f"({_c(o.usable_roof_fraction.confidence)}); shading {o.shading.value} "
                               f"({_c(o.shading.confidence)}); existing solar {o.existing_solar.value} "
                               f"({_c(o.existing_solar.confidence)})"
                               + ("" if self.wide else "; wider context not pulled")),
                       done="re-inspected roof with context" if self.wide else "inspected roof",
                       evidence=self.overhead.image_id)

    async def inspect_interior(self, step: Step) -> Outcome:
        if self.interior_obs is not None and not step.count:
            raise ToolError("already inspected these panoramas; pass a larger count for new ones, or move on")
        if not self.base_images or (step.count and min(step.count, MAX_PANOS) != len(self.base_panos)):
            got = await self.get_panoramas(Step(tool="get_panoramas", purpose=step.purpose,
                                                model_id=step.model_id, count=step.count))
            if not self.base_images:
                return got
        failed = None
        try:
            obs = await llm.vision_json(interior.prompt_for(self.profile, self.base_images, self.base_panos),
                                        self.base_images, interior.InteriorObservation)
        except Exception as e:  # noqa: BLE001 - same fallback as the fixed inspector: unknowns
            log.warning("interior inspector failed for %s: %s", self.profile.building_id, e)
            failed = type(e).__name__
            self.emit("error", f"vision model failed ({failed}); interior marked unknown", interior.AGENT)
            obs = interior.unknown_observation()
        self.interior_obs = obs
        hv = (", ".join(i.replace("_", " ") for i in obs.hvac.items) if obs.hvac.items
              else UNKNOWN if failed or obs.hvac.confidence == 0 else "none seen")
        n = len(self.base_panos)
        self.fact("lighting", f"lighting {obs.lighting.value}", "interior inspection")
        self.fact("hvac", f"HVAC {hv}", "interior inspection")
        self.fact("windows", f"windows {obs.window.value}", "interior inspection")
        self.emit("observe", f"lighting {obs.lighting.value}; HVAC {hv}", interior.AGENT, self.base_images[0].image_id)
        return Outcome(result=(f"from {n} panoramas: lighting {obs.lighting.value} ({_c(obs.lighting.confidence)}); "
                               f"HVAC {hv} ({_c(obs.hvac.confidence)}); windows {obs.window.value} "
                               f"({_c(obs.window.confidence)})" + (f"; vision model failed ({failed})" if failed else "")),
                       done=f"inspected interior ({n} panorama{'s' if n != 1 else ''})",
                       evidence=self.base_images[0].image_id)

    async def label_rooms(self, step: Step) -> Outcome:
        if self.interior_obs is None:
            raise ToolError("call inspect_interior before label_rooms")
        if not self.room_info:
            await self._ensure_model(step.model_id)
        rids = self._room_ids(step.room_ids or [r["room_id"] for r in self.room_info])
        if not rids:
            raise ToolError("unknown room_ids: use the ids from get_matterport_rooms")
        await self._room_panoramas(self.model_id, rids)
        subset = [r for r in self.room_info if r["room_id"] in rids and self.room_images.get(r["room_id"])]
        if not subset:
            return _unknown("label_rooms", "no room panoramas returned")
        by_id = {i.image_id: i for i in self.base_images + self.room_imgs}
        new = await interior.label_rooms(self.profile, subset, self.room_images, by_id)
        fresh = {o.room_id: o for o in new.rooms if o.room_id in {r["room_id"] for r in subset}}
        if not fresh:
            return _unknown("label_rooms", "no labels returned")
        kept = [o for o in (self.room_obs.rooms if self.room_obs else []) if o.room_id not in fresh]
        self.room_obs = interior.RoomLabelsObservation(rooms=kept + list(fresh.values()))
        self.labelled = [r for r in self.labelled if r not in fresh] + list(fresh)
        n = len(fresh)
        self.fact("room_labels", ", ".join(o.type.replace("_", " ") for o in fresh.values()), "room labelling")
        return Outcome(result="; ".join(f"`{interior.short_id(o.room_id)}` {o.type}"
                                        + (f" + {', '.join(o.also_contains)}" if o.also_contains else "")
                                        + f" ({_c(o.confidence)})" for o in fresh.values()),
                       done=f"labelled {n} room{'s' if n != 1 else ''}",
                       evidence=self.room_images[next(iter(fresh))][0])

    # ----------------------------------------------------------------- loop

    async def decide(self) -> Step:
        return await llm.text_json(self.prompt(), Step)

    async def call(self, step: Step) -> Outcome:
        """Run one tool; a failure or an empty return becomes 'unknown', never a guess."""
        if step.tool == "finish":
            return Outcome(result="done", done="finished")
        try:
            return await getattr(self, step.tool)(step)
        except ToolError as e:  # wrong order / unknown id: the agent can fix it
            return Outcome(result=f"{UNKNOWN} (refused: {e})", done=f"{TOOL_TEXT[step.tool]} refused")
        except Exception as e:  # noqa: BLE001 - adapter/API failure: unknown, and tell the agent
            log.warning("tool %s failed for %s: %s", step.tool, self.profile.building_id, e)
            self.emit("error", f"{TOOL_TEXT[step.tool]} failed ({type(e).__name__})")
            return _unknown(step.tool, f"failed: {type(e).__name__}")

    def record_step(self, step: Step, outcome: Outcome) -> None:
        shown, quoted = self.compose(step, outcome)
        self.emit("decide", shown, evidence=outcome.evidence)
        self.history.append({"tool": step.tool, "args": _args(step), "purpose": step.purpose,
                             "because": step.because, "result": outcome.result, "shown": shown,
                             "quoted": {f: self.facts[f] for f in quoted}, "evidence": outcome.evidence})

    async def run(self) -> None:
        while len(self.history) < MAX_CALLS:
            try:
                step = await self.decide()
            except Exception as e:  # noqa: BLE001 - no decision: stop here; required steps still run
                log.warning("investigator decision failed for %s: %s", self.profile.building_id, e)
                self.emit("error", f"investigator could not decide ({type(e).__name__}); finishing")
                break
            self.record_step(step, await self.call(step))
            if step.tool == "finish":
                break
        else:
            self.emit("decide", "call limit reached; finishing")

        if self.aerial is None:  # required for every building
            self.emit("decide", "roof inspection is required for pricing; inspecting it before finishing")
            step = Step(tool="inspect_roof", purpose="solar_evidence")
            out = await self.inspect_roof(step)
            if self.aerial is None:
                raise RuntimeError(f"roof could not be inspected: {out.result}")  # → fixed pipeline fallback
            self.record_step(step, out)

    # ----------------------------------------------------------------- outputs

    async def interior_result(self) -> interior.InteriorResult | None:
        if self.interior_obs is None or not self.model_id:
            return None
        mid, profile = self.model_id, self.profile
        try:
            scan = interior.scan_areas(await mp.rooms(mid), profile)
        except Exception as e:  # noqa: BLE001 - floor area unknown, not zero
            log.warning("scan rooms failed for %s: %s", mid, e)
            scan = {"rooms": [], "scanned_floor_area_sqft": None, "coverage_of_rba": None, "wall_edges": None,
                    "floorplans": [], "rooms_error": type(e).__name__}
        findings, claims = interior.build_findings(profile, mid, self.interior_obs, self.base_images,
                                                   self.base_panos, scan)
        info = [r for r in self.room_info if r["room_id"] in self.labelled]
        findings, claims = interior.add_rooms(profile, findings, claims, info, self.room_images, self.room_obs,
                                              self.all_panos)
        known = {i.image_id for i in self.base_images}
        images = self.base_images + [i for i in self.room_imgs if i.image_id not in known]
        findings = findings.model_copy(update={"evidence_ids": sorted({i.image_id for i in images})})
        self.emit("observe", f"windows {findings.window_type}; {len(findings.pins)} findings pinned in 3D",
                  interior.AGENT)
        for n, r in enumerate(findings.rooms, start=1):
            self.emit("observe", f"room {n} ({interior.short_id(r.room_id)}): "
                                 f"{interior.room_title(r.type, r.also_contains).lower()}", interior.AGENT,
                      self.room_images.get(r.room_id, [None])[0])
        try:
            paths = await mp.matterpak(mid)
            scan["mesh"] = {"obj": Path(paths.obj).name if paths.obj else None,
                            "mtl": Path(paths.mtl).name if paths.mtl else None}
        except Exception as e:  # noqa: BLE001 - mesh is optional
            scan["mesh"], scan["mesh_error"] = None, str(e)[:200]
            self.emit("error", "3D mesh not available from Matterport yet", interior.AGENT)
        return interior.InteriorResult(model_id=mid, images=images, panos=self.base_panos, obs=self.interior_obs,
                                       findings=findings, claims=claims, scan=scan,
                                       room_info=info, room_images={r["room_id"]: self.room_images[r["room_id"]]
                                                                    for r in info if r["room_id"] in self.room_images},
                                       room_obs=self.room_obs, all_panos=self.all_panos)

    async def use_scan_in_profile(self) -> BuildingProfile:
        """A non-hero building whose scan the agent inspected: record the model (and tour link)."""
        if not self.model_id or self.model_id == self.profile.matterport_model_id:
            return self.profile
        url = await records.showcase_url(self.model_id)
        src = {**self.profile.source_fields,
               "matterport_model_id": "models_index.csv via CoStar PropertyId (chosen by the investigator)"}
        if url:
            src["showcase_url"] = "Matterport model visibility (public) + model id"
        self.profile = self.profile.model_copy(update={"matterport_model_id": self.model_id, "showcase_url": url,
                                                      "source_fields": src})
        write_json_atomic(records.profile_path(self.profile.building_id), self.profile.model_dump(mode="json"))
        return self.profile

    def images_returned(self) -> set[str]:
        """Every image id a tool returned in this investigation."""
        imgs = [self.overhead, self.wide] + self.base_images + self.room_imgs
        return {i.image_id for i in imgs if i is not None}

    def save_trace(self) -> None:
        from app.agents import store
        write_json_atomic(store.building_dir(self.profile.building_id) / "investigation.json",
                          {"building_id": self.profile.building_id, "run_id": self.run_id, "max_calls": MAX_CALLS,
                           "facts": self.facts, "steps": self.history})


def _args(step: Step) -> dict:
    return {k: v for k, v in (("model_id", step.model_id), ("room_ids", step.room_ids), ("count", step.count)) if v}


def _args_text(args: dict) -> str:
    return f" {args}" if args else ""


async def investigate(profile: BuildingProfile, run_id: str | None, goal: Goal | None,
                      hero: bool = False) -> dict[str, Any]:
    """Run the investigator for one building; returns the survey-state update inspect_node returns."""
    inv = Investigation(profile, run_id, goal, hero)
    await inv.run()
    inter = await inv.interior_result()
    if inter is not None:
        await inv.use_scan_in_profile()
    inv.save_trace()
    claims: list[Claim] = list(inv.aerial.claims) + (list(inter.claims) if inter else [])
    return {"profile": inv.profile, "aerial": inv.aerial, "interior": inter, "claims": claims,
            "investigation": inv.history}
