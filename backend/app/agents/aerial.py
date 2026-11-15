"""Aerial inspector (T1.6): Vexcel imagery + Gemini vision → AerialFindings + Claims.

Gemini returns observations only (enums, fractions, counts, confidences, boxes). Code turns
each into a Claim, computes usable_roof_m2 = area(footprint) × usable_roof_fraction, writes
aerial.json / claims.json / images.json and a debug PNG with the marks drawn.

Obliques: the Vexcel oblique API isn't documented in what we have, so the inspector runs
overhead-only (plan fallback "skip obliques"); facades stay empty until vexcel.oblique works.
"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw
from pydantic import BaseModel, Field
from shapely import wkt as shapely_wkt

from app.adapters import geometry, vexcel
from app.adapters.cache import write_json_atomic
from app.adapters.types import ImageRef, Orientation
from app.agents import llm, store
from app.config import get_settings
from app.events import emit
from app.schemas.aerial import AerialFindings, FacadeFinding
from app.schemas.claims import Claim, Mark
from app.schemas.profile import BuildingProfile

log = logging.getLogger(__name__)
AGENT = "Aerial"
PROMPT_PATH = Path(__file__).parent / "prompts" / "aerial.md"


# ---- Gemini response schema (observations only; no derived numbers) ----

class Box(BaseModel):
    image_id: str
    label: str
    x0: float
    y0: float
    x1: float
    y1: float


class RoofTypeObs(BaseModel):
    value: Literal["flat", "pitched", "mixed", "unknown"]
    confidence: float
    marks: list[Box] = []


class RoofColorObs(BaseModel):
    value: Literal["dark", "light", "mixed", "unknown"]
    confidence: float
    marks: list[Box] = []


class FractionObs(BaseModel):
    value: float | None
    confidence: float
    marks: list[Box] = []


class ShadingObs(BaseModel):
    value: Literal["none", "partial", "heavy", "unknown"]
    confidence: float
    marks: list[Box] = []


class SolarObs(BaseModel):
    value: Literal["yes", "no", "unknown"]
    confidence: float
    marks: list[Box] = []


class FacadeObs(BaseModel):
    orientation: Literal["N", "E", "S", "W"]
    glazing_ratio: float | None
    window_count: int | None
    confidence: float
    marks: list[Box] = []


class AerialObservation(BaseModel):
    roof_type: RoofTypeObs
    roof_color: RoofColorObs
    usable_roof_fraction: FractionObs
    shading: ShadingObs
    existing_solar: SolarObs
    facades: list[FacadeObs] = Field(default_factory=list)


# ---- files ----

building_dir = store.building_dir


def _clip01(x: float) -> float:
    return min(1.0, max(0.0, float(x)))


def _marks(boxes: list[Box], valid_ids: set[str]) -> list[Mark]:
    out = []
    for b in boxes:
        if b.image_id not in valid_ids:
            continue  # model invented an image id: drop the mark, keep the claim
        x0, x1 = sorted((_clip01(b.x0), _clip01(b.x1)))
        y0, y1 = sorted((_clip01(b.y0), _clip01(b.y1)))
        out.append(Mark(image_id=b.image_id, label=b.label[:60], bbox=(x0, y0, x1, y1)))
    return out


def _describe(i: ImageRef, images: list[ImageRef]) -> str:
    if i.source != "vexcel_overhead":
        return f"oblique, {i.orientation} facade"
    overheads = [o for o in images if o.source == "vexcel_overhead"]
    if len(overheads) > 1 and i.gsd_m and i.gsd_m == max(o.gsd_m or 0 for o in overheads):
        # pulled by the investigator: same point, larger area (neighbours, trees) for shading
        return ("wider overhead context, same building at the centre with its surroundings: use it for "
                "shading from neighbouring buildings and trees")
    return "overhead"


def prompt_for(profile: BuildingProfile, images: list[ImageRef], question: str | None = None) -> str:
    lines = [f"- `{i.image_id}`: {_describe(i, images)}" for i in images]
    ctx = [f"- Name: {profile.name}", f"- Type: {profile.property_type}"]
    if profile.stories:
        ctx.append(f"- Stories above grade: {profile.stories}")
    if profile.year_built:
        ctx.append(f"- Year built: {profile.year_built}")
    q = (f"\n## Verifier questions\nThe verifier doubted some of your earlier answers. Look again and answer "
         f"these questions, re-checking the items they concern:\n{question}\n" if question else "")
    return (PROMPT_PATH.read_text()
            .replace("{{image_list}}", "\n".join(lines))
            .replace("{{building_context}}", "\n".join(ctx))
            .replace("{{verifier_question}}", q))


def build_findings(profile: BuildingProfile, obs: AerialObservation, images: list[ImageRef]
                   ) -> tuple[AerialFindings, list[Claim]]:
    bid = profile.building_id
    ids = {i.image_id for i in images}
    overhead_ids = [i.image_id for i in images if i.source == "vexcel_overhead"]
    claims: list[Claim] = []

    def claim(field: str, value, conf: float, boxes: list[Box], evidence: list[str]) -> Claim:
        marks = _marks(boxes, ids)
        ev = sorted({m.image_id for m in marks} | set(evidence))
        c = Claim(claim_id=f"{bid}.aerial.{field}", building_id=bid, agent="aerial", field=field,
                  value=value, confidence=_clip01(conf), evidence_ids=ev, marks=marks)
        claims.append(c)
        return c

    claim("roof.type", obs.roof_type.value, obs.roof_type.confidence, obs.roof_type.marks, overhead_ids)
    claim("roof.color", obs.roof_color.value, obs.roof_color.confidence, obs.roof_color.marks, overhead_ids)
    frac = obs.usable_roof_fraction.value
    frac = None if frac is None else _clip01(frac)
    claim("roof.usable_fraction", "unknown" if frac is None else frac,
          obs.usable_roof_fraction.confidence if frac is not None else 0.0,
          obs.usable_roof_fraction.marks, overhead_ids)
    claim("roof.shading", obs.shading.value, obs.shading.confidence, obs.shading.marks, overhead_ids)
    solar = obs.existing_solar.value
    claim("roof.existing_solar", {"yes": True, "no": False}.get(solar, "unknown"),
          obs.existing_solar.confidence, obs.existing_solar.marks, overhead_ids)

    oblique_by_dir = {i.orientation: i.image_id for i in images if i.source == "vexcel_oblique"}
    facades: dict[Orientation, FacadeFinding] = {}
    for f in obs.facades:
        if f.orientation not in oblique_by_dir:
            continue  # no image of that facade: refuse the claim
        g = None if f.glazing_ratio is None else _clip01(f.glazing_ratio)
        n = None if f.window_count is None else max(0, int(f.window_count))
        ev = [oblique_by_dir[f.orientation]]
        if g is not None:
            claim(f"facade.{f.orientation}.glazing", g, f.confidence, f.marks, ev)
        if n is not None:
            claim(f"facade.{f.orientation}.window_count", float(n), f.confidence, f.marks, ev)
        facades[f.orientation] = FacadeFinding(glazing_ratio=g, window_count_est=n)

    # Numbers computed in code, never by the model.
    footprint_m2 = geometry.area_m2(profile.footprint_wkt, profile.city) if profile.footprint_wkt else 0.0
    usable_m2 = round(footprint_m2 * (frac or 0.0), 1)

    findings = AerialFindings(
        building_id=bid,
        roof_type=obs.roof_type.value,
        roof_color=obs.roof_color.value,
        usable_roof_fraction=frac or 0.0,
        # AerialFindings.shading has no "unknown"; "partial" is the conservative reading (derates solar)
        # and the roof.shading claim keeps "unknown" with its confidence for the verifier.
        shading=obs.shading.value if obs.shading.value != "unknown" else "partial",
        existing_solar=solar == "yes",
        usable_roof_m2=usable_m2,
        facades=facades,
        claim_ids=[c.claim_id for c in claims],
        evidence_ids=sorted(ids),
    )
    return findings, claims


def unknown_observation() -> AerialObservation:
    """Fallback when Gemini fails or returns invalid JSON twice (TRD §10)."""
    return AerialObservation(
        roof_type=RoofTypeObs(value="unknown", confidence=0.0),
        roof_color=RoofColorObs(value="unknown", confidence=0.0),
        usable_roof_fraction=FractionObs(value=None, confidence=0.0),
        shading=ShadingObs(value="unknown", confidence=0.0),
        existing_solar=SolarObs(value="unknown", confidence=0.0),
    )


def draw_debug(profile: BuildingProfile, overhead: ImageRef, claims: list[Claim], out: Path) -> Path:
    """Overhead image with the estimated footprint (cyan) and every mark (labelled boxes)."""
    with Image.open(overhead.local_path) as im:
        im = im.convert("RGB")
    w, h = im.size
    d = ImageDraw.Draw(im)
    if overhead.bounds_wkt and profile.footprint_wkt:
        minx, miny, maxx, maxy = shapely_wkt.loads(overhead.bounds_wkt).bounds
        fp = shapely_wkt.loads(profile.footprint_wkt)
        pts = [((x - minx) / (maxx - minx) * w, (maxy - y) / (maxy - miny) * h) for x, y in fp.exterior.coords]
        d.line(pts, fill=(0, 220, 255), width=3)
    colors = [(255, 60, 60), (255, 200, 0), (60, 255, 60), (255, 0, 255), (255, 140, 0)]
    for i, c in enumerate(claims):
        for m in c.marks:
            if m.image_id != overhead.image_id or not m.bbox:
                continue
            x0, y0, x1, y1 = m.bbox
            col = colors[i % len(colors)]
            d.rectangle([x0 * w, y0 * h, x1 * w, y1 * h], outline=col, width=3)
            d.text((x0 * w + 4, y0 * h + 4), f"{c.field}: {m.label}", fill=col)
    out.parent.mkdir(parents=True, exist_ok=True)
    im.save(out)
    return out


async def fetch_images(profile: BuildingProfile) -> list[ImageRef]:
    images = await vexcel.overhead(geometry.point_wkt(profile.lat, profile.lon),
                                   vexcel.overhead_buffer_m(profile.rba_sqft, profile.stories), city=profile.city)
    if profile.footprint_wkt:
        for o in ("N", "E", "S", "W"):
            try:
                images += await vexcel.oblique(profile.footprint_wkt, o)
            except NotImplementedError:
                break  # obliques not available yet: overhead-only
    return images


class AerialResult(BaseModel):
    images: list[ImageRef]
    obs: AerialObservation
    findings: AerialFindings
    claims: list[Claim]

    @property
    def overhead(self) -> ImageRef:
        return next(i for i in self.images if i.source == "vexcel_overhead")


def _emitter(profile: BuildingProfile, run_id: str | None):
    if not run_id:
        return lambda *a, **k: None
    return lambda kind, msg, evidence=None: emit(run_id, AGENT, kind, msg, profile.building_id, evidence,
                                                 building_name=profile.name)


async def inspect(profile: BuildingProfile, run_id: str | None = None,
                  images: list[ImageRef] | None = None) -> AerialResult:
    """Fetch imagery (unless the investigator already pulled it: `images`, the building's own
    overhead first), ask Gemini, build findings + claims, emit observe events. Writes nothing."""
    ev = _emitter(profile, run_id)
    pulled = images is not None
    images = images if pulled else await fetch_images(profile)
    overhead = next(i for i in images if i.source == "vexcel_overhead")
    n_obl = sum(1 for i in images if i.source == "vexcel_oblique")
    if not pulled:
        ev("fetch", f"overhead image ({overhead.gsd_m * 100:.0f} cm/px)" + (f" + {n_obl} obliques" if n_obl else ""),
           overhead.image_id)

    try:
        obs = await llm.vision_json(prompt_for(profile, images), images, AerialObservation)
    except Exception as e:  # noqa: BLE001 - Gemini/validation failure → unknowns (TRD §10)
        log.warning("aerial inspector failed for %s: %s", profile.building_id, e)
        ev("error", f"vision model failed ({type(e).__name__}); roof marked unknown")
        obs = unknown_observation()

    findings, claims = build_findings(profile, obs, images)
    solar = {True: "panels present", False: "no panels"}[findings.existing_solar] \
        if obs.existing_solar.value != "unknown" else "panels unknown"
    ev("observe", f"roof {findings.roof_type}, {findings.roof_color}, {solar}", overhead.image_id)
    usable = "unknown" if obs.usable_roof_fraction.value is None else f"{findings.usable_roof_fraction:.0%}"
    ev("observe", f"usable roof {usable}, shading {obs.shading.value}", overhead.image_id)  # never "0%" for unknown
    return AerialResult(images=images, obs=obs, findings=findings, claims=claims)


def save(profile: BuildingProfile, res: AerialResult) -> None:
    d = building_dir(profile.building_id)
    write_json_atomic(d / "aerial.json", res.findings.model_dump(mode="json"))
    store.add_images(profile.building_id, res.images)
    draw_debug(profile, res.overhead, res.claims, d / "aerial_debug.png")


async def run(profile: BuildingProfile, run_id: str | None = None) -> tuple[AerialFindings, list[Claim]]:
    """inspect + save, including claims.json (used by survey_one.py)."""
    res = await inspect(profile, run_id)
    save(profile, res)
    store.save_claims(profile.building_id, res.claims)
    return res.findings, res.claims


FIELD_ATTR = {"roof.type": "roof_type", "roof.color": "roof_color", "roof.usable_fraction": "usable_roof_fraction",
              "roof.shading": "shading", "roof.existing_solar": "existing_solar"}


async def reinspect(profile: BuildingProfile, res: AerialResult, asks: list[tuple[Claim, str]]) -> AerialResult:
    """Re-answer the sent-back claims (one Gemini call), given the verifier's questions; every
    other observation is kept as it was."""
    questions = "\n".join(f"- about `{c.field}`: {q}" for c, q in asks)
    prompt = prompt_for(profile, res.images, question=questions)
    try:
        new = await llm.vision_json(prompt, res.images, AerialObservation)
    except Exception as e:  # noqa: BLE001 - keep the old answers; the verifier decides again
        log.warning("aerial reinspect failed for %s: %s", profile.building_id, e)
        return res
    obs = res.obs
    for claim, _ in asks:
        if claim.field in FIELD_ATTR:
            attr = FIELD_ATTR[claim.field]
            obs = obs.model_copy(update={attr: getattr(new, attr)})
        elif claim.field.startswith("facade."):
            o = claim.field.split(".")[1]
            keep = [f for f in obs.facades if f.orientation != o]
            obs = obs.model_copy(update={"facades": keep + [f for f in new.facades if f.orientation == o]})
    findings, claims = build_findings(profile, obs, res.images)
    return AerialResult(images=res.images, obs=obs, findings=findings, claims=claims)
