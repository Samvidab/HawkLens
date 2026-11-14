"""Vexcel adapter, per docs/agent/costar-quickstart.md section 7.

Overhead: POST https://api.vexcelgroup.com/v2/ortho/extract with the key in the X-API-KEY header;
the response body is the image (JPEG). Hackathon keys cover Houston and Los Angeles only (else 403).

Obliques: the Vexcel quickstart (backend/toolkit/) that documents them has not been received;
`oblique` raises until it is. The aerial inspector runs overhead-only meanwhile (plan fallback).
"""
from __future__ import annotations

import httpx
from shapely import wkt as shapely_wkt

from app.adapters.cache import cache_key, cached_bytes
from app.adapters.geometry import square_wkt
from app.adapters.types import ImageRef, Orientation
from app.config import get_settings

ORTHO_URL = "https://api.vexcelgroup.com/v2/ortho/extract"
ORTHO_LAYER = "urban,urban-r,wide-area,urban-g"  # quickstart §7
DEFAULT_PX = 1400


class VexcelError(RuntimeError):
    pass


async def _extract(body: dict) -> bytes:
    key = get_settings().vexcel_api_key
    if not key:
        raise VexcelError("VEXCEL_API_KEY is not set")
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(ORTHO_URL, json=body, headers={"X-API-KEY": key})
    if r.status_code == 403:
        raise VexcelError("Vexcel 403: outside Houston/LA coverage or key rejected")
    r.raise_for_status()
    if not r.headers.get("content-type", "").startswith("image/"):
        raise VexcelError(f"Vexcel returned {r.headers.get('content-type')}: {r.text[:200]}")
    return r.content


def overhead_buffer_m(rba_sqft: float | None, stories: int | None, *, minimum: float = 40) -> float:
    """Half-side of the overhead crop: 1.1 × the estimated footprint side, so the square is ~2.2×
    the estimated footprint: real roofs run larger than the estimate, and neighbours (shade) stay in view."""
    if not rba_sqft:
        return minimum
    side_m = (rba_sqft / max(stories or 1, 1) / 10.763910416709722) ** 0.5
    return max(minimum, round(1.1 * side_m, 1))


async def overhead(point_wkt: str, buffer_m: float = 40, *, px: int = DEFAULT_PX,
                   city: str | None = None) -> list[ImageRef]:
    """Latest Vexcel orthophoto clipped to a square of half-side `buffer_m` around the point."""
    pt = shapely_wkt.loads(point_wkt)
    area = square_wkt(pt.y, pt.x, 2 * buffer_m, city)
    body = {
        "wkt": area, "srid": 4326, "layer": ORTHO_LAYER, "crop": "bounding_box",
        "image-format": "jpeg", "destination-dimensions": f"{px},{px}", "attribution": "false",
    }
    params = {"wkt": area, "px": px, "layer": ORTHO_LAYER}
    path = await cached_bytes("vexcel.ortho", params, lambda: _extract(body), ext=".jpg")
    image_id = "vxo_" + cache_key("vexcel.ortho", params)[:16]
    return [ImageRef(image_id=image_id, source="vexcel_overhead", local_path=str(path),
                     gsd_m=2 * buffer_m / px, bounds_wkt=area)]


async def oblique(footprint_wkt: str, orientation: Orientation) -> list[ImageRef]:
    raise NotImplementedError(
        "Vexcel oblique API not documented in the material received (Vexcel quickstart in backend/toolkit/ "
        "is missing); see adapters/README.md")
