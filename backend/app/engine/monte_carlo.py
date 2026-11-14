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
- PER ESTIMATE (optional `uncertainty` block in assumptions): a multiplier per scenario
  for each listed fixed value (e.g. upgrades.cool_roof.unit_cost), shared by every upgrade
  that uses it, seeded by the field name. ±h means a 95% range of ±h: Normal(1, h/2).
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
from .models import SIZE_UNIT_BY_TYPE, FeasibleUpgrade
from .npv import npv as npv_fn

# For "fraction_of_building_kwh" types: what the savings fraction is scaled by
# (ASSUMPTIONS.md "Scales with"). None = not scaled (fixed).
_COVERAGE_AREA = {
    "heat_pump": lambda b: b.floor_area_sqft,
    "led_retrofit": lambda b: b.floor_area_sqft,
    "window_upgrade": None,
}
SAVINGS_UNITS = ("fraction_of_building_kwh", "kwh_per_sqft_year", "fraction_of_modeled_generation")

# Fixed values that may carry a spread in assumptions["uncertainty"] (dotted path -> half-width).
_UPGRADE_SPREAD_FIELDS = ("unit_cost", "avoided_replacement_cost_per_unit", "maint_frac_per_year",
                          "incentive_fraction", "incentive_usd_per_kwh_saved", "replacement_due_age_years")
_CITY_SPREAD_FIELDS = ("electricity_rate_usd_per_kwh", "export_rate_usd_per_kwh", "solar_kwh_per_kw_year")
_GLOBAL_SPREAD_FIELDS = ("discount_rate", "general_inflation")
DEFAULT_ANALYSIS_YEAR = 2026


def check_uncertainty(a: dict[str, Any]) -> dict[str, float]:
    """Validate assumptions["uncertainty"]: known dotted paths only, half-width in (0, 1)."""
    out = {}
    for key, h in (a.get("uncertainty") or {}).items():
        if key.startswith("_"):
            continue
        parts = key.split(".")
        ok = ((len(parts) == 3 and parts[0] == "upgrades" and parts[1] in a["upgrades"]
               and parts[2] in _UPGRADE_SPREAD_FIELDS)
              or (len(parts) == 3 and parts[0] == "cities" and parts[1] in a["cities"]
                  and parts[2] in _CITY_SPREAD_FIELDS)
              or (len(parts) == 4 and parts[0] == "cities" and parts[1] in a["cities"]
                  and parts[2] == "kwh_per_sqft_year"
                  and parts[3] in a["cities"][parts[1]]["kwh_per_sqft_year"])
              or (len(parts) == 2 and parts[0] == "global" and parts[1] in _GLOBAL_SPREAD_FIELDS))
        if not ok:
            raise ValueError(f"uncertainty.{key}: not a field that can carry a spread")
        if not isinstance(h, (int, float)) or isinstance(h, bool) or not 0 < h < 1:
            raise ValueError(f"uncertainty.{key}: half-width must be a decimal in (0, 1), e.g. 0.3 for ±30%")
        out[key] = float(h)
    return out


def replacement_due(t: dict[str, Any], b: BuildingFacts, a: dict[str, Any]) -> bool:
    """Is the existing item due for like-for-like replacement now?

    No `replacement_due_age_years` key at all -> no rule configured, credit applies (legacy).
    Key present but null, or building year unknown -> can't confirm, no credit.
    Otherwise due when analysis_year - year_built >= the age.
    """
    if "replacement_due_age_years" not in t:
        return True
    age_rule = t["replacement_due_age_years"]
    if age_rule is None or b.year_built is None:
        return False
    year = a["global"].get("analysis_year", DEFAULT_ANALYSIS_YEAR)
    return year - int(b.year_built) >= age_rule


@dataclass(frozen=True)
class UpgradeInputs:
    """Fixed (non-random) numbers for one upgrade."""
    upgrade_id: str
    type: str
    city: str
    benchmark_type: str
    gross_cost_usd: float           # unit_cost x size: full installed price
    avoided_replacement_usd: float  # avoided_replacement_cost_per_unit x size, 0 if not due
    replacement_due: bool           # the replacement-due rule's answer for this building
    avoided_if_due_usd: float       # the credit before the rule (for per-scenario due ages)
    due_rule: str                   # "always" (no rule configured), "never", or "age"
    building_age: float | None
    due_age_years: float | None
    upfront_usd: float              # C0 = max(gross - avoided, 0): incremental cost
    incentive_usd: float            # amount IF received = incentive_fraction x gross cost
    incentive_fraction: float
    incentive_usd_per_kwh_saved: float   # utility rebate on verified year-1 kWh saved
    incentive_cap_frac_of_cost: float    # incentive never exceeds this share of the full cost
    incentive_min_kwh_saved: float       # rebate needs at least this many kWh saved in a year
    incentive_lag_years: int
    maint_frac_per_year: float
    maintenance_usd_per_year: float  # M at today's prices = maint_frac x net upfront when an
                                     # avoided replacement applies, else x gross (same thing then)
    coverage: float                 # 0-1; 1 unless the type scales by floor area
    kwh_basis_per_year: float       # what savings draw s multiplies to give kWh saved/yr
    basis_uses_baseline: bool       # True for fraction_of_building_kwh (scales with baseline)
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
    expected_unit = SIZE_UNIT_BY_TYPE[u.type]
    if u.size_unit != expected_unit:
        raise ValueError(
            f"{u.upgrade_id}: {u.type} must be sized in {expected_unit!r} (priced in "
            f"{t['cost_unit']}), but size_unit is {u.size_unit!r} (size_value {u.size_value}). "
            f"Convert it before calling the engine; e.g. LED is sized by floor area in sqft, "
            f"not by fixture count.")

    gross = t["unit_cost"] * u.size_value
    due = replacement_due(t, b, a)
    avoided_if_due = t.get("avoided_replacement_cost_per_unit", 0.0) * u.size_value
    avoided = avoided_if_due if due else 0.0
    if "replacement_due_age_years" not in t:
        due_rule, due_age = "always", None
    elif t["replacement_due_age_years"] is None or b.year_built is None:
        due_rule, due_age = "never", None
    else:
        due_rule, due_age = "age", float(t["replacement_due_age_years"])
    age = (a["global"].get("analysis_year", DEFAULT_ANALYSIS_YEAR) - int(b.year_built)
           if b.year_built is not None else None)
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
        type=u.type,
        city=b.city,
        benchmark_type=b.benchmark_type,
        gross_cost_usd=gross,
        avoided_replacement_usd=avoided,
        replacement_due=due,
        avoided_if_due_usd=avoided_if_due,
        due_rule=due_rule,
        building_age=age,
        due_age_years=due_age,
        upfront_usd=upfront,
        # Expected-value view for reporting; simulate() recomputes per scenario. Tax credits are
        # a share of the full cost; rebates are $/kWh saved; both capped.
        incentive_usd=min(t["incentive_fraction"] * gross, t.get("incentive_cap_frac_of_cost", 1.0) * gross, gross),
        incentive_fraction=t["incentive_fraction"],
        incentive_usd_per_kwh_saved=t.get("incentive_usd_per_kwh_saved", 0.0),
        incentive_cap_frac_of_cost=t.get("incentive_cap_frac_of_cost", 1.0),
        incentive_min_kwh_saved=t.get("incentive_min_kwh_saved", 0.0),
        incentive_lag_years=t["incentive_lag_years"],
        maint_frac_per_year=t["maint_frac_per_year"],
        # Like-for-like: the conventional replacement needs upkeep too, so only the
        # incremental (net) cost adds maintenance. Without an avoided cost, net == gross.
        maintenance_usd_per_year=t["maint_frac_per_year"] * (upfront if avoided > 0 else gross),
        coverage=coverage,
        kwh_basis_per_year=kwh_basis,
        basis_uses_baseline=unit == "fraction_of_building_kwh",
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
    spreads = check_uncertainty(assumptions)
    ones = np.ones(k)
    mult_cache: dict[str, np.ndarray] = {}

    def mult(key: str) -> np.ndarray:
        """Per-scenario multiplier for one estimated field (1 if it has no spread)."""
        if key not in spreads:
            return ones
        if key not in mult_cache:
            rng = np.random.default_rng(np.random.SeedSequence([seed, 2, zlib.crc32(key.encode())]))
            mult_cache[key] = np.maximum(rng.normal(1.0, spreads[key] / 2.0, size=k), 0.0)
        return mult_cache[key]

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

    # Per-upgrade (n, K) arrays: each fixed input times its estimate multiplier (1 if none).
    gross = np.empty((n, k)); avoided = np.empty((n, k)); maint_frac = np.empty((n, k))
    basis = np.empty((n, k)); cap = np.empty((n, k)); rate = np.empty((n, k)); export = np.empty((n, k))
    for i, x in enumerate(inputs):
        up, ci = f"upgrades.{x.type}", f"cities.{x.city}"
        bench = mult(f"{ci}.kwh_per_sqft_year.{x.benchmark_type}")   # scales the baseline
        gross[i] = x.gross_cost_usd * mult(f"{up}.unit_cost")
        if x.due_rule == "always":
            due_k = ones
        elif x.due_rule == "never":
            due_k = 0.0 * ones
        else:   # due when building age >= due age (the due age may carry a spread)
            due_k = (x.building_age >= x.due_age_years * mult(f"{up}.replacement_due_age_years")).astype(float)
        avoided[i] = x.avoided_if_due_usd * due_k * mult(f"{up}.avoided_replacement_cost_per_unit")
        maint_frac[i] = x.maint_frac_per_year * mult(f"{up}.maint_frac_per_year")
        basis[i] = x.kwh_basis_per_year * (bench if x.basis_uses_baseline else
                                           mult(f"{ci}.solar_kwh_per_kw_year") if x.exports_excess else ones)
        cap[i] = x.kwh_cap_per_year * bench
        rate[i] = x.electricity_rate_usd_per_kwh * mult(f"{ci}.electricity_rate_usd_per_kwh")
        export[i] = x.export_rate_usd_per_kwh * mult(f"{ci}.export_rate_usd_per_kwh")
    upfront = np.maximum(gross - avoided, 0.0)
    maintenance = maint_frac * np.where(avoided > 0, upfront, gross)    # net basis when avoided applies

    col = lambda name: np.array([getattr(x, name) for x in inputs], float)[:, None]   # (n, 1)
    raw_kwh = s * basis                                                               # (n, K)
    kwh_on_site = np.minimum(raw_kwh, cap)                       # saved / self-consumed
    exports = col("exports_excess") > 0
    kwh_exported = np.where(exports, raw_kwh - kwh_on_site, 0.0)  # efficiency excess is dropped
    savings_usd = kwh_on_site * rate + kwh_exported * export

    # Incentive if received: tax credit (share of full cost) + utility rebate ($ per verified
    # year-1 kWh saved, only if the minimum is met), capped at a share of the full cost.
    inc_frac = np.vstack([x.incentive_fraction * mult(f"upgrades.{x.type}.incentive_fraction") for x in inputs])
    per_kwh = np.vstack([x.incentive_usd_per_kwh_saved * mult(f"upgrades.{x.type}.incentive_usd_per_kwh_saved")
                         for x in inputs])
    rebate = np.where(kwh_on_site >= col("incentive_min_kwh_saved"), per_kwh * kwh_on_site, 0.0)
    incentive = np.minimum(inc_frac * gross + rebate, np.minimum(col("incentive_cap_frac_of_cost"), 1.0) * gross)
    # Exported solar still displaces grid generation, so it counts toward CO2 avoided.
    tonnes_per_year = (kwh_on_site + kwh_exported) * col("grid_kg_co2_per_kwh") / 1000.0

    values = npv_fn(
        upfront_usd=upfront,
        incentive_usd=np.where(got_incentive, incentive, 0.0),
        incentive_lag_years=col("incentive_lag_years"),
        base_savings_usd=savings_usd,
        energy_price_growth=shared["growth"],            # (K,) broadcasts over every upgrade
        general_inflation=g["general_inflation"] * mult("global.general_inflation"),
        discount_rate=r * mult("global.discount_rate"),
        life_years=life,
        maintenance_usd_per_year=maintenance,
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
