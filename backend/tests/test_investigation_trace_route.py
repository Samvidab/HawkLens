"""GET /investigation_trace/{id}: the investigation_trace widget's props, verbatim from investigation.json; 404 when there
is no trace (or an old one without recorded feed lines), never a filled-in list."""
import json

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    get_settings.cache_clear()
    b = tmp_path / "buildings" / "b1"
    b.mkdir(parents=True)
    (b / "profile.json").write_text(json.dumps({"building_id": "b1", "costar_id": "c1", "name": "Test Tower", "address": "x",
                                                "city": "Houston", "lat": 29.7, "lon": -95.3, "footprint_wkt": None,
                                                "footprint_source": "estimated", "property_type": "Office", "source_fields": {}}))
    yield TestClient(app), b
    get_settings.cache_clear()


def test_steps_verbatim(client):
    c, b = client
    (b / "investigation.json").write_text(json.dumps({"steps": [
        {"tool": "inspect_roof", "shown": "inspected roof: for solar, given built 1983", "evidence": "vxo_1",
         "quoted": {"built": {"text": "built 1983", "source": "CoStar record"}}},
        {"tool": "finish", "shown": "finished"}]}))
    assert c.get("/investigation_trace/b1").json() == {"steps": [
        {"feed_line": "inspected roof: for solar, given built 1983", "tool": "inspect_roof",
         "facts_quoted": [{"id": "built", "text": "built 1983", "source": "CoStar record"}], "image_ids": ["vxo_1"]},
        {"feed_line": "finished", "tool": "finish", "facts_quoted": [], "image_ids": []}]}


def test_no_trace_or_old_trace_is_404(client):
    c, b = client
    assert c.get("/investigation_trace/b1").status_code == 404  # no investigation.json
    (b / "investigation.json").write_text(json.dumps({"steps": [{"tool": "inspect_roof"}]}))  # no recorded feed line
    assert c.get("/investigation_trace/b1").status_code == 404
    assert c.get("/investigation_trace/nope").status_code == 404
