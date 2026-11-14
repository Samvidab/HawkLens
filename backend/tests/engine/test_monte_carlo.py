"""Step 3: monte_carlo.py + risk.py."""
import copy
import dataclasses
from pathlib import Path

import numpy as np
import pytest

from app.engine.buildings import load_building
from app.engine.models import load_assumptions, load_feasibility
from app.engine.monte_carlo import price_inputs, simulate
from app.engine.npv import npv
from app.engine.risk import cvar, hist_bins, summarize

FIXTURES = Path(__file__).parent / "fixtures"
TEST_ASSUMPTIONS = FIXTURES / "assumptions.json"
BUILDING_IDS = ["hou-001", "hou-002", "hou-003"]


@pytest.fixture(scope="module")
def portfolio():
    a = load_assumptions(TEST_ASSUMPTIONS)   # frozen placeholders: mechanics, not data
    buildings = {b: load_building(b, root=FIXTURES, assumptions=a) for b in BUILDING_IDS}
    upgrades = [u for b in BUILDING_IDS for u in load_feasibility(FIXTURES / b / "feasibility.json")]
    return upgrades, buildings, a


def deterministic(a):
    """Every sd = 0, every life fixed, incentive and carbon fee certain."""
    a = copy.deepcopy(a)
    a["global"]["energy_price_growth"]["sd"] = 0.0
    a["global"]["carbon_price"].update(p_fee_starts=1.0, start_year_range=[3, 3],
                                       price_range_per_tonne=[50, 50])
    for t in a["upgrades"].values():
        t["savings_sd"] = 0.0
        t["life_max"] = t["life_min"]
        t["incentive_p"] = 1.0
    return a


# --- requested tests ---------------------------------------------------------------

def test_zero_spread_mean_equals_npv_py(portfolio):
    upgrades, buildings, a = portfolio
    d = deterministic(a)
    sim = simulate(upgrades, buildings, d, n_scenarios=500)
    g = d["global"]
    for i, u in enumerate(upgrades):
        x = price_inputs(u, buildings[u.building_id], d)
        t = d["upgrades"][u.type]
        raw = t["savings_mu"] * x.kwh_basis_per_year
        on_site = min(raw, x.kwh_cap_per_year)
        exported = raw - on_site if x.exports_excess else 0.0
        kwh = on_site + exported
        expected = npv(
            upfront_usd=x.upfront_usd, incentive_usd=x.incentive_usd,
            incentive_lag_years=x.incentive_lag_years,
            base_savings_usd=on_site * x.electricity_rate_usd_per_kwh + exported * x.export_rate_usd_per_kwh,
            energy_price_growth=g["energy_price_growth"]["mu"],
            general_inflation=g["general_inflation"], discount_rate=g["discount_rate"],
            life_years=t["life_min"], maintenance_usd_per_year=x.maintenance_usd_per_year,
            tonnes_per_year=kwh * x.grid_kg_co2_per_kwh / 1000,
            carbon_price_per_tonne=50, carbon_start_year=3,
        )
        assert sim.npv[i].mean() == pytest.approx(expected, rel=1e-12, abs=1e-6), u.upgrade_id
        assert np.ptp(sim.npv[i]) == pytest.approx(0, abs=1e-6)        # every scenario identical


def test_mean_is_stable_from_1k_to_10k(portfolio):
    upgrades, buildings, a = portfolio
    small = simulate(upgrades, buildings, a, n_scenarios=1_000)
    big = simulate(upgrades, buildings, a, n_scenarios=10_000)
    for i, uid in enumerate(big.upgrade_ids):
        se_small = big.npv[i].std() / np.sqrt(1_000)                    # standard error at K = 1,000
        diff = abs(small.npv[i].mean() - big.npv[i].mean())
        assert diff <= 4 * se_small, f"{uid}: means differ by {diff:.0f}, > 4 SE ({4 * se_small:.0f})"


def test_same_seed_identical_output_and_new_seed_differs(portfolio):
    upgrades, buildings, a = portfolio
    one = simulate(upgrades, buildings, a, n_scenarios=2_000, seed=7)
    two = simulate(upgrades, buildings, a, n_scenarios=2_000, seed=7)
    other = simulate(upgrades, buildings, a, n_scenarios=2_000, seed=8)
    for field in ("npv", "tonnes_per_year", "tonnes_lifetime", "energy_price_growth"):
        assert np.array_equal(getattr(one, field), getattr(two, field)), field
    assert not np.array_equal(one.npv, other.npv)


# --- supporting checks -------------------------------------------------------------

def test_energy_price_growth_is_shared(portfolio):
    """With only g random, every upgrade's NPV moves with the same g, so they're ~perfectly correlated."""
    upgrades, buildings, a = portfolio
    d = deterministic(a)
    d["global"]["energy_price_growth"]["sd"] = 0.015
    sim = simulate(upgrades, buildings, d, n_scenarios=2_000)
    assert sim.energy_price_growth.shape == (2_000,)
    corr = np.corrcoef(sim.npv)
    assert corr.min() > 0.99


def test_excluding_an_upgrade_does_not_change_the_others(portfolio):
    upgrades, buildings, a = portfolio
    full = simulate(upgrades, buildings, a, n_scenarios=1_000)
    fewer = simulate(upgrades[1:], buildings, a, n_scenarios=1_000)
    for uid in fewer.upgrade_ids:
        assert np.array_equal(full.npv[full.index(uid)], fewer.npv[fewer.index(uid)])


def test_price_inputs_led_hand_check(portfolio):
    """hou-001 LED: 112,000 sqft of 112,000 sqft floor -> coverage 1.
    Baseline = 15 kWh/sqft (Office) x 120,000 rba = 1,800,000 kWh.
    Upfront = 112,000 x $1.50 = $168,000; incentive if received = 10% = $16,800."""
    upgrades, buildings, a = portfolio
    led = next(u for u in upgrades if u.upgrade_id == "hou-001-led_retrofit")
    x = price_inputs(led, buildings["hou-001"], a)
    assert x.coverage == 1.0
    assert x.kwh_basis_per_year == pytest.approx(1_800_000)
    assert x.upfront_usd == pytest.approx(168_000)
    assert x.incentive_usd == pytest.approx(16_800)
    assert x.maintenance_usd_per_year == 0


def test_solar_kwh_basis_is_generation(portfolio):
    """hou-002 solar: 307.2 kW x 1,450 kWh/kW/yr = 445,440 kWh."""
    upgrades, buildings, a = portfolio
    solar = next(u for u in upgrades if u.upgrade_id == "hou-002-rooftop_solar")
    assert price_inputs(solar, buildings["hou-002"], a).kwh_basis_per_year == pytest.approx(445_440)


def test_shapes_and_no_nans(portfolio):
    upgrades, buildings, a = portfolio
    sim = simulate(upgrades, buildings, a, n_scenarios=1_000)
    assert sim.npv.shape == sim.tonnes_per_year.shape == (len(upgrades), 1_000)
    assert np.isfinite(sim.npv).all() and (sim.tonnes_per_year >= 0).all()


def test_non_houston_city_is_rejected(portfolio):
    upgrades, buildings, a = portfolio
    la = {**buildings, "hou-002": dataclasses.replace(buildings["hou-002"], city="Los Angeles")}
    with pytest.raises(ValueError, match="Houston only"):
        simulate(upgrades, la, a, n_scenarios=10)


# --- risk.py -----------------------------------------------------------------------

def test_risk_hand_case():
    """NPVs -100, -99, ..., 99 (K = 200).
    exp_npv = -0.5; p_loss = 100/200 = 0.5; worst 5% = 10 values -100..-91 -> mean -95.5."""
    v = np.arange(-100, 100, dtype=float)
    r = summarize(v)
    assert r["exp_npv"] == pytest.approx(-0.5)
    assert r["p_loss"] == pytest.approx(0.5)
    assert r["cvar5"] == pytest.approx(-95.5)


def test_hist_bins_format():
    v = np.random.default_rng(0).normal(0, 1, 10_000)
    bins = hist_bins(v)
    assert len(bins) == 30
    assert all(b["x0"] < b["x1"] for b in bins)
    assert all(a["x1"] == pytest.approx(b["x0"]) for a, b in zip(bins, bins[1:]))
    assert 0.98 * 10_000 <= sum(b["count"] for b in bins) <= 10_000


def test_hist_bins_when_all_values_equal():
    bins = hist_bins(np.full(100, 42.0))
    assert len(bins) == 30 and sum(b["count"] for b in bins) == 100


def test_cvar_vectorized_over_upgrades():
    v = np.vstack([np.arange(-100, 100.0), np.arange(0, 200.0)])
    assert cvar(v) == pytest.approx([-95.5, 4.5])


# --- per-sqft savings and avoided replacement cost ------------------------------------

def test_cool_roof_and_insulation_savings_scale_with_area_treated(portfolio):
    """kwh_per_sqft_year: basis = sqft treated, so a 3x larger roof saves 3x more,
    whatever the building's height or total energy use.
    hou-001 roof 15,000 sqft, hou-002 roof 45,000 sqft; hou-001 wall 51,400 sqft."""
    upgrades, buildings, a = portfolio
    by_id = {u.upgrade_id: u for u in upgrades}
    basis = lambda uid: price_inputs(by_id[uid], buildings[by_id[uid].building_id], a).kwh_basis_per_year
    assert basis("hou-001-cool_roof") == 15_000
    assert basis("hou-002-cool_roof") == 45_000
    assert basis("hou-001-insulation") == 51_400
    # With the placeholder 0.4 kWh/sqft/yr, mean kWh saved = 0.4 x sqft.
    sim = simulate(upgrades, buildings, deterministic(a), n_scenarios=10)
    kwh = lambda uid: sim.tonnes_per_year[sim.index(uid)][0] * 1000 / 0.38
    assert kwh("hou-001-cool_roof") == pytest.approx(6_000)
    assert kwh("hou-002-cool_roof") == pytest.approx(18_000)


def test_avoided_replacement_cost_hand_check(portfolio):
    """hou-001 heat pump, 112,000 sqft:
    gross    = 112,000 x $20  = $2,240,000
    avoided  = 112,000 x $12  = $1,344,000
    upfront  = 2,240,000 - 1,344,000 = $896,000   (incremental over like-for-like)
    incentive if received = 20% x gross = $448,000
    maintenance = 2% x NET upfront = 2% x $896,000 = $17,920/yr (like-for-like would need upkeep too)"""
    upgrades, buildings, a = portfolio
    hp = next(u for u in upgrades if u.upgrade_id == "hou-001-heat_pump")
    x = price_inputs(hp, buildings["hou-001"], a)
    assert x.gross_cost_usd == pytest.approx(2_240_000)
    assert x.avoided_replacement_usd == pytest.approx(1_344_000)
    assert x.upfront_usd == pytest.approx(896_000)
    assert x.incentive_usd == pytest.approx(448_000)
    assert x.maintenance_usd_per_year == pytest.approx(17_920)


def test_upfront_never_below_zero(portfolio):
    upgrades, buildings, a = portfolio
    d = copy.deepcopy(a)
    d["upgrades"]["cool_roof"]["avoided_replacement_cost_per_unit"] = 5.0     # > unit_cost 2.0
    roof = next(u for u in upgrades if u.upgrade_id == "hou-001-cool_roof")
    assert price_inputs(roof, buildings["hou-001"], d).upfront_usd == 0.0


def test_avoided_cost_is_optional(portfolio):
    upgrades, buildings, a = portfolio
    d = copy.deepcopy(a)
    del d["upgrades"]["heat_pump"]["avoided_replacement_cost_per_unit"]
    hp = next(u for u in upgrades if u.upgrade_id == "hou-001-heat_pump")
    x = price_inputs(hp, buildings["hou-001"], d)
    assert x.avoided_replacement_usd == 0 and x.upfront_usd == x.gross_cost_usd


def test_unknown_savings_unit_is_rejected(portfolio):
    upgrades, buildings, a = portfolio
    d = copy.deepcopy(a)
    d["upgrades"]["insulation"]["savings_unit"] = "percent"
    ins = next(u for u in upgrades if u.upgrade_id == "hou-001-insulation")
    with pytest.raises(ValueError, match="unknown savings_unit"):
        price_inputs(ins, buildings["hou-001"], d)


# --- caps ------------------------------------------------------------------------------

def test_efficiency_kwh_capped_at_share_of_baseline(portfolio):
    """hou-001 heat pump, deterministic, savings_mu raised to 0.8 by hand:
    raw = 0.8 x 1,800,000 baseline = 1,440,000 kWh; cap = 0.5 x 1,800,000 = 900,000 kWh.
    Excess is dropped (not exported): tonnes = 900,000 x 0.38 / 1000 = 342.0 t/yr."""
    upgrades, buildings, a = portfolio
    d = deterministic(a)
    d["upgrades"]["heat_pump"]["savings_mu"] = 0.8
    hp = next(u for u in upgrades if u.upgrade_id == "hou-001-heat_pump")
    x = price_inputs(hp, buildings["hou-001"], d)
    assert x.kwh_cap_per_year == pytest.approx(900_000)
    assert not x.exports_excess and x.export_rate_usd_per_kwh == 0
    sim = simulate([hp], buildings, d, n_scenarios=10)
    assert sim.tonnes_per_year[0][0] == pytest.approx(342.0)


def test_solar_self_consumes_up_to_baseline_and_exports_the_rest(portfolio):
    """hou-002 solar resized to 600 kW by hand, deterministic (s = 0.95):
    generation   = 600 x 1,450 x 0.95                 = 826,500 kWh
    self-used    = min(826,500, 630,000 baseline x 1.0) = 630,000 kWh at $0.12 = $75,600
    exported     = 826,500 - 630,000                   = 196,500 kWh at $0.04 = $7,860
    savings      = $83,460 / yr at trailing-12-month prices
    CO2 counts ALL generation: 826,500 x 0.38 / 1000   = 314.07 t/yr"""
    upgrades, buildings, a = portfolio
    d = deterministic(a)
    solar = next(u for u in upgrades if u.upgrade_id == "hou-002-rooftop_solar").model_copy(
        update={"size_value": 600.0})
    x = price_inputs(solar, buildings["hou-002"], d)
    assert x.kwh_cap_per_year == pytest.approx(630_000)        # 100%, not max_savings_share
    assert x.exports_excess and x.export_rate_usd_per_kwh == pytest.approx(0.04)
    sim = simulate([solar], buildings, d, n_scenarios=10)
    assert sim.tonnes_per_year[0][0] == pytest.approx(314.07)
    g = d["global"]
    t = d["upgrades"]["rooftop_solar"]
    expected = npv(
        upfront_usd=x.upfront_usd, incentive_usd=x.incentive_usd,
        incentive_lag_years=x.incentive_lag_years, base_savings_usd=83_460,
        energy_price_growth=g["energy_price_growth"]["mu"], general_inflation=g["general_inflation"],
        discount_rate=g["discount_rate"], life_years=t["life_min"],
        maintenance_usd_per_year=x.maintenance_usd_per_year, tonnes_per_year=314.07,
        carbon_price_per_tonne=50, carbon_start_year=3,
    )
    assert sim.npv[0][0] == pytest.approx(expected, rel=1e-9)


def test_fixture_solar_is_not_capped(portfolio):
    """hou-002's real 307.2 kW system makes ~423,000 kWh, below its 630,000 kWh baseline,
    so nothing is exported and every kWh is valued at the retail rate."""
    upgrades, buildings, a = portfolio
    solar = next(u for u in upgrades if u.upgrade_id == "hou-002-rooftop_solar")
    sim = simulate([solar], buildings, a, n_scenarios=5_000)
    kwh = sim.tonnes_per_year[0] * 1000 / 0.38
    assert kwh.max() < 630_000


def test_zero_export_rate_still_counts_exported_co2(portfolio):
    """A $0 buyback rate values exports at $0 but they still displace grid power (CO2 counted)."""
    upgrades, buildings, a = portfolio
    d = deterministic(a)
    d["cities"]["Houston"]["export_rate_usd_per_kwh"] = 0.0
    solar = next(u for u in upgrades if u.upgrade_id == "hou-002-rooftop_solar").model_copy(
        update={"size_value": 600.0})
    sim = simulate([solar], buildings, d, n_scenarios=10)
    assert sim.tonnes_per_year[0][0] == pytest.approx(314.07)


def test_invalid_max_savings_share_is_rejected(portfolio):
    upgrades, buildings, a = portfolio
    d = copy.deepcopy(a)
    d["global"]["max_savings_share"] = 50          # percent, not decimal
    led = next(u for u in upgrades if u.upgrade_id == "hou-001-led_retrofit")   # efficiency, not solar
    with pytest.raises(ValueError, match="max_savings_share"):
        price_inputs(led, buildings["hou-001"], d)


def test_incentive_never_exceeds_gross_cost(portfolio):
    """incentive_fraction 1.5 by mistake -> incentive = gross cost, not 150% of it."""
    upgrades, buildings, a = portfolio
    d = copy.deepcopy(a)
    d["upgrades"]["led_retrofit"]["incentive_fraction"] = 1.5
    led = next(u for u in upgrades if u.upgrade_id == "hou-001-led_retrofit")
    x = price_inputs(led, buildings["hou-001"], d)
    assert x.incentive_usd == x.gross_cost_usd == pytest.approx(168_000)


def test_incentive_on_full_cost_even_with_avoided_replacement(portfolio):
    """hou-001 heat pump: incentive = 20% of gross $2,240,000 = $448,000, not 20% of the $896,000 upfront."""
    upgrades, buildings, a = portfolio
    hp = next(u for u in upgrades if u.upgrade_id == "hou-001-heat_pump")
    x = price_inputs(hp, buildings["hou-001"], a)
    assert x.incentive_usd == pytest.approx(448_000) and x.upfront_usd == pytest.approx(896_000)



# --- maintenance basis and size_unit validation ----------------------------------------------

def test_maintenance_on_gross_when_no_avoided_replacement(portfolio):
    """hou-001 solar: no avoided cost -> maintenance = 1% x gross 125.4 kW x $2,500 = $3,135/yr."""
    upgrades, buildings, a = portfolio
    solar = next(u for u in upgrades if u.upgrade_id == "hou-001-rooftop_solar")
    x = price_inputs(solar, buildings["hou-001"], a)
    assert x.upfront_usd == x.gross_cost_usd == pytest.approx(313_500)
    assert x.maintenance_usd_per_year == pytest.approx(3_135)


@pytest.mark.parametrize("uid,bad_unit", [
    ("hou-001-led_retrofit", "fixtures"),     # LED counted in fixtures instead of floor sqft
    ("hou-001-rooftop_solar", "sqft"),        # solar in sqft instead of kW
    ("hou-001-heat_pump", "kW"),
])
def test_size_unit_mismatch_raises_clear_error(portfolio, uid, bad_unit):
    upgrades, buildings, a = portfolio
    u = next(x for x in upgrades if x.upgrade_id == uid).model_copy(update={"size_unit": bad_unit})
    with pytest.raises(ValueError, match=rf"{uid}: .* must be sized in .* but size_unit is '{bad_unit}'"):
        price_inputs(u, buildings["hou-001"], a)
    with pytest.raises(ValueError, match="size_unit"):
        simulate([u], buildings, a, n_scenarios=10)
