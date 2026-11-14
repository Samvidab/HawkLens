"""In-memory cache of the latest simulation (engine/CLAUDE.md "State").

The contract simulate() stores its result here; macc() and optimize() read the
latest one. set_assumption() records an override and calls mark_stale(), so the
next macc()/optimize() re-simulates with the same upgrades and buildings.
One process, one cache: fine for a single-user demo.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .buildings import BuildingFacts
from .models import FeasibleUpgrade
from .monte_carlo import SimulationResult


class NoSimulation(RuntimeError):
    """macc()/optimize() called before any simulate()."""


@dataclass
class _Cache:
    sim: SimulationResult | None = None
    upgrades: list[FeasibleUpgrade] | None = None
    buildings: dict[str, BuildingFacts] = field(default_factory=dict)
    assumptions: dict[str, Any] | None = None    # the `assumptions` passed to simulate() (before overrides)
    overrides: dict[str, Any] = field(default_factory=dict)   # dotted key -> value, from set_assumption
    buildings_root: Path | None = None           # None = data_dir/buildings
    assumptions_path: Path | None = None         # None = app/engine/assumptions.json
    generation: int = 0                          # bumps on every new simulation; plan cache keys use it
    plans: dict = field(default_factory=dict)    # (generation, request...) -> optimize() result
    precomputed: set = field(default_factory=set)  # (generation, context) already queued
    last_context: tuple | None = None            # (risk_lambda, budget, exclusions) of the last optimize
    stale: bool = False


_cache = _Cache()
LOCK = threading.RLock()


def set_simulation(sim: SimulationResult, upgrades: list[FeasibleUpgrade],
                   buildings: dict[str, BuildingFacts] | None = None,
                   assumptions: dict[str, Any] | None = None) -> None:
    if [u.upgrade_id for u in upgrades] != sim.upgrade_ids:
        raise ValueError("upgrades must be the same list, in the same order, that was simulated")
    with LOCK:
        _cache.sim, _cache.upgrades, _cache.stale = sim, list(upgrades), False
        _cache.generation += 1
        _cache.plans.clear(); _cache.precomputed.clear()
    if buildings is not None:
        _cache.buildings = dict(buildings)
    if assumptions is not None:
        _cache.assumptions = assumptions


def current() -> tuple[SimulationResult, list[FeasibleUpgrade]]:
    if _cache.sim is None or _cache.upgrades is None:
        raise NoSimulation("no simulation cached yet; call simulate() first")
    return _cache.sim, _cache.upgrades


def buildings() -> dict[str, BuildingFacts]:
    return _cache.buildings


def overrides() -> dict[str, Any]:
    return _cache.overrides


def set_override(key: str, value: Any) -> None:
    _cache.overrides[key] = value
    _cache.stale = True


def mark_stale() -> None:
    _cache.stale = True


def is_stale() -> bool:
    return _cache.stale


def clear() -> None:
    """Forget everything, including set_assumption overrides. Background precompute threads
    see the generation change and stop storing results."""
    global _cache
    with LOCK:
        gen = _cache.generation
        _cache = _Cache()
        _cache.generation = gen + 1


def has_simulation() -> bool:
    return _cache.sim is not None


def request_assumptions() -> dict[str, Any]:
    """The `assumptions` dict passed to the latest simulate() ({} if none)."""
    return _cache.assumptions or {}


def set_buildings_root(root: str | Path | None) -> None:
    _cache.buildings_root = Path(root) if root is not None else None


def set_assumptions_path(path: str | Path | None) -> None:
    _cache.assumptions_path = Path(path) if path is not None else None
    _cache.stale = True


def assumptions_path() -> Path | None:
    return _cache.assumptions_path


def buildings_root() -> Path | None:
    return _cache.buildings_root


def forget_buildings() -> None:
    _cache.buildings = {}



def generation() -> int:
    return _cache.generation


def get_plan(key: tuple):
    with LOCK:
        return _cache.plans.get(key)


def put_plan(key: tuple, result: dict) -> None:
    """Store only if the simulation it was computed on is still current."""
    with LOCK:
        if key[0] == _cache.generation:
            _cache.plans[key] = result


def claim_precompute(context: tuple) -> bool:
    """True the first time a (generation, context) is claimed; False if already queued."""
    with LOCK:
        k = (_cache.generation, context)
        if k in _cache.precomputed:
            return False
        _cache.precomputed.add(k)
        return True


def set_last_context(context: tuple) -> None:
    _cache.last_context = context


def last_context() -> tuple | None:
    return _cache.last_context
