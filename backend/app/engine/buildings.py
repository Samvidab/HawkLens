"""Building facts the engine needs, read from data/buildings/<id>/.

This is the ONLY module that knows the field names in profile.json and
interior.json. If the agent team renames a field, change it here.
"""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import get_settings

from .models import load_assumptions

SQFT_PER_M2 = 10.7639
FT_PER_M = 3.28084

# CoStar property_type -> benchmark key in assumptions.json cities.<city>.kwh_per_sqft_year.
# Matching is case-insensitive. Anything not listed falls back to DEFAULT_BENCHMARK_TYPE.
# TODO(agent owner): confirm these against CoStar's real property_type values once
# T0.3 discovery has the field list; add every real spelling we see in data/.
PROPERTY_TYPE_TO_BENCHMARK: dict[str, str] = {
    "office": "Office",
    "retail": "Retail",
    "industrial": "Industrial",
    "multi-family": "Multi-Family",
    "multifamily": "Multi-Family",
}
DEFAULT_BENCHMARK_TYPE = "Other"


def benchmark_type(property_type: str | None) -> str:
    """Map a CoStar property_type to a benchmark key; unknown or missing -> 'Other'."""
    if not property_type:
        return DEFAULT_BENCHMARK_TYPE
    return PROPERTY_TYPE_TO_BENCHMARK.get(property_type.strip().lower(), DEFAULT_BENCHMARK_TYPE)


@dataclass(frozen=True)
class BuildingFacts:
    building_id: str
    city: str
    property_type: str | None
    benchmark_type: str
    rba_sqft: float | None
    stories: int | None
    floor_area_sqft: float | None
    floor_area_estimated: bool       # True = rba_sqft stand-in, not measured by the scan
    envelope_area_sqft: float | None
    envelope_area_estimated: bool    # True = geometric estimate, not measured by the scan


def estimate_envelope_area_sqft(
    rba_sqft: float | None, stories: int | None, floor_height_m: float
) -> float | None:
    """Exterior wall area, assuming a square footprint of rba_sqft / stories.

    Same formula as TRD section 7 (wall length x floor height x stories), with the
    wall length taken from a square instead of a measured footprint. A long thin
    building has more wall than this, so the estimate is a lower bound.
    """
    if not rba_sqft or not stories or rba_sqft <= 0 or stories <= 0:
        return None
    footprint_sqft = rba_sqft / stories
    perimeter_ft = 4 * math.sqrt(footprint_sqft)
    return perimeter_ft * floor_height_m * FT_PER_M * stories


def _read_json(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text()) if path.exists() else None


def load_building(
    building_id: str,
    root: str | Path | None = None,
    assumptions: dict[str, Any] | None = None,
) -> BuildingFacts:
    """Read profile.json (required) and interior.json (optional) for one building."""
    root = Path(root) if root is not None else get_settings().data_dir / "buildings"
    a = assumptions if assumptions is not None else load_assumptions()
    folder = root / building_id

    profile = _read_json(folder / "profile.json")
    if profile is None:
        raise FileNotFoundError(f"no profile.json for building {building_id!r} in {root}")
    interior = _read_json(folder / "interior.json") or {}

    rba = profile.get("rba_sqft")
    stories = profile.get("stories")

    floor_area = interior.get("floor_area_sqft")
    floor_estimated = floor_area is None
    if floor_estimated:
        floor_area = rba

    envelope = interior.get("envelope_area_sqft")
    envelope_estimated = envelope is None
    if envelope_estimated:
        floor_height_m = a["building_estimates"]["floor_height_m"]
        envelope = estimate_envelope_area_sqft(rba, stories, floor_height_m)

    return BuildingFacts(
        building_id=profile["building_id"],
        city=profile["city"],
        property_type=profile.get("property_type"),
        benchmark_type=benchmark_type(profile.get("property_type")),
        rba_sqft=rba,
        stories=stories,
        floor_area_sqft=floor_area,
        floor_area_estimated=floor_estimated,
        envelope_area_sqft=envelope,
        envelope_area_estimated=envelope_estimated,
    )


def roof_area_sqft(b: BuildingFacts) -> float | None:
    """Roof area = footprint = rba_sqft / stories (flat-roof assumption, same as TRD section 7)."""
    if not b.rba_sqft or not b.stories or b.rba_sqft <= 0 or b.stories <= 0:
        return None
    return b.rba_sqft / b.stories


def baseline_kwh_per_year(b: BuildingFacts, assumptions: dict[str, Any]) -> float:
    """Annual electricity use from the city benchmark: kWh/sqft/yr for the building type x rba_sqft.

    TODO(step 6): when NESSIE_MODE=live, use the trailing 12 months of bills instead.
    """
    city = assumptions["cities"].get(b.city)
    if city is None:
        raise ValueError(f"no assumptions for city {b.city!r}; the engine is Houston only")
    if not b.rba_sqft or b.rba_sqft <= 0:
        raise ValueError(f"building {b.building_id!r} has no rba_sqft, so no benchmark baseline")
    return city["kwh_per_sqft_year"][b.benchmark_type] * b.rba_sqft


def baseline_tonnes_per_year(b: BuildingFacts, assumptions: dict[str, Any]) -> float:
    """CO2 from the building's baseline electricity: baseline kWh x grid kg/kWh / 1000."""
    grid = assumptions["cities"][b.city]["grid_kg_co2_per_kwh"]
    return baseline_kwh_per_year(b, assumptions) * grid / 1000.0
