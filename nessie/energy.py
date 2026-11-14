
import json
from get_bills import get_bills

def get_annual_spend(building_id):
    bills = get_bills()

    electricity = 0
    gas = 0
    count = 0

    for bill in bills:
        nickname = bill["nickname"]

        if nickname.startswith(building_id + "_"):
            if "_electricity_" in nickname:
                electricity += bill["payment_amount"]
                count += 1

            elif "_gas_" in nickname:
                gas += bill["payment_amount"]
                count += 1

    if count == 0:
        return None

    return {
        "building_id": building_id,
        "annual_spend": round(electricity + gas, 2),
        "electricity_spend": round(electricity, 2),
        "gas_spend": round(gas, 2),
        "bill_count": count,
        "source": "nessie_api_synthetic_bills"
    }


if __name__ == "__main__":
    result = get_annual_spend("sample_001")
    print(json.dumps(result, indent=4))
