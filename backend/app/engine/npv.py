"""Net present value of one upgrade, closed form (engine/CLAUDE.md "Math").

    NPV = -C0 + I/(1+r)^lag
          + sum_{t=1..L} [ B*s*(1+g)^t + T*P_t - M*(1+i)^t ] / (1+r)^t

Year 1 is the first year after install, so the first cash flow is discounted
once (t starts at 1, not 0). Every argument can be a number or a NumPy array of
scenarios; arrays are combined element by element, so 10,000 scenarios cost one
call, not a Python loop.

Why year 1 already includes one year of growth: B is the building's trailing
12 months of bills, so it is priced at last year's rates. Year 1 is the NEXT
12 months, one year later, so its savings are B*s*(1+g). The same holds for
maintenance: M is today's yearly cost, so year 1 costs M*(1+i).
"""
from __future__ import annotations

import numpy as np
from numpy.typing import ArrayLike

_EPS = 1e-12


def _safe_ratio_sum(x: np.ndarray, n: np.ndarray) -> np.ndarray:
    """sum_{t=1..n} x^t, with the x == 1 case (sum = n) handled without dividing by zero."""
    at_one = np.abs(x - 1.0) < _EPS
    denom = np.where(at_one, 1.0, 1.0 - x)
    return np.where(at_one, n, x * (1.0 - x**n) / denom)


def growing_annuity_pv(amount: ArrayLike, growth: ArrayLike,
                       discount_rate: ArrayLike, life: ArrayLike) -> np.ndarray:
    """PV of amount*(1+growth)^t for years 1..L: amount * q(1-q^L)/(1-q), q=(1+growth)/(1+r).

    Used for energy savings (growth = energy price growth) and maintenance
    (growth = general inflation). growth = 0 gives a plain annuity.
    """
    q = (1.0 + np.asarray(growth, float)) / (1.0 + np.asarray(discount_rate, float))
    return np.asarray(amount, float) * _safe_ratio_sum(q, np.asarray(life, float))


def incentive_pv(incentive_usd: ArrayLike, lag_years: ArrayLike,
                 discount_rate: ArrayLike) -> np.ndarray:
    """PV of an incentive received lag_years after install (0 = rebate at install, 1 = tax credit)."""
    r = np.asarray(discount_rate, float)
    return np.asarray(incentive_usd, float) / (1.0 + r) ** np.asarray(lag_years, float)


def carbon_pv(tonnes_per_year: ArrayLike, price_per_tonne: ArrayLike, start_year: ArrayLike,
              discount_rate: ArrayLike, life: ArrayLike) -> np.ndarray:
    """PV of T*P earned in years start_year..L (P_t = 0 before the fee starts).

    start_year counts from year 1: start_year = 2 means the fee applies in years 2..L.
    sum_{t=s..L} d^t = sum_{t=1..L} d^t - sum_{t=1..s-1} d^t, with d = 1/(1+r).
    A start year after the upgrade's life earns nothing.
    """
    d = 1.0 / (1.0 + np.asarray(discount_rate, float))
    life = np.asarray(life, float)
    start = np.maximum(np.asarray(start_year, float), 1.0)
    years_before = np.minimum(start - 1.0, life)       # caps at L, so s > L gives 0
    factor = _safe_ratio_sum(d, life) - _safe_ratio_sum(d, years_before)
    return np.asarray(tonnes_per_year, float) * np.asarray(price_per_tonne, float) * factor


def npv(*, upfront_usd: ArrayLike, incentive_usd: ArrayLike, incentive_lag_years: ArrayLike,
        base_savings_usd: ArrayLike, energy_price_growth: ArrayLike, general_inflation: ArrayLike,
        discount_rate: ArrayLike, life_years: ArrayLike,
        maintenance_usd_per_year: ArrayLike = 0.0, tonnes_per_year: ArrayLike = 0.0,
        carbon_price_per_tonne: ArrayLike = 0.0, carbon_start_year: ArrayLike = 1) -> np.ndarray | float:
    """NPV in USD. Keyword-only so a caller can't swap two rates by position.

    upfront_usd               C0: installed cost, paid at install (t = 0, not discounted)
    incentive_usd             I: rebate/credit amount (pass 0 in scenarios that don't get it)
    incentive_lag_years       years after install the incentive arrives (0 rebate, 1 tax credit)
    base_savings_usd          B*s: yearly energy savings at trailing-12-month prices
    energy_price_growth       g: decimal per year (0.02, not 2)
    general_inflation         i: decimal per year, grows maintenance
    discount_rate             r: decimal per year (0.07, not 7)
    life_years                L: whole years, >= 1
    maintenance_usd_per_year  M: yearly upkeep at today's prices
    tonnes_per_year           T: CO2 avoided per year
    carbon_price_per_tonne    P: USD per tonne once the fee starts (0 = no fee)
    carbon_start_year         first year t the fee applies, counting from year 1
    """
    r = np.asarray(discount_rate, float)
    life = np.asarray(life_years, float)
    lag = np.asarray(incentive_lag_years, float)
    if np.any(r <= -1) or np.any(r >= 1):
        raise ValueError("discount_rate must be a decimal in (-1, 1), e.g. 0.07 not 7")
    for name, rate in (("energy_price_growth", energy_price_growth), ("general_inflation", general_inflation)):
        if np.any(np.abs(np.asarray(rate, float)) >= 1):
            raise ValueError(f"{name} must be a decimal, e.g. 0.02 not 2")
    if np.any(life < 1) or np.any(life != np.round(life)):
        raise ValueError("life_years must be whole years >= 1")
    if np.any(lag < 0):
        raise ValueError("incentive_lag_years must be >= 0")

    total = (
        -np.asarray(upfront_usd, float)
        + incentive_pv(incentive_usd, lag, r)
        + growing_annuity_pv(base_savings_usd, energy_price_growth, r, life)
        - growing_annuity_pv(maintenance_usd_per_year, general_inflation, r, life)
        + carbon_pv(tonnes_per_year, carbon_price_per_tonne, carbon_start_year, r, life)
    )
    return float(total) if total.ndim == 0 else total
