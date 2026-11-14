"""Site engineer: deterministic feasibility rules (TRD §7). No LLM, no network.

evaluate(profile, aerial, interior, claims) -> list[FeasibleUpgrade]
apply_verification(upgrades, claims, owner_included) re-derives verified / include_in_optimizer
after the verifier loop (TRD §6.3).
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable

import yaml
from pyproj import Transformer
from shapely import wkt as shapely_wkt
import shapely

from app.adapters.geometry import SQFT_PER_M2, area_m2, footprint_polygon, utm_epsg
from app.schemas.aerial import AerialFindings
from app.schemas.claims import Claim
from app.schemas.interior import InteriorFindings
from app.schemas.profile import BuildingProfile
from app.schemas.upgrades import FeasibleUpgrade

RULES_PATH = Path(__file__).with_name("feasibility.yaml")

CATEGORY = {"rooftop_solar": "solar", "cool_roof": "roof", "window_upgrade": "envelope",
            "heat_pump": "hvac", "insulation": "envelope", "led_retrofit": "lighting"}
BAD_STATES = {"rejected", "unverified"}


@lru_cache
def load_rules(path: str | None = None) -> dict:
    return yaml.safe_load(Path(path or RULES_PATH).read_text())


def _facade_lengths_m(footprint_wkt: str, city: str) -> dict[str, float]:
    """Facade length per orientation from the footprint's UTM bounding box (N/S = width, E/W = depth)."""
    geom = shapely_wkt.loads(footprint_wkt)
    tr = Transformer.from_crs(4326, utm_epsg(city, geom.centroid.x), always_xy=True)
    x0, y0, x1, y1 = shapely.transform(geom, lambda x, y: tr.transform(x, y), interleaved=False).bounds
    return {"N": x1 - x0, "S": x1 - x0, "E": y1 - y0, "W": y1 - y0}


def _link(claims: Iterable[Claim], prefixes: list[str]) -> list[Claim]:
    return [c for c in claims if any(c.field.startswith(p) for p in prefixes)]


def _state(linked: list[Claim]) -> tuple[str, bool]:
    """(verified|unverified, include_in_optimizer) from the status of the backing claims."""
    if not linked:
        return "unverified", False
    if all(c.status == "verified" for c in linked):
        return "verified", True
    return "unverified", False  # pending / sent_back / unverified / rejected


def _make(profile, rule_type: str, size: float, unit: str, reason: str, linked: list[Claim],
          *, record_based: bool = False, assumed_conf: float | None = None) -> FeasibleUpgrade:
    if assumed_conf is not None and not linked:
        verified, include, conf = "assumed", True, assumed_conf
    elif record_based and not linked:
        verified, include, conf = "verified", True, 1.0  # driven by a CoStar record field
    else:
        verified, include = _state(linked)
        conf = min((c.confidence for c in linked), default=0.0)
    return FeasibleUpgrade(
        upgrade_id=f"{profile.building_id}:{rule_type}", building_id=profile.building_id,
        category=CATEGORY[rule_type], type=rule_type, size_value=round(size, 1), size_unit=unit,
        reason=reason, confidence=conf, claim_ids=[c.claim_id for c in linked],
        evidence_ids=sorted({e for c in linked for e in c.evidence_ids}),
        verified=verified, include_in_optimizer=include)


def evaluate(profile: BuildingProfile, aerial: AerialFindings, interior: InteriorFindings | None = None,
             claims: list[Claim] | None = None, rules: dict | None = None) -> list[FeasibleUpgrade]:
    rules = rules or load_rules()
    claims = claims or []
    cf = rules["claim_fields"]
    out: list[FeasibleUpgrade] = []

    fp_wkt, _ = footprint_polygon(profile)
    footprint_sqft = area_m2(fp_wkt, profile.city) * SQFT_PER_M2
    floor_area = (interior.floor_area_sqft if interior else None) or profile.rba_sqft
    shading_label = aerial.shading

    # rooftop_solar
    r = rules["rooftop_solar"]; q = r["requires"]
    if (aerial.existing_solar == q["existing_solar"] and aerial.shading in q["shading_in"]
            and aerial.usable_roof_m2 >= q["usable_roof_m2_min"]):
        derate = r["shading_derate"][aerial.shading]
        kw = aerial.usable_roof_m2 * r["packing_factor"] * r["panel_kw_per_m2"] * derate
        out.append(_make(profile, "rooftop_solar", kw, "kW",
                         f"{aerial.usable_roof_m2:.0f} m2 usable roof, no existing solar, "
                         f"shading {shading_label} (derate {derate})",
                         _link(claims, cf["rooftop_solar"])))

    # cool_roof
    r = rules["cool_roof"]; q = r["requires"]
    if aerial.roof_color == q["roof_color"] and aerial.roof_type in q["roof_type_in"]:
        out.append(_make(profile, "cool_roof", footprint_sqft, "sqft",
                         f"{aerial.roof_type} {aerial.roof_color} roof in a hot climate",
                         _link(claims, cf["cool_roof"])))

    # window_upgrade
    r = rules["window_upgrade"]
    facades = r["requires_any_facade_in"]
    hot = [o for o in facades if (f := aerial.facades.get(o)) and f.glazing_ratio is not None]
    if any(aerial.facades[o].glazing_ratio >= r["glazing_ratio_min"] for o in hot):
        lengths = _facade_lengths_m(fp_wkt, profile.city)
        height = (profile.stories or 1) * rules["constants"]["floor_height_m"]
        sqft = sum(lengths[o] * height * aerial.facades[o].glazing_ratio for o in hot) * SQFT_PER_M2
        prefixes = [p.replace("{O}", o) for p in cf["window_upgrade"] for o in facades]
        ratios = ", ".join(f"{o} {aerial.facades[o].glazing_ratio:.0%}" for o in hot)
        out.append(_make(profile, "window_upgrade", sqft, "sqft", f"high glazing on sun-facing facades ({ratios})",
                         _link(claims, prefixes)))

    # heat_pump
    r = rules["heat_pump"]
    year_hit = profile.year_built is not None and any(
        profile.year_built <= t["year_built_max"] for t in r["requires_any"] if "year_built_max" in t)
    needles = [n for t in r["requires_any"] for n in t.get("hvac_visible_contains", [])]
    hvac_hits = [h for h in (interior.hvac_visible if interior else []) if any(n in h.lower() for n in needles)]
    hp_size = floor_area
    if (year_hit or hvac_hits) and hp_size:
        why = [f"built {profile.year_built}"] if year_hit else []
        why += [f"visible {h}" for h in hvac_hits]
        linked = _link(claims, cf["heat_pump"]) if hvac_hits else []
        out.append(_make(profile, "heat_pump", hp_size, "sqft", "; ".join(why), linked,
                         record_based=year_hit and not hvac_hits))

    # insulation
    if interior and interior.envelope_area_sqft:
        out.append(_make(profile, "insulation", interior.envelope_area_sqft, "sqft",
                         "envelope area measured from the interior wall graph", _link(claims, cf["insulation"])))

    # led_retrofit
    r = rules["led_retrofit"]
    lighting = interior.lighting_type if interior else "unknown"
    if lighting != r["skip_if"]["lighting_type"] and floor_area:
        linked = _link(claims, cf["led_retrofit"]) if lighting != "unknown" else []
        why = f"lighting observed as {lighting}" if linked else "lighting type not observed; assumed non-LED"
        out.append(_make(profile, "led_retrofit", floor_area, "sqft", why, linked,
                         assumed_conf=r["assumed_confidence"]))

    return out


def apply_verification(upgrades: list[FeasibleUpgrade], claims: Iterable[Claim],
                       owner_included: set[str] | None = None) -> list[FeasibleUpgrade]:
    """Re-derive verified / include_in_optimizer / confidence from final claim statuses.

    Assumed and record-based upgrades (no claims) are left as they are. An owner override
    (`include_unverified`) turns include_in_optimizer on but never changes `verified`.
    """
    by_id = {c.claim_id: c for c in claims}
    owner_included = owner_included or set()
    out = []
    for u in upgrades:
        linked = [by_id[i] for i in u.claim_ids if i in by_id]
        if linked:
            verified, include = _state(linked)
            u = u.model_copy(update={"verified": verified, "include_in_optimizer": include,
                                     "confidence": min(c.confidence for c in linked)})
        if u.upgrade_id in owner_included:
            u = u.model_copy(update={"include_in_optimizer": True})
        out.append(u)
    return out
