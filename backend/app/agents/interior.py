"""Interior inspector (T2.3, hero building): Matterport panoramas + rooms → InteriorFindings.

Gemini looks at up to MAX_PANOS panoramas (ceiling face + two horizon faces each), spread across
the scan, and reports lighting / visible HVAC / window type as claims with marks. Code places a pin
at the 3D scan position of each claim's evidence panorama.

Areas (code, from Matterport room dimensions):
- The scan's measured floor area goes to interior_scan.json. It replaces CoStar's floor area in
  InteriorFindings.floor_area_sqft only when the scan covers ≥ MIN_COVERAGE of the building's RBA;
  a one-suite scan of a large building would otherwise shrink every building-wide upgrade.
- envelope_area_sqft needs the wall graph (exterior walls × floor height × stories). Models with an
  empty wall graph (the hero's) leave it null.
The MatterPak (OBJ mesh) is downloaded when Matterport has it available; otherwise an event says so.

Room annotation (commercial interiors are unlabelled in Matterport): for each room, up to
MAX_PANOS_PER_ROOM of its own panoramas (ModelRoom.panoLocations) go to Gemini in one call, which
labels every room with a commercial type, a confidence and a short evidence note. Each label is a
claim `interior.room.<room_id>` that the verifier checks (and sends back when unsure); each room
gets a pin at the mean scan position of its panoramas. rooms.json (widget Room shape) carries the
types to the floor_plan and hero_3d widgets.
"""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from app.adapters import matterport as mp
from app.adapters.cache import write_json_atomic
from app.adapters.geometry import SQFT_PER_M2
from app.adapters.types import ImageRef, PanoramaRef
from app.agents import llm, store
from app.agents.aerial import Box, _clip01, _marks
from app.events import emit
from app.guardrails import check_numbers
from app.schemas.claims import Claim
from app.schemas.interior import InteriorFindings, Pin, RoomLabel, RoomType
from app.schemas.profile import BuildingProfile

log = logging.getLogger(__name__)
AGENT = "Interior"
PROMPT_PATH = Path(__file__).parent / "prompts" / "interior.md"
ROOMS_PROMPT_PATH = Path(__file__).parent / "prompts" / "interior_rooms.md"
MAX_PANOS = 5
FACES = (0, 1, 3)  # up, and two opposite horizon faces
MIN_COVERAGE = 0.5
MAX_PINS_PER_CLAIM = 3
MAX_PANOS_PER_ROOM = 4
M2_PER_ROOM_PANO = 20.0  # big Matterport "rooms" are often merged regions: show more of them
ROOM_FACES = ((1, 2, 3, 4), (1, 3), (1, 3), (1, 3))  # first pano: all four horizon faces; others: two opposite
TYPE_LABEL = {"open_office": "Open office", "private_office": "Private office", "conference": "Conference room",
              "corridor": "Corridor", "lobby": "Lobby", "restroom": "Restroom", "mechanical_it": "Mechanical / IT",
              "storage": "Storage", "kitchen_break": "Kitchen / break room", "unknown": "Unlabelled room"}

HvacItem = Literal["vav_diffuser", "split_system", "fan_coil", "window_unit", "packaged_terminal",
                   "boiler", "radiator", "exposed_ductwork", "thermostat"]


class LightingObs(BaseModel):
    value: Literal["LED", "fluorescent", "incandescent", "mixed", "unknown"]
    confidence: float
    marks: list[Box] = []


class HvacObs(BaseModel):
    items: list[HvacItem] = Field(default_factory=list)
    confidence: float
    marks: list[Box] = []


class WindowObs(BaseModel):
    value: Literal["single", "double", "unknown"]
    confidence: float
    marks: list[Box] = []


class InteriorObservation(BaseModel):
    lighting: LightingObs
    hvac: HvacObs
    window: WindowObs


class RoomObs(BaseModel):
    room_id: str
    type: RoomType
    also_contains: list[RoomType] = []
    confidence: float
    evidence_note: str = ""
    marks: list[Box] = []


class RoomLabelsObservation(BaseModel):
    rooms: list[RoomObs]


class InteriorResult(BaseModel):
    model_id: str
    images: list[ImageRef]
    panos: list[PanoramaRef]
    obs: InteriorObservation
    findings: InteriorFindings
    claims: list[Claim]
    scan: dict
    room_info: list[dict] = []  # matterport.room_panos()
    room_images: dict[str, list[str]] = {}  # room_id → image ids shown for that room
    room_obs: RoomLabelsObservation | None = None
    all_panos: list[PanoramaRef] = []


def image_id(model_id: str, pano_id: str, face: int) -> str:
    return f"mpp_{model_id}_{pano_id}_{face}"


def sample_panos(panos: list[PanoramaRef], k: int = MAX_PANOS) -> list[PanoramaRef]:
    """Farthest-point sampling on (x, y) so the panoramas cover the scan; deterministic."""
    panos = [p for p in panos if len(p.skybox_urls) >= 6]
    if len(panos) <= k:
        return panos
    cx = sum(p.xyz[0] for p in panos) / len(panos)
    cy = sum(p.xyz[1] for p in panos) / len(panos)
    first = min(panos, key=lambda p: ((p.xyz[0] - cx) ** 2 + (p.xyz[1] - cy) ** 2, p.pano_id))
    chosen = [first]
    while len(chosen) < k:
        nxt = max((p for p in panos if p not in chosen),
                  key=lambda p: (min(math.dist(p.xyz[:2], c.xyz[:2]) for c in chosen), p.pano_id))
        chosen.append(nxt)
    return chosen


def scan_areas(rooms: dict, profile: BuildingProfile) -> dict:
    room_rows = []
    for r in rooms.get("rooms") or []:
        dims = r.get("dimensions") or {}
        area = dims.get("areaFloor")
        labels = [c["label"] for c in r.get("classifications") or []]
        room_rows.append({"room_id": r["id"], "type": labels[0] if labels else None, "polygon": [],
                          "area_sqft": round(area * SQFT_PER_M2, 1) if area else None})
    scanned = round(sum(x["area_sqft"] or 0 for x in room_rows), 1)
    coverage = scanned / profile.rba_sqft if profile.rba_sqft else None
    walls = sum(len(f.get("edges") or []) for f in rooms.get("floors") or [])
    return {"rooms": room_rows, "scanned_floor_area_sqft": scanned,
            "coverage_of_rba": round(coverage, 4) if coverage is not None else None,
            "wall_edges": walls,
            "floorplans": [{k: f.get(k) for k in ("format", "flags", "width", "height", "resolution", "origin")}
                           for f in (rooms.get("assets") or {}).get("floorplans") or []]}


def base_images(images: list[ImageRef], panos: list[PanoramaRef]) -> list[ImageRef]:
    """The images the lighting/HVAC/window prompt lists (sampled panos × FACES), not the room images."""
    ids = {image_id(p.model_id, p.pano_id, f) for p in panos for f in FACES}
    return [i for i in images if i.image_id in ids]


def prompt_for(profile: BuildingProfile, images: list[ImageRef], panos: list[PanoramaRef],
               question: str | None = None) -> str:
    face_name = {0: "ceiling (up)", 1: "horizontal", 3: "horizontal, opposite"}
    lines = []
    for n, p in enumerate(panos, start=1):
        for f in FACES:
            lines.append(f"- `{image_id(p.model_id, p.pano_id, f)}`: panorama {n}, {face_name[f]}")
    ctx = [f"- Name: {profile.name}", f"- Type: {profile.property_type}"]
    if profile.year_built:
        ctx.append(f"- Year built: {profile.year_built}")
    q = (f"\n## Verifier questions\nThe verifier doubted some of your earlier answers. Look again and answer "
         f"these questions, re-checking the items they concern:\n{question}\n" if question else "")
    return (PROMPT_PATH.read_text().replace("{{image_list}}", "\n".join(lines))
            .replace("{{building_context}}", "\n".join(ctx)).replace("{{verifier_question}}", q))


def build_findings(profile: BuildingProfile, model_id: str, obs: InteriorObservation, images: list[ImageRef],
                   panos: list[PanoramaRef], scan: dict) -> tuple[InteriorFindings, list[Claim]]:
    bid = profile.building_id
    ids = {i.image_id for i in images}
    pano_of = {image_id(p.model_id, p.pano_id, f): p for p in panos for f in FACES}
    claims: list[Claim] = []

    def claim(field: str, value, conf: float, boxes: list[Box]) -> None:
        marks = _marks(boxes, ids)
        claims.append(Claim(claim_id=f"{bid}.interior.{field}", building_id=bid, agent="interior",
                            field=f"interior.{field}", value=value, confidence=_clip01(conf),
                            evidence_ids=sorted({m.image_id for m in marks}), marks=marks))

    claim("lighting", obs.lighting.value, obs.lighting.confidence, obs.lighting.marks)
    hvac = sorted(set(obs.hvac.items))
    claim("hvac", ", ".join(hvac) if hvac else "unknown", obs.hvac.confidence if hvac else 0.0, obs.hvac.marks)
    claim("window", obs.window.value, obs.window.confidence, obs.window.marks)

    pins = []
    for c in claims:
        seen = []
        for e in c.evidence_ids:
            p = pano_of.get(e)
            if p and p.pano_id not in seen:
                seen.append(p.pano_id)
                label = next((m.label for m in c.marks if m.image_id == e), c.field.split(".")[1])
                pins.append(Pin(claim_id=c.claim_id, label=label[:60], xyz=p.xyz, status=c.status))
            if len(seen) >= MAX_PINS_PER_CLAIM:
                break

    coverage = scan.get("coverage_of_rba")
    floor_area = scan["scanned_floor_area_sqft"] if coverage and coverage >= MIN_COVERAGE else None
    findings = InteriorFindings(
        building_id=bid, model_id=model_id, lighting_type=obs.lighting.value, hvac_visible=hvac,
        window_type=obs.window.value, floor_area_sqft=floor_area,
        envelope_area_sqft=None,  # needs the wall graph; see module docstring
        claim_ids=[c.claim_id for c in claims], evidence_ids=sorted(ids), pins=pins)
    return findings, claims


def unknown_observation() -> InteriorObservation:
    return InteriorObservation(lighting=LightingObs(value="unknown", confidence=0.0),
                               hvac=HvacObs(items=[], confidence=0.0),
                               window=WindowObs(value="unknown", confidence=0.0))


async def fetch_images(model_id: str) -> tuple[list[PanoramaRef], list[ImageRef]]:
    panos = sample_panos(await mp.panoramas(model_id))
    images = []
    for p in panos:
        for f in FACES:
            path = await mp.pano_face(p, f)
            images.append(ImageRef(image_id=image_id(model_id, p.pano_id, f), source="matterport_pano",
                                   local_path=str(path)))
    return panos, images


# --------------------------------------------------------------------------- room annotation

def short_id(room_id: str) -> str:
    return room_id[:4]


async def fetch_room_images(model_id: str, room_info: list[dict], all_panos: list[PanoramaRef]
                            ) -> tuple[dict[str, list[str]], list[ImageRef]]:
    """Up to MAX_PANOS_PER_ROOM panoramas per room (spread out), horizontal faces only."""
    by_id = {p.pano_id: p for p in all_panos}
    room_images: dict[str, list[str]] = {}
    images: list[ImageRef] = []
    for r in room_info:
        area = (r.get("dimensions") or {}).get("areaFloor") or 0
        k = max(1, min(MAX_PANOS_PER_ROOM, math.ceil(area / M2_PER_ROOM_PANO)))
        panos = sample_panos([by_id[i] for i in r["pano_ids"] if i in by_id], k)
        ids = []
        for p, faces in zip(panos, ROOM_FACES):
            for f in faces:
                path = await mp.pano_face(p, f)
                iid = image_id(model_id, p.pano_id, f)
                ids.append(iid)
                images.append(ImageRef(image_id=iid, source="matterport_pano", local_path=str(path)))
        room_images[r["room_id"]] = ids
    return room_images, images


def rooms_prompt(profile: BuildingProfile, room_info: list[dict], room_images: dict[str, list[str]],
                 question: str | None = None) -> str:
    lines = []
    for n, r in enumerate(room_info, start=1):
        if not room_images.get(r["room_id"]):
            continue
        dims = r.get("dimensions") or {}
        size = (f"floor area about {dims['areaFloor']:.0f} m², ceiling about {dims['height']:.1f} m"
                if dims.get("areaFloor") and dims.get("height") else "size unknown")
        imgs = ", ".join(f"`{i}`" for i in room_images[r["room_id"]])
        lines.append(f"- Room {n}, room_id `{r['room_id']}`: {size}; {len(r['pano_ids'])} panoramas captured "
                     f"inside. Images: {imgs}")
    ctx = [f"- Name: {profile.name}", f"- Type: {profile.property_type}"]
    q = (f"\n## Verifier questions\nThe verifier doubted some of your room labels. Look again at those rooms "
         f"and answer:\n{question}\n" if question else "")
    return (ROOMS_PROMPT_PATH.read_text().replace("{{rooms}}", "\n".join(lines))
            .replace("{{building_context}}", "\n".join(ctx)).replace("{{verifier_question}}", q))


async def label_rooms(profile: BuildingProfile, room_info: list[dict], room_images: dict[str, list[str]],
                      images_by_id: dict[str, ImageRef], question: str | None = None) -> RoomLabelsObservation:
    imgs = [images_by_id[i] for r in room_info for i in room_images.get(r["room_id"], []) if i in images_by_id]
    return await llm.vision_json(rooms_prompt(profile, room_info, room_images, question), imgs,
                                 RoomLabelsObservation)


def _note(text: str, room: dict) -> str | None:
    """Inspector's evidence note: shown to users, so no invented numbers (guardrail) and short."""
    text = " ".join((text or "").split())[:160]
    if not text or check_numbers(text, {"room": room}):
        return None
    return text


def add_rooms(profile: BuildingProfile, findings: InteriorFindings, claims: list[Claim], room_info: list[dict],
              room_images: dict[str, list[str]], room_obs: RoomLabelsObservation | None,
              all_panos: list[PanoramaRef]) -> tuple[InteriorFindings, list[Claim]]:
    """One claim, one pin and one RoomLabel per Matterport room."""
    bid = profile.building_id
    by_pano = {p.pano_id: p for p in all_panos}
    answers = {o.room_id: o for o in (room_obs.rooms if room_obs else [])}
    claims = [c for c in claims if not c.field.startswith("interior.room.")]
    pins = [p for p in findings.pins if ".interior.room." not in p.claim_id]
    labels: list[RoomLabel] = []
    for r in room_info:
        rid = r["room_id"]
        shown = set(room_images.get(rid, []))
        o = answers.get(rid)
        rtype = o.type if o else "unknown"
        also = sorted({t for t in (o.also_contains if o else []) if t not in (rtype, "unknown")})
        conf = _clip01(o.confidence) if o and rtype != "unknown" else 0.0
        marks = _marks(o.marks, shown) if o else []
        claim_id = f"{bid}.interior.room.{rid}"
        value = " + ".join([rtype, *also])  # the verifier judges the whole label, incl. merged spaces
        c = Claim(claim_id=claim_id, building_id=bid, agent="interior", field=f"interior.room.{rid}",
                  value=value, confidence=conf, evidence_ids=sorted(shown), marks=marks)
        claims.append(c)
        pts = [by_pano[i].xyz for i in r["pano_ids"] if i in by_pano]
        xyz = tuple(sum(v[k] for v in pts) / len(pts) for k in range(3)) if pts else None
        note = _note(o.evidence_note, r) if o else None
        area = (r.get("dimensions") or {}).get("areaFloor")
        labels.append(RoomLabel(room_id=rid, type=rtype, also_contains=also, confidence=conf, evidence_note=note,
                                claim_id=claim_id,
                                status=c.status, area_sqft=round(area * SQFT_PER_M2, 1) if area else None,
                                pano_ids=r["pano_ids"], xyz=xyz, matterport_tags=r.get("tags") or []))
        if xyz:
            label = room_title(rtype, also) + (f": {note}" if note else "")
            pins.append(Pin(claim_id=claim_id, label=label[:120], xyz=xyz, status=c.status))
    findings = findings.model_copy(update={"rooms": labels, "pins": pins,
                                           "claim_ids": [c.claim_id for c in claims]})
    return findings, claims


PLURAL = {"open_office": "open offices", "private_office": "private offices", "conference": "conference rooms",
          "corridor": "corridors", "lobby": "lobby", "restroom": "restrooms", "mechanical_it": "mechanical / IT",
          "storage": "storage", "kitchen_break": "kitchen / break"}


def room_title(rtype: str, also: list[str]) -> str:
    """'Corridor + private offices' for a merged Matterport region; else the plain type."""
    return TYPE_LABEL[rtype] + "".join(f" + {PLURAL[t]}" for t in also)


def widget_rooms(findings: InteriorFindings) -> list[dict]:
    """rooms.json for widgets/resolver.py: registry Room shape (room_id, type, polygon, area_sqft)."""
    return [{"room_id": r.room_id, "type": room_title(r.type, r.also_contains), "polygon": [], "area_sqft": r.area_sqft}
            for r in findings.rooms]


async def inspect(profile: BuildingProfile, run_id: str | None = None) -> InteriorResult:
    bid, model_id = profile.building_id, profile.matterport_model_id
    ev = (lambda kind, msg, evidence=None: emit(run_id, AGENT, kind, msg, bid, evidence, building_name=profile.name)
          ) if run_id else (lambda *a, **k: None)

    rooms = await mp.rooms(model_id)
    scan = scan_areas(rooms, profile)
    all_panos = await mp.panoramas(model_id)
    panos, images = await fetch_images(model_id)
    ev("fetch", f"Matterport scan: {len(scan['rooms'])} rooms, {len(all_panos)} panoramas; "
                f"inspecting {len(panos)}", images[0].image_id if images else None)

    try:
        obs = await llm.vision_json(prompt_for(profile, images, panos), images, InteriorObservation)
    except Exception as e:  # noqa: BLE001
        log.warning("interior inspector failed for %s: %s", bid, e)
        ev("error", f"vision model failed ({type(e).__name__}); interior marked unknown")
        obs = unknown_observation()

    findings, claims = build_findings(profile, model_id, obs, images, panos, scan)
    hv = ", ".join(i.replace("_", " ") for i in findings.hvac_visible) or "none seen"
    ev("observe", f"lighting {findings.lighting_type}; HVAC {hv}"[:90], images[0].image_id if images else None)
    ev("observe", f"windows {findings.window_type}; {len(findings.pins)} findings pinned in 3D")

    # Room annotation
    room_info, room_images, room_obs = [], {}, None
    try:
        room_info = await mp.room_panos(model_id)
        room_images, room_imgs = await fetch_room_images(model_id, room_info, all_panos)
        known = {i.image_id for i in images}
        images = images + [i for i in room_imgs if i.image_id not in known and not known.add(i.image_id)]
        room_obs = await label_rooms(profile, room_info, room_images, {i.image_id: i for i in images})
    except Exception as e:  # noqa: BLE001 - rooms stay unlabelled; the rest of the interior stands
        log.warning("room annotation failed for %s: %s", bid, e)
        ev("error", f"room labelling failed ({type(e).__name__}); rooms left unlabelled")
    findings, claims = add_rooms(profile, findings, claims, room_info, room_images, room_obs, all_panos)
    findings = findings.model_copy(update={"evidence_ids": sorted({i.image_id for i in images})})
    for n, r in enumerate(findings.rooms, start=1):
        ev("observe", f"room {n} ({short_id(r.room_id)}): {room_title(r.type, r.also_contains).lower()}",
           room_images.get(r.room_id, [None])[0])

    try:
        paths = await mp.matterpak(model_id)
        scan["mesh"] = {"obj": Path(paths.obj).name if paths.obj else None,
                        "mtl": Path(paths.mtl).name if paths.mtl else None}
        ev("fetch", "MatterPak mesh downloaded for the 3D view")
    except Exception as e:  # noqa: BLE001 - mesh is optional; the survey goes on
        scan["mesh"] = None
        scan["mesh_error"] = str(e)[:200]
        ev("error", "3D mesh not available from Matterport yet")
    return InteriorResult(model_id=model_id, images=images, panos=panos, obs=obs, findings=findings,
                          claims=claims, scan=scan, room_info=room_info, room_images=room_images,
                          room_obs=room_obs, all_panos=all_panos)


def with_statuses(res: InteriorResult, by_id: dict[str, Claim]) -> InteriorResult:
    claims = [by_id.get(c.claim_id, c) for c in res.claims]
    status = {c.claim_id: c.status for c in claims}
    pins = [p.model_copy(update={"status": status.get(p.claim_id, p.status)}) for p in res.findings.pins]
    rooms = [r.model_copy(update={"status": status.get(r.claim_id, r.status)}) for r in res.findings.rooms]
    return res.model_copy(update={"claims": claims,
                                  "findings": res.findings.model_copy(update={"pins": pins, "rooms": rooms})})


async def reinspect(profile: BuildingProfile, res: InteriorResult, asks: list[tuple[Claim, str]]) -> InteriorResult:
    """Re-answer sent-back claims: lighting/HVAC/window in one call, room labels in another."""
    base = [(c, q) for c, q in asks if not c.field.startswith("interior.room.")]
    room_asks = [(c, q) for c, q in asks if c.field.startswith("interior.room.")]
    obs, room_obs = res.obs, res.room_obs
    if base:
        questions = "\n".join(f"- about `{c.field}`: {q}" for c, q in base)
        try:
            imgs = base_images(res.images, res.panos)
            new = await llm.vision_json(prompt_for(profile, imgs, res.panos, questions), imgs, InteriorObservation)
            for c, _ in base:
                attr = c.field.split(".", 1)[1]
                if attr in ("lighting", "hvac", "window"):
                    obs = obs.model_copy(update={attr: getattr(new, attr)})
        except Exception as e:  # noqa: BLE001
            log.warning("interior reinspect failed: %s", e)
    if room_asks:
        asked = {c.field.split(".")[2]: q for c, q in room_asks}
        subset = [r for r in res.room_info if r["room_id"] in asked]
        questions = "\n".join(f"- room_id `{rid}`: {q}" for rid, q in asked.items())
        try:
            new_rooms = await label_rooms(profile, subset, res.room_images, {i.image_id: i for i in res.images},
                                          questions)
            fresh = {o.room_id: o for o in new_rooms.rooms if o.room_id in asked}
            kept = [o for o in (room_obs.rooms if room_obs else []) if o.room_id not in fresh]
            room_obs = RoomLabelsObservation(rooms=kept + list(fresh.values()))
        except Exception as e:  # noqa: BLE001
            log.warning("room reinspect failed: %s", e)
    findings, claims = build_findings(profile, res.model_id, obs, res.images, res.panos, res.scan)
    findings, claims = add_rooms(profile, findings, claims, res.room_info, res.room_images, room_obs, res.all_panos)
    findings = findings.model_copy(update={"evidence_ids": res.findings.evidence_ids})
    return res.model_copy(update={"obs": obs, "room_obs": room_obs, "findings": findings, "claims": claims})


def save(profile: BuildingProfile, res: InteriorResult) -> None:
    d = store.building_dir(profile.building_id)
    write_json_atomic(d / "interior.json", res.findings.model_dump(mode="json"))
    mesh = res.scan.get("mesh")
    scan = {**res.scan, "model_id": res.model_id, "showcase_url": profile.showcase_url,
            "mesh_url": f"/media/mesh/{res.model_id}/{mesh['obj']}" if mesh and mesh.get("obj") else None,
            "mtl_url": f"/media/mesh/{res.model_id}/{mesh['mtl']}" if mesh and mesh.get("mtl") else None}
    if res.findings.rooms:
        rooms = widget_rooms(res.findings)
        write_json_atomic(d / "rooms.json", rooms)  # widgets/resolver.py: list[Room] → floor_plan, hero_3d
        scan["rooms"] = rooms
    write_json_atomic(d / "interior_scan.json", scan)
    store.add_images(profile.building_id, res.images)
