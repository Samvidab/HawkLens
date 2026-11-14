import pytest
from shapely import wkt as shapely_wkt

from app.adapters.geometry import (
    SQFT_PER_M2, area_m2, buffer_wkt, footprint_polygon, point_wkt, square_wkt,
)

HOUSTON = (29.7604, -95.3698)


def test_100m_square_in_houston_utm():
    sq = square_wkt(*HOUSTON, 100, city="Houston")
    assert area_m2(sq, "Houston") == pytest.approx(10_000, rel=0.01)


def test_area_infers_zone_from_lon():
    sq = square_wkt(*HOUSTON, 100, city="Houston")
    assert area_m2(sq) == pytest.approx(10_000, rel=0.01)


def test_point_is_lon_lat():
    p = shapely_wkt.loads(point_wkt(*HOUSTON))
    assert (p.x, p.y) == (HOUSTON[1], HOUSTON[0])


def test_buffer_area():
    import math
    b = buffer_wkt(*HOUSTON, 40, city="Houston")
    assert area_m2(b, "Houston") == pytest.approx(math.pi * 40**2, rel=0.01)


def test_footprint_from_record():
    sq = square_wkt(*HOUSTON, 50, city="Houston")
    assert footprint_polygon({"footprint_wkt": sq}) == (sq, "costar")


def test_footprint_estimated_from_sqft():
    profile = {"lat": HOUSTON[0], "lon": HOUSTON[1], "city": "Houston",
               "rba_sqft": 100_000, "stories": 4, "footprint_wkt": None}
    fp, src = footprint_polygon(profile)
    assert src == "estimated"
    assert area_m2(fp, "Houston") == pytest.approx(25_000 / SQFT_PER_M2, rel=0.01)
