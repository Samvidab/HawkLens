"""Resolver: fills widget props from data JSON (never from an LLM) and assembles a validated Layout.

Inputs live under data/ (TRD §5 file map). Shapes assumed for files this lane does not own
(adjust here if the pricing/finance owners differ):

plans/current.json (written by the pricing node; keys beyond these are ignored)
  plan_id, goal{target_pct,budget_usd,risk_lambda,...}, selected[upgrade_id], excluded_building_ids[],
  owner_included[upgrade_id], exp_npv, cvar5, p_loss, p_hit_target, total_upfront, tonnes_per_year,
  tonnes_needed, hist_bins[{x0,x1,count}], stub(bool),
  macc{bars:[{upgrade_id,building_id,type,tonnes_per_year,cost_per_tonne}]},
  simulate{upgrade_id:{exp_npv,p_loss,cvar5,cost_per_tonne,hist_bins,upfront_usd?}},
  by_building{building_id:{exp_npv,cvar5,p_loss,hist_bins}}   (optional, per-building risk)
  baseline{building_id:{annual_spend_usd,tonnes_per_year}}    (optional)
  bills[{contractor,amount}], financing{state,nessie_ids}      (written by finance agent)
buildings/<id>/verification.json = list[Claim] with final statuses
buildings/<id>/rooms.json (optional) = list[Room]
memo/<plan_id>.md
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from pydantic import TypeAdapter

from app.rules.feasibility import load_rules
from app.schemas.aerial import AerialFindings
from app.schemas.claims import Claim
from app.schemas.interior import InteriorFindings
from app.schemas.layout import Layout, Situation, WidgetSpec
from app.schemas.profile import BuildingProfile
from app.schemas.upgrades import FeasibleUpgrade
from app.widgets.registry import validate_layout, validate_props
from app.widgets.templates import template_for

CONTRACTOR = {"rooftop_solar": "Solar installer", "cool_roof": "Roofing contractor",
              "window_upgrade": "Glazing contractor", "heat_pump": "HVAC contractor",
              "insulation": "Insulation contractor", "led_retrofit": "Electrical contractor"}
STATUS_BADNESS = {"rejected": 4, "unverified": 3, "sent_back": 2, "pending": 1, "verified": 0}
MAX_GALLERY_ITEMS = 12
EXTRA_CUTS = 3


class ResolveError(ValueError):
    pass


def _read(path: Path, default=None):
    return json.loads(path.read_text()) if path.exists() else default


def _fmt_size(u: FeasibleUpgrade) -> str:
    return f"{u.size_value:,.0f} {u.size_unit}"


@dataclass
class ResolveContext:
    run_id: str
    plan: dict = field(default_factory=dict)
    profiles: dict[str, BuildingProfile] = field(default_factory=dict)
    aerial: dict[str, AerialFindings] = field(default_factory=dict)
    interior: dict[str, InteriorFindings] = field(default_factory=dict)
    upgrades: dict[str, list[FeasibleUpgrade]] = field(default_factory=dict)
    claims: dict[str, list[Claim]] = field(default_factory=dict)
    rooms: dict[str, list[dict]] = field(default_factory=dict)
    memo_md: str = ""
    focus_building_id: str | None = None
    selected_upgrade_ids: list[str] = field(default_factory=list)  # highlighted bar / upgrade
    overhead_image_ids: dict[str, str] = field(default_factory=dict)  # building_id -> image_id
    image_meta: dict[str, dict] = field(default_factory=dict)  # image_id -> {source, orientation}
    situation: Situation = "portfolio_overview"
    floor_height_m: float = 4.0

    @classmethod
    def load(cls, data_dir: Path, run_id: str, **kw) -> "ResolveContext":
        d = Path(data_dir)
        ctx = cls(run_id=run_id, plan=_read(d / "plans" / "current.json", {}),
                  floor_height_m=load_rules()["constants"]["floor_height_m"], **kw)
        for bdir in sorted(p for p in (d / "buildings").glob("*") if p.is_dir()):
            bid = bdir.name
            if (prof := _read(bdir / "profile.json")) is None:
                continue
            ctx.profiles[bid] = BuildingProfile.model_validate(prof)
            if (a := _read(bdir / "aerial.json")) is not None:
                ctx.aerial[bid] = AerialFindings.model_validate(a)
            if (i := _read(bdir / "interior.json")) is not None:
                ctx.interior[bid] = InteriorFindings.model_validate(i)
            ctx.upgrades[bid] = TypeAdapter(list[FeasibleUpgrade]).validate_python(
                _read(bdir / "feasibility.json", []))
            ctx.claims[bid] = TypeAdapter(list[Claim]).validate_python(_read(bdir / "verification.json", []))
            ctx.rooms[bid] = _read(bdir / "rooms.json", [])
        pid = ctx.plan.get("plan_id")
        memo = d / "memo" / f"{pid}.md"
        ctx.memo_md = memo.read_text() if pid and memo.exists() else ""
        return ctx

    # -- lookups
    def name(self, bid: str) -> str:
        return self.profiles[bid].name if bid in self.profiles else bid

    def all_upgrades(self) -> dict[str, FeasibleUpgrade]:
        return {u.upgrade_id: u for ups in self.upgrades.values() for u in ups}

    @property
    def selected(self) -> set[str]:
        return set(self.plan.get("selected", []))

    @property
    def owner_included(self) -> set[str]:
        return set(self.plan.get("owner_included", []))

    @property
    def excluded(self) -> set[str]:
        return set(self.plan.get("excluded_building_ids", []))


# ---- per-widget resolvers ---------------------------------------------------------------------
def _target_control(ctx: ResolveContext) -> tuple[str, dict]:
    goal, plan = ctx.plan.get("goal", {}), ctx.plan
    planned = plan.get("tonnes_per_year")
    return "plans/current.json#/goal", dict(
        target_pct=goal.get("target_pct", 0.0), budget_usd=goal.get("budget_usd"),
        risk_lambda=goal.get("risk_lambda", 0.5), p_hit_target=plan.get("p_hit_target"),
        tonnes_needed=plan.get("tonnes_needed"), tonnes_planned=planned)


def _overlays(ctx: ResolveContext, bid: str) -> list[dict]:
    prof, out = ctx.profiles[bid], []
    in_plan = {u.type for u in ctx.upgrades.get(bid, []) if u.upgrade_id in ctx.selected}
    if "rooftop_solar" in in_plan:
        out.append({"type": "solar", "polygon_wkt": prof.footprint_wkt})
    if "cool_roof" in in_plan:
        out.append({"type": "cool_roof", "polygon_wkt": prof.footprint_wkt})
    if "window_upgrade" in in_plan and bid in ctx.aerial:
        for o in ("S", "W"):
            f = ctx.aerial[bid].facades.get(o)
            if f and f.glazing_ratio is not None:
                out.append({"type": "window", "facade": o})
    return out


def _portfolio_3d(ctx: ResolveContext) -> tuple[str, dict]:
    tonnes: dict[str, float] = {}
    for b in ctx.plan.get("macc", {}).get("bars", []):
        if b["upgrade_id"] in ctx.selected:
            tonnes[b["building_id"]] = tonnes.get(b["building_id"], 0.0) + b["tonnes_per_year"]
    buildings = []
    for bid, p in ctx.profiles.items():
        img = ctx.overhead_image_ids.get(bid)
        buildings.append(dict(
            building_id=bid, name=p.name, lat=p.lat, lon=p.lon, footprint_wkt=p.footprint_wkt,
            height_m=(p.stories or 1) * ctx.floor_height_m,
            roof_texture_url=f"/media/{img}" if img else None,
            color_metric="tonnes_per_year", color_value=tonnes.get(bid),
            excluded=bid in ctx.excluded, overlays=_overlays(ctx, bid)))
    return "buildings/*/profile.json", dict(buildings=buildings, focus_building_id=ctx.focus_building_id)


def _need_focus(ctx: ResolveContext) -> str:
    if not ctx.focus_building_id or ctx.focus_building_id not in ctx.profiles:
        raise ResolveError("widget needs focus_building_id of a known building")
    return ctx.focus_building_id


def _hero_3d(ctx: ResolveContext) -> tuple[str, dict]:
    bid = _need_focus(ctx)
    model = ctx.profiles[bid].matterport_model_id
    if not model:
        raise ResolveError(f"{bid} has no Matterport model")
    inter = ctx.interior.get(bid)
    return f"buildings/{bid}/interior.json", dict(
        building_id=bid, mesh_url=f"/media/mesh/{model}/model.obj", mtl_url=f"/media/mesh/{model}/model.mtl",
        pins=[p.model_dump() for p in inter.pins] if inter else [],
        rooms=ctx.rooms.get(bid) or None)


def _bars(ctx: ResolveContext) -> list[dict]:
    return [dict(upgrade_id=b["upgrade_id"], building_id=b["building_id"],
                 building_name=ctx.name(b["building_id"]), type=b["type"],
                 tonnes_per_year=b["tonnes_per_year"], cost_per_tonne=b["cost_per_tonne"],
                 in_plan=b["upgrade_id"] in ctx.selected)
            for b in ctx.plan.get("macc", {}).get("bars", [])]


def _abatement_curve(ctx: ResolveContext) -> tuple[str, dict]:
    return "plans/current.json#/macc", dict(bars=_bars(ctx), selected_upgrade_ids=ctx.selected_upgrade_ids)


def _upfront(ctx: ResolveContext, uid: str) -> float | None:
    return ctx.plan.get("simulate", {}).get(uid, {}).get("upfront_usd")


def _plan_table(ctx: ResolveContext) -> tuple[str, dict]:
    sim, bars = ctx.plan.get("simulate", {}), {b["upgrade_id"]: b for b in ctx.plan.get("macc", {}).get("bars", [])}
    ups, rows = ctx.all_upgrades(), []
    for uid in ctx.plan.get("selected", []):
        u = ups.get(uid)
        if u is None:
            raise ResolveError(f"plan selects unknown upgrade {uid}")
        s, b = sim.get(uid, {}), bars.get(uid, {})
        rows.append(dict(upgrade_id=uid, building_name=ctx.name(u.building_id), type=u.type, size=_fmt_size(u),
                         upfront_usd=s.get("upfront_usd"), exp_npv=s.get("exp_npv"),
                         cost_per_tonne=b.get("cost_per_tonne", s.get("cost_per_tonne")),
                         tonnes_per_year=b.get("tonnes_per_year"), verified=u.verified,
                         owner_included=uid in ctx.owner_included))
    p = ctx.plan
    totals = {"upfront_usd": p.get("total_upfront"), "exp_npv": p.get("exp_npv"),
              "tonnes_per_year": p.get("tonnes_per_year")}
    return "plans/current.json#/selected", dict(rows=rows, totals=totals, sample_pricing=bool(p.get("stub")))


def _risk_histogram(ctx: ResolveContext) -> tuple[str, dict]:
    bid = ctx.focus_building_id
    scoped = ctx.plan.get("by_building", {}).get(bid) if bid else None
    src, scope = (scoped, "building") if scoped else (ctx.plan, "plan")
    ref = f"plans/current.json#/by_building/{bid}" if scoped else "plans/current.json"
    return ref, dict(bins=src.get("hist_bins", []), exp_npv=src.get("exp_npv"), cvar5=src.get("cvar5"),
                     p_loss=src.get("p_loss"), scope=scope)


def _image_source(ctx: ResolveContext, image_id: str, agent: str) -> tuple[str | None, str | None]:
    m = ctx.image_meta.get(image_id, {})
    return m.get("source", "matterport_pano" if agent == "interior" else None), m.get("orientation")


def _evidence_gallery(ctx: ResolveContext) -> tuple[str, dict]:
    bids = [ctx.focus_building_id] if ctx.focus_building_id else list(ctx.profiles)
    per_image: dict[str, list[Claim]] = {}
    for bid in bids:
        for c in ctx.claims.get(bid, []):
            for img in c.evidence_ids:
                per_image.setdefault(img, []).append(c)
    items = []
    for img, cs in per_image.items():
        source, orient = _image_source(ctx, img, cs[0].agent)
        items.append(dict(
            image_id=img, url=f"/media/{img}", source=source, orientation=orient,
            marks=[m.model_dump() for c in cs for m in c.marks if m.image_id == img],
            claim_ids=[c.claim_id for c in cs], claim_summaries=[f"{c.field}: {c.value}" for c in cs],
            status=max((c.status for c in cs), key=STATUS_BADNESS.__getitem__),
            verifier_notes=[c.verifier_note for c in cs if c.verifier_note]))
    if ctx.situation == "verification_issue":
        items.sort(key=lambda i: -STATUS_BADNESS[i["status"]])  # stable: issues first
    return "buildings/*/verification.json", dict(items=items[:MAX_GALLERY_ITEMS])


def _facade_compass(ctx: ResolveContext) -> tuple[str, dict]:
    bid = _need_focus(ctx)
    a = ctx.aerial.get(bid)
    facades = {o: {"glazing_ratio": f.glazing_ratio, "window_count_est": f.window_count_est}
               for o, f in (a.facades if a else {}).items()}
    return f"buildings/{bid}/aerial.json", dict(facades=facades)


def _floor_plan(ctx: ResolveContext) -> tuple[str, dict]:
    bid = _need_focus(ctx)
    inter = ctx.interior.get(bid)
    return f"buildings/{bid}/interior.json", dict(
        rooms=ctx.rooms.get(bid, []), pins=[p.model_dump() for p in inter.pins] if inter else [])


def _upgrade_list(ctx: ResolveContext) -> tuple[str, dict]:
    bids = [ctx.focus_building_id] if ctx.focus_building_id else list(ctx.upgrades)
    rows = [dict(upgrade=u.model_dump(), in_plan=u.upgrade_id in ctx.selected,
                 owner_included=u.upgrade_id in ctx.owner_included,
                 highlighted=u.upgrade_id in ctx.selected_upgrade_ids)
            for b in bids for u in ctx.upgrades.get(b, [])
            if ctx.situation != "verification_issue" or u.verified == "unverified"]
    return "buildings/*/feasibility.json", dict(upgrades=rows)


def _building_header(ctx: ResolveContext) -> tuple[str, dict]:
    bid = _need_focus(ctx)
    base = ctx.plan.get("baseline", {}).get(bid, {})
    return f"buildings/{bid}/profile.json", dict(
        profile=ctx.profiles[bid].model_dump(),
        baseline=dict(annual_spend_usd=base.get("annual_spend_usd"), tonnes_per_year=base.get("tonnes_per_year")))


def _target_gap_card(ctx: ResolveContext) -> tuple[str, dict]:
    p = ctx.plan
    needed, planned = p.get("tonnes_needed"), p.get("tonnes_per_year")
    if needed is None or planned is None:
        raise ResolveError("plan lacks tonnes_needed / tonnes_per_year")
    extras = sorted((b for b in _bars(ctx) if not b["in_plan"]), key=lambda b: b["cost_per_tonne"])[:EXTRA_CUTS]
    return "plans/current.json#/macc", dict(
        shortfall_tonnes=max(needed - planned, 0.0),
        cheapest_extra=[{k: b[k] for k in ("upgrade_id", "cost_per_tonne", "tonnes_per_year")} for b in extras])


def _financing_card(ctx: ResolveContext) -> tuple[str, dict]:
    p, ups = ctx.plan, ctx.all_upgrades()
    bills = p.get("bills")
    if bills is None:  # derive: one bill per contractor type from the selected upgrades' upfront cost
        acc: dict[str, float | None] = {}
        for uid in p.get("selected", []):
            if uid not in ups:
                continue
            c, up = CONTRACTOR[ups[uid].type], _upfront(ctx, uid)
            acc[c] = None if (up is None or acc.get(c, 0.0) is None) else acc.get(c, 0.0) + up
        bills = [{"contractor": c, "amount": a} for c, a in acc.items()]
    fin = p.get("financing", {})
    return "plans/current.json#/financing", dict(
        plan_id=p.get("plan_id"), total_upfront_usd=p.get("total_upfront"), bills=bills,
        state=fin.get("state", "proposed"), nessie_ids=fin.get("nessie_ids"))


def _memo(ctx: ResolveContext) -> tuple[str, dict]:
    return f"memo/{ctx.plan.get('plan_id')}.md", dict(markdown=ctx.memo_md)


def _activity_feed(ctx: ResolveContext) -> tuple[str, dict]:
    return f"runs/{ctx.run_id}/events.jsonl", dict(run_id=ctx.run_id)


RESOLVERS: dict[str, Callable[[ResolveContext], tuple[str, dict]]] = {
    "target_control": _target_control, "portfolio_3d": _portfolio_3d, "hero_3d": _hero_3d,
    "abatement_curve": _abatement_curve, "plan_table": _plan_table, "risk_histogram": _risk_histogram,
    "evidence_gallery": _evidence_gallery, "facade_compass": _facade_compass, "floor_plan": _floor_plan,
    "upgrade_list": _upgrade_list, "building_header": _building_header, "target_gap_card": _target_gap_card,
    "financing_card": _financing_card, "memo": _memo, "activity_feed": _activity_feed,
}


def resolve_widget(spec: WidgetSpec, ctx: ResolveContext) -> WidgetSpec:
    """Return `spec` with data_ref and props filled from data; props validated against the registry."""
    if spec.type not in RESOLVERS:
        raise ResolveError(f"no resolver for widget type {spec.type!r}")
    ref, props = RESOLVERS[spec.type](ctx)
    validated = validate_props(spec.type, props)
    return spec.model_copy(update={"data_ref": ref, "props": validated.model_dump(mode="json")})


def resolve_layout(ctx: ResolveContext, situation: Situation | None = None,
                   widgets: list[WidgetSpec] | None = None, *, layout_id: str | None = None) -> Layout:
    """Build a validated Layout. `widgets` defaults to the situation's template; the composer may
    pass its own selection (types/order/why only — props are always overwritten here)."""
    situation = situation or ctx.situation
    ctx.situation = situation
    if widgets is None:
        fid = ctx.focus_building_id
        has_mp = bool(fid and fid in ctx.profiles and ctx.profiles[fid].matterport_model_id)
        widgets = template_for(situation, has_matterport=has_mp)
    resolved = [resolve_widget(w, ctx) for w in widgets]
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    layout = Layout(layout_id=layout_id or f"lay_{ctx.run_id}_{now}", run_id=ctx.run_id, situation=situation,
                    focus_building_id=ctx.focus_building_id, generated_at=now, widgets=resolved)
    return validate_layout(layout)
