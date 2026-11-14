
import csv
from datetime import date
from decimal import Decimal
from pathlib import Path


def load_bills(csv_path, building_id):
    bills = []
    seen = set()

    with Path(csv_path).open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)

        required = {
            "building_id", "service_start", "service_end",
            "utility", "amount_usd"
        }

        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("Missing required CSV columns")

        for row in reader:
            if row["building_id"].strip() != str(building_id):
                continue

            utility = row["utility"].strip().lower()
            if utility not in ("electricity", "gas"):
                raise ValueError("Invalid utility")

            start = date.fromisoformat(row["service_start"].strip())
            end = date.fromisoformat(row["service_end"].strip())
            amount = Decimal(row["amount_usd"].strip())

            if end < start or not amount.is_finite() or amount < 0:
                raise ValueError("Invalid bill")

            key = (
                building_id,
                utility,
                start,
                end
            )

            if key in seen:
                raise ValueError("Duplicate bill")

            seen.add(key)

            bills.append({
                "building_id": str(building_id),
                "utility": utility,
                "service_start": start.isoformat(),
                "service_end": end.isoformat(),
                "amount_usd": float(amount),
                "source": "actual_utility_bill"
            })

    return bills


def summarize_bills(csv_path, building_id):
    bills = load_bills(csv_path, building_id)

    electricity = sum(
        bill["amount_usd"]
        for bill in bills
        if bill["utility"] == "electricity"
    )

    gas = sum(
        bill["amount_usd"]
        for bill in bills
        if bill["utility"] == "gas"
    )

    return {
        "building_id": str(building_id),
        "observed_spend_usd": round(electricity + gas, 2),
        "electricity_spend_usd": round(electricity, 2),
        "gas_spend_usd": round(gas, 2),
        "bill_count": len(bills),
        "source": "actual_utility_bills",
        "annualized": False
    }
