"""Update HawkLens quant-engine assumptions.json without changing its schema.

Run: python update_hawklens_assumptions.py path/to/assumptions.json
The original is backed up to assumptions.json.bak. All unchanged placeholder
values are reported; no invented tariffs, PVWatts outputs, or incentives.
"""
import argparse
import json
import shutil
from datetime import date
from pathlib import Path

EIA_ELECTRIC = 'https://www.eia.gov/electricity/monthly/epm_table_grapher.php?t=epmt_5_6_a'
EIA_CBECS = 'https://www.eia.gov/consumption/commercial/data/2018/ce/pdf/c22.pdf'
EPA_EGRID = 'https://www.epa.gov/egrid/summary-data'
DOE_SOLAR = 'https://www.energy.gov/cmei/systems/solar-photovoltaic-system-cost-benchmarks'
DOE_LED = 'https://www.energy.gov/cmei/femp/espc-enable-project-us-department-energy-headquarters-reduces-lighting-energy-use-50'
DOE_HVAC = 'https://betterbuildingssolutioncenter.energy.gov/sites/default/files/2024-08/BB%20Commercial%20Building%20Heat%20Pump%20Accelerator%20-%20Slides.pdf'
IRS_SOLAR = 'https://www.irs.gov/irb/2025-36_IRB'


def source_append(block, message):
    existing = block.get('source', '')
    if existing == 'PLACEHOLDER':
        existing = ''
    block['source'] = '; '.join(s for s in (existing, message) if s)


def update(data):
    city = data['cities']['Houston']
    city['electricity_rate_usd_per_kwh'] = 0.0896
    city['grid_kg_co2_per_kwh'] = round(733.862 / 2204.62262185, 6)
    city['kwh_per_sqft_year']['Office'] = 13.6
    source_append(city,
        'EIA Electric Power Monthly Table 5.6.A, Texas commercial, August 2026, 8.96 cents/kWh /100 = $0.0896/kWh, ' + EIA_ELECTRIC)
    source_append(city,
        'EPA eGRID2023, ERCT total output CO2 rate 733.862 lb/MWh / 2204.6226 = kg/kWh, ' + EPA_EGRID)
    source_append(city,
        'EIA 2018 CBECS Table C22, US office electricity-using buildings, 13.6 kWh/sqft/year, ' + EIA_CBECS)
    # Export rate and PVWatts require a verified commercial contract / actual PVWatts run.
    # Do not overwrite these with an invented number.

    solar = data['upgrades']['rooftop_solar']
    solar['unit_cost'] = 1980.0  # DOE commercial PV-only modeled 2025Q1 market price, $/kWdc
    source_append(solar, 'DOE Solar PV System Cost Benchmarks, 2025Q1 commercial PV-only modeled market price $1.98/Wdc x 1000 = $1980/kWdc, ' + DOE_SOLAR)
    source_append(solar, 'IRS Notice 2025-42 / post-2025 federal solar credit timing; eligibility and probability must be verified for the project, ' + IRS_SOLAR)

    led = data['upgrades']['led_retrofit']
    # Approximate whole-building electricity savings = lighting share * fixture savings.
    # 20% lighting share * 50% lighting reduction = 10% total.
    led['savings_mu'] = 0.10
    led['savings_sd'] = 0.03  # modeling uncertainty, not an observed statistical SD
    source_append(led,
        'Scenario assumption: 20% whole-building electricity lighting share x 50% lighting reduction = 10% whole-building; SD 3 percentage points is team modeling uncertainty, not a measured SD. DOE LED lighting retrofit case, ' + DOE_LED)

    heat = data['upgrades']['heat_pump']
    # This model only reduces electricity; gas-to-electric fuel switching needs a different model.
    heat['savings_mu'] = 0.10
    heat['savings_sd'] = 0.05
    source_append(heat,
        'Scenario assumption: 10% whole-building electricity savings with 5 percentage-point SD, based on ~40% space-conditioning share and measure-level HVAC savings; not valid for gas-to-electric fuel switching. DOE Commercial Heat Pump Accelerator, ' + DOE_HVAC)

    # Do NOT automatically claim a federal solar tax credit, commercial export
    # compensation, CenterPoint rebate, or an installation-completion probability.
    # Preserve original entries until specific program and schedule are checked.
    return data


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('json_file', type=Path, help='Path to quant-engine assumptions.json')
    args = parser.parse_args()
    path = args.json_file
    if not path.is_file():
        parser.error(f'File not found: {path}')
    data = json.loads(path.read_text(encoding='utf-8'))
    for section in ('cities', 'upgrades', 'global'):
        if section not in data:
            parser.error(f'Missing required section: {section}')
    shutil.copy2(path, path.with_suffix(path.suffix + '.bak'))
    updated = update(data)
    path.write_text(json.dumps(updated, indent=2) + '\n', encoding='utf-8')
    print('Updated:', path)
    print('Backup:', path.with_suffix(path.suffix + '.bak'))
    print('Updated: electricity rate, ERCOT grid factor, office EUI, solar cost, LED and heat-pump savings')
    print('NOT VERIFIED: PVWatts, commercial solar export tariff, non-office EUIs, remaining costs, incentives, and project timing')
    print('Review original placeholder values before using simulation results in a pitch.')


if __name__ == '__main__':
    main()
