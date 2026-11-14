"""Widget registry: one Pydantic props model per widget type (App Flow §5).

`GET /registry` should return `json_schemas()`; the frontend mirrors these as TypeScript.
Props are filled by widgets.resolver from tool/data JSON — never by an LLM.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.schemas.claims import Mark
from app.schemas.interior import Pin
from app.schemas.layout import GRID_COLUMNS, MAX_WIDGETS, Layout, Size
from app.schemas.profile import BuildingProfile
from app.schemas.upgrades import FeasibleUpgrade


class Props(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---- shared row models -------------------------------------------------------------------------
class Overlay(Props):
    type: Literal["solar", "cool_roof", "window"]
    polygon_wkt: str | None = None
    facade: Literal["N", "E", "S", "W"] | None = None


class Building3D(Props):
    building_id: str
    name: str
    lat: float
    lon: float
    footprint_wkt: str | None = None
    height_m: float
    roof_texture_url: str | None = None
    color_metric: str
    color_value: float | None = None
    excluded: bool = False
    overlays: list[Overlay] = []


class Room(Props):
    room_id: str
    type: str | None = None
    polygon: list[tuple[float, float]] = []  # empty when only the room list (no geometry) is known
    area_sqft: float | None = None


class Bar(Props):
    upgrade_id: str
    building_id: str
    building_name: str
    type: str
    tonnes_per_year: float
    cost_per_tonne: float
    in_plan: bool


class PlanRow(Props):
    upgrade_id: str
    building_name: str
    type: str
    size: str  # e.g. "150 kW", formatted by code
    upfront_usd: float | None = None
    exp_npv: float | None = None
    cost_per_tonne: float | None = None
    tonnes_per_year: float | None = None
    verified: Literal["verified", "unverified", "assumed"]
    owner_included: bool = False


class HistBin(Props):
    x0: float
    x1: float
    count: float


class GalleryItem(Props):
    image_id: str
    url: str
    source: str | None = None
    orientation: str | None = None
    marks: list[Mark] = []
    claim_ids: list[str]
    claim_summaries: list[str]
    status: Literal["pending", "verified", "sent_back", "unverified", "rejected"]
    verifier_notes: list[str] = []


class FacadeStats(Props):
    glazing_ratio: float | None = None
    window_count_est: int | None = None


class UpgradeRow(Props):
    upgrade: FeasibleUpgrade
    in_plan: bool
    owner_included: bool = False
    highlighted: bool = False


class Bill(Props):
    contractor: str
    amount: float | None = None


class ExtraCut(Props):
    upgrade_id: str
    cost_per_tonne: float
    tonnes_per_year: float


# ---- widget props -----------------------------------------------------------------------------
class TargetControl(Props):
    target_pct: float
    budget_usd: float | None = None
    risk_lambda: float
    p_hit_target: float | None = None
    tonnes_needed: float | None = None
    tonnes_planned: float | None = None
    risk_supported: bool = True  # False: the engine ignores risk_lambda; the UI should hide or disable the risk slider


class Portfolio3D(Props):
    buildings: list[Building3D]
    focus_building_id: str | None = None


class Hero3D(Props):
    """`mode` "mesh": render the OBJ/MTL (pins are in mesh coordinates). `mode` "showcase": embed the Matterport
    3D tour (`showcase_url`, an iframe link); mesh urls are then null and pins are informational only."""
    building_id: str
    mode: Literal["mesh", "showcase"] = "mesh"
    mesh_url: str | None = None
    mtl_url: str | None = None
    showcase_url: str | None = None
    pins: list[Pin] = []
    rooms: list[Room] | None = None

    @model_validator(mode="after")
    def _has_a_source(self) -> "Hero3D":
        if self.mode == "showcase" and not self.showcase_url:
            raise ValueError("showcase mode needs showcase_url")
        if self.mode == "mesh" and not self.mesh_url:
            raise ValueError("mesh mode needs mesh_url")
        return self


class AbatementCurve(Props):
    bars: list[Bar]
    selected_upgrade_ids: list[str] = []


class PlanTable(Props):
    rows: list[PlanRow]
    totals: dict[str, float | None]
    sample_pricing: bool = False  # stub engine badge; remove before demo


class RiskHistogram(Props):
    bins: list[HistBin]
    exp_npv: float | None = None
    cvar5: float | None = None
    p_loss: float | None = None
    scope: Literal["plan", "building"]


class EvidenceGallery(Props):
    items: list[GalleryItem]


class FacadeCompass(Props):
    facades: dict[Literal["N", "E", "S", "W"], FacadeStats]


class FloorPlan(Props):
    rooms: list[Room]
    pins: list[Pin] = []


class UpgradeList(Props):
    upgrades: list[UpgradeRow]


class Baseline(Props):
    annual_spend_usd: float | None = None
    tonnes_per_year: float | None = None


class BuildingHeader(Props):
    profile: BuildingProfile
    baseline: Baseline


class TargetGapCard(Props):
    shortfall_tonnes: float
    cheapest_extra: list[ExtraCut]


class FinancingCard(Props):
    plan_id: str | None = None
    total_upfront_usd: float | None = None
    bills: list[Bill] = []
    state: Literal["proposed", "executed"] = "proposed"
    nessie_ids: dict[str, str] | None = None


class Memo(Props):
    markdown: str


class ActivityFeed(Props):
    run_id: str


@dataclass(frozen=True)
class WidgetDef:
    type: str
    props_model: type[Props]
    default_size: Size
    emits: tuple[str, ...] = ()  # OwnerAction types the widget can send
    description: str = ""
    required: tuple[str, ...] = field(default=())


def _d(type_: str, model: type[Props], size: Size, emits: tuple[str, ...] = (), desc: str = "") -> WidgetDef:
    req = tuple(n for n, f in model.model_fields.items() if f.is_required())
    return WidgetDef(type_, model, size, emits, desc, req)


WIDGETS: dict[str, WidgetDef] = {w.type: w for w in [
    _d("target_control", TargetControl, "full", ("set_target", "set_budget", "set_risk"), "Goal sliders and p(hit)"),
    _d("portfolio_3d", Portfolio3D, "wide", ("open_building", "exclude_building", "include_building"), "Buildings in 3D"),
    _d("hero_3d", Hero3D, "wide", (), "Matterport mesh with finding pins"),
    _d("abatement_curve", AbatementCurve, "half", ("select_bar",), "Marginal abatement cost curve"),
    _d("plan_table", PlanTable, "wide", ("toggle_upgrade", "open_building"), "Selected upgrades with totals"),
    _d("risk_histogram", RiskHistogram, "half", (), "NPV distribution"),
    _d("evidence_gallery", EvidenceGallery, "wide", (), "Images with marks and verifier status"),
    _d("facade_compass", FacadeCompass, "half", (), "Glazing per facade"),
    _d("floor_plan", FloorPlan, "half", (), "Matterport rooms and pins"),
    _d("upgrade_list", UpgradeList, "half", ("toggle_upgrade", "include_unverified"), "Feasible upgrades"),
    _d("building_header", BuildingHeader, "full", (), "Building profile and baseline"),
    _d("target_gap_card", TargetGapCard, "half", (), "Shortfall and cheapest extra cuts"),
    _d("financing_card", FinancingCard, "half", ("approve",), "Plan financing and Approve"),
    _d("memo", Memo, "wide", (), "Investment memo"),
    _d("activity_feed", ActivityFeed, "side", (), "Live agent events (frontend reads SSE)"),
]}


class RegistryError(ValueError):
    pass


def validate_props(widget_type: str, props: dict) -> Props:
    if widget_type not in WIDGETS:
        raise RegistryError(f"unknown widget type {widget_type!r}")
    try:
        return WIDGETS[widget_type].props_model.model_validate(props)
    except ValidationError as e:
        raise RegistryError(f"{widget_type}: invalid props: {e}") from e


def validate_layout(layout: Layout) -> Layout:
    """Layout rules beyond schema: registered types, valid props, unique ids, widget cap."""
    ids = [w.id for w in layout.widgets]
    if len(set(ids)) != len(ids):
        raise RegistryError("duplicate widget ids")
    if len(layout.widgets) > MAX_WIDGETS:
        raise RegistryError(f"more than {MAX_WIDGETS} widgets")
    for w in layout.widgets:
        validate_props(w.type, w.props)
    return layout


def json_schemas() -> dict:
    """Payload for GET /registry."""
    return {
        "grid_columns": GRID_COLUMNS,
        "max_widgets": MAX_WIDGETS,
        "widgets": {
            t: {"description": d.description, "default_size": d.default_size, "emits": list(d.emits),
                "required": list(d.required), "props_schema": d.props_model.model_json_schema()}
            for t, d in WIDGETS.items()
        },
    }
