
"""Research Houston retrofit simulation assumptions with cited sources.

Run:
python -m backend.app.agents.simulation_assumptions
"""

import argparse
import json
import os
import re

from datetime import datetime, timezone
from pathlib import Path

from deepagents import create_deep_agent
from dotenv import load_dotenv
from google import genai
from google.genai import types
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from tavily import TavilyClient


load_dotenv()

ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = ROOT / "backend" / "data" / "simulation_assumptions"


# All requested simulation assumptions
ITEMS = [
    ("1", "Houston commercial electricity price", "$/kWh"),
    ("2", "Houston commercial solar buyback/export price", "$/kWh"),
    ("3", "ERCOT eGRID CO2 emissions factor", "kg CO2/kWh"),
    ("4", "Houston PVWatts solar annual production", "kWh/kW/year"),
    ("5a", "Office energy use intensity", "kWh/ft2/year"),
    ("5b", "Retail energy use intensity", "kWh/ft2/year"),
    ("5c", "Industrial energy use intensity", "kWh/ft2/year"),
    ("5d", "Multi-family energy use intensity", "kWh/ft2/year")
]

UPGRADES = [
    "rooftop solar",
    "cool roof",
    "windows",
    "insulation",
    "heat pump",
    "LED"
]

for upgrade in UPGRADES:
    unit = "$/kW" if upgrade == "rooftop solar" else "$/ft2"

    ITEMS.append((
        f"6 {upgrade}",
        f"{upgrade.title()} installed cost",
        unit
    ))

for upgrade in ["cool roof", "windows", "heat pump"]:
    ITEMS.append((
        f"7 {upgrade}",
        f"{upgrade.title()} like-for-like replacement cost",
        "$/ft2"
    ))

for upgrade in UPGRADES:
    if upgrade == "rooftop solar":
        unit = "kWh/kW/year (production)"
    elif upgrade in ["cool roof", "insulation"]:
        unit = "kWh/ft2 roof-or-wall/year"
    else:
        unit = "fraction of whole-building energy"

    ITEMS.append((
        f"8 {upgrade}",
        f"{upgrade.title()} annual energy effect",
        unit
    ))

for upgrade in UPGRADES:
    ITEMS.append((
        f"9 {upgrade}",
        f"{upgrade.title()} lifespan",
        "years"
    ))

for upgrade in UPGRADES:
    ITEMS.append((
        f"10 {upgrade}",
        f"{upgrade.title()} annual maintenance",
        "% of installed cost/year or none"
    ))

for upgrade in UPGRADES:
    ITEMS.append((
        f"11 {upgrade}",
        f"{upgrade.title()} incentive and probability",
        "% or $; probability 0-1"
    ))

ITEMS += [
    ("12", "Annual electricity price growth", "%/year"),
    ("13", "Commercial real-estate discount rate", "%/year"),
    ("14", "General inflation", "%/year"),
    (
        "15",
        "Carbon fee probability, start year, price",
        "probability 0-1; year; $/tonne CO2"
    ),
    (
        "16",
        "Probability solar project starting now qualifies before deadline",
        "probability 0-1"
    )
]

PRIORITY = {
    "1", "3", "4",
    "5a", "5b", "5c", "5d",
    "6 LED", "6 heat pump",
    "8 LED", "8 heat pump",
    "16"
}


def find_assumptions():
    paths = [
        ROOT / "ASSUMPTIONS.md",
        ROOT / "backend" / "ASSUMPTIONS.md",
        ROOT / "docs" / "ASSUMPTIONS.md"
    ]

    for path in paths:
        if path.is_file():
            text = path.read_text(encoding="utf-8")
            return str(path.relative_to(ROOT)), text[:30000]

    return None, None


def extract_text(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for part in content:
            if isinstance(part, str):
                parts.append(part)

            elif isinstance(part, dict):
                if part.get("type") == "text":
                    parts.append(part.get("text", ""))

        return "\n".join(parts)

    return str(content)


def parse_json(content):
    raw = extract_text(content).strip()

    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1]
        raw = raw.rsplit("```", 1)[0].strip()

    try:
        return json.loads(raw), None

    except json.JSONDecodeError:
        decoder = json.JSONDecoder()

        for match in re.finditer(r"\{", raw):
            try:
                result, _ = decoder.raw_decode(raw[match.start():])

                if isinstance(result, dict):
                    return result, None

            except json.JSONDecodeError:
                continue

        return {}, raw


def research():
    tavily = TavilyClient(
        api_key=os.environ["TAVILY_API_KEY"]
    )

    assumptions_path, assumptions_text = find_assumptions()

    if assumptions_path:
        print("Found assumptions:", assumptions_path, flush=True)
    else:
        print("ASSUMPTIONS.md not found.", flush=True)

    # Tavily research tool
    @tool
    def search_public_sources(query: str) -> str:
        """Search public sources for energy, costs, incentives, and retrofit data."""

        try:
            results = tavily.search(
                query=query,
                search_depth="advanced",
                max_results=5
            )

            sources = []

            for item in results.get("results", []):
                sources.append({
                    "title": item.get("title"),
                    "url": item.get("url"),
                    "content": item.get("content")
                })

            return json.dumps(sources)

        except Exception as error:
            return json.dumps({
                "error": str(error)
            })

    # Working Vertex AI v1 client
    client = genai.Client(
        vertexai=True,
        api_key=os.environ["VERTEX_API_KEY"],
        http_options=types.HttpOptions(
            api_version="v1"
        )
    )

    model = ChatGoogleGenerativeAI(
        model="gemini-3.5-flash-lite",
        vertexai=True,
        google_api_key=os.environ["VERTEX_API_KEY"]
    )

    # Replace LangChain's default client with the tested client
    model.client = client

    print("Vertex AI API version: v1", flush=True)

    agent = create_deep_agent(
        model=model,
        tools=[search_public_sources],
        system_prompt=(
            "You are HawkLens, a research agent for commercial "
            "building retrofit simulation assumptions.\n\n"

            "Research Houston, Texas using reliable sources.\n"

            "Prioritize official sources:\n"
            "- US Energy Information Administration (EIA)\n"
            "- EPA eGRID\n"
            "- NREL PVWatts\n"
            "- ENERGY STAR\n"
            "- US Department of Energy\n"
            "- IRS\n"
            "- Official utility and government websites\n\n"

            "RESEARCH RULES:\n"

            "1. Search for actual published numbers.\n"
            "2. Never invent numerical values or source URLs.\n"
            "3. Distinguish published facts from analyst estimates.\n"
            "4. For requested ranges, give typical, low, and high.\n"
            "5. Use null for values that cannot be established.\n"
            "6. Clearly flag placeholders and missing values.\n"
            "7. Include source URLs supporting each row.\n"
            "8. Do not claim that a source supports a number "
            "unless the source actually provides it.\n"
            "9. Clearly explain when a number is a regional proxy.\n"
            "10. Do not claim that incentives are guaranteed.\n"
            "11. Treat probabilities as analyst judgments unless "
            "supported by a statistical source.\n"
            "12. Do not confuse energy savings with electricity "
            "generation from solar.\n"
            "13. Do not confuse site electricity with total "
            "building energy use.\n"
            "14. Use the definitions from ASSUMPTIONS.md when "
            "that file is available.\n\n"

            "Return ONLY valid JSON with a top-level 'rows' array.\n"

            "Each row must contain:\n"
            "id, typical, low, high, source_url, notes, "
            "status, evidence_type.\n\n"

            "Allowed status values:\n"
            "sourced, estimated, placeholder, missing.\n\n"

            "Allowed evidence_type values:\n"
            "published_data, derived_calculation, "
            "analyst_assumption, unknown.\n\n"

            "Example JSON structure:\n"
            "{"
            "\"rows\": ["
            "{"
            "\"id\": \"1\","
            "\"typical\": null,"
            "\"low\": null,"
            "\"high\": null,"
            "\"source_url\": null,"
            "\"notes\": \"Explanation\","
            "\"status\": \"missing\","
            "\"evidence_type\": \"unknown\""
            "}"
            "]"
            "}\n\n"

            "Return every requested row. "
            "Do not use markdown code fences."
        )
    )

    catalog = "\n".join(
        f"{item_id} | {name} | {unit}"
        for item_id, name, unit in ITEMS
    )

    prompt = (
        "Create a Houston, Texas commercial-building retrofit "
        "simulation assumption table as of November 14, 2026.\n\n"

        "Research these exact rows:\n"
        + catalog +

        "\n\nPrioritize rows 1, 3, 4, 5a-d, "
        "6 LED, 6 heat pump, 8 LED, 8 heat pump, and 16.\n\n"

        "For item 1, use an EIA Texas commercial all-in "
        "electricity average as a Houston proxy, labeled as such.\n"

        "For item 2, find an actual Houston-area retail solar "
        "buyback plan. Distinguish residential eligibility "
        "from commercial eligibility.\n"

        "For item 3, use EPA eGRID ERCT CO2 OUTPUT factor. "
        "Convert lb/MWh to kg/kWh by multiplying by "
        "0.00045359237. Do not confuse CO2 with CO2e.\n"

        "For item 4, provide an actual NREL PVWatts Houston "
        "result if available. Include system size, tilt, "
        "azimuth, losses, and DC/AC ratio. "
        "Otherwise mark the result missing.\n"

        "For item 5, distinguish site electricity kWh from "
        "total site energy expressed as kWh-equivalent. "
        "Explain category differences for multifamily "
        "and industrial properties.\n"

        "For item 6, find installed upgrade costs in "
        "the units specified for each upgrade.\n"

        "For item 7, give the cost of a normal like-for-like "
        "replacement per square foot of the replaced component.\n"

        "For item 8, use the exact energy savings definitions "
        "specified for each upgrade. Provide typical, low, high.\n"

        "For items 9-11, research lifespan, maintenance, "
        "incentive amounts, and eligibility probability.\n"

        "For items 12-15, distinguish historical data from "
        "simulation scenario assumptions.\n"

        "For item 16, explain the difference between projects "
        "that began construction before July 5, 2026, "
        "and projects beginning now. "
        "Give a probability only as a clearly labeled "
        "analyst judgment when justified.\n\n"

        "If reliable data is unavailable, use null and "
        "mark the row missing. Do not invent numbers.\n"
    )

    if assumptions_text is None:
        prompt += (
            "\nASSUMPTIONS.md was not found. "
            "Flag this in notes. Do not claim to have "
            "checked its definitions.\n"
        )

    else:
        prompt += (
            f"\nASSUMPTIONS.md at {assumptions_path}:\n"
            f"{assumptions_text}\n"
        )

    print(
        "Researching Houston simulation assumptions...",
        flush=True
    )

    response = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        },
        config={
            "recursion_limit": 90
        }
    )

    parsed, raw = parse_json(
        response["messages"][-1].content
    )

    incoming = parsed.get("rows", [])

    if not isinstance(incoming, list):
        incoming = []

    valid_ids = {item[0] for item in ITEMS}
    by_id = {}

    for row in incoming:
        if not isinstance(row, dict):
            continue

        item_id = str(row.get("id", ""))

        if item_id in valid_ids:
            by_id[item_id] = row

    # Preserve every requested row, even if research is missing
    rows = []

    for item_id, item_name, unit in ITEMS:
        found = by_id.get(item_id, {})

        row = {
            "id": item_id,
            "item": item_name,
            "typical": found.get("typical"),
            "low": found.get("low"),
            "high": found.get("high"),
            "unit": unit,
            "source_url": found.get("source_url"),
            "notes": found.get("notes") or "",
            "status": found.get("status", "missing"),
            "evidence_type": found.get(
                "evidence_type",
                "unknown"
            ),
            "priority": item_id in PRIORITY
        }

        # Reject missing or malformed source URLs
        source = row["source_url"]

        if (
            not isinstance(source, str)
            or not source.startswith(("https://", "http://"))
        ):
            row["source_url"] = None

            if row["status"] == "sourced":
                row["status"] = "estimated"
                row["notes"] += (
                    " No source URL supplied."
                )

        # Mark empty results as missing
        if (
            row["typical"] is None
            and row["low"] is None
            and row["high"] is None
        ):
            if row["status"] != "placeholder":
                row["status"] = "missing"

        rows.append(row)

    # Save structured JSON
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True
    )

    result = {
        "location": "Houston, Texas, USA",
        "researched_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "assumptions_file": assumptions_path,
        "rows": rows,
        "warning": (
            "AI-researched values are not independently audited. "
            "Verify official figures and project eligibility "
            "before using them for financial decisions."
        )
    }

    if raw:
        result["raw_response"] = raw
        result["warning"] += (
            " Model output was not valid JSON."
        )

    json_path = OUTPUT_DIR / "houston.json"

    json_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    # Format the Markdown table
    def fmt(value):
        if value is None:
            return "—"

        return str(value).replace("|", "\\|")

    def format_value(row):
        typical = row["typical"]
        low = row["low"]
        high = row["high"]

        if typical is None and low is None and high is None:
            return "Not established"

        if low is not None or high is not None:
            return (
                f"Typical {fmt(typical)}; "
                f"low {fmt(low)}; "
                f"high {fmt(high)}"
            )

        return fmt(typical)

    lines = [
        "# Houston Simulation Assumptions",
        "",
        "| Item | Value or low–high | Unit | Source link | Notes |",
        "|---|---|---|---|---|"
    ]

    for row in rows:
        source = row["source_url"] or "No verified link"

        notes = (
            f"[{row['status']}; {row['evidence_type']}] "
            f"{row['notes']}"
        )

        notes = (
            notes.replace("|", "\\|")
            .replace("\n", " ")
        )

        lines.append(
            f"| {row['id']} {row['item']} "
            f"| {format_value(row)} "
            f"| {row['unit']} "
            f"| {source} "
            f"| {notes} |"
        )

    missing_rows = [
        row["id"]
        for row in rows
        if row["status"] in (
            "missing",
            "placeholder"
        )
    ]

    lines += [
        "",
        "**Missing or placeholder rows:** "
        + (", ".join(missing_rows) or "None"),
        "",
        "**Note:** AI-generated research. "
        "Verify figures and eligibility before financial use."
    ]

    md_path = OUTPUT_DIR / "houston.md"

    md_path.write_text(
        "\n".join(lines) + "\n",
        encoding="utf-8"
    )

    print(
        "Saved JSON:", json_path,
        flush=True
    )

    print(
        "Saved table:", md_path,
        flush=True
    )

    print(
        "Missing/placeholder:",
        len(missing_rows),
        "of",
        len(rows),
        flush=True
    )

    return json_path, md_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.parse_args()

    research()
