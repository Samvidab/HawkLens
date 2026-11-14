"""Matterport Model API adapter (GraphQL), per docs/agent/costar-quickstart.md.

POST https://api.matterport.com/api/models/graph, HTTP basic auth:
user = MATTERPORT_API_KEY, password = MATTERPORT_API_TOKEN. Production only.

Signed asset URLs (skybox faces, floor plans, MatterPak) expire, so anything we need later is
downloaded right away into cache/media/ and served from there. GraphQL responses are cached by
(query name, variables) like every other external call.
"""
from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

import httpx

from app.adapters.cache import CacheMiss, cached, cached_bytes
from app.adapters.types import MatterPakPaths, MatterportModelRef, PanoramaRef
from app.config import BACKEND_DIR, get_settings

GRAPH_URL = "https://api.matterport.com/api/models/graph"

Q_KEYCHECK = """{ rootFolder { name modelCountSummary(includeModelsInSubfolders: true) } }"""

Q_BASICS = """query Basics($id: ID!) { model(id: $id) {
  id name description created visibility
  address { address locality administrativeArea postalCode }
  geolocation { lat long }
  generatedDescription { summary }
  propertyClassifications { classification type }
  floors { id label } rooms { id } panoLocations { id }
  image { url }
} }"""

Q_PANOS = """query Panos($id: ID!) { model(id: $id) {
  panoLocations { id label position { x y z } skybox(resolution: "2k") { status children } }
} }"""

# Separate: not every model has a defurnished view, and asking for a missing one fails the query.
Q_DEFURNISHED = """query Defurnished($id: ID!) { model(id: $id) { view(type: "matterport.model.defurnished") { id } } }"""

Q_ROOMS = """query Rooms($id: ID!) { model(id: $id) {
  floors { id label vertices { id position { x y } } edges { id type thickness vertices { id } } }
  rooms { id floor { id } classifications { label confidence } boundary { edges { id } }
          dimensions(units: metric) { areaFloor width depth height } }
  assets { floorplans(provider: "matterport") { format flags url width height resolution origin { x y } } }
  panoLocations { label position { x y } }
} }"""

# Room ↔ pano membership (found by schema introspection: ModelRoom.panoLocations, tags, keywords).
Q_ROOM_PANOS = """query RoomPanos($id: ID!) { model(id: $id) { rooms {
  id tags keywords classifications { label confidence }
  dimensions(units: metric) { areaFloor width depth height }
  panoLocations { id label position { x y z } } } } }"""

Q_MATTERPAK = """query MatterPak($id: ID!) { model(id: $id) {
  bundle(id: "mp:matterpak") { availability }
  assets { resources(format: "matterpak") { status filename url } }
} }"""


EXPIRED_LINK = {400, 401, 403, 410}  # what Matterport's CDN answers for an expired signed URL (410 seen)


class MatterportError(RuntimeError):
    pass


def _auth() -> tuple[str, str]:
    key = get_settings().matterport_api_key
    token = os.environ.get("MATTERPORT_API_TOKEN")
    if not token:
        from dotenv import dotenv_values

        token = dotenv_values(BACKEND_DIR / ".env").get("MATTERPORT_API_TOKEN")
    if not key or not token:
        raise MatterportError("MATTERPORT_API_KEY and MATTERPORT_API_TOKEN must both be set")
    return key, token


async def _post(query: str, variables: dict[str, Any]) -> dict[str, Any]:
    async with httpx.AsyncClient(timeout=60) as c:
        r = await c.post(GRAPH_URL, json={"query": query, "variables": variables}, auth=_auth())
    if r.status_code == 401:
        raise MatterportError("Matterport rejected the key/token (401)")
    r.raise_for_status()
    body = r.json()
    if body.get("errors"):
        raise MatterportError("; ".join(e.get("message", str(e)) for e in body["errors"]))
    return body["data"]


async def graph(name: str, query: str, variables: dict[str, Any] | None = None, *, fresh: bool = False) -> dict:
    """Run a GraphQL query through the cache. fresh=True skips the cache read (for new signed URLs)."""
    variables = variables or {}
    if fresh and get_settings().cache_mode != "read_only":
        return await cached(f"matterport.{name}", {"variables": variables, "fresh": True},
                            lambda: _post(query, variables), mode="off")
    return await cached(f"matterport.{name}", {"variables": variables}, lambda: _post(query, variables))


async def key_check() -> dict:
    return (await graph("keycheck", Q_KEYCHECK))["rootFolder"]


async def basics(model_id: str) -> dict:
    return (await graph("basics", Q_BASICS, {"id": model_id}))["model"]


async def matterpak_status(model_id: str) -> dict:
    """{'availability': 'unlocked'|'locked'|..., 'resources': [{status, filename, url}]}"""
    m = (await graph("matterpak", Q_MATTERPAK, {"id": model_id}))["model"]
    return {"availability": (m.get("bundle") or {}).get("availability"),
            "resources": (m.get("assets") or {}).get("resources") or []}


async def model_ref(model_id: str) -> MatterportModelRef:
    b = await basics(model_id)
    try:
        avail = (await matterpak_status(model_id))["availability"]
    except MatterportError:
        avail = None
    geo = b.get("geolocation") or {}
    return MatterportModelRef(
        model_id=model_id, name=b.get("name"), address=(b.get("address") or {}).get("address"),
        lat=float(geo["lat"]) if geo.get("lat") else None, lon=float(geo["long"]) if geo.get("long") else None,
        rooms=len(b.get("rooms") or []), panos=len(b.get("panoLocations") or []),
        matterpak=avail if avail in ("unlocked", "locked") else "unknown",
    )


async def models_for_property(profile: Any) -> list[MatterportModelRef]:
    """Models for a building, matched by CoStar PropertyId through the kit's join table."""
    from app.adapters import costar

    costar_id = profile.get("costar_id") if isinstance(profile, dict) else profile.costar_id
    return [await model_ref(mid) for mid in await costar.matterport_model_ids(costar_id)]


async def panoramas(model_id: str) -> list[PanoramaRef]:
    m = (await graph("panos", Q_PANOS, {"id": model_id}))["model"]
    out = []
    for p in m.get("panoLocations") or []:
        pos = p.get("position") or {}
        sky = p.get("skybox") or {}
        out.append(PanoramaRef(
            pano_id=p["id"], model_id=model_id, label=p.get("label"),
            xyz=(pos.get("x", 0.0), pos.get("y", 0.0), pos.get("z", 0.0)),
            skybox_urls=sky.get("children") or [] if sky.get("status") == "available" else [],
        ))
    return out


async def defurnished_view(model_id: str) -> str | None:
    try:
        m = (await graph("defurnished", Q_DEFURNISHED, {"id": model_id}))["model"]
    except MatterportError:
        return None
    return (m.get("view") or {}).get("id")


async def room_panos(model_id: str) -> list[dict]:
    """Per room: id, Matterport tags/keywords/classifications, metric dimensions and the ids of the
    panoramas captured inside it."""
    rooms = (await graph("room_panos", Q_ROOM_PANOS, {"id": model_id}))["model"]["rooms"] or []
    return [{"room_id": r["id"], "tags": r.get("tags") or [], "keywords": r.get("keywords") or [],
             "classifications": [c["label"] for c in r.get("classifications") or []],
             "dimensions": r.get("dimensions") or {},
             "pano_ids": [p["id"] for p in r.get("panoLocations") or []]} for r in rooms]


async def pano_face(pano: PanoramaRef, face: int) -> Path:
    """Download one 2k skybox face (0 up, 1–4 horizon, 5 down) into cache/media."""
    async def fetch() -> bytes:
        url = pano.skybox_urls[face] if face < len(pano.skybox_urls) else None
        if not url:
            raise MatterportError(f"no skybox face {face} for pano {pano.pano_id}")
        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as c:
            r = await c.get(url)
            if r.status_code in EXPIRED_LINK:  # signed link expired (cached query): re-query once
                fresh = {p.pano_id: p for p in await _fresh_panos(pano.model_id)}
                r = await c.get(fresh[pano.pano_id].skybox_urls[face])
            r.raise_for_status()
            return r.content

    return await cached_bytes("matterport.skybox",
                              {"model_id": pano.model_id, "pano_id": pano.pano_id, "face": face, "res": "2k"},
                              fetch, ext=".jpg")


async def _fresh_panos(model_id: str) -> list[PanoramaRef]:
    m = (await graph("panos", Q_PANOS, {"id": model_id}, fresh=True))["model"]
    return [PanoramaRef(pano_id=p["id"], model_id=model_id, label=p.get("label"),
                        xyz=tuple((p.get("position") or {}).get(k, 0.0) for k in "xyz"),
                        skybox_urls=(p.get("skybox") or {}).get("children") or [])
            for p in m.get("panoLocations") or []]


async def rooms(model_id: str) -> dict:
    """Raw room data: floors (wall-graph vertices/edges), rooms (labels, boundaries, metric dims),
    floor-plan renders (origin + px/m), pano 2D positions."""
    return (await graph("rooms", Q_ROOMS, {"id": model_id}))["model"]


MESH_EXTS = {".obj", ".mtl", ".jpg", ".jpeg", ".png"}


async def matterpak(model_id: str, *, include_pointcloud: bool = False) -> MatterPakPaths:
    """Download the MatterPak zip and extract mesh + textures + floor plan into cache/media/mesh/<model_id>/.

    Served by the API at /media/mesh/{model_id}/... In read_only mode returns what is on disk or
    raises CacheMiss.
    """
    s = get_settings()
    out_dir = Path(s.cache_dir) / "media" / "mesh" / model_id
    done = out_dir / ".complete"
    if not done.exists():
        if s.cache_mode == "read_only":
            raise CacheMiss(f"matterpak {model_id}")
        status = await matterpak_status(model_id)
        if status["availability"] != "unlocked":
            raise MatterportError(f"MatterPak for {model_id} is {status['availability']}")
        fresh = (await graph("matterpak", Q_MATTERPAK, {"id": model_id}, fresh=True))["model"]
        res = next((r for r in fresh["assets"]["resources"]
                    if r.get("status") == "available" and "matterpak" in (r.get("filename") or "")), None)
        if not res or not res.get("url"):
            raise MatterportError(f"no MatterPak download for {model_id}")
        out_dir.mkdir(parents=True, exist_ok=True)
        zpath = out_dir / "matterpak.zip.part"
        async with httpx.AsyncClient(timeout=600, follow_redirects=True) as c:
            async with c.stream("GET", res["url"]) as r:
                r.raise_for_status()
                with zpath.open("wb") as f:
                    async for chunk in r.aiter_bytes(1 << 20):
                        f.write(chunk)
        with zipfile.ZipFile(zpath) as z:
            for info in z.infolist():
                name = Path(info.filename).name
                ext = Path(name).suffix.lower()
                if not name or (ext not in MESH_EXTS and not (include_pointcloud and name == "cloud.xyz")
                                and name != "colorplan.pdf"):
                    continue
                with z.open(info) as src, (out_dir / name).open("wb") as dst:
                    shutil.copyfileobj(src, dst)
        zpath.unlink()
        done.touch()

    files = sorted(p for p in out_dir.iterdir() if p.is_file() and not p.name.startswith("."))
    pick = lambda ext: next((str(p) for p in files if p.suffix.lower() == ext), None)  # noqa: E731
    return MatterPakPaths(
        model_id=model_id, dir=str(out_dir), obj=pick(".obj"), mtl=pick(".mtl"),
        textures=[str(p) for p in files if p.suffix.lower() in {".jpg", ".jpeg", ".png"}
                  and not p.name.startswith("colorplan")],
        floorplan=next((str(p) for p in files if p.name.startswith("colorplan") and p.suffix == ".jpg"), None),
        pointcloud=str(out_dir / "cloud.xyz") if (out_dir / "cloud.xyz").exists() else None,
    )
