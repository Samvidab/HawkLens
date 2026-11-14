
import json
from pathlib import Path
from datetime import datetime, timezone

OUTPUT = Path(__file__).resolve().parents[2] / "data" / "pricing_assumptions.json"

EIA = "https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_a"
EPA = "https://www.epa.gov/egrid/summary-data"
CBECS = "https://www.eia.gov/consumption/commercial/data/2018/ce/pdf/c22.pdf"
PVWATTS = "https://pvwatts.nrel.gov/"
SOLAR_COST = "https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks"
LED_SOURCE = "https://www.energy.gov/cmei/femp/espc-enable-project-us-department-energy-headquarters-reduces-lighting-energy-use-50"
HEAT_SOURCE = "https://betterbuildingssolutioncenter.energy.gov/"
IRS = "https://www.irs.gov/credits-deductions/clean-electricity-investment-credit"


def upgrade(cost, savings, sd, life_min, life_max, maintenance,
            cost_unit, savings_unit, source, notes):
    return {
        "cost_unit": cost_unit,
        "unit_cost": cost,
        "avoided_replacement_cost_per_unit": 0,
        "savings_unit": savings_unit,
        "savings_mu": savings,
        "savings_sd": sd,
        "life_min": life_min,
        "life_max": life_max,
        "incentive_fraction": 0,
        "incentive_p": 0,
        "incentive_lag_years": 0,
        "maint_frac_per_year": maintenance,
        "source": source,
        "research_notes": notes
    }


def build_dataset():
    global_inputs = {
        "n_scenarios": 10000,
        "n_scenarios_optimizer": 1000,
        "seed": 42,
        "discount_rate": 0.07,
        "general_inflation": 0.025,
        "max_savings_share": 0.5,
        "min_p_hit": 0.8,
        "source": "TEAM MODELING ASSUMPTIONS",
        "energy_price_growth": {
            "mu": 0.025,
            "sd": 0.02,
            "source": "PLACEHOLDER: 2.5% nominal growth and 2% standard deviation. Not an EIA forecast."
        },
        "carbon_price": {
            "p_fee_starts": 0,
            "start_year_range": None,
            "price_range_per_tonne": None,
            "source": "BASELINE: no carbon fee modeled. Future policy uncertainty not estimated."
        }
    }

    houston = {
        "electricity_rate_usd_per_kwh": 0.0896,
        "export_rate_usd_per_kwh": 0,
        "grid_kg_co2_per_kwh": 0.332874,
        "solar_kwh_per_kw_year": None,
        "kwh_per_sqft_year": {
            "Office": 13.6,
            "Retail": None,
            "Industrial": None,
            "Multi-Family": None,
            "Other": None
        },
        "source": (
            "EIA Texas commercial electricity, August 2026: " + EIA
            + "; EPA eGRID2023 ERCOT: " + EPA
            + "; EIA CBECS 2018 Office: " + CBECS
            + "; Solar yield requires actual PVWatts run: " + PVWATTS
            + "; Export rate 0 is a conservative modeling default, not a verified tariff."
        )
    }

    upgrades = {
        "rooftop_solar": upgrade(
            1980, 0.85, 0.08, 25, 30, 0.01,
            "usd_per_kw",
            "fraction_of_modeled_generation",
            SOLAR_COST + "; " + PVWATTS + "; " + IRS,
            "Installed cost is a DOE benchmark. Savings factor, uncertainty, life and maintenance are provisional scenarios. PVWatts generation is still required. Tax credit not assumed."
        ),

        "cool_roof": upgrade(
            3.00, 0.40, 0.20, 15, 25, 0.005,
            "usd_per_sqft",
            "kwh_per_sqft_year",
            "https://www.energy.gov/energysaver/cool-roofs",
            "PLACEHOLDER: cost per treated roof sqft and annual electricity savings per roof sqft. Values require Houston commercial-building validation."
        ),

        "window_upgrade": upgrade(
            35.00, 0.04, 0.02, 20, 30, 0.005,
            "usd_per_sqft",
            "fraction_of_building_kwh",
            "https://www.energy.gov/energysaver/energy-efficient-windows",
            "PLACEHOLDER: cost per treated window sqft. Whole-building savings assume a targeted window retrofit; validate against window area and orientation."
        ),

        "insulation": upgrade(
            3.00, 0.30, 0.15, 20, 30, 0.002,
            "usd_per_sqft",
            "kwh_per_sqft_year",
            "https://www.energy.gov/energysaver/insulation",
            "PLACEHOLDER: cost and annual savings per treated wall sqft. Validate against existing insulation and Houston climate."
        ),

        "heat_pump": upgrade(
            20.00, 0.10, 0.05, 15, 20, 0.02,
            "usd_per_sqft",
            "fraction_of_building_kwh",
            HEAT_SOURCE,
            "PLACEHOLDER: installed cost per treated floor sqft and whole-building electricity savings. Replacing gas heat can increase electricity use. Fuel switching is not modeled."
        ),

        "led_retrofit": upgrade(
            1.50, 0.10, 0.03, 10, 15, 0.005,
            "usd_per_sqft",
            "fraction_of_building_kwh",
            LED_SOURCE,
            "PLACEHOLDER: installed cost per treated floor sqft. 10% whole-building electricity savings is a provisional scenario based on lighting savings."
        )
    }

    research = {}

    def add(name, value, unit, source, status, notes=""):
        research[name] = {
            "value": value,
            "unit": unit,
            "source_url": source,
            "status": status,
            "notes": notes
        }

    add(
        "Houston commercial electricity",
        houston["electricity_rate_usd_per_kwh"],
        "USD/kWh", EIA, "published_benchmark",
        "Texas statewide commercial average, not a specific Houston tariff."
    )

    add(
        "ERCOT grid emissions",
        houston["grid_kg_co2_per_kwh"],
        "kg CO2/kWh", EPA, "published_benchmark",
        "Average emissions, not marginal avoided emissions."
    )

    add(
        "Office electricity intensity",
        13.6, "kWh/sqft/year", CBECS,
        "published_benchmark",
        "National office benchmark, not Houston-specific."
    )

    add(
        "Houston solar generation",
        None, "kWh/kW/year", PVWATTS,
        "needs_verification",
        "Run PVWatts v8 for Houston, 1 kW DC, 20-degree tilt, 180-degree azimuth, 14% losses."
    )

    add(
        "Commercial solar export rate",
        0, "USD/kWh", None,
        "conservative_default",
        "Zero until a Houston commercial export agreement is verified."
    )

    add(
        "Energy price growth standard deviation",
        0.02, "fraction/year", None,
        "placeholder",
        "Requires historical Texas commercial electricity price analysis."
    )

    for building_type, value in houston["kwh_per_sqft_year"].items():
        if building_type != "Office":
            add(
                building_type + " electricity intensity",
                value, "kWh/sqft/year", None,
                "needs_verification",
                "Find an appropriate benchmark for this building category."
            )

    for name, values in upgrades.items():
        for key in [
            "unit_cost",
            "savings_mu",
            "savings_sd",
            "life_min",
            "life_max",
            "maint_frac_per_year"
        ]:
            status = "placeholder"

            if name == "rooftop_solar" and key == "unit_cost":
                status = "published_benchmark"

            add(
                name + "." + key,
                values[key],
                values["cost_unit"] if key == "unit_cost" else key,
                values["source"],
                status,
                values["research_notes"]
            )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "scope": "Houston-wide, not building-specific",
        "warning": (
            "Development scenario only. Placeholder values are not "
            "verified market estimates. Do not use for investment decisions."
        ),
        "engine_inputs": {
            "global": global_inputs,
            "building_estimates": {
                "floor_height_m": 4.0,
                "source": "PLACEHOLDER: assumed commercial floor height."
            },
            "cities": {
                "Houston": houston
            },
            "upgrades": upgrades
        },
        "research_table": research,
        "unverified_fields": [
            name for name, entry in research.items()
            if entry["status"] in ("placeholder", "needs_verification")
        ]
    }


def main():
    data = build_dataset()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)

    with open(OUTPUT, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2)

    print("Saved:", OUTPUT)
    print("Unverified fields:", len(data["unverified_fields"]))


if __name__ == "__main__":
    main()
