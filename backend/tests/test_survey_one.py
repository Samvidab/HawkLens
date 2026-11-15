import importlib.util
import json
from pathlib import Path

from app.config import get_settings
from app.events import load_events, reset_run
from app.schemas.upgrades import FeasibleUpgrade

spec = importlib.util.spec_from_file_location(
    "survey_one", Path(__file__).resolve().parent.parent / "scripts" / "survey_one.py")
so = importlib.util.module_from_spec(spec)
spec.loader.exec_module(so)


def up(t, size, unit="sqft"):
    return FeasibleUpgrade(upgrade_id=f"b:{t}", building_id="b", category="solar" if t == "rooftop_solar" else "hvac",
                           type=t, size_value=size, size_unit=unit, reason="r", confidence=1, claim_ids=[],
                           evidence_ids=[], verified="assumed", include_in_optimizer=True)


def test_decide_message():
    assert so.decide_message([]) == "0 feasible upgrades"
    assert so.decide_message([up("heat_pump", 1)]) == "1 feasible upgrade"
    assert so.decide_message([up("rooftop_solar", 417.4, "kW"), up("heat_pump", 1)]) == \
        "2 feasible upgrades (solar 417 kW)"


async def test_survey_pipeline_with_fakes(tmp_path, monkeypatch):
    """records → aerial → feasibility wiring, files and events (network-free)."""
    from tests.test_aerial import obs, overhead
    from tests.test_records import REC

    monkeypatch.setenv("DATA_DIR", str(tmp_path / "data"))
    get_settings.cache_clear()
    ov = overhead(tmp_path)

    async def fake_get(pid):
        return REC

    async def fake_images(p):
        return [ov]

    async def fake_vision(prompt, images, schema):
        return obs()

    monkeypatch.setattr(so.records.costar, "get_property", fake_get)
    monkeypatch.setattr(so.aerial, "fetch_images", fake_images)
    monkeypatch.setattr(so.aerial.llm, "vision_json", fake_vision)
    reset_run("sv")
    try:
        ups = await so.survey("23347", "sv")
        saved = json.loads((tmp_path / "data" / "buildings" / "23347" / "feasibility.json").read_text())
        assert saved == [u.model_dump(mode="json") for u in ups]
        types = {u.type for u in ups}
        assert {"rooftop_solar", "cool_roof", "heat_pump", "led_retrofit"} <= types  # dark flat roof, built 1980
        solar = next(u for u in ups if u.type == "rooftop_solar")
        assert solar.evidence_ids == ["vxo_1"] and solar.verified == "unverified"  # verifier not run yet
        agents = [e.agent for e in load_events("sv")]
        assert agents[0] == "Records" and agents[-1] == "Site engineer"
    finally:
        get_settings.cache_clear()
