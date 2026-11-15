from app.config import get_settings

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PORTFOLIO = get_settings().data_dir / "portfolio.json"


def get_building_context(building_id):
    with open(PORTFOLIO, encoding="utf-8") as file:
        data = json.load(file)

    for building in data["buildings"]:
        if str(building["building_id"]) == str(building_id):
            return {
                "building_id": building["building_id"],
                "name": building["name"],
                "address": building["address"],
                "latitude": building["lat"],
                "longitude": building["lon"],
                "property_type": building["property_type"],
                "square_feet": building["rba_sqft"],
                "stories": building["stories"],
                "year_built": building["year_built"],
                "matterport_model_id": building.get(
                    "matterport_model_id"
                ),
                "vexcel_coverage": building.get(
                    "coverage", {}
                ).get("vexcel"),
            }

    raise ValueError("Building not found")
