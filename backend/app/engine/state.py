"""In-memory cache of the latest simulation (engine/CLAUDE.md "State").

The contract simulate() (step 6) stores its result here; macc() and optimize()
read the latest one. set_assumption() will call mark_stale() so the next read
knows to re-simulate. One process, one cache: fine for a single-user demo.
"""
from __future__ import annotations

from dataclasses import dataclass

from .models import FeasibleUpgrade
from .monte_carlo import SimulationResult


class NoSimulation(RuntimeError):
    """macc()/optimize() called before any simulate()."""


@dataclass
class _Cache:
    sim: SimulationResult | None = None
    upgrades: list[FeasibleUpgrade] | None = None
    stale: bool = False


_cache = _Cache()


def set_simulation(sim: SimulationResult, upgrades: list[FeasibleUpgrade]) -> None:
    if [u.upgrade_id for u in upgrades] != sim.upgrade_ids:
        raise ValueError("upgrades must be the same list, in the same order, that was simulated")
    _cache.sim, _cache.upgrades, _cache.stale = sim, list(upgrades), False


def current() -> tuple[SimulationResult, list[FeasibleUpgrade]]:
    if _cache.sim is None or _cache.upgrades is None:
        raise NoSimulation("no simulation cached yet; call simulate() first")
    return _cache.sim, _cache.upgrades


def mark_stale() -> None:
    _cache.stale = True


def is_stale() -> bool:
    return _cache.stale


def clear() -> None:
    _cache.sim, _cache.upgrades, _cache.stale = None, None, False
