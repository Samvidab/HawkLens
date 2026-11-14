
import json
import os

LEDGER_FILE = os.path.join(os.path.dirname(__file__), "funding_ledger.json")


def get_funding_summary():
    if not os.path.exists(LEDGER_FILE):
        return {
            "total_allocated": 0,
            "allocation_count": 0,
            "transactions": []
        }

    with open(LEDGER_FILE, "r") as file:
        records = json.load(file)

    total = 0

    for record in records:
        if record["status"] == "allocated":
            total += record["amount"]

    return {
        "total_allocated": total,
        "allocation_count": len(records),
        "transactions": records
    }


if __name__ == "__main__":
    print(json.dumps(get_funding_summary(), indent=4))
