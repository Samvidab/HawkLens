import json

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import get_settings
from app.main import app


@pytest.fixture
def env(tmp_path, monkeypatch):
    data, cache = tmp_path / "data", tmp_path / "cache"
    monkeypatch.setenv("DATA_DIR", str(data)); monkeypatch.setenv("CACHE_DIR", str(cache))
    get_settings.cache_clear()
    yield TestClient(app), data, cache, tmp_path
    get_settings.cache_clear()


def register(data, bid, entries):
    d = data / "buildings" / bid
    d.mkdir(parents=True)
    (d / "images.json").write_text(json.dumps(entries))


def test_image_served_from_images_json(env):
    c, data, cache, _ = env
    (cache / "media").mkdir(parents=True)
    Image.new("RGB", (8, 8), "red").save(cache / "media" / "abc.png")
    register(data, "b1", {"vxo_1": {"image_id": "vxo_1", "source": "vexcel_overhead", "local_path": str(cache / "media/abc.png")}})
    r = c.get("/media/vxo_1")
    assert r.status_code == 200 and r.headers["content-type"] == "image/png" and r.content[:4] == b"\x89PNG"
    assert c.get("/media/nope").status_code == 404


def test_image_outside_cache_or_data_is_refused(env):
    c, data, cache, tmp = env
    secret = tmp / "secret.txt"; secret.write_text("x")
    register(data, "b1", {"evil": {"image_id": "evil", "local_path": str(secret)},
                          "missing": {"image_id": "missing", "local_path": str(cache / "media/gone.png")}})
    assert c.get("/media/evil").status_code == 404 and c.get("/media/missing").status_code == 404


def test_image_id_in_second_building(env):
    c, data, cache, _ = env
    (cache / "media").mkdir(parents=True)
    (cache / "media/x.jpg").write_bytes(b"\xff\xd8jpg")
    register(data, "b1", {"a": {"local_path": str(cache / "media/none.jpg")}})
    register(data, "b2", {"pano_9": {"local_path": str(cache / "media/x.jpg")}})
    assert c.get("/media/pano_9").status_code == 200


def mesh(cache, mid="m1"):
    d = cache / "media" / "mesh" / mid
    d.mkdir(parents=True)
    (d / "Suite266.obj").write_text("v 0 0 0\n"); (d / "Suite266.mtl").write_text("newmtl a\n")
    (d / "tex_0.jpg").write_bytes(b"\xff\xd8x"); (d / "cloud.xyz").write_text("0 0 0 1 1 1\n")
    (d / "matterpak.zip").write_bytes(b"PK"); (d / ".complete").write_text("")
    return d


def test_mesh_files_and_aliases(env):
    c, _, cache, _ = env
    mesh(cache)
    assert c.get("/media/mesh/m1/model.obj").text == "v 0 0 0\n"  # alias to the real .obj
    assert c.get("/media/mesh/m1/model.mtl").text == "newmtl a\n"
    assert c.get("/media/mesh/m1/Suite266.obj").status_code == 200
    r = c.get("/media/mesh/m1/tex_0.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"


def test_mesh_refuses_unlisted_and_traversal(env):
    c, _, cache, tmp = env
    mesh(cache)
    (cache / "media/mesh/secret.obj").write_text("s")
    for bad in ["cloud.xyz", "matterpak.zip", ".complete", "nope.obj", "../secret.obj", "%2e%2e/secret.obj"]:
        assert c.get(f"/media/mesh/m1/{bad}").status_code == 404, bad
    assert c.get("/media/mesh/unknown/model.obj").status_code == 404
    assert c.get("/media/mesh/.hidden/model.obj").status_code == 404


def test_resolver_urls_match_routes(env):
    """hero_3d urls from the resolver must hit these routes."""
    c, _, cache, _ = env
    mesh(cache)
    from app.widgets.registry import validate_props
    props = validate_props("hero_3d", {"building_id": "b", "mesh_url": "/media/mesh/m1/model.obj", "mtl_url": "/media/mesh/m1/model.mtl"})
    assert c.get(props.mesh_url).status_code == 200 and c.get(props.mtl_url).status_code == 200
