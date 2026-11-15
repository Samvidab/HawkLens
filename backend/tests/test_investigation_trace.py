"""investigation_trace widget: every field comes from buildings/<id>/investigation.json, verbatim,
in order; nothing else is in the props."""
import json
from pathlib import Path

import pytest

from app.schemas.layout import WidgetSpec
from app.widgets.registry import validate_props
from app.widgets.resolver import ResolveContext, ResolveError, resolve_widget

DATA = Path(__file__).resolve().parents[1] / "data"
STEP_KEYS = {"feed_line", "tool", "facts_quoted", "image_ids"}


def spec() -> WidgetSpec:
    return WidgetSpec(id="w1", type="investigation_trace", title="t", why="", size="wide")


def expected(step: dict) -> dict:
    """The only mapping allowed: recorded fields copied, renamed, nothing computed."""
    return {"feed_line": step["shown"], "tool": step["tool"],
            "facts_quoted": [{"id": k, **{f: v[f] for f in ("text", "source")}} for k, v in (step.get("quoted") or {}).items()],
            "image_ids": [step["evidence"]] if step.get("evidence") else []}


def world(tmp_path, trace: dict | None) -> Path:
    d = tmp_path / "data" / "buildings" / "b1"
    d.mkdir(parents=True)
    (d / "profile.json").write_text(json.dumps({
        "building_id": "b1", "costar_id": "b1", "name": "Bldg", "address": "x", "city": "Houston", "lat": 29.7, "lon": -95.4,
        "footprint_source": "estimated", "property_type": "Office", "source_fields": {}}))
    if trace is not None:
        (d / "investigation.json").write_text(json.dumps(trace))
    return tmp_path / "data"


TRACE = {"building_id": "b1", "run_id": "r", "max_calls": 8, "facts": {}, "steps": [
    {"tool": "inspect_roof", "args": {}, "purpose": "solar_evidence", "because": ["built", "made_up"],
     "result": "roof flat (0.95)", "shown": "inspected roof: for solar, given built 1983",
     "quoted": {"built": {"text": "built 1983", "source": "CoStar record"}}, "evidence": "vxo_abc"},
    {"tool": "find_matterport_scans", "args": {}, "purpose": "find_interior_evidence", "because": [],
     "result": "unknown (failed: RuntimeError)", "shown": "Matterport scans unknown: for interior evidence",
     "quoted": {}, "evidence": None},
    {"tool": "finish", "args": {}, "purpose": "no_more_value", "because": [], "result": "done",
     "shown": "finished: more evidence won't change an upgrade", "quoted": {}, "evidence": None},
]}


def test_every_field_comes_from_investigation_json(tmp_path):
    ctx = ResolveContext.load(world(tmp_path, TRACE), "r", focus_building_id="b1")
    w = resolve_widget(spec(), ctx)
    assert w.data_ref == "buildings/b1/investigation.json#/steps"
    assert set(w.props) == {"steps"}
    assert [set(s) for s in w.props["steps"]] == [STEP_KEYS] * 3
    assert w.props["steps"] == [expected(s) for s in TRACE["steps"]]  # verbatim, in order
    # nothing from the model's own choice (purpose, because, result) leaks into the widget
    text = json.dumps(w.props)
    assert "made_up" not in text and "solar_evidence" not in text and "0.95" not in text
    validate_props("investigation_trace", w.props)


def test_no_trace_or_old_trace_is_not_shown(tmp_path):
    with pytest.raises(ResolveError, match="no investigation trace"):
        resolve_widget(spec(), ResolveContext.load(world(tmp_path / "a", None), "r", focus_building_id="b1"))
    old = {**TRACE, "steps": [{k: v for k, v in TRACE["steps"][0].items() if k != "shown"}]}
    with pytest.raises(ResolveError, match="predates recorded feed lines"):
        resolve_widget(spec(), ResolveContext.load(world(tmp_path / "b", old), "r", focus_building_id="b1"))


@pytest.mark.skipif(not any(DATA.glob("buildings/*/investigation.json")), reason="no warm-cache data in this checkout")
def test_real_run_traces_match_their_files():
    ctx = ResolveContext.load(DATA, "warm_full")
    n = 0
    for f in sorted(DATA.glob("buildings/*/investigation.json")):
        ctx.focus_building_id = f.parent.name
        w = resolve_widget(spec(), ctx)
        assert w.props["steps"] == [expected(s) for s in json.loads(f.read_text())["steps"]]
        n += 1
    assert n >= 1
