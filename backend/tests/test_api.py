import json

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


def test_media_and_mesh_routes(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("CACHE_DIR", str(tmp_path / "cache"))
    get_settings.cache_clear()
    try:
        img = tmp_path / "x.jpg"
        img.write_bytes(b"\xff\xd8jpeg")
        b = tmp_path / "data" / "buildings" / "1"
        b.mkdir(parents=True)
        (b / "images.json").write_text(json.dumps({"vxo_1": {"image_id": "vxo_1", "source": "vexcel_overhead",
                                                              "local_path": str(img)}}))
        mesh = tmp_path / "cache" / "media" / "mesh" / "m1"
        mesh.mkdir(parents=True)
        (mesh / "a.obj").write_text("v 0 0 0\n")
        (tmp_path / "cache" / "secret.txt").write_text("no")
        c = TestClient(app)
        assert c.get("/media/vxo_1").content == b"\xff\xd8jpeg"
        assert c.get("/media/nope").status_code == 404
        assert c.get("/media/mesh/m1/a.obj").text == "v 0 0 0\n"
        assert c.get("/media/mesh/m1/..%2F..%2Fsecret.txt").status_code == 404
        assert c.get("/state/run_missing").status_code == 404
    finally:
        get_settings.cache_clear()
