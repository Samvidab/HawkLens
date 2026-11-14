

import json
import random

random.seed(42)

# Temporary sample building
# Replace this when CoStar building data is ready
buildings = [
    {
        "id": "sample_001",
        "name": "Sample Houston Office",
        "square_feet": 50000,
        "type": "Office"
    }
]

def generate_bills(building):
    bills = []

    # Temporary demo estimates, not researched benchmarks
    electric_rate = 0.25
    gas_rate = 0.05

    for month in range(1, 13):
        # Seasonal variation
        seasonal = 1.2 if month in [6, 7, 8, 9] else 1.0

        electric = building["square_feet"] * electric_rate
        electric = electric * seasonal
        electric = electric * random.uniform(0.95, 1.05)

        gas = building["square_feet"] * gas_rate
        gas = gas * random.uniform(0.95, 1.05)

        bills.append({
            "building_id": building["id"],
            "month": month,
            "utility": "electricity",
            "amount": round(electric, 2)
        })

        bills.append({
            "building_id": building["id"],
            "month": month,
            "utility": "gas",
            "amount": round(gas, 2)
        })

    return bills


all_bills = []

for building in buildings:
    all_bills.extend(generate_bills(building))

with open("nessie/sample_bills.json", "w") as file:
    json.dump(all_bills, file, indent=4)

print("Generated", len(all_bills), "sample bills")
print("Saved to nessie/sample_bills.json")
