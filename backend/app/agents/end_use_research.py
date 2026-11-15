"""End-use research agent: a sourced electricity end-use split for Houston offices (emissions_3d).

Approach reused from the utility-research agent (origin/nessie_data 0867940): a Gemini agent picks
official sources, numbers are never invented, unknowns stay null/"unknown", and nothing is called
verified without a source that states it. Differences: our cached llm.py (temperature 0, replayable
offline) instead of deepagents + live web search, and a verbatim check of every number in code.

Steps (each emits a "Research" activity event, composed by code from what the step returned):
1. pick   - Gemini chooses the official table and row from CATALOG (official EIA CBECS 2018 tables),
            preferring electricity consumption by end use for office buildings, South region if the
            table cross-tabulates it.
2. fetch  - code downloads the PDF (cache: research.pdf) and extracts its text (cache: research.text).
3. extract- Gemini returns the table title, unit line, column headers, section heading and the row,
            each as an exact quote from the text, plus each end use's value as written.
4. verify - code checks every quote appears verbatim in the fetched text, the headers in that order,
            the row under that section, and every value equals the row's token in that column. The
            title must say "Electricity consumption" (not intensity). Any mismatch → that value is
            "unknown" and the source is not saved as verified.
5. save   - shares = value / row total (code), with quotes, URL, table/row/column, scope,
            measures: electricity, verification status → app/agents/sources/houston_office_end_use.json.
"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path
from typing import Literal

import httpx
from pydantic import BaseModel

from app.adapters.cache import cached, cached_bytes, write_json_atomic
from app.agents import llm
from app.events import emit

log = logging.getLogger(__name__)
AGENT = "Research"
RUN_ID = "end_use_research"
OUT = Path(__file__).parent / "sources" / "houston_office_end_use.json"
UNKNOWN = "unknown"

CATALOG = {  # official sources the agent may pick from (EIA CBECS 2018 consumption & expenditures)
    "cbecs2018_e5": {"table": "E5", "url": "https://www.eia.gov/consumption/commercial/data/2018/ce/pdf/e5.pdf",
                     "title": "CBECS 2018 Table E5. Electricity consumption (kWh) by end use",
                     "about": "billion kWh by end use; rows by building activity (incl. Office), census region, "
                              "climate zone, size, age (each a separate breakdown)"},
    "cbecs2018_e6": {"table": "E6", "url": "https://www.eia.gov/consumption/commercial/data/2018/ce/pdf/e6.pdf",
                     "title": "CBECS 2018 Table E6. Electricity consumption intensities (kWh/sq ft) by end use",
                     "about": "kWh per square foot by end use, each column conditional on the end use's presence, "
                              "so columns do not add up to the total"},
}

# Source end-use column → emissions_3d category.
CATEGORY = {"space heating": "heating", "cooling": "cooling", "ventilation": "ventilation",
            "water heating": "water_heating", "lighting": "lighting", "cooking": "cooking",
            "refrigeration": "refrigeration", "office equipment": "office_equipment",
            "computing": "computing", "other": "other"}


class Pick(BaseModel):
    source_id: Literal["cbecs2018_e5", "cbecs2018_e6"]
    row_label: str  # e.g. "Office"
    region_crossed_with_activity: bool  # does the table give office x South directly?


class Value(BaseModel):
    column: str  # header as in the text, e.g. "Lighting"
    value_text: str  # as written in the row, e.g. "38"


class Extraction(BaseModel):
    table_title_quote: str
    unit_quote: str
    header_quote: str  # all column headers in order, as one line, e.g. "Total Space heating Cooling ..."
    section_quote: str  # the heading the row sits under, e.g. "Principal building activity"
    row_quote: str  # the full row line, e.g. "Office 227 13 ..."
    total_text: str  # the row's Total value as written
    values: list[Value]  # one per end-use column (not Total)


def _emit(kind: str, msg: str, run_id: str | None) -> None:
    if run_id:
        emit(run_id, AGENT, kind, msg)


# --------------------------------------------------------------------------- fetch (code)

def normalize(raw: str) -> str:
    """Deterministic text Gemini reads and code verifies against: words split by a line-break hyphen
    are rejoined ("Venti-\\nlation" → "Ventilation"); other line breaks are kept."""
    return re.sub(r"(\w)-\n(\w)", r"\1\2", raw)


async def fetch_text(url: str) -> str:
    async def download() -> bytes:
        async with httpx.AsyncClient(timeout=60, follow_redirects=True,
                                     headers={"User-Agent": "Mozilla/5.0 (research client)"}) as c:
            r = await c.get(url)
            r.raise_for_status()
            if not r.content.startswith(b"%PDF"):
                raise ValueError("not a PDF")
            return r.content

    path = await cached_bytes("research.pdf", {"url": url}, download, ext=".pdf")

    async def extract() -> dict:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(Path(path).read_bytes()))
        return {"url": url, "pages": len(reader.pages),
                "text": "\n".join(p.extract_text() or "" for p in reader.pages)}

    return (await cached("research.text", {"url": url}, extract))["text"]


# --------------------------------------------------------------------------- verify (code)

def _num(s: str) -> float | None:
    s = s.strip()
    return float(s.replace(",", "")) if re.fullmatch(r"\d{1,3}(,\d{3})*(\.\d+)?|\d+(\.\d+)?", s) else None


def verify(text: str, ex: Extraction) -> dict:
    """Every quote verbatim in the text and every value at its column in the quoted row.
    Returns {checks: [...], values: {column: number | "unknown"}, total, ok}."""
    lines = text.splitlines()
    flat = " ".join(text.split())
    checks, ok = [], True

    def check(name: str, passed: bool, detail: str = "") -> None:
        nonlocal ok
        checks.append({"check": name, "passed": passed, **({"detail": detail} if detail else {})})
        ok = ok and passed

    check("table title quoted verbatim", ex.table_title_quote.strip() in text, ex.table_title_quote)
    check("title measures electricity consumption (not intensity)",
          "Electricity consumption" in ex.table_title_quote and "intensit" not in ex.table_title_quote.lower())
    check("unit quoted verbatim", ex.unit_quote.strip() in text, ex.unit_quote)
    check("column headers quoted verbatim, in order", " ".join(ex.header_quote.split()) in flat, ex.header_quote)
    row = ex.row_quote.strip()
    row_idx = next((i for i, l in enumerate(lines) if l.strip() == row), None)
    check("row quoted verbatim as a full line", row_idx is not None, row)
    sec_idx = next((i for i, l in enumerate(lines) if l.strip() == ex.section_quote.strip()), None)
    check("row sits under the quoted section", sec_idx is not None and row_idx is not None and sec_idx < row_idx,
          ex.section_quote)

    headers = ex.header_quote.split()
    columns = [v.column for v in ex.values]
    joined = " ".join(["Total", *columns])
    check("end-use columns match the quoted headers", " ".join(headers) == joined, joined)

    m = re.match(r"^(.*?)\s((?:[\d,.]+|\(\*\)|Q|N)(?:\s(?:[\d,.]+|\(\*\)|Q|N))*)$", row)
    tokens = m.group(2).split() if m else []
    check("row has one value per column", len(tokens) == len(columns) + 1, f"{len(tokens)} values")
    total = _num(ex.total_text) if tokens and tokens[0] == ex.total_text.strip() else None
    check("total equals the row's first value", total is not None, ex.total_text)

    values: dict[str, float | str] = {}
    for i, v in enumerate(ex.values, start=1):
        good = i < len(tokens) and tokens[i] == v.value_text.strip() and _num(v.value_text) is not None
        values[v.column] = _num(v.value_text) if good else UNKNOWN
        check(f"{v.column} = {v.value_text} at its column in the row", good)
    if total is not None and all(isinstance(x, float) for x in values.values()):
        s = sum(values.values())
        check("end uses add up to the total (rounding allowed)", abs(s - total) <= 0.5 * len(values),
              f"sum {s:g} vs total {total:g}")
    return {"checks": checks, "values": values, "total": total, "ok": ok, "row_label": m.group(1) if m else None}


# --------------------------------------------------------------------------- the agent

def pick_prompt() -> str:
    cat = "\n".join(f"- `{k}`: {v['title']} ({v['url']}): {v['about']}" for k, v in CATALOG.items())
    return (
        "You choose the official source for an electricity end-use split of Houston office buildings "
        "(how a typical office's electricity divides into lighting, cooling, ventilation, ...). The split must be "
        "a share of electricity consumption, so it can multiply an electricity-based CO2 baseline. Prefer EIA "
        "CBECS 2018 electricity consumption by end use for office buildings, the South census region only if the "
        "table cross-tabulates region with building activity.\n\nSources:\n" + cat +
        "\n\nAnswer: `source_id`, the `row_label` to read, and `region_crossed_with_activity` (true only if the "
        "table has a row for offices in the South region).")


def extract_prompt(text: str, pick: Pick) -> str:
    return (
        "Below is the text of an official statistical table, extracted from its PDF. Copy EXACT quotes from it; "
        "do not reformat, round or compute anything.\n"
        f"Find the row labelled `{pick.row_label}` and return:\n"
        "- table_title_quote: the table's title line\n- unit_quote: the line that states the unit\n"
        "- header_quote: every column header in order on one line, starting with Total (join words the text "
        "splits across lines with a space)\n- section_quote: the heading line the row sits under\n"
        "- row_quote: the row's full line\n- total_text: the row's Total value as written\n"
        "- values: for each column after Total, the header and the value as written in the row\n\n"
        "TEXT:\n" + text)


async def research(run_id: str | None = RUN_ID, out: Path = OUT) -> dict:
    """Run pick → fetch → extract → verify → save. Raises if the source can't be read or verified."""
    pick = await llm.text_json(pick_prompt(), Pick)
    src = CATALOG[pick.source_id]
    _emit("plan", f"picked EIA CBECS 2018 Table {src['table']}: row \"{pick.row_label}\"", run_id)

    text = normalize(await fetch_text(src["url"]))
    _emit("fetch", f"fetched Table {src['table']} PDF text ({len(text):,} characters)", run_id)

    ex = await llm.text_json(extract_prompt(text, pick), Extraction, fast=False)
    _emit("observe", f"extracted {len(ex.values)} end uses from row \"{ex.row_quote.split()[0]}\"", run_id)

    v = verify(text, ex)
    passed = sum(c["passed"] for c in v["checks"])
    _emit("verify", f"verified {passed} of {len(v['checks'])} checks verbatim against the fetched text", run_id)
    if not v["ok"] or v["total"] is None:
        failed = [c["check"] for c in v["checks"] if not c["passed"]]
        _emit("error", f"source not verified ({len(failed)} checks failed); nothing saved", run_id)
        raise ValueError(f"end-use source failed verification: {failed}")

    unmapped = [c for c in v["values"] if c.lower() not in CATEGORY]
    if unmapped:
        raise ValueError(f"end-use columns with no emissions_3d category: {unmapped}")
    region = ("South census region offices" if pick.region_crossed_with_activity
              else "all U.S. office buildings (Table E5 has no office x census-region cross-tabulation, so the "
                   "South region is not broken out for offices)")
    total, row_label = v["total"], v["row_label"]
    split = {
        "citation": f"U.S. EIA, 2018 Commercial Buildings Energy Consumption Survey (CBECS), Table {src['table']}",
        "url": src["url"], "table": src["table"], "table_title": ex.table_title_quote, "unit": ex.unit_quote,
        "section": ex.section_quote, "row": row_label, "row_quote": ex.row_quote,
        "scope": region, "measures": "electricity", "basis": "share of the row's total electricity consumption",
        "verification": {"status": "verified", "method": "every quote and value found verbatim in the fetched "
                                                          "PDF text; shares computed in code as value / row total",
                         "checks": v["checks"]},
        "end_uses": [{"name": col, "category": CATEGORY[col.lower()], "column": col, "value_text": val_text,
                      "total_text": ex.total_text, "share": v["values"][col] / total, "quote": ex.row_quote,
                      "verified": True}
                     for col, val_text in ((x.column, x.value_text) for x in ex.values)],
    }
    write_json_atomic(out, split)
    top = sorted(split["end_uses"], key=lambda e: -e["share"])[:3]
    _emit("decide", "saved shares: " + ", ".join(f"{e['name'].lower()} {e['share']:.0%}" for e in top)
          + f" ({'South offices' if pick.region_crossed_with_activity else 'all U.S. offices'})", run_id)
    return split
