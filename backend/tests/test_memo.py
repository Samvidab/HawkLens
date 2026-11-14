import json

import pytest

from app import events
from app.agents import memo
from app.agents.pricing import run_pricing
from app.config import get_settings
from app.guardrails import check_numbers
from app.integrations import engine_client as eng
from app.schemas.goal import Goal
from tests.test_compose_flow import put, upgrade
from app.adapters.geometry import square_wkt


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path)); monkeypatch.setenv("ENGINE_MODE", "stub")
    get_settings.cache_clear(); eng.reset_stub(); events._seq.clear(); events._subs.clear()
    for bid, name, ups in [
        ("b1", "Allen Center 2", [upgrade("b1", "rooftop_solar", "solar", 300, "kW"), upgrade("b1", "led_retrofit", "lighting", 400_000, "sqft")]),
        ("b2", "Harbor Lofts", [upgrade("b2", "cool_roof", "roof", 50_000, "sqft"), upgrade("b2", "heat_pump", "hvac", 200_000, "sqft")])]:
        put(tmp_path / f"buildings/{bid}/profile.json", dict(
            building_id=bid, costar_id=bid, name=name, address="a", city="Houston", lat=29.7, lon=-95.3,
            footprint_wkt=square_wkt(29.7, -95.3, 60, "Houston"), footprint_source="costar", property_type="Office",
            stories=8, rba_sqft=400_000.0, source_fields={}))
        put(tmp_path / f"buildings/{bid}/feasibility.json", ups)
    yield tmp_path
    get_settings.cache_clear()


def fake_llm(monkeypatch, drafts):
    calls = []

    async def _t(prompt, schema, **kw):
        calls.append(prompt)
        return schema(markdown=drafts[min(len(calls) - 1, len(drafts) - 1)])
    monkeypatch.setattr(memo, "text_json", _t)
    return calls


GOOD = ("The plan cuts {{tonnes_per_year}} toward a {{target_pct}} target using {{n_upgrades}} upgrades.\n\n"
        "Upfront cost is {{total_upfront}}, expected value {{exp_npv}}, worst case {{cvar5}}, loss chance {{p_loss}}.\n\n"
        "Hit probability is {{p_hit_target}}; budget: {{budget}}.")

GOALS = [Goal(city="Houston", target_pct=10), Goal(city="Houston", target_pct=35, risk_lambda=0.8),
         Goal(city="Houston", target_pct=90, budget_usd=250_000.0)]


@pytest.mark.parametrize("goal", GOALS)
async def test_numbers_pass_guardrail_on_three_plans(data, monkeypatch, goal):
    calls = fake_llm(monkeypatch, [GOOD])
    plan = await run_pricing("r", goal)
    md = await memo.write_memo("r")
    values, raw = memo.build_values(plan, {})
    assert "{{" not in md and len(calls) == 1
    prose = md.split("## Upgrades")[0]
    assert check_numbers(prose, [plan, raw, {"n": "Allen Center 2"}]) == []
    assert values["total_upfront"] in md
    assert (data / "memo" / f"{plan['plan_id']}.md").read_text() == md
    assert "Sample pricing" in md  # stub engine is disclosed


async def test_invented_number_rejected_and_regenerated(data, monkeypatch):
    calls = fake_llm(monkeypatch, ["Saves 4,242 tonnes. {{total_upfront}} upfront.", "Saves carbon for {{total_upfront}} upfront."])
    await run_pricing("r", GOALS[0])
    md = await memo.write_memo("r")
    assert "4,242" not in md and "Saves carbon for" in md
    assert len(calls) == 2 and "previous draft contained a number" in calls[1]


async def test_falls_back_to_template(data, monkeypatch):
    fake_llm(monkeypatch, ["Always 9,999 t. {{total_upfront}}"])  # invents numbers both times
    plan = await run_pricing("r", GOALS[0])
    md = await memo.write_memo("r")
    assert "9,999" not in md and "This plan cuts" in md

    async def boom(*a, **k):
        raise RuntimeError("gemini down")
    monkeypatch.setattr(memo, "text_json", boom)
    assert "This plan cuts" in await memo.write_memo("r")

    fake_llm(monkeypatch, ["Uses {{secret_number}} here."])  # unknown placeholder
    assert "This plan cuts" in await memo.write_memo("r")


async def test_prompt_contains_no_numbers_from_plan(data, monkeypatch):
    calls = fake_llm(monkeypatch, [GOOD])
    plan = await run_pricing("r", GOALS[0])
    await memo.write_memo("r")
    import re
    assert not re.search(str(round(plan["total_upfront"])), calls[0])
    assert "Allen Center 2" in calls[0] or "Harbor Lofts" in calls[0]


async def test_memo_feeds_the_approved_layout(data, monkeypatch):
    from app.widgets.resolver import ResolveContext, resolve_layout
    fake_llm(monkeypatch, [GOOD])
    plan = await run_pricing("r", GOALS[0])
    md = await memo.write_memo("r")
    lay = resolve_layout(ResolveContext.load(data, "r"), "approved")
    assert {w.type: w for w in lay.widgets}["memo"].props["markdown"] == md


async def test_no_plan_raises(data):
    with pytest.raises(ValueError):
        await memo.write_memo("r")
