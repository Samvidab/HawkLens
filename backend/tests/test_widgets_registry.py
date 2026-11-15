import json
import re

import pytest

from app.schemas.layout import Layout, WidgetSpec
from app.widgets import registry
from app.widgets.registry import RegistryError, WIDGETS, json_schemas, validate_layout, validate_props
from app.widgets.templates import TEMPLATES, stock_title, stock_why, template_for

SPEC_TYPES = {"target_control", "portfolio_3d", "hero_3d", "abatement_curve", "plan_table", "risk_histogram",
              "evidence_gallery", "facade_compass", "floor_plan", "upgrade_list", "building_header",
              "target_gap_card", "financing_card", "memo", "activity_feed", "investigation_trace"}

SPEC_REQUIRED = {  # App Flow §5 "Required props"
    "target_control": {"target_pct", "budget_usd", "risk_lambda", "p_hit_target", "tonnes_needed", "tonnes_planned"},
    "portfolio_3d": {"buildings", "focus_building_id"},
    "abatement_curve": {"bars"},
    "plan_table": {"rows", "totals"},
    "risk_histogram": {"bins", "exp_npv", "cvar5", "p_loss", "scope"},
    "hero_3d": {"building_id", "mesh_url", "mtl_url", "pins"},
    "activity_feed": {"run_id"},
    "memo": {"markdown"},
    "investigation_trace": {"steps"},
}


def test_registry_has_exactly_the_spec_widgets():
    assert set(WIDGETS) == SPEC_TYPES


@pytest.mark.parametrize("wtype,names", SPEC_REQUIRED.items())
def test_every_spec_prop_exists_in_model(wtype, names):
    assert names <= set(WIDGETS[wtype].props_model.model_fields)


def test_json_schema_export_is_serialisable():
    s = json_schemas()
    json.dumps(s)
    assert set(s["widgets"]) == SPEC_TYPES
    assert s["widgets"]["activity_feed"]["default_size"] == "side"
    assert "approve" in s["widgets"]["financing_card"]["emits"]
    assert s["widgets"]["activity_feed"]["required"] == ["run_id"]


def test_validate_props():
    assert validate_props("activity_feed", {"run_id": "r"}).run_id == "r"
    with pytest.raises(RegistryError):
        validate_props("activity_feed", {})
    with pytest.raises(RegistryError):
        validate_props("activity_feed", {"run_id": "r", "extra": 1})
    with pytest.raises(RegistryError, match="unknown"):
        validate_props("chatbot", {})


def test_templates_use_registered_types_and_fit_the_cap():
    for sit in TEMPLATES:
        for mp in (True, False):
            specs = template_for(sit, has_matterport=mp)
            assert all(s.type in WIDGETS for s in specs)
            assert specs[-1].type == "activity_feed" and specs[-1].size == "side"
            assert len(specs) <= 8 and len({s.id for s in specs}) == len(specs)


def test_template_contents_match_spec():
    names = lambda sit, mp=False: [s.type for s in template_for(sit, has_matterport=mp)][:-1]
    assert names("portfolio_overview") == ["target_control", "portfolio_3d", "abatement_curve", "plan_table",
                                           "risk_histogram", "financing_card"]
    assert names("target_gap") == ["target_control", "target_gap_card", "abatement_curve", "plan_table", "portfolio_3d"]
    assert names("verification_issue") == ["evidence_gallery", "upgrade_list", "target_control", "portfolio_3d"]
    assert names("approved") == ["financing_card", "memo", "plan_table"]
    assert names("building_detail", True) == ["building_header", "hero_3d", "evidence_gallery", "facade_compass",
                                              "floor_plan", "upgrade_list", "risk_histogram"]
    no_mp = names("building_detail", False)
    assert "hero_3d" not in no_mp and "floor_plan" not in no_mp and "portfolio_3d" in no_mp


def test_stock_why_short_and_numberless():
    for sit, items in TEMPLATES.items():
        for it in items:
            assert len(it.why) <= 90 and not re.search(r"\d", it.why), it
    assert stock_why("memo") and stock_title("plan_table") == "Recommended plan"
    assert stock_why("facade_compass")


def test_validate_layout():
    specs = template_for("approved")
    for s in specs:
        s.props = {"run_id": "r"} if s.type == "activity_feed" else {}
    lay = Layout(layout_id="l", run_id="r", situation="approved", generated_at="t", widgets=specs)
    with pytest.raises(RegistryError):  # financing_card has all-optional props -> ok; memo needs markdown
        validate_layout(lay)
    for s in lay.widgets:
        if s.type == "memo":
            s.props = {"markdown": "x"}
        if s.type == "plan_table":
            s.props = {"rows": [], "totals": {}}
    assert validate_layout(lay) is lay
    lay.widgets[0] = WidgetSpec(id="w9", type="nope", title="t", why="w", size="half")
    with pytest.raises(RegistryError, match="unknown"):
        validate_layout(lay)
