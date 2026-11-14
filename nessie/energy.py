"""Read Nessie sandbox bills or CoStar-derived modeled building costs.

Sandbox bills are NOT proof of actual utility consumption.
"""
import json
try:
    from .bills import estimate_energy_costs
    from .get_bills import get_bills
except ImportError:
    from bills import estimate_energy_costs
    from get_bills import get_bills


def get_annual_spend(building_id, source='nessie', **estimate_assumptions):
    """source='nessie' reads sandbox bills; source='estimate' uses building profile.

    The Nessie result is an observed sum of matching sandbox bill records, not
    necessarily a full 12 months of paid bills. It is not annualized.
    """
    if source == 'estimate':
        return estimate_energy_costs(building_id, **estimate_assumptions)
    if source != 'nessie':
        raise ValueError("source must be 'nessie' or 'estimate'")
    bills = get_bills()
    electricity = gas = 0.0
    count = 0
    for bill in bills:
        nickname = str(bill.get('nickname', ''))
        if not nickname.startswith(str(building_id) + '_'):
            continue
        amount = bill.get('payment_amount')
        if not isinstance(amount, (int, float)) or amount < 0:
            continue
        if nickname.startswith(str(building_id) + '_electricity_'):
            electricity += amount
        elif nickname.startswith(str(building_id) + '_gas_'):
            gas += amount
        else:
            continue
        count += 1
    if not count:
        return None
    return {
        'building_id': str(building_id),
        'observed_sandbox_bill_total_usd': round(electricity + gas, 2),
        'electricity_spend_usd': round(electricity, 2),
        'gas_spend_usd': round(gas, 2), 'bill_count': count,
        'source': 'nessie_sandbox_bills', 'annualized': False,
        'measurement_status': 'sandbox_not_verified_utility_invoices'
    }


if __name__ == '__main__':
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('building_id')
    p.add_argument('--source', choices=['nessie', 'estimate'], default='nessie')
    p.add_argument('--kwh-per-sqft', type=float)
    p.add_argument('--electric-rate', type=float)
    p.add_argument('--therms-per-sqft', type=float)
    p.add_argument('--gas-rate', type=float)
    args = p.parse_args()
    options = {}
    if args.source == 'estimate':
        options = {
            'annual_kwh_per_sqft': args.kwh_per_sqft,
            'electricity_usd_per_kwh': args.electric_rate,
            'annual_therms_per_sqft': args.therms_per_sqft,
            'gas_usd_per_therm': args.gas_rate,
        }
    print(json.dumps(get_annual_spend(args.building_id, source=args.source, **options), indent=2))
