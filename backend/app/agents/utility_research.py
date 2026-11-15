from app.config import get_settings

"""Research public utility tariffs and energy data for a building."""

import argparse
import json
import os
import requests

from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types
from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.tools import tool
from tavily import TavilyClient


load_dotenv()

ROOT = Path(__file__).resolve().parents[3]


def load_property(building_id):
    path = get_settings().data_dir / "portfolio.json"

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    for building in data["buildings"]:
        if str(building["building_id"]) == str(building_id):
            return building

    raise ValueError("Building not found: " + str(building_id))


def empty_tariff():
    return {
        "name": None,
        "rate_type": None,
        "energy_rate_per_kwh": None,
        "demand_rate_per_kw": None,
        "monthly_fixed_charge": None,
        "rate_per_therm": None,
        "effective_date": None,
        "eligibility": None,
        "source_url": None,
        "verification_status": "unverified"
    }


def normalize_tariffs(tariffs):
    if not isinstance(tariffs, list):
        return []

    normalized = []

    for tariff in tariffs:
        if not isinstance(tariff, dict):
            continue

        item = empty_tariff()

        for key in item:
            if key in tariff:
                item[key] = tariff[key]

        # Never allow a tariff to be called verified without a source.
        if not item["source_url"]:
            item["verification_status"] = "unverified"

        normalized.append(item)

    return normalized


def normalize_research(data):
    if not isinstance(data, dict):
        data = {}

    electricity = data.get("electricity")
    if not isinstance(electricity, dict):
        electricity = {}

    natural_gas = data.get("natural_gas")
    if not isinstance(natural_gas, dict):
        natural_gas = {}

    consumption = data.get("building_consumption")
    if not isinstance(consumption, dict):
        consumption = {}

    sources = data.get("sources")
    if not isinstance(sources, list):
        sources = []

    return {
        "electricity": {
            "delivery_provider": electricity.get("delivery_provider"),
            "retail_provider": electricity.get("retail_provider"),
            "market_type": electricity.get("market_type"),
            "tariffs": normalize_tariffs(
                electricity.get("tariffs", [])
            )
        },
        "natural_gas": {
            "utility_provider": natural_gas.get("utility_provider"),
            "tariffs": normalize_tariffs(
                natural_gas.get("tariffs", [])
            )
        },
        "building_consumption": {
            "measured_annual_energy": consumption.get(
                "measured_annual_energy"
            ),
            "measured_electricity_kwh": consumption.get(
                "measured_electricity_kwh"
            ),
            "measured_natural_gas_therms": consumption.get(
                "measured_natural_gas_therms"
            ),
            "energy_use_intensity_eui": consumption.get(
                "energy_use_intensity_eui"
            ),
            "measurement_period": consumption.get(
                "measurement_period"
            ),
            "source_url": consumption.get("source_url")
        },
        "sources": sources,
        "notes": data.get("notes"),
        "research_status": data.get(
            "research_status",
            "requires_verification"
        )
    }


def extract_text(content):
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        parts = []

        for item in content:
            if isinstance(item, str):
                parts.append(item)

            elif isinstance(item, dict):
                if item.get("type") == "text":
                    parts.append(item.get("text", ""))

        return "\n".join(parts)

    return str(content)


def parse_json_answer(answer):
    clean = extract_text(answer).strip()

    if clean.startswith("```"):
        clean = clean.split("\n", 1)[-1]
        clean = clean.rsplit("```", 1)[0].strip()

    try:
        return json.loads(clean)

    except json.JSONDecodeError:
        return {
            "research_status": "manual_review_required",
            "raw_research": clean
        }


def research(building_id):
    building = load_property(building_id)

    tavily = TavilyClient(
        api_key=os.environ["TAVILY_API_KEY"]
    )

    @tool
    def search_public_sources(query: str) -> str:
        """Search the web for official utility tariffs and energy disclosures."""

        try:
            results = tavily.search(
                query=query,
                search_depth="advanced",
                max_results=6
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

    @tool
    def lookup_electricity_tariffs(address: str) -> str:
        """Find commercial electricity tariff candidates using OpenEI."""

        api_key = os.environ.get("OPENEI_API_KEY")

        if not api_key:
            return json.dumps({
                "error": "OPENEI_API_KEY not configured"
            })

        try:
            response = requests.get(
                "https://api.openei.org/utility_rates",
                params={
                    "version": "latest",
                    "format": "json",
                    "api_key": api_key,
                    "address": address,
                    "sector": "Commercial",
                    "limit": 25,
                    "detail": "full"
                },
                timeout=25
            )

            response.raise_for_status()

            data = response.json()
            candidates = []

            fields = [
                "name",
                "utility",
                "label",
                "uri",
                "startdate",
                "enddate",
                "fixedmonthlycharge",
                "energyratestructure",
                "demandratestructure"
            ]

            for item in data.get("items", []):
                candidate = {}

                for field in fields:
                    candidate[field] = item.get(field)

                candidates.append(candidate)

            return json.dumps({
                "candidates": candidates,
                "warning": (
                    "OpenEI results are tariff candidates. "
                    "Verify current rates, service territory, "
                    "effective dates, and eligibility."
                )
            })

        except Exception as error:
            return json.dumps({
                "error": str(error)
            })

    # Working Google Vertex AI client using API v1
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

    # Use the tested Vertex client instead of LangChain's default.
    model.client = client

    print("Vertex API version: v1", flush=True)

    agent = create_deep_agent(
        model=model,
        tools=[
            search_public_sources,
            lookup_electricity_tariffs
        ],
        system_prompt=(
            "You are HawkLens, a commercial building utility "
            "research agent.\n\n"

            "Your job is to research electricity tariffs, natural gas "
            "tariffs, and publicly available building energy data.\n\n"

            "RESEARCH RULES:\n"
            "1. Search official utility, government, and regulatory "
            "websites first.\n"
            "2. Search for actual tariff schedules and rate sheets, "
            "not just general descriptions.\n"
            "3. Find fixed monthly charges, energy charges, demand "
            "charges, and natural gas volumetric rates when available.\n"
            "4. Include effective dates and source URLs.\n"
            "5. Clearly identify whether each rate is verified, "
            "a candidate, or unverified.\n"
            "6. Never invent numerical rates, utility bills, "
            "energy consumption, or tariff eligibility.\n"
            "7. Do not assume a tariff applies to the building "
            "without enough information about its service class.\n"
            "8. If a tariff has multiple tiers, seasons, or "
            "time-of-use periods, do not present one rate as "
            "the complete tariff.\n"
            "9. If a tariff is too complex to express as one "
            "number, leave the corresponding numerical field null "
            "and explain the structure in eligibility or notes.\n"
            "10. Use null for unknown numerical information.\n"
            "11. Never treat estimated consumption as measured data.\n"
            "12. Do not calculate energy costs or retrofit savings.\n\n"

            "RETURN ONLY VALID JSON IN THIS FORMAT:\n"

            "{"
            "\"electricity\": {"
            "\"delivery_provider\": null,"
            "\"retail_provider\": null,"
            "\"market_type\": null,"
            "\"tariffs\": [{"
            "\"name\": null,"
            "\"rate_type\": null,"
            "\"energy_rate_per_kwh\": null,"
            "\"demand_rate_per_kw\": null,"
            "\"monthly_fixed_charge\": null,"
            "\"rate_per_therm\": null,"
            "\"effective_date\": null,"
            "\"eligibility\": null,"
            "\"source_url\": null,"
            "\"verification_status\": \"unverified\""
            "}]"
            "},"

            "\"natural_gas\": {"
            "\"utility_provider\": null,"
            "\"tariffs\": [{"
            "\"name\": null,"
            "\"rate_type\": null,"
            "\"energy_rate_per_kwh\": null,"
            "\"demand_rate_per_kw\": null,"
            "\"monthly_fixed_charge\": null,"
            "\"rate_per_therm\": null,"
            "\"effective_date\": null,"
            "\"eligibility\": null,"
            "\"source_url\": null,"
            "\"verification_status\": \"unverified\""
            "}]"
            "},"

            "\"building_consumption\": {"
            "\"measured_annual_energy\": null,"
            "\"measured_electricity_kwh\": null,"
            "\"measured_natural_gas_therms\": null,"
            "\"energy_use_intensity_eui\": null,"
            "\"measurement_period\": null,"
            "\"source_url\": null"
            "},"

            "\"sources\": [],"
            "\"notes\": null,"
            "\"research_status\": \"requires_verification\""
            "}\n\n"

            "A verified tariff must be supported by an official "
            "source that explicitly states the relevant charges. "
            "A source URL alone does not prove tariff eligibility. "
            "If no reliable rate is found, leave its value null. "
            "Do not add markdown code fences."
        )
    )

    address = building.get("address", "")
    name = building.get("name", "")
    property_type = building.get("property_type", "")
    square_feet = building.get("rba_sqft", "")

    message = (
        f"Research this commercial building:\n"
        f"Building ID: {building_id}\n"
        f"Building name: {name}\n"
        f"Address: {address}\n"
        f"Property type: {property_type}\n"
        f"Square footage: {square_feet}\n\n"

        "Find the electricity delivery utility, available "
        "retail electricity supplier information, and relevant "
        "commercial electricity tariffs.\n\n"

        "Find the natural gas distribution utility and "
        "relevant commercial natural gas tariffs.\n\n"

        "For each tariff, research:\n"
        "- Exact tariff name or schedule\n"
        "- Rate type\n"
        "- Energy rate in dollars per kWh, if applicable\n"
        "- Demand rate in dollars per kW, if applicable\n"
        "- Fixed monthly charge, if applicable\n"
        "- Natural gas rate in dollars per therm, if applicable\n"
        "- Effective date\n"
        "- Eligibility requirements\n"
        "- Official source URL\n"
        "- Verification status\n\n"

        "Also search for property-specific measured electricity "
        "consumption, natural gas consumption, and energy use "
        "intensity from public disclosure records.\n\n"

        "Use the research tools. Do not invent missing values. "
        "Return only valid JSON."
    )

    print("Researching building:", building_id, flush=True)

    response = agent.invoke({
        "messages": [
            {
                "role": "user",
                "content": message
            }
        ]
    })

    answer = response["messages"][-1].content
    parsed = parse_json_answer(answer)

    research_data = normalize_research(parsed)

    if "raw_research" in parsed:
        research_data["raw_research"] = parsed["raw_research"]
        research_data["research_status"] = "manual_review_required"

    result = {
        "building_id": str(building_id),
        "building_name": name,
        "address": address,
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "measurement_status": "research_only_not_actual_utility_bill",
        "research": research_data
    }

    output_dir = get_settings().data_dir / "utility_research"
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{building_id}.json"

    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(result, file, indent=2)

    print("Research complete!", flush=True)
    print("Saved to:", output_path, flush=True)

    return output_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--building-id",
        default="23551"
    )

    args = parser.parse_args()

    research(args.building_id)
