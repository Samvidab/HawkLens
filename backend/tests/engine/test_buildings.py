"""buildings.py: field reading, envelope/floor fallbacks, property-type mapping."""
from pathlib import Path

import pytest

from app.engine.buildings import (
    DEFAULT_BENCHMARK_TYPE,
    PROPERTY_TYPE_TO_BENCHMARK,
    benchmark_type,
    estimate_envelope_area_sqft,
    load_building,
)
from app.engine.models import load_assumptions

FIXTURES = Path(__file__).parent / "fixtures"


def test_scanned_building_uses_measured_areas():
    b = load_building("hou-001", root=FIXTURES)
    assert (b.floor_area_sqft, b.floor_area_estimated) == (112000, False)
    assert (b.envelope_area_sqft, b.envelope_area_estimated) == (51400, False)
    assert b.city == "Houston" and b.benchmark_type == "Office"


def test_unscanned_building_gets_estimates_flagged():
    # hou-002: 45,000 sqft, 1 story -> square footprint 212.13 ft a side.
    # Envelope = 4 x 212.13 ft x 4.0 m x 3.28084 ft/m x 1 story = 11,135 sqft.
    b = load_building("hou-002", root=FIXTURES)
    assert b.floor_area_estimated and b.floor_area_sqft == 45000
    assert b.envelope_area_estimated
    assert b.envelope_area_sqft == pytest.approx(11135, abs=1)


def test_estimate_agrees_with_scan_for_square_building():
    # hou-001's scanned envelope (51,400) was sized with the same square-footprint
    # geometry, so the fallback should land within 0.1%.
    est = estimate_envelope_area_sqft(120000, 8, 4.0)
    assert est == pytest.approx(51400, rel=1e-3)


@pytest.mark.parametrize("rba,stories", [(None, 5), (80000, None), (0, 5), (80000, 0)])
def test_estimate_is_none_when_inputs_missing(rba, stories):
    assert estimate_envelope_area_sqft(rba, stories, 4.0) is None


def test_missing_profile_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_building("nope", root=tmp_path)


@pytest.mark.parametrize("raw,expected", [
    ("Office", "Office"), ("  office ", "Office"), ("Multifamily", "Multi-Family"),
    ("Hospitality", DEFAULT_BENCHMARK_TYPE), ("", DEFAULT_BENCHMARK_TYPE), (None, DEFAULT_BENCHMARK_TYPE),
])
def test_benchmark_type_mapping(raw, expected):
    assert benchmark_type(raw) == expected


def test_every_benchmark_type_has_a_houston_value():
    benchmarks = load_assumptions()["cities"]["Houston"]["kwh_per_sqft_year"]
    needed = set(PROPERTY_TYPE_TO_BENCHMARK.values()) | {DEFAULT_BENCHMARK_TYPE}
    assert needed <= set(benchmarks)
