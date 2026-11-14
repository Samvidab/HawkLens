"""Marginal abatement cost curve (engine/CLAUDE.md "Abatement curve", TRD §8.1).

Named curve.py, not macc.py, so that `app.engine.macc` is always the contract
function and never this module.

cost_per_tonne = -exp_npv / mean(tonnes_lifetime)
Negative = the upgrade cuts carbon AND makes money. Bars are sorted cheapest first.

This module is the one place cost_per_tonne is computed; simulate()'s contract
output and the optimizer's "cheapest extra" both call cost_per_tonne() here.
"""
from __future__ import annotations

from typing import Iterable

import numpy as np

from . import state
from .models import FeasibleUpgrade


def cost_per_tonne(npv: np.ndarray, tonnes_lifetime: np.ndarray) -> np.ndarray:
    """USD per tonne CO2, per upgrade (row). Rows with no CO2 avoided give NaN (undefined)."""
    npv = np.atleast_2d(np.asarray(npv, float))
    tonnes = np.atleast_2d(np.asarray(tonnes_lifetime, float)).mean(axis=-1)
    exp_npv = npv.mean(axis=-1)
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(tonnes > 0, -exp_npv / np.where(tonnes > 0, tonnes, 1.0), np.nan)


def is_excluded(u: FeasibleUpgrade, exclusions: Iterable[str]) -> bool:
    """Excluded if its upgrade ID or its building ID is in exclusions, or it isn't optimizer-eligible."""
    ex = set(exclusions)
    return u.upgrade_id in ex or u.building_id in ex or not u.include_in_optimizer


def macc(exclusions: list[str] | None = None) -> dict:
    """{bars: [{upgrade_id, building_id, type, tonnes_per_year, cost_per_tonne}]}, cheapest first.

    Uses the latest cached simulation. Upgrades that avoid no CO2 have no cost per
    tonne, so they get no bar (a zero-width bar would be invisible anyway).
    """
    sim, upgrades = state.current()
    cpt = cost_per_tonne(sim.npv, sim.tonnes_lifetime)
    tpy = sim.tonnes_per_year.mean(axis=-1)
    bars = [
        {
            "upgrade_id": u.upgrade_id,
            "building_id": u.building_id,
            "type": u.type,
            "tonnes_per_year": float(tpy[i]),
            "cost_per_tonne": float(cpt[i]),
        }
        for i, u in enumerate(upgrades)
        if not is_excluded(u, exclusions or []) and np.isfinite(cpt[i])
    ]
    bars.sort(key=lambda b: (b["cost_per_tonne"], b["upgrade_id"]))   # ID breaks ties -> stable order
    return {"bars": bars}
