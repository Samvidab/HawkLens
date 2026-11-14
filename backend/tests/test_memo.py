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
        "{{return_summary}} Hit probability is {{p_hit_target}}; budget: {{budget}}.")

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
    calls = fake_llm(monkeypatch, ["Saves 4,242 tonnes. {{total_upfront}} upfront. {{return_summary}}", "Saves carbon for {{total_upfront}} upfront. {{return_summary}}"])
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


# ---- digits in building names and addresses are allowed, and copied exactly (never spelled out) ----------------------
async def test_names_and_addresses_with_digits_pass_the_number_guard(data, monkeypatch):
    import json
    for bid, name, addr in [("b1", "7900 Fannin", "7900 Fannin St, Houston, TX 77054"), ("b2", "CityNorth 6", "9999 N Interstate 45")]:
        f = data / f"buildings/{bid}/profile.json"
        d = json.loads(f.read_text()); d.update(name=name, address=addr); f.write_text(json.dumps(d))
    calls = fake_llm(monkeypatch, [
        "Buildings 7900 Fannin (7900 Fannin St, Houston, TX 77054) and CityNorth 6 get {{n_upgrades}} upgrades.\n\n"
        "Upfront cost is {{total_upfront}}. {{return_summary}}\n\nHit probability is {{p_hit_target}}."])
    await run_pricing("r", GOALS[1])
    md = await memo.write_memo("r")
    assert "7900 Fannin" in md and "CityNorth 6" in md and "77054" in md  # copied as written, not rejected, no template fallback
    assert "This plan cuts" not in md and len(calls) == 1
    assert "seventy" not in md.lower() and "CityNorth six" not in md


async def test_the_prompt_tells_the_model_to_copy_names_exactly(data, monkeypatch):
    import json
    f = data / "buildings/b1/profile.json"; d = json.loads(f.read_text()); d["name"] = "7900 Fannin"; f.write_text(json.dumps(d))
    calls = fake_llm(monkeypatch, [GOOD])
    await run_pricing("r", GOALS[1])
    await memo.write_memo("r")
    p = calls[0]
    assert "7900 Fannin" in p and "Copy those EXACTLY" in p and "Never spell" in p
    assert "NEVER write a digit or a number, with ONE exception" in p


async def test_a_number_that_is_not_in_any_name_is_still_rejected(data, monkeypatch):
    calls = fake_llm(monkeypatch, ["Allen Center 2 saves 4,242 tonnes. {{total_upfront}}. {{return_summary}}", "Allen Center 2 saves carbon for {{total_upfront}}. {{return_summary}}"])
    await run_pricing("r", GOALS[0])
    md = await memo.write_memo("r")
    assert "4,242" not in md and "Allen Center 2 saves carbon" in md and len(calls) == 2



# ---- neutral wording, a plain return sentence written by code, and count words that match the data -------------------------
import re as _re  # noqa: E402

from app.agents.memo import DraftRejected, check_draft, return_summary  # noqa: E402
from app.guardrails import EVALUATIVE_WORDS, check_wording  # noqa: E402


def upg(*types):
    return {f"b{i}:{t}": {"upgrade_id": f"b{i}:{t}", "building_id": f"b{i}", "type": t} for i, t in enumerate(types)}


def plan_with(exp_npv, per_upgrade):
    return {"exp_npv": exp_npv, "selected": list(per_upgrade), "simulate": {k: {"exp_npv": v} for k, v in per_upgrade.items()}}


def test_return_summary_says_plainly_whether_the_plan_pays_back():
    u = upg("rooftop_solar", "led_retrofit", "heat_pump")
    solar, led, hp = "b0:rooftop_solar", "b1:led_retrofit", "b2:heat_pump"
    # the user's example: negative on average, the solar portion pays for itself
    assert return_summary(plan_with(-500.0, {solar: 900.0, led: -700.0, hp: -700.0}), u) == \
        "On average the plan costs more than it saves; the rooftop solar portion pays for itself."
    assert return_summary(plan_with(-500.0, {solar: 900.0, led: 200.0, hp: -1600.0}), u) == \
        "On average the plan costs more than it saves; the LED retrofit and rooftop solar portions pay for themselves."
    assert return_summary(plan_with(-5.0, {solar: -1.0, led: -2.0, hp: -2.0}), u) == \
        "On average the plan costs more than it saves; no upgrade type pays for itself on average."
    assert return_summary(plan_with(300.0, {solar: 900.0, led: 100.0, hp: -700.0}), u) == \
        "On average the plan saves more than it costs; the heat pump portion costs more than it saves."
    assert return_summary(plan_with(300.0, {solar: 200.0, led: 100.0, hp: 0.5}), u) == "On average the plan saves more than it costs."
    assert return_summary({"selected": []}, u) == "The expected net present value of the plan is not available."
    # several upgrades of one type add up before the type is judged
    two = {**upg("rooftop_solar", "rooftop_solar")}
    assert return_summary(plan_with(-1.0, {"b0:rooftop_solar": 500.0, "b1:rooftop_solar": -100.0}), two).endswith("the rooftop solar portion pays for itself.")


def test_return_summary_has_no_digits_or_evaluative_words():
    u = upg("rooftop_solar", "led_retrofit")
    for npv in (-9e6, 0.0, 9e6):
        t = return_summary(plan_with(npv, {"b0:rooftop_solar": 10.0, "b1:led_retrofit": -10.0}), u)
        assert not _re.search(r"\d", t) and check_wording(t) == []


async def test_negative_expected_npv_is_stated_plainly_in_the_memo(data, monkeypatch):
    fake_llm(monkeypatch, [GOOD])
    plan = await run_pricing("r", GOALS[1])
    ups = {u["upgrade_id"]: u for b in ("b1", "b2") for u in json.loads((data / f"buildings/{b}/feasibility.json").read_text())}
    for uid in plan["selected"]:  # solar pays for itself, everything else does not, and the plan loses money on average
        plan["simulate"][uid]["exp_npv"] = 1000.0 if ups[uid]["type"] == "rooftop_solar" else -5000.0
    plan["exp_npv"] = -20000.0
    md = await memo.write_memo("r", plan)
    assert "On average the plan costs more than it saves; the rooftop solar portion pays for itself." in md
    plan["exp_npv"] = 20000.0
    for uid in plan["selected"]:
        plan["simulate"][uid]["exp_npv"] = 1000.0
    assert "On average the plan saves more than it costs." in await memo.write_memo("r", plan)


async def test_evaluative_wording_is_rejected_and_regenerated_with_the_reason(data, monkeypatch):
    calls = fake_llm(monkeypatch, [
        "A strong plan with robust financial protections. {{return_summary}} It costs {{total_upfront}}.",
        "The plan costs {{total_upfront}} upfront. {{return_summary}} Hit probability is {{p_hit_target}}."])
    await run_pricing("r", GOALS[0])
    md = await memo.write_memo("r")
    assert len(calls) == 2 and "rejected because it used evaluative or promotional wording (strong, robust, protections)" in calls[1]
    assert "rejected" not in calls[0]
    assert check_wording(md) == [] and "A strong plan" not in md and "The plan costs" in md


async def test_a_draft_that_keeps_judging_the_results_falls_back_to_the_neutral_template(data, monkeypatch):
    calls = fake_llm(monkeypatch, ["An attractive, solid return. {{return_summary}}", "Excellent value with strong protections. {{return_summary}}"])
    await run_pricing("r", GOALS[0])
    md = await memo.write_memo("r")
    assert len(calls) == memo.MAX_DRAFTS == 2
    assert "This plan cuts" in md and check_wording(md.split("## Upgrades")[0]) == [] and "attractive" not in md.lower()


async def test_the_return_sentence_is_required_and_appears_once(data, monkeypatch):
    calls = fake_llm(monkeypatch, ["The plan costs {{total_upfront}}.", "The plan costs {{total_upfront}}. {{return_summary}} {{return_summary}}",
                                   "The plan costs {{total_upfront}}. {{return_summary}}"])
    await run_pricing("r", GOALS[0])
    with pytest.raises(DraftRejected, match="exactly once"):
        check_draft("The plan costs {{total_upfront}}.")
    with pytest.raises(DraftRejected, match="found 2"):
        check_draft("{{return_summary}} {{return_summary}}")
    md = await memo.write_memo("r")  # draft 1 lacks it -> draft 2 (told why) repeats it -> template
    assert len(calls) == 2 and "This plan cuts" in md
    assert "return_summary" in calls[1] and "(found 0)" in calls[1]


def test_count_words_must_match_what_is_counted():
    for bad in ("It has {{n_upgrades}} upgrade types.", "It has {{n_upgrades}} distinct upgrade types across {{n_buildings}} buildings.",
                "It has {{n_upgrades}} individual types of upgrades.", "{{n_upgrade_types}} upgrades are planned.", "{{n_upgrade_types}} separate upgrades"):
        with pytest.raises(DraftRejected, match="counts"):
            check_draft(bad + " {{return_summary}}")
    for good in ("It has {{n_upgrades}} upgrades across {{n_buildings}} buildings and {{n_upgrade_types}} upgrade types.",
                 "{{n_upgrade_types}} upgrade types, {{n_upgrades}} upgrades in total.", "{{n_upgrades}} upgrades of {{n_upgrade_types}} upgrade types."):
        check_draft(good + " {{return_summary}}")


async def test_the_memo_counts_upgrades_and_types_as_the_data_says(data, monkeypatch):
    calls = fake_llm(monkeypatch, [
        "It has {{n_upgrades}} upgrade types. {{return_summary}}",
        "The plan has {{n_upgrades}} upgrades of {{n_upgrade_types}} upgrade types across {{n_buildings}} buildings. {{return_summary}}"])
    plan = await run_pricing("r", GOALS[1])
    md = await memo.write_memo("r")
    ups = {u["upgrade_id"]: u for b in ("b1", "b2") for u in json.loads((data / f"buildings/{b}/feasibility.json").read_text())}
    n, types = len(plan["selected"]), len({ups[u]["type"] for u in plan["selected"]})
    assert f"The plan has {n} upgrades of {types} upgrade types" in md and f"{n} upgrade types" not in md.replace(f"{types} upgrade types", "")
    assert "counts individual upgrades" in calls[1]  # the first draft was rejected and told why


async def test_the_prompt_states_the_wording_rules(data, monkeypatch):
    calls = fake_llm(monkeypatch, [GOOD])
    await run_pricing("r", GOALS[0])
    await memo.write_memo("r")
    p = calls[0]
    for needle in ("Describe results NEUTRALLY", "strong", "robust", "attractive", "protection(s)", "{{return_summary}}", "{{n_upgrade_types}}",
                   'Never write "{{n_upgrades}} upgrade types"'):
        assert needle in p, needle
    assert all(w in EVALUATIVE_WORDS for w in ("strong", "robust", "attractive", "protection", "protections"))
