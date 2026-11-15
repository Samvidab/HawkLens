import pytest

from app.guardrails import (CapExceeded, StepCounter, check_numbers, fill_placeholders, guarded_text)

SRC = {"tonnes": 3100.0, "p_hit": 0.82, "upfront": 1_234_567.0, "npv": -50.0, "name": "Allen Center 2",
       "rows": [{"kw": 310.4}], "year": 1980}


@pytest.mark.parametrize("text", [
    "3,100 t/yr short", "p(hit) 0.82", "p(hit) 82%", "about $1.2M upfront", "$1,234,567 upfront",
    "1.23M", "1,235 k", "solar 310 kW", "solar 310.4 kW", "Allen Center 2", "built 1980", "NPV -50",
    "loss of 50", "no digits here", "Orchestrator · Plan: {{n_buildings}} buildings", "3100 t",
])
def test_accepts_explained_numbers(text):
    assert check_numbers(text, SRC) == [], text


@pytest.mark.parametrize("text,bad", [
    ("saves 4,200 t/yr", ["4,200"]), ("p(hit) 0.9", ["0.9"]), ("90% likely", ["90%"]),
    ("$2M upfront", ["$2M"]), ("310.5 kW", ["310.5"]), ("3 buildings", ["3"]),
])
def test_rejects_invented_numbers(text, bad):
    assert check_numbers(text, SRC) == bad


async def test_guarded_text_regenerates_without_numbers():
    calls = []

    async def gen(allow):
        calls.append(allow)
        return "saves 9,999 t" if allow else "saves a lot of carbon"

    assert await guarded_text(gen, SRC) == "saves a lot of carbon"
    assert calls == [True, False]


async def test_guarded_text_passes_good_draft_and_falls_back():
    async def good(allow):
        return "3,100 t short"
    assert await guarded_text(good, SRC) == "3,100 t short"

    async def bad(allow):
        return "saves 9,999 t"
    assert await guarded_text(bad, SRC, fallback="stock") == "stock"
    with pytest.raises(ValueError):
        await guarded_text(bad, SRC)


def test_fill_placeholders():
    assert fill_placeholders("{{a}} t and {{ b }}", {"a": "3,100", "b": 5}) == "3,100 t and 5"
    with pytest.raises(KeyError):
        fill_placeholders("{{zz}}", {})


def test_caps():
    c = StepCounter(max_steps=2, max_loops=2)
    c.step("a"); c.step("a")
    with pytest.raises(CapExceeded):
        c.step("a")
    c.step("b")
    assert c.loop("k") == 1 and c.loop("k") == 2 and not c.can_loop("k")
    with pytest.raises(CapExceeded):
        c.loop("k")
