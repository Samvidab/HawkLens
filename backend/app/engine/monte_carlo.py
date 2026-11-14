"""Monte Carlo simulation of every upgrade's NPV and CO2 (engine/CLAUDE.md "Monte Carlo").

Two layers:
1. price_inputs(): turns one FeasibleUpgrade into fixed numbers (cost, incentive,
   maintenance, the kWh its savings fraction applies to). No randomness.
2. simulate(): draws K scenarios and evaluates npv() once for all upgrades x all
   scenarios as (n_upgrades, K) arrays. The only Python loop is over upgrades
   (to draw each one's random inputs); nothing loops over scenarios.

Random streams:
- SHARED by all upgrades (one draw per scenario): energy price growth g, and the
  carbon fee (whether it starts, its start year, its price). These are market-wide,
  so sharing them makes upgrades rise and fall together, which is what the
  optimizer's risk term needs to see.
- PER UPGRADE: savings fraction s, life L, whether the incentive is received.
  Each upgrade gets its own stream seeded from (seed, upgrade_id), so adding or
  excluding one upgrade never changes another upgrade's numbers.
"""
from __future__ import annotations

import zlib
from dataclasses import dataclass
from typing import Any

import numpy as np

from .buildings import BuildingFacts, baseline_kwh_per_year
from .models import FeasibleUpgrade
from .npv import npv as npv_fn

# For "fraction_of_building_kwh" types: what the savings fraction is scaled by
# (ASSUMPTIONS.md "Scales with"). None = not scaled (fixed).
_COVERAGE_AREA = {
    "heat_pump": lambda b: b.floor_area_sqft,
    "led_retrofit": lambda b: b.floor_area_sqft,
    "window_upgrade": None,
}
SAVINGS_UNITS = ("fraction_of_building_kwh", "kwh_per_sqft_year", "fraction_of_modeled_generation")


@dataclass(frozen=True)
class UpgradeInputs:
    """Fixed (non-random) numbers for one upgrade."""
    upgrade_id: str
    gross_cost_usd: float           # unit_cost x size: full installed price
    avoided_replacement_usd: float  # avoided_replacement_cost_per_unit x size
    upfront_usd: float              # C0 = max(gross - avoided, 0): incremental cost
    incentive_usd: float            # amount IF received = incentive_fraction x gross cost
    incentive_lag_years: int
    maintenance_usd_per_year: float  # M at today's prices = maint_frac x gross cost
    coverage: float                 # 0-1; 1 unless the type scales by floor area
    kwh_basis_per_year: float       # what savings draw s multiplies to give kWh saved/yr
    kwh_cap_per_year: float         # efficiency: max kWh saved (baseline x max_savings_share)
                                    # solar: max kWh self-consumed (baseline x 1.0)
    exports_excess: bool            # True for solar: kWh above the cap are exported, not dropped
    export_rate_usd_per_kwh: float  # solar: value of each exported kWh; efficiency: 0
    electricity_rate_usd_per_kwh: float
    grid_kg_co2_per_kwh: float


def price_inputs(u: FeasibleUpgrade, b: BuildingFacts, a: dict[str, Any]) -> UpgradeInputs:
    city = a["cities"].get(b.city)
    if city is None:
        raise ValueError(f"no assumptions for city {b.city!r}; the engine is Houston only")
    t = a["upgrades"][u.type]

    gross = t["unit_cost"] * u.size_value
    avoided = t.get("avoided_replacement_cost_per_unit", 0.0) * u.size_value
    upfront = max(gross - avoided, 0.0)     # incremental cost over a like-for-like replacement

    unit = t["savings_unit"]
    coverage = 1.0
    if unit == "fraction_of_modeled_generation":
        # s = realized fraction of modeled output; basis = kW x city yield.
        kwh_basis = u.size_value * city["solar_kwh_per_kw_year"]
    elif unit == "kwh_per_sqft_year":
        # s = kWh saved per sqft treated per year; basis = sqft treated (the upgrade's size).
        kwh_basis = u.size_value
    elif unit == "fraction_of_building_kwh":
        # s = fraction of the whole building's annual use, at full coverage.
        area_fn = _COVERAGE_AREA[u.type]
        area = area_fn(b) if area_fn is not None else None
        coverage = 1.0 if not area else min(max(u.size_value / area, 0.0), 1.0)
        kwh_basis = coverage * baseline_kwh_per_year(b, a)
    else:
        raise ValueError(f"{u.type}: unknown savings_unit {unit!r}; expected one of {SAVINGS_UNITS}")

    baseline = baseline_kwh_per_year(b, a)
    if unit == "fraction_of_modeled_generation":
        # Solar: the building can use at most its own baseline; the rest is exported.
        kwh_cap = baseline
        export_rate = city["export_rate_usd_per_kwh"]
        if export_rate < 0:
            raise ValueError("cities.<city>.export_rate_usd_per_kwh must be >= 0")
    else:
        # Efficiency: one measure can't save more than this share of the building's use.
        share = a["global"]["max_savings_share"]
        if not 0 < share <= 1:
            raise ValueError("global.max_savings_share must be a decimal in (0, 1], e.g. 0.5")
        kwh_cap = share * baseline
        export_rate = 0.0

    return UpgradeInputs(
        upgrade_id=u.upgrade_id,
        gross_cost_usd=gross,
        avoided_replacement_usd=avoided,
        upfront_usd=upfront,
        # On full cost (correct for tax credits), but never more than the full cost.
        incentive_usd=min(t["incentive_fraction"] * gross, gross),
        incentive_lag_years=t["incentive_lag_years"],
        maintenance_usd_per_year=t["maint_frac_per_year"] * gross,
        coverage=coverage,
        kwh_basis_per_year=kwh_basis,
        kwh_cap_per_year=kwh_cap,
        exports_excess=unit == "fraction_of_modeled_generation",
        export_rate_usd_per_kwh=export_rate,
        electricity_rate_usd_per_kwh=city["electricity_rate_usd_per_kwh"],
        grid_kg_co2_per_kwh=city["grid_kg_co2_per_kwh"],
    )


@dataclass(frozen=True)
class SimulationResult:
    upgrade_ids: list[str]
    inputs: list[UpgradeInputs]
    npv: np.ndarray                  # (n_upgrades, K) USD
    tonnes_per_year: np.ndarray      # (n_upgrades, K)
    tonnes_lifetime: np.ndarray      # (n_upgrades, K) = tonnes_per_year x life
    energy_price_growth: np.ndarray  # (K,) the shared draw
    seed: int
    n_scenarios: int

    def index(self, upgrade_id: str) -> int:
        return self.upgrade_ids.index(upgrade_id)


def _upgrade_rng(seed: int, upgrade_id: str) -> np.random.Generator:
    # crc32 is stable across runs and machines (Python's hash() is not).
    return np.random.default_rng(np.random.SeedSequence([seed, 1, zlib.crc32(upgrade_id.encode())]))


def _shared_draws(rng: np.random.Generator, a: dict[str, Any], k: int) -> dict[str, np.ndarray]:
    g_cfg, c_cfg = a["global"]["energy_price_growth"], a["global"]["carbon_price"]
    growth = rng.normal(g_cfg["mu"], g_cfg["sd"], size=k)
    fee_starts = rng.random(k) < c_cfg["p_fee_starts"]
    y0, y1 = c_cfg["start_year_range"]
    start_year = rng.integers(max(int(y0), 1), int(y1) + 1, size=k)   # whole years, counted from year 1
    p0, p1 = c_cfg["price_range_per_tonne"]
    price = np.where(fee_starts, rng.uniform(p0, p1, size=k), 0.0)  # no fee -> price 0
    return {"growth": growth, "carbon_start_year": start_year, "carbon_price": price}


def simulate(upgrades: list[FeasibleUpgrade], buildings: dict[str, BuildingFacts],
             assumptions: dict[str, Any], *, n_scenarios: int | None = None,
             seed: int | None = None, discount_rate: float | None = None) -> SimulationResult:
    """Simulate every upgrade over K scenarios. Defaults come from assumptions['global']."""
    g = assumptions["global"]
    k = int(n_scenarios if n_scenarios is not None else g["n_scenarios"])
    seed = int(seed if seed is not None else g["seed"])
    r = float(discount_rate if discount_rate is not None else g["discount_rate"])
    if k < 1:
        raise ValueError("n_scenarios must be >= 1")

    missing = sorted({u.building_id for u in upgrades} - set(buildings))
    if missing:
        raise KeyError(f"no building facts for: {missing}")
    inputs = [price_inputs(u, buildings[u.building_id], assumptions) for u in upgrades]

    shared = _shared_draws(np.random.default_rng(np.random.SeedSequence([seed, 0])), assumptions, k)

    n = len(upgrades)
    s = np.empty((n, k))
    life = np.empty((n, k), dtype=np.int64)
    got_incentive = np.empty((n, k), dtype=bool)
    for i, u in enumerate(upgrades):          # loop over upgrades, not scenarios
        t = assumptions["upgrades"][u.type]
        rng = _upgrade_rng(seed, u.upgrade_id)
        s[i] = np.maximum(rng.normal(t["savings_mu"], t["savings_sd"], size=k), 0.0)
        life[i] = rng.integers(int(t["life_min"]), int(t["life_max"]) + 1, size=k)
        got_incentive[i] = rng.random(k) < t["incentive_p"]

    col = lambda name: np.array([getattr(x, name) for x in inputs], float)[:, None]   # (n, 1)
    raw_kwh = s * col("kwh_basis_per_year")                                           # (n, K)
    kwh_on_site = np.minimum(raw_kwh, col("kwh_cap_per_year"))   # saved / self-consumed
    exports = col("exports_excess") > 0
    kwh_exported = np.where(exports, raw_kwh - kwh_on_site, 0.0)  # efficiency excess is dropped
    savings_usd = (kwh_on_site * col("electricity_rate_usd_per_kwh")
                   + kwh_exported * col("export_rate_usd_per_kwh"))
    # Exported solar still displaces grid generation, so it counts toward CO2 avoided.
    tonnes_per_year = (kwh_on_site + kwh_exported) * col("grid_kg_co2_per_kwh") / 1000.0

    values = npv_fn(
        upfront_usd=col("upfront_usd"),
        incentive_usd=np.where(got_incentive, col("incentive_usd"), 0.0),
        incentive_lag_years=col("incentive_lag_years"),
        base_savings_usd=savings_usd,
        energy_price_growth=shared["growth"],            # (K,) broadcasts over every upgrade
        general_inflation=g["general_inflation"],
        discount_rate=r,
        life_years=life,
        maintenance_usd_per_year=col("maintenance_usd_per_year"),
        tonnes_per_year=tonnes_per_year,
        carbon_price_per_tonne=shared["carbon_price"],
        carbon_start_year=shared["carbon_start_year"],
    )
    values = np.atleast_2d(np.asarray(values, float)).reshape(n, k)

    return SimulationResult(
        upgrade_ids=[u.upgrade_id for u in upgrades],
        inputs=inputs,
        npv=values,
        tonnes_per_year=tonnes_per_year,
        tonnes_lifetime=tonnes_per_year * life,
        energy_price_growth=shared["growth"],
        seed=seed,
        n_scenarios=k,
    )
