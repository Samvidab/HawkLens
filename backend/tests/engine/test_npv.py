"""Step 2: closed-form NPV matches hand-computed (spreadsheet-style) values to the cent."""
import numpy as np
import pytest

from app.engine.npv import npv


def test_npv_tax_credit_lag_inflated_maintenance_and_carbon():
    """r = 10%, g = 0, inflation = 10%, L = 3, credit paid 1 year late, carbon fee from year 2.

    Inflation equals r, so maintenance hits the q == 1 case: each year's PV is exactly 500.

    incentive   2000 / 1.10                                          = 1818.1818
    year  energy  carbon  maint     net      discount   PV
      1    5000      0   -550.00  4450.00   / 1.100   4045.4545
      2    5000    500   -605.00  4895.00   / 1.210   4045.4545
      3    5000    500   -665.50  4834.50   / 1.331   3632.2314
    NPV = -10000 + 1818.1818 + 11723.1405 = 3541.3223
    """
    value = npv(
        upfront_usd=10_000, incentive_usd=2_000, incentive_lag_years=1,
        base_savings_usd=5_000, energy_price_growth=0.0, general_inflation=0.10,
        discount_rate=0.10, life_years=3, maintenance_usd_per_year=500,
        tonnes_per_year=10, carbon_price_per_tonne=50, carbon_start_year=2,
    )
    assert value == pytest.approx(3541.3223, abs=0.01)


def test_npv_rebate_at_install_growth_equals_discount_and_carbon_after_life():
    """q = (1+g)/(1+r) == 1 must not divide by zero; a fee starting after the life earns nothing.

    Both: C0 = 3000, rebate 500 at install (lag 0, not discounted), r = 5%, L = 4,
          no maintenance, carbon fee starts in year 5 (after the 4-year life) -> 0.
    Scenario A: g = r = 5% -> growth and discounting cancel, each year is worth 1000.
                NPV = -3000 + 500 + 4 x 1000 = 1500
    Scenario B: g = 0 -> annuity factor 0.95238 + 0.90703 + 0.86384 + 0.82270 = 3.54595
                NPV = -3000 + 500 + 1000 x 3.54595 = 1045.95
    """
    values = npv(
        upfront_usd=3_000, incentive_usd=500, incentive_lag_years=0,
        base_savings_usd=1_000, energy_price_growth=np.array([0.05, 0.0]),
        general_inflation=0.025, discount_rate=0.05, life_years=4,
        tonnes_per_year=10, carbon_price_per_tonne=50, carbon_start_year=5,
    )
    assert not np.isnan(values).any()
    assert values == pytest.approx([1500.00, 1045.95], abs=0.01)
