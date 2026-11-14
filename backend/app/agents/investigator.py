"""Investigator: one Gemini agent per building that decides which data to pull, in what order,
and when to stop (AGENTIC_SURVEY, default on).

Loop: Gemini sees the owner's goal, the CoStar record, the tool list and everything pulled so
far, and returns one validated tool call {tool, args, reason}. Code runs that tool through the
existing adapters and inspectors (so every external call is cached and replayable), and appends
the result to the next prompt. At most MAX_CALLS calls per building (`finish` included);
temperature 0 (llm.py). Each step emits an "Investigator" activity event with its reason.

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

from pydantic import BaseModel, Field

from app.adapters import costar, geometry, vexcel
from app.adapters import matterport as mp
from app.adapters.types import ImageRef, PanoramaRef
from app.adapters.cache import write_json_atomic
from app.agents import aerial, interior, llm, records
from app.events import emit
from app.guardrails import check_numbers
from app.schemas.claims import Claim
from app.schemas.goal import Goal
from app.schemas.profile import BuildingProfile

log = logging.getLogger(__name__)
AGENT = "Investigator"
PROMPT_PATH = Path(__file__).parent / "prompts" / "investigator.md"
MAX_CALLS = 8
MAX_ROOMS = 4
MAX_SCANS_LISTED = 4
MAX_FEED = 90  # events.MAX_MESSAGE: "<action>: <reason>" must fit
WIDE_FACTOR = 3.0  # wider context: 3x the building's own crop (neighbours, trees)

ToolName = Literal["get_costar_record", "get_vexcel_overhead", "get_vexcel_wider_context",
                   "find_matterport_scans", "get_matterport_rooms", "get_panoramas", "inspect_roof",
                   "inspect_interior", "label_rooms", "finish"]


def enabled() -> bool:
    return os.getenv("AGENTIC_SURVEY", "true").strip().lower() not in ("0", "false", "no", "off")


class Step(BaseModel):
    """One tool call chosen by Gemini."""
    reason: str = Field(description="One short sentence for the activity feed, no numbers")
    tool: ToolName
    model_id: str | None = None
    room_ids: list[str] = []
    count: int | None = None


class Investigation:
    """State of one building's investigation; each tool is a method returning a text result."""

    def __init__(self, profile: BuildingProfile, run_id: str | None, goal: Goal | None, hero: bool = False):
        self.profile, self.run_id, self.goal, self.hero = profile, run_id, goal, hero
        self.history: list[dict] = []  # {tool, args, reason, result}
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

    # ----------------------------------------------------------------- events

    def emit(self, kind: str, msg: str, agent: str = AGENT, evidence: str | None = None) -> None:
        if self.run_id:
            emit(self.run_id, agent, kind, msg[:160], self.profile.building_id, evidence,
                 building_name=self.profile.name)

    # ----------------------------------------------------------------- prompt

    def building_card(self) -> str:
        p = self.profile
        lines = [f"- Name: {p.name}", f"- Type: {p.property_type}" + (f", class {p.building_class}" if p.building_class else "")]
        if p.year_built:
            lines.append(f"- Year built: {p.year_built}")
        if p.stories:
            lines.append(f"- Stories above grade: {p.stories}")
        if p.rba_sqft:
            lines.append(f"- Rentable area: {p.rba_sqft:,.0f} sq ft")
        lines.append(f"- Matterport scans linked in CoStar: {len(self.scan_ids())}")
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
        hist = "\n".join(f"{n}. `{h['tool']}`{_args_text(h['args'])}: {h['reason']}\n   → {h['result']}"
                         for n, h in enumerate(self.history, start=1)) or "Nothing yet."
        return (PROMPT_PATH.read_text()
                .replace("{{goal}}", self.goal_text())
                .replace("{{building}}", self.building_card())
                .replace("{{history}}", hist)
                .replace("{{max_calls}}", str(MAX_CALLS))
                .replace("{{max_panos}}", str(interior.MAX_PANOS))
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

    async def get_costar_record(self, step: Step) -> str:
        rec = await costar.get_property(self.profile.costar_id)
        office = rec.get("propertyOffice") or {}
        fields = {
            "year built": rec.get("yearBuilt") or self.profile.year_built,
            "year renovated": rec.get("yearRenovated") or rec.get("renovatedYear"),
            "stories": rec.get("numStoriesAboveGrade"),
            "typical floor sq ft": rec.get("grossTypicalFloorSquareFeet"),
            "rentable sq ft": rec.get("rentableBuildingAreaSquareFeet"),
            "lot size": rec.get("lotSize"),
            "parking ratio": rec.get("parkingRatio"),
            "slab-to-slab height ft": (office.get("structural") or {}).get("slabToSlabHeightFeet"),
            "occupancy %": self.profile.occupancy_pct,
            "footprint": "estimated from typical floor (no footprint in the record)"
            if self.profile.footprint_source == "estimated" else "from CoStar",
            "Matterport scans linked": len(self.scan_ids()),
        }
        self.record = {k: v for k, v in fields.items() if v not in (None, "")}
        return "; ".join(f"{k}: {v}" for k, v in self.record.items())

    async def get_vexcel_overhead(self, step: Step) -> str:
        imgs = await vexcel.overhead(geometry.point_wkt(self.profile.lat, self.profile.lon),
                                     vexcel.overhead_buffer_m(self.profile.rba_sqft, self.profile.stories),
                                     city=self.profile.city)
        self.overhead = imgs[0]
        self.emit("fetch", f"overhead image ({self.overhead.gsd_m * 100:.0f} cm/px)", "Aerial", self.overhead.image_id)
        return f"overhead image `{self.overhead.image_id}`, {self.overhead.gsd_m * 100:.0f} cm per pixel, roof at the centre"

    async def get_vexcel_wider_context(self, step: Step) -> str:
        buf = vexcel.overhead_buffer_m(self.profile.rba_sqft, self.profile.stories) * WIDE_FACTOR
        imgs = await vexcel.overhead(geometry.point_wkt(self.profile.lat, self.profile.lon), buf,
                                     city=self.profile.city)
        self.wide = imgs[0]
        self.emit("fetch", f"wider overhead context ({2 * buf:,.0f} m across) for shading", "Aerial", self.wide.image_id)
        return (f"wider overhead `{self.wide.image_id}`, {2 * buf:,.0f} m across, {self.wide.gsd_m * 100:.0f} cm per "
                "pixel; inspect_roof will now also see neighbours and trees")

    async def find_matterport_scans(self, step: Step) -> str:
        ids = self.scan_ids()
        if not ids:
            return "no Matterport scans are linked to this building in CoStar"
        out = []
        for mid in ids[:MAX_SCANS_LISTED]:
            try:
                b = await mp.basics(mid)
            except Exception as e:  # noqa: BLE001 - a private or broken model: skip it
                log.info("scan %s unavailable: %s", mid, e)
                continue
            out.append({"model_id": mid, "name": b.get("name") or "", "rooms": len(b.get("rooms") or []),
                        "panoramas": len(b.get("panoLocations") or []), "visibility": b.get("visibility")})
        out = [s for s in out if s["panoramas"]]
        hero = self.profile.matterport_model_id
        self.scans = sorted(out, key=lambda s: (s["model_id"] != hero, -s["panoramas"]))
        if not self.scans:
            return f"{len(ids)} scans linked, none with panoramas available"
        more = f" ({len(ids) - MAX_SCANS_LISTED} more not listed)" if len(ids) > MAX_SCANS_LISTED else ""
        return f"{len(ids)} scans linked{more}: " + "; ".join(
            f"`{s['model_id']}` \"{s['name']}\": {s['rooms']} rooms, {s['panoramas']} panoramas" for s in self.scans)

    async def get_matterport_rooms(self, step: Step) -> str:
        mid = await self._ensure_model(step.model_id)
        rows = []
        for r in self.room_info:
            area = (r.get("dimensions") or {}).get("areaFloor")
            tags = ", ".join((r.get("tags") or []) + (r.get("keywords") or [])) or "none"
            rows.append(f"`{interior.short_id(r['room_id'])}` "
                        f"{'%.0f sq ft' % (area * 10.7639) if area else 'size unknown'}, "
                        f"{len(r['pano_ids'])} panoramas, Matterport tags: {tags}")
        self.emit("fetch", f"Matterport scan: {len(self.room_info)} rooms, {len(self.all_panos)} panoramas",
                  interior.AGENT)
        return f"scan `{mid}`: {len(self.room_info)} rooms, {len(self.all_panos)} panoramas. Rooms: " + "; ".join(rows)

    async def get_panoramas(self, step: Step) -> str:
        mid = await self._ensure_model(step.model_id)
        if step.room_ids:
            return await self._room_panoramas(mid, step.room_ids)
        k = max(1, min(interior.MAX_PANOS, step.count or interior.MAX_PANOS))
        self.base_panos, self.base_images = await interior.fetch_images(mid, k)
        self.interior_obs = None
        return (f"{len(self.base_panos)} panoramas spread across the scan, {len(self.base_images)} views "
                "(ceiling + two horizon faces each), ready for inspect_interior")

    async def _room_panoramas(self, mid: str, ids: list[str]) -> str:
        rids = [r for r in self._room_ids(ids) if r not in self.room_images]
        if not rids and not self._room_ids(ids):
            raise ToolError("unknown room_ids: use the ids from get_matterport_rooms")
        subset = [r for r in self.room_info if r["room_id"] in rids]
        imgs_by_room, imgs = await interior.fetch_room_images(mid, subset, self.all_panos)
        self.room_images.update(imgs_by_room)
        have = {i.image_id for i in self.room_imgs}
        self.room_imgs += [i for i in imgs if i.image_id not in have and not have.add(i.image_id)]
        return f"{len(imgs)} views from {len(subset)} rooms ready for label_rooms" if subset else "already pulled"

    async def inspect_roof(self, step: Step) -> str:
        if self.overhead is None:
            await self.get_vexcel_overhead(step)
        images = [self.overhead] + ([self.wide] if self.wide else [])
        self.aerial = await aerial.inspect(self.profile, self.run_id, images=images)
        o = self.aerial.obs
        return (f"roof {o.roof_type.value} ({o.roof_type.confidence:.2f}), {o.roof_color.value} "
                f"({o.roof_color.confidence:.2f}); usable fraction "
                f"{'unknown' if o.usable_roof_fraction.value is None else f'{o.usable_roof_fraction.value:.2f}'} "
                f"({o.usable_roof_fraction.confidence:.2f}); shading {o.shading.value} ({o.shading.confidence:.2f}); "
                f"existing solar {o.existing_solar.value} ({o.existing_solar.confidence:.2f})"
                + ("" if self.wide else "; wider context not pulled"))

    async def inspect_interior(self, step: Step) -> str:
        if not self.base_images or (step.count and step.count != len(self.base_panos)):
            await self.get_panoramas(Step(reason="", tool="get_panoramas", model_id=step.model_id, count=step.count))
        try:
            obs = await llm.vision_json(interior.prompt_for(self.profile, self.base_images, self.base_panos),
                                        self.base_images, interior.InteriorObservation)
        except Exception as e:  # noqa: BLE001 - same fallback as the fixed inspector
            log.warning("interior inspector failed for %s: %s", self.profile.building_id, e)
            self.emit("error", f"vision model failed ({type(e).__name__}); interior marked unknown", interior.AGENT)
            obs = interior.unknown_observation()
        self.interior_obs = obs
        hv = ", ".join(i.replace("_", " ") for i in obs.hvac.items) or "none seen"
        self.emit("observe", f"lighting {obs.lighting.value}; HVAC {hv}"[:90], interior.AGENT,
                  self.base_images[0].image_id)
        return (f"lighting {obs.lighting.value} ({obs.lighting.confidence:.2f}); HVAC {hv} "
                f"({obs.hvac.confidence:.2f}); windows {obs.window.value} ({obs.window.confidence:.2f})")

    async def label_rooms(self, step: Step) -> str:
        if self.interior_obs is None:
            raise ToolError("call inspect_interior before label_rooms")
        if not self.room_info:
            await self._ensure_model(step.model_id)
        rids = self._room_ids(step.room_ids or [r["room_id"] for r in self.room_info])
        if not rids:
            raise ToolError("unknown room_ids: use the ids from get_matterport_rooms")
        await self._room_panoramas(self.model_id, rids)
        subset = [r for r in self.room_info if r["room_id"] in rids]
        by_id = {i.image_id: i for i in self.base_images + self.room_imgs}
        new = await interior.label_rooms(self.profile, subset, self.room_images, by_id)
        fresh = {o.room_id: o for o in new.rooms if o.room_id in rids}
        kept = [o for o in (self.room_obs.rooms if self.room_obs else []) if o.room_id not in fresh]
        self.room_obs = interior.RoomLabelsObservation(rooms=kept + list(fresh.values()))
        self.labelled = [r for r in self.labelled if r not in fresh] + list(fresh)
        return "; ".join(f"`{interior.short_id(o.room_id)}` {o.type}"
                         + (f" + {', '.join(o.also_contains)}" if o.also_contains else "")
                         + f" ({o.confidence:.2f})" for o in fresh.values()) or "no labels returned"

    # ----------------------------------------------------------------- loop

    async def decide(self) -> Step:
        return await llm.text_json(self.prompt(), Step)

    def feed_reason(self, step: Step) -> str:
        room = MAX_FEED - len(action_text(step, self)) - 2
        words, reason = step.reason.split(), ""
        for w in words:  # whole words that fit the feed line (events.MAX_MESSAGE)
            if len(reason) + len(w) + 1 > room:
                break
            reason = f"{reason} {w}".strip()
        reason = reason.rstrip(" .,;:")
        if reason:
            reason = reason[0].lower() + reason[1:]
        sources = [self.profile.model_dump(mode="json"), self.goal.model_dump(mode="json") if self.goal else {},
                   self.record or {}, [h["result"] for h in self.history]]
        if not reason or check_numbers(reason, sources):
            return DEFAULT_REASON[step.tool]
        return reason

    async def run(self) -> None:
        while len(self.history) < MAX_CALLS:
            try:
                step = await self.decide()
            except Exception as e:  # noqa: BLE001 - no decision: stop here; required steps still run
                log.warning("investigator decision failed for %s: %s", self.profile.building_id, e)
                self.emit("error", f"investigator could not decide ({type(e).__name__}); finishing")
                break
            reason = self.feed_reason(step)
            self.emit("decide", f"{action_text(step, self)}: {reason}")
            if step.tool == "finish":
                self.history.append({"tool": "finish", "args": {}, "reason": reason, "result": "done"})
                break
            try:
                result = await getattr(self, step.tool)(step)
            except ToolError as e:
                result = f"error: {e}"
            except Exception as e:  # noqa: BLE001 - tell the agent; it can choose something else
                log.warning("tool %s failed for %s: %s", step.tool, self.profile.building_id, e)
                result = f"error: {type(e).__name__}"
                self.emit("error", f"{step.tool.replace('_', ' ')} failed ({type(e).__name__})")
            self.history.append({"tool": step.tool, "args": _args(step), "reason": reason, "result": result})
        else:
            self.emit("decide", "call limit reached; finishing")

        if self.aerial is None:  # required for every building
            self.emit("decide", "roof inspection is required for pricing; inspecting it before finishing")
            self.history.append({"tool": "inspect_roof", "args": {}, "reason": "required", "result":
                                 await self.inspect_roof(Step(reason="required", tool="inspect_roof"))})

    # ----------------------------------------------------------------- outputs

    async def interior_result(self) -> interior.InteriorResult | None:
        if self.interior_obs is None or not self.model_id:
            return None
        mid, profile = self.model_id, self.profile
        scan = interior.scan_areas(await mp.rooms(mid), profile)
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

    def save_trace(self) -> None:
        from app.agents import store
        write_json_atomic(store.building_dir(self.profile.building_id) / "investigation.json",
                          {"building_id": self.profile.building_id, "run_id": self.run_id, "max_calls": MAX_CALLS,
                           "steps": self.history})


class ToolError(ValueError):
    """A tool call the agent can fix (wrong order, unknown id): returned to it as the result."""


DEFAULT_REASON = {
    "get_costar_record": "checking the CoStar record for details that change what to inspect",
    "get_vexcel_overhead": "need the roof image before judging solar",
    "get_vexcel_wider_context": "shading from neighbours is outside the roof crop",
    "find_matterport_scans": "checking for a 3D scan that could show lighting and HVAC",
    "get_matterport_rooms": "need the scan's rooms to choose what to look at",
    "get_panoramas": "need interior views as evidence",
    "inspect_roof": "reading the roof for solar",
    "inspect_interior": "reading lighting and HVAC for LED and heat pump decisions",
    "label_rooms": "labelling how the scanned space is used",
    "finish": "more evidence would not change an upgrade decision",
}


def _args(step: Step) -> dict:
    return {k: v for k, v in (("model_id", step.model_id), ("room_ids", step.room_ids), ("count", step.count)) if v}


def _args_text(args: dict) -> str:
    return f" {args}" if args else ""


def action_text(step: Step, inv: Investigation) -> str:
    t = step.tool
    if t == "get_panoramas":
        if step.room_ids:
            n = len(inv._room_ids(step.room_ids)) or len(step.room_ids[:MAX_ROOMS])
            return f"pulling panoramas of {n} room{'s' if n != 1 else ''}"
        k = max(1, min(interior.MAX_PANOS, step.count or interior.MAX_PANOS))
        return f"pulling {k} panorama{'s' if k != 1 else ''} across the scan"
    if t == "label_rooms":
        n = len(inv._room_ids(step.room_ids)) if step.room_ids else len(inv.room_info[:MAX_ROOMS])
        return f"labelling {n} room{'s' if n != 1 else ''}"
    return {
        "get_costar_record": "reading the CoStar record",
        "get_vexcel_overhead": "pulling Vexcel overhead",
        "get_vexcel_wider_context": "pulling wider Vexcel context",
        "find_matterport_scans": "looking for Matterport scans",
        "get_matterport_rooms": "listing the scan's rooms",
        "inspect_roof": "re-inspecting roof with context" if inv.aerial and inv.wide else "inspecting roof",
        "inspect_interior": "inspecting interior",
        "finish": "finishing",
    }[t]


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
