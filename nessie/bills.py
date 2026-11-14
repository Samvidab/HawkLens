"""Building-aware energy estimates from HawkLens CoStar profiles.

Vexcel and Matterport evidence is consumed through the backend's building
pipeline; neither service provides utility invoices. All costs here are MODELED.
No API writes or fabricated 'actual' bills.
"""
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_building_profile(building_id, data_dir=None):
    """Read the CoStar-derived profile written by backend/app/agents/records.py."""
    base = Path(data_dir or os.getenv('HAWKLENS_DATA_DIR', str(ROOT / 'backend' / 'data')))
    path = base / 'buildings' / str(building_id) / 'profile.json'
    if not path.is_file():
        raise FileNotFoundError(f'Building profile not found: {path}. Run the records agent first.')
    with path.open(encoding='utf-8') as f:
        profile = json.load(f)
    if str(profile.get('building_id')) != str(building_id):
        raise ValueError('Building ID mismatch in profile')
    return profile


def estimate_energy_costs(building_id, annual_kwh_per_sqft=None,
                          electricity_usd_per_kwh=None, annual_therms_per_sqft=None,
                          gas_usd_per_therm=None, data_dir=None):
    """Return transparent estimates; requires explicitly supplied assumptions.

    Use researched benchmarks or a calibrated model to supply rates and EUI.
    No invented consumption or prices are silently substituted.
    """
    profile = load_building_profile(building_id, data_dir)
    sqft = profile.get('rba_sqft')
    if not isinstance(sqft, (int, float)) or sqft <= 0:
        raise ValueError('CoStar profile has no usable rba_sqft')
    values = [annual_kwh_per_sqft, electricity_usd_per_kwh,
              annual_therms_per_sqft, gas_usd_per_therm]
    if any(x is None or not isinstance(x, (int, float)) or x < 0 for x in values):
        raise ValueError('Supply nonnegative annual kWh/sqft, $/kWh, therms/sqft, and $/therm')
    kwh = sqft * annual_kwh_per_sqft
    therms = sqft * annual_therms_per_sqft
    electricity = kwh * electricity_usd_per_kwh
    gas = therms * gas_usd_per_therm
    return {
        'building_id': str(building_id), 'building_name': profile.get('name'),
        'property_type': profile.get('property_type'), 'rba_sqft': sqft,
        'annual_electricity_kwh_estimate': round(kwh, 2),
        'annual_gas_therms_estimate': round(therms, 2),
        'electricity_spend_estimate_usd': round(electricity, 2),
        'gas_spend_estimate_usd': round(gas, 2),
        'annual_spend_estimate_usd': round(electricity + gas, 2),
        'assumptions': {
            'annual_kwh_per_sqft': annual_kwh_per_sqft,
            'electricity_usd_per_kwh': electricity_usd_per_kwh,
            'annual_therms_per_sqft': annual_therms_per_sqft,
            'gas_usd_per_therm': gas_usd_per_therm,
        },
        'source': 'modeled_from_costar_building_profile',
        'measurement_status': 'estimate_not_actual_utility_bill',
        'building_profile_source_fields': profile.get('source_fields', {}),
        'matterport_model_id': profile.get('matterport_model_id'),
        'note': 'Vexcel/Matterport do not supply utility consumption; their analyses can inform model assumptions.'
    }
