import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.schemas.layout import Layout
from app.widgets.registry import json_schemas, validate_layout

BACKEND = Path(__file__).resolve().parents[1]
SAMPLES = BACKEND.parent / "docs" / "agent" / "samples"
SITUATIONS = {"portfolio_overview", "target_gap", "verification_issue", "building_detail", "approved"}


def layouts():
    return sorted(p for p in SAMPLES.glob("*.json") if p.name != "registry.json")


def test_every_situation_has_a_sample():
    got = {json.loads(p.read_text())["situation"] for p in layouts()}
    assert got == SITUATIONS and (SAMPLES / "README.md").exists()


@pytest.mark.parametrize("path", layouts(), ids=lambda p: p.stem)
def test_sample_validates_against_the_current_schema_and_registry(path):
    lay = Layout.model_validate_json(path.read_text())
    validate_layout(lay)
    assert lay.widgets[-1].type == "activity_feed" and all(len(w.why) <= 90 for w in lay.widgets)


def test_registry_sample_matches_the_live_registry():
    assert json.loads((SAMPLES / "registry.json").read_text()) == json.loads(json.dumps(json_schemas()))


def test_samples_are_up_to_date(tmp_path):
    """Regenerating gives byte-identical files; if this fails run `python scripts/make_samples.py` and commit."""
    r = subprocess.run([sys.executable, str(BACKEND / "scripts" / "make_samples.py"), "--out", str(tmp_path)],
                       capture_output=True, text=True, cwd=BACKEND, timeout=120)
    assert r.returncode == 0, r.stderr
    for p in sorted(SAMPLES.glob("*.json")):
        assert (tmp_path / p.name).read_text() == p.read_text(), f"{p.name} is stale"
