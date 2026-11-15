from app.config import get_settings

import json
from pathlib import Path

from nessie.bills import estimate_energy_costs


ROOT = Path(__file__).resolve().parents[3]


def estimate_building(building_id, kwh_per_sqft,
                      electricity_rate, therms_per_sqft,
                      gas_rate):

    result = estimate_energy_costs(
        building_id,
        annual_kwh_per_sqft=kwh_per_sqft,
        electricity_usd_per_kwh=electricity_rate,
        annual_therms_per_sqft=therms_per_sqft,
        gas_usd_per_therm=gas_rate,
        data_dir=get_settings().data_dir
    )

    result["monthly_average_estimate_usd"] = round(
        result["annual_spend_estimate_usd"] / 12, 2
    )

    output = (
        get_settings().data_dir /
        "energy_estimates" / f"{building_id}.json"
    )

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(result, indent=2),
        encoding="utf-8"
    )

    return result
