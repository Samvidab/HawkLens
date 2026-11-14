"""Step 4: curve.py (abatement curve) on the cached simulation."""
from pathlib import Path

import numpy as np
import pytest

from app.engine import state
from app.engine.buildings import load_building
from app.engine.curve import cost_per_tonne, macc
from app.engine.models import load_assumptions, load_feasibility
from app.engine.monte_carlo import simulate

FIXTURES = Path(__file__).parent / "fixtures"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]
BAR_KEYS = {"upgrade_id", "building_id", "type", "tonnes_per_year", "cost_per_tonne"}


@pytest.fixture(scope="module")
def sim_and_upgrades():
    a = load_assumptions()
    buildings = {b: load_building(b, root=FIXTURES, assumptions=a) for b in BUILDING_IDS}
    upgrades = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    return simulate(upgrades, buildings, a, n_scenarios=10_000), upgrades


@pytest.fixture(autouse=True)
def cached(sim_and_upgrades):
    state.set_simulation(*sim_and_upgrades)
    yield
    state.clear()


def test_bars_sorted_ascending_and_match_trd_shape():
    bars = macc([])["bars"]
    assert bars
    assert all(set(b) == BAR_KEYS for b in bars)
    costs = [b["cost_per_tonne"] for b in bars]
    assert costs == sorted(costs)


def test_positive_npv_gives_negative_cost_per_tonne(sim_and_upgrades):
    sim, _ = sim_and_upgrades
    by_id = {b["upgrade_id"]: b for b in macc([])["bars"]}
    checked = 0
    for i, uid in enumerate(sim.upgrade_ids):
        if uid not in by_id:
            continue
        exp_npv = sim.npv[i].mean()
        assert np.sign(by_id[uid]["cost_per_tonne"]) == -np.sign(exp_npv), uid
        checked += exp_npv > 0
    assert checked >= 1     # the fixtures do contain money-making upgrades (solar, cool roof)


def test_excluding_a_building_removes_all_its_bars():
    bars = macc(["hou-001"])["bars"]
    assert bars and all(b["building_id"] != "hou-001" for b in bars)
    assert {b["building_id"] for b in bars} == {"hou-002", "hou-003"}


def test_excluding_an_upgrade_removes_only_that_bar():
    full = {b["upgrade_id"] for b in macc([])["bars"]}
    fewer = {b["upgrade_id"] for b in macc(["hou-002-cool_roof"])["bars"]}
    assert full - fewer == {"hou-002-cool_roof"}


def test_unverified_hou_003_window_upgrade_is_excluded():
    ids = {b["upgrade_id"] for b in macc([])["bars"]}
    assert "hou-003-window_upgrade" not in ids
    assert len(ids) == 12      # 13 fixture upgrades minus the one with include_in_optimizer=False


def test_cost_per_tonne_hand_case():
    """exp_npv = mean(-100, 300) = 100; lifetime tonnes mean(4, 6) = 5 -> -100 / 5 = -20 $/t.
    Second row: exp_npv -50, tonnes 10 -> +5 $/t. Third row: zero tonnes -> NaN (no bar)."""
    npv = np.array([[-100.0, 300.0], [-50.0, -50.0], [10.0, 10.0]])
    tonnes = np.array([[4.0, 6.0], [10.0, 10.0], [0.0, 0.0]])
    out = cost_per_tonne(npv, tonnes)
    assert out[:2] == pytest.approx([-20.0, 5.0])
    assert np.isnan(out[2])


def test_macc_before_simulate_raises():
    state.clear()
    with pytest.raises(state.NoSimulation):
        macc([])
