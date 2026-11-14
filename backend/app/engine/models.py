"""Engine-side copies of the TRD §5 schemas the engine consumes.

TEMPORARY MIRROR: `FeasibleUpgrade` and `Goal` are copied field-for-field from
docs/agent/02-TRD.md §5. When the agent branch lands `app/schemas/upgrades.py`
on main, delete these two classes and import from there instead.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, TypeAdapter

UpgradeType = Literal[
    "rooftop_solar", "cool_roof", "window_upgrade", "heat_pump", "insulation", "led_retrofit"
]
Category = Literal["lighting", "hvac", "envelope", "solar", "roof"]
City = Literal["Houston", "Los Angeles"]


class FeasibleUpgrade(BaseModel):          # feasibility.json = list[FeasibleUpgrade]
    upgrade_id: str
    building_id: str
    category: Category
    type: UpgradeType
    size_value: float
    size_unit: Literal["kW", "sqft", "fixtures"]
    reason: str
    confidence: float
    claim_ids: list[str]
    evidence_ids: list[str]
    verified: Literal["verified", "unverified", "assumed"]   # led_retrofit default = "assumed"
    include_in_optimizer: bool             # False if unverified unless owner overrides


class Goal(BaseModel):
    city: City
    building_ids: list[str] | None
    target_pct: float
    budget_usd: float | None
    risk_lambda: float = 0.5
    discount_rate: float = 0.07


# Engine-only lookups (not in the TRD schema). Category per type is fixed by the
# vocabulary table in engine/CLAUDE.md; the optimizer's one-per-building-per-category
# rule depends on it.
CATEGORY_BY_TYPE: dict[str, str] = {
    "rooftop_solar": "solar",
    "cool_roof": "roof",
    "window_upgrade": "envelope",
    "insulation": "envelope",
    "heat_pump": "hvac",
    "led_retrofit": "lighting",
}

# Unit the agent's feasibility rules (TRD §7) size each type in. led_retrofit is
# sized in sqft there, not fixtures; unit_cost in assumptions.json follows this.
SIZE_UNIT_BY_TYPE: dict[str, str] = {
    "rooftop_solar": "kW",
    "cool_roof": "sqft",
    "window_upgrade": "sqft",
    "insulation": "sqft",
    "heat_pump": "sqft",
    "led_retrofit": "sqft",
}

ASSUMPTIONS_PATH = Path(__file__).with_name("assumptions.json")

_upgrade_list = TypeAdapter(list[FeasibleUpgrade])


def load_feasibility(path: str | Path) -> list[FeasibleUpgrade]:
    """Read a feasibility.json file and validate every upgrade in it."""
    return _upgrade_list.validate_json(Path(path).read_bytes())


def load_assumptions(path: str | Path = ASSUMPTIONS_PATH) -> dict[str, Any]:
    """Read assumptions.json as a plain dict (keys starting with '_' are notes)."""
    return json.loads(Path(path).read_text())
