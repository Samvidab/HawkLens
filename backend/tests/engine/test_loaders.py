"""Step 1: models, assumptions.json and fixtures load and agree with each other."""
import json
from pathlib import Path

import pytest

from app.engine.models import (
    ASSUMPTIONS_PATH,
    CATEGORY_BY_TYPE,
    SIZE_UNIT_BY_TYPE,
    FeasibleUpgrade,
    Goal,
    load_assumptions,
    load_feasibility,
)

FIXTURES = Path(__file__).parent / "fixtures"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]
ALL_TYPES = set(CATEGORY_BY_TYPE)

UPGRADE_KEYS = {
    "cost_unit", "unit_cost", "savings_mu", "savings_sd", "life_min", "life_max",
    "incentive_fraction", "incentive_p", "maint_frac_per_year", "source",
}
CITY_KEYS = {
    "electricity_rate_usd_per_kwh", "grid_kg_co2_per_kwh", "solar_kwh_per_kw_year",
    "kwh_per_sqft_year", "source",
}


def all_upgrades() -> list[FeasibleUpgrade]:
    return [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]


# --- fixtures -----------------------------------------------------------------

@pytest.mark.parametrize("building_id", BUILDING_IDS)
def test_feasibility_loads_and_matches_its_building(building_id):
    upgrades = load_feasibility(FIXTURES / building_id / "feasibility.json")
    assert upgrades
    for u in upgrades:
        assert u.building_id == building_id
        assert u.category == CATEGORY_BY_TYPE[u.type]
        assert u.size_unit == SIZE_UNIT_BY_TYPE[u.type]
        assert u.size_value > 0
        assert 0 <= u.confidence <= 1


@pytest.mark.parametrize("building_id", BUILDING_IDS)
def test_profile_has_fields_the_engine_needs(building_id):
    profile = json.loads((FIXTURES / building_id / "profile.json").read_text())
    assert profile["building_id"] == building_id
    assert profile["city"] == "Houston"
    assert profile["rba_sqft"] > 0
    assert profile["property_type"]


def test_fixtures_cover_every_upgrade_type_once_per_building():
    ups = all_upgrades()
    assert {u.type for u in ups} == ALL_TYPES
    ids = [u.upgrade_id for u in ups]
    assert len(ids) == len(set(ids))
    pairs = [(u.building_id, u.type) for u in ups]
    assert len(pairs) == len(set(pairs))


def test_fixtures_exercise_optimizer_edge_cases():
    ups = all_upgrades()
    # Two envelope upgrades on one building -> one-per-category constraint has work to do.
    hou1_envelope = [u for u in ups if u.building_id == "hou-001" and u.category == "envelope"]
    assert len(hou1_envelope) == 2
    # At least one upgrade the optimizer must skip, and one "assumed" upgrade.
    assert any(not u.include_in_optimizer for u in ups)
    assert any(u.verified == "assumed" for u in ups)


# --- assumptions.json -----------------------------------------------------------

def test_assumptions_cover_every_type_and_city():
    a = load_assumptions()
    assert set(a["upgrades"]) == ALL_TYPES
    for t, block in a["upgrades"].items():
        assert set(block) == UPGRADE_KEYS, t
        assert block["life_min"] <= block["life_max"], t
        assert 0 <= block["incentive_p"] <= 1, t
        assert block["savings_sd"] >= 0, t
    assert set(a["cities"]) == {"Houston"}   # Houston only; no LA values on purpose
    for c, block in a["cities"].items():
        assert set(block) == CITY_KEYS, c


def test_assumptions_globals_and_rates_are_decimals():
    g = load_assumptions()["global"]
    assert g["n_scenarios"] == 10000 and g["n_scenarios_optimizer"] == 1000
    assert isinstance(g["seed"], int)
    # "7 instead of 0.07" guard.
    assert 0 < g["discount_rate"] < 1
    assert {"mu", "sd", "source"} <= set(g["energy_price_growth"])
    assert {"p_fee_starts", "start_year_range", "price_range_per_tonne", "source"} <= set(g["carbon_price"])


def test_every_assumption_block_has_a_source():
    a = load_assumptions()
    blocks = [a["global"], a["global"]["energy_price_growth"], a["global"]["carbon_price"],
              a["building_estimates"], *a["cities"].values(), *a["upgrades"].values()]
    assert all(isinstance(b.get("source"), str) and b["source"] for b in blocks)


def test_assumptions_doc_lists_every_field():
    """ASSUMPTIONS.md must have a row for every key in assumptions.json."""
    doc = ASSUMPTIONS_PATH.with_name("ASSUMPTIONS.md").read_text()
    a = load_assumptions()
    names_not_fields = set(a["upgrades"]) | set(a["cities"])   # covered by <type> / Houston rows
    keys: set[str] = set()

    def walk(d):
        for k, v in d.items():
            if k.startswith("_"):
                continue                      # notes
            if k not in names_not_fields:
                keys.add(k)
            if isinstance(v, dict) and k != "kwh_per_sqft_year":   # its keys are a <type> row
                walk(v)

    walk(a)
    def in_a_path(k):   # key appears as the start, middle or end of a backticked path
        return any(p in doc for p in (f"`{k}.", f".{k}.", f".{k}`"))

    missing = sorted(k for k in keys if not in_a_path(k))
    assert not missing, f"add rows to ASSUMPTIONS.md for: {missing}"


def test_cost_units_match_size_units():
    expected = {"kW": "usd_per_kw", "sqft": "usd_per_sqft", "fixtures": "usd_per_fixture"}
    for t, block in load_assumptions()["upgrades"].items():
        assert block["cost_unit"] == expected[SIZE_UNIT_BY_TYPE[t]], t


# --- Goal -----------------------------------------------------------------------

def test_goal_defaults_match_trd():
    g = Goal(city="Houston", building_ids=None, target_pct=40, budget_usd=None)
    assert g.risk_lambda == 0.5 and g.discount_rate == 0.07


def test_goal_still_accepts_los_angeles_per_trd():
    assert Goal(city="Los Angeles", building_ids=None, target_pct=40, budget_usd=None).city == "Los Angeles"
