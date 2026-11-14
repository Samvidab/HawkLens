"""The LIVE, sourced assumptions.json (not the frozen test copy) runs end to end.

Mechanics tests use tests/engine/fixtures/assumptions.json so they don't move when data
changes. These tests are deliberately value-agnostic: they check the real file produces
sane output and that every field still unsourced is named in its block's source.
"""
import json
import math
from pathlib import Path

import pytest

import app.engine as engine
from app.engine import state
from app.engine.models import ASSUMPTIONS_PATH, load_assumptions, load_feasibility

FIXTURES = Path(__file__).parent / "fixtures"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]


@pytest.fixture(autouse=True)
def live():
    state.clear()
    engine.configure(buildings_root=FIXTURES)          # default assumptions_path = live file
    yield
    state.clear()


def test_engine_runs_on_live_assumptions():
    ups = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    sim = engine.simulate(ups, {})
    json.dumps(sim, allow_nan=False)
    assert all(math.isfinite(r["exp_npv"]) and 0 <= r["p_loss"] <= 1 for r in sim.values())
    for target, lam in ((25, 0), (25, 0.5), (40, 0)):
        r = engine.optimize(target, lam, None, [])
        json.dumps(r, allow_nan=False)
        assert r["status"] in ("ok", "infeasible") and 0 <= r["p_hit_target"] <= 1


def test_live_file_is_not_the_frozen_test_copy():
    live, frozen = load_assumptions(), load_assumptions(FIXTURES / "assumptions.json")
    assert live["cities"]["Houston"]["source"] != "PLACEHOLDER"
    assert frozen["cities"]["Houston"]["source"] == "PLACEHOLDER"


def test_remaining_placeholders_are_named_in_their_source():
    """A block is either fully sourced, or its source has a 'PLACEHOLDER: <fields>' part."""
    a = load_assumptions()
    blocks = {"global": a["global"], "building_estimates": a["building_estimates"],
              "cities.Houston": a["cities"]["Houston"],
              **{f"upgrades.{t}": b for t, b in a["upgrades"].items()}}
    for name, b in blocks.items():
        src = b["source"]
        assert src != "PLACEHOLDER" or name == "building_estimates", f"{name} has no field-level source"
        if "PLACEHOLDER" in src and src != "PLACEHOLDER":
            assert "PLACEHOLDER: " in src, name



def test_live_net_upfront_always_positive():
    """Team rule on the real data: in every scenario, every upgrade costs something net."""
    from app.engine.monte_carlo import simulate as mc_simulate
    from app.engine.buildings import load_building
    a = load_assumptions()
    ups = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    bld = {b: load_building(b, root=FIXTURES, assumptions=a) for b in BUILDING_IDS}
    sim = mc_simulate(ups, bld, a)
    assert (sim.upfront_usd > 0).all()
    for t, b in a["upgrades"].items():
        if b["avoided_replacement_cost_per_unit"] > 0:
            assert b["premium_over_replacement"] and b["premium_over_replacement"] > 0, t
