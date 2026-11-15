"""End-use research: every number and quote must appear verbatim in the fetched source text;
a number that isn't there is rejected and nothing is saved (no network, no Gemini)."""
import json

import pytest

from app.agents import end_use_research as r
from app.agents import emissions_3d as e3
from app.events import load_events, reset_run

# Shaped like pypdf's text of CBECS 2018 Table E5 (header split across lines, as in the PDF).
RAW = """Release date: December 2022
Total
Space
heating Cooling
Venti-
lation
Water
heating Lighting Cooking
Refrig-
eration
Office
equip-
ment
Com-
puting Other
All buildings 1,196 70 170 213 24 208 26 108 14 79 284
Principal building activity
Education 128 7 26 19 3 22 2 6 2 10 30
Office 227 13 23 63 2 38 1 6 4 25 52
Total electricity consumption (billion kWh)
Table E5. Electricity consumption (in kilowatthours [kWh]) by end use, 2018
Census region and division
South 477 27 101 78 10 77 11 39 5 25 105
"""
COLS = ["Space heating", "Cooling", "Ventilation", "Water heating", "Lighting", "Cooking", "Refrigeration",
        "Office equipment", "Computing", "Other"]
VALS = ["13", "23", "63", "2", "38", "1", "6", "4", "25", "52"]


def extraction(**over) -> r.Extraction:
    base = dict(table_title_quote="Table E5. Electricity consumption (in kilowatthours [kWh]) by end use, 2018",
                unit_quote="Total electricity consumption (billion kWh)",
                header_quote="Total " + " ".join(COLS), section_quote="Principal building activity",
                row_quote="Office 227 13 23 63 2 38 1 6 4 25 52", total_text="227",
                values=[r.Value(column=c, value_text=v) for c, v in zip(COLS, VALS)])
    return r.Extraction(**(base | over))


TEXT = r.normalize(RAW)


def test_correct_extraction_verifies():
    v = r.verify(TEXT, extraction())
    assert v["ok"], [c for c in v["checks"] if not c["passed"]]
    assert v["total"] == 227 and v["values"]["Ventilation"] == 63 and v["row_label"] == "Office"


def test_number_not_in_source_is_rejected():
    vals = [r.Value(column=c, value_text=("40" if c == "Lighting" else v)) for c, v in zip(COLS, VALS)]
    v = r.verify(TEXT, extraction(values=vals))  # model says 40; the row says 38
    assert not v["ok"] and v["values"]["Lighting"] == "unknown"
    assert v["values"]["Ventilation"] == 63  # the rest still check out, but the source is not verified


def test_value_from_another_row_or_column_is_rejected():
    swapped = [r.Value(column=c, value_text=v) for c, v in zip(COLS, ["23", "13", *VALS[2:]])]  # in row, wrong columns
    assert not r.verify(TEXT, extraction(values=swapped))["ok"]
    south = extraction(row_quote="Office 227 13 23 63 2 38 1 6 4 25 99")  # a row that isn't in the text
    assert not r.verify(TEXT, south)["ok"]


def test_quotes_must_be_verbatim_and_electricity():
    assert not r.verify(TEXT, extraction(table_title_quote="Table E5. Electricity use by end use, 2018"))["ok"]
    assert not r.verify(TEXT, extraction(unit_quote="Total electricity consumption (million kWh)"))["ok"]
    assert not r.verify(TEXT, extraction(section_quote="Census region and division"))["ok"]  # row isn't under it
    intensity = TEXT.replace("Table E5. Electricity consumption (in", "Table E6. Electricity consumption intensities (in")
    ex = extraction(table_title_quote="Table E6. Electricity consumption intensities (in kilowatthours [kWh]) by end use, 2018")
    assert not r.verify(intensity, ex)["ok"]  # intensities are not shares


@pytest.fixture
def agent(tmp_path, monkeypatch):
    async def fake_text(url):
        return RAW

    monkeypatch.setattr(r, "fetch_text", fake_text)
    answers = {}

    async def fake_llm(prompt, schema, fast=True):
        return answers[schema.__name__]
    monkeypatch.setattr(r.llm, "text_json", fake_llm)
    answers["Pick"] = r.Pick(source_id="cbecs2018_e5", row_label="Office", region_crossed_with_activity=False)
    return answers, tmp_path / "split.json"


async def test_research_saves_verified_split_with_events(agent):
    answers, out = agent
    answers["Extraction"] = extraction()
    reset_run("res1")
    split = await r.research("res1", out=out)
    saved = json.loads(out.read_text())
    assert saved == split and saved["measures"] == "electricity" and saved["verification"]["status"] == "verified"
    assert saved["table"] == "E5" and saved["row"] == "Office" and "all U.S. office buildings" in saved["scope"]
    by = {e["name"]: e for e in saved["end_uses"]}
    assert by["Ventilation"]["share"] == 63 / 227 and by["Ventilation"]["value_text"] == "63"
    for e in saved["end_uses"]:  # every number saved is in the source text (or value/total of two that are)
        assert e["value_text"] in e["quote"].split() and e["quote"] in TEXT and e["total_text"] == "227"
    msgs = [e.message for e in load_events("res1")]
    assert msgs[0] == 'picked EIA CBECS 2018 Table E5: row "Office"'
    assert msgs[-1].startswith("saved shares: ventilation 28%, other 23%, lighting 17%")
    # emissions_3d accepts it
    s = e3.load_split(out)
    assert round(sum(x.share for x in s.end_uses), 9) == 1


async def test_research_refuses_and_saves_nothing_on_mismatch(agent):
    answers, out = agent
    answers["Extraction"] = extraction(values=[r.Value(column=c, value_text=("40" if c == "Lighting" else v))
                                               for c, v in zip(COLS, VALS)])
    reset_run("res2")
    with pytest.raises(ValueError, match="failed verification"):
        await r.research("res2", out=out)
    assert not out.exists()
    assert any(e.kind == "error" and "nothing saved" in e.message for e in load_events("res2"))


def test_emissions_refuses_unverified_split(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"citation": "x", "scope": "y", "basis": "z", "verification": {"status": "failed"},
                             "end_uses": [{"name": "Lighting", "category": "lighting", "share": 0.2}]}))
    with pytest.raises(ValueError, match="not verified"):
        e3.load_split(p)
