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
from app.schemas.claims import Claim
from app.schemas.interior import InteriorFindings, Pin
from app.schemas.profile import BuildingProfile

log = logging.getLogger(__name__)
AGENT = "Interior"
PROMPT_PATH = Path(__file__).parent / "prompts" / "interior.md"
MAX_PANOS = 5
FACES = (0, 1, 3)  # up, and two opposite horizon faces
MIN_COVERAGE = 0.5
MAX_PINS_PER_CLAIM = 3

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


class InteriorResult(BaseModel):
    model_id: str
    images: list[ImageRef]
    panos: list[PanoramaRef]
    obs: InteriorObservation
    findings: InteriorFindings
    claims: list[Claim]
    scan: dict


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
        room_rows.append({"room_id": r["id"], "type": labels[0] if labels else None,
                          "area_sqft": round(area * SQFT_PER_M2, 1) if area else None,
                          "height_m": dims.get("height")})
    scanned = round(sum(x["area_sqft"] or 0 for x in room_rows), 1)
    coverage = scanned / profile.rba_sqft if profile.rba_sqft else None
    walls = sum(len(f.get("edges") or []) for f in rooms.get("floors") or [])
    return {"rooms": room_rows, "scanned_floor_area_sqft": scanned,
            "coverage_of_rba": round(coverage, 4) if coverage is not None else None,
            "wall_edges": walls,
            "floorplans": [{k: f.get(k) for k in ("format", "flags", "width", "height", "resolution", "origin")}
                           for f in (rooms.get("assets") or {}).get("floorplans") or []]}


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
                          claims=claims, scan=scan)


def with_statuses(res: InteriorResult, by_id: dict[str, Claim]) -> InteriorResult:
    claims = [by_id.get(c.claim_id, c) for c in res.claims]
    status = {c.claim_id: c.status for c in claims}
    pins = [p.model_copy(update={"status": status.get(p.claim_id, p.status)}) for p in res.findings.pins]
    return res.model_copy(update={"claims": claims, "findings": res.findings.model_copy(update={"pins": pins})})


async def reinspect(profile: BuildingProfile, res: InteriorResult, asks: list[tuple[Claim, str]]) -> InteriorResult:
    questions = "\n".join(f"- about `{c.field}`: {q}" for c, q in asks)
    try:
        new = await llm.vision_json(prompt_for(profile, res.images, res.panos, questions), res.images,
                                    InteriorObservation)
    except Exception as e:  # noqa: BLE001
        log.warning("interior reinspect failed: %s", e)
        return res
    obs = res.obs
    for c, _ in asks:
        attr = c.field.split(".", 1)[1]
        if attr in ("lighting", "hvac", "window"):
            obs = obs.model_copy(update={attr: getattr(new, attr)})
    findings, claims = build_findings(profile, res.model_id, obs, res.images, res.panos, res.scan)
    return res.model_copy(update={"obs": obs, "findings": findings, "claims": claims})


def save(profile: BuildingProfile, res: InteriorResult) -> None:
    d = store.building_dir(profile.building_id)
    write_json_atomic(d / "interior.json", res.findings.model_dump(mode="json"))
    mesh = res.scan.get("mesh")
    scan = {**res.scan, "model_id": res.model_id,
            "mesh_url": f"/media/mesh/{res.model_id}/{mesh['obj']}" if mesh and mesh.get("obj") else None,
            "mtl_url": f"/media/mesh/{res.model_id}/{mesh['mtl']}" if mesh and mesh.get("mtl") else None}
    write_json_atomic(d / "interior_scan.json", scan)
    store.add_images(profile.building_id, res.images)
