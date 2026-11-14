"""In-memory cache of the latest simulation (engine/CLAUDE.md "State").

The contract simulate() stores its result here; macc() and optimize() read the
latest one. set_assumption() records an override and calls mark_stale(), so the
next macc()/optimize() re-simulates with the same upgrades and buildings.
One process, one cache: fine for a single-user demo.
"""
from __future__ import annotations

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
    stale: bool = False


_cache = _Cache()


def set_simulation(sim: SimulationResult, upgrades: list[FeasibleUpgrade],
                   buildings: dict[str, BuildingFacts] | None = None,
                   assumptions: dict[str, Any] | None = None) -> None:
    if [u.upgrade_id for u in upgrades] != sim.upgrade_ids:
        raise ValueError("upgrades must be the same list, in the same order, that was simulated")
    _cache.sim, _cache.upgrades, _cache.stale = sim, list(upgrades), False
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
    """Forget everything, including set_assumption overrides."""
    global _cache
    _cache = _Cache()


def has_simulation() -> bool:
    return _cache.sim is not None


def request_assumptions() -> dict[str, Any]:
    """The `assumptions` dict passed to the latest simulate() ({} if none)."""
    return _cache.assumptions or {}


def set_buildings_root(root: str | Path | None) -> None:
    _cache.buildings_root = Path(root) if root is not None else None


def buildings_root() -> Path | None:
    return _cache.buildings_root


def forget_buildings() -> None:
    _cache.buildings = {}
