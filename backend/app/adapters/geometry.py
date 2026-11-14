"""Geometry helpers. Inputs/outputs are WGS84 WKT (lon/lat order); areas are computed in UTM."""
from __future__ import annotations

import math
from functools import lru_cache
from typing import Any, Literal

from pyproj import Transformer
import shapely
from shapely import wkt as shapely_wkt
from shapely.geometry import Point, box

City = Literal["Houston", "Los Angeles"]

UTM_EPSG: dict[str, int] = {"Houston": 32615, "Los Angeles": 32611}
SQFT_PER_M2 = 10.763910416709722


def utm_epsg(city: str | None = None, lon: float | None = None) -> int:
    if city in UTM_EPSG:
        return UTM_EPSG[city]
    if lon is None:
        raise ValueError("need a known city or a longitude to pick a UTM zone")
    zone = int((lon + 180) // 6) + 1
    return 32600 + zone  # northern hemisphere (Houston/LA only)


@lru_cache
def _transformers(epsg: int) -> tuple[Transformer, Transformer]:
    to_utm = Transformer.from_crs(4326, epsg, always_xy=True)
    to_wgs = Transformer.from_crs(epsg, 4326, always_xy=True)
    return to_utm, to_wgs


def _reproject(geom, tr: Transformer):
    return shapely.transform(geom, lambda x, y: tr.transform(x, y), interleaved=False)


def point_wkt(lat: float, lon: float) -> str:
    return Point(lon, lat).wkt


def buffer_wkt(lat: float, lon: float, meters: float, city: str | None = None) -> str:
    """Circle of radius `meters` around (lat, lon), buffered in UTM, returned as WGS84 WKT."""
    to_utm, to_wgs = _transformers(utm_epsg(city, lon))
    x, y = to_utm.transform(lon, lat)
    return _reproject(Point(x, y).buffer(meters), to_wgs).wkt


def square_wkt(lat: float, lon: float, side_m: float, city: str | None = None) -> str:
    """Axis-aligned square (in UTM) of side `side_m` centred on (lat, lon), as WGS84 WKT."""
    to_utm, to_wgs = _transformers(utm_epsg(city, lon))
    x, y = to_utm.transform(lon, lat)
    h = side_m / 2
    return _reproject(box(x - h, y - h, x + h, y + h), to_wgs).wkt


def area_m2(wkt: str, city: str | None = None) -> float:
    geom = shapely_wkt.loads(wkt)
    lon = geom.centroid.x
    to_utm, _ = _transformers(utm_epsg(city, lon))
    return _reproject(geom, to_utm).area


def _get(profile: Any, name: str) -> Any:
    return profile.get(name) if isinstance(profile, dict) else getattr(profile, name, None)


def footprint_polygon(profile: Any) -> tuple[str, Literal["costar", "estimated"]]:
    """Footprint WKT for a building profile (dict or BuildingProfile).

    Uses the record's footprint if present; otherwise a square of area rba_sqft / stories
    centred on the building's point.
    """
    fp = _get(profile, "footprint_wkt")
    if fp:
        return fp, "costar"

    lat, lon = _get(profile, "lat"), _get(profile, "lon")
    rba = _get(profile, "rba_sqft")
    stories = _get(profile, "stories") or 1
    if lat is None or lon is None or not rba:
        raise ValueError("cannot estimate footprint: need lat, lon and rba_sqft")
    side_m = math.sqrt((rba / stories) / SQFT_PER_M2)
    return square_wkt(lat, lon, side_m, _get(profile, "city")), "estimated"
