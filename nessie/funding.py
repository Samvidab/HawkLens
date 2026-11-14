
import json
import os
import requests
from datetime import date
from client import API_KEY, BASE_URL

OPERATING_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"
LEDGER_FILE = os.path.join(os.path.dirname(__file__), "funding_ledger.json")


def fund_retrofit(amount, approved=False):
    if not approved:
        print("Funding blocked: Retrofit plan must be approved")
        return

    if amount <= 0:
        print("Invalid funding amount")
        return

    records = []

    if os.path.exists(LEDGER_FILE):
        with open(LEDGER_FILE, "r") as file:
            records = json.load(file)

    # Prevent duplicate funding for this demo project
    for record in records:
        if record["status"] == "allocated":
            print("Retrofit funding already allocated")
            print("Existing amount: $" + str(record["amount"]))
            print("No new Nessie transaction created")
            return

    data = {
        "transaction_date": date.today().isoformat(),
        "status": "completed",
        "amount": amount,
        "description": "Hawk Lens retrofit funding allocation"
    }

    response = requests.post(
        BASE_URL + "/accounts/" + OPERATING_ID + "/transfers",
        params={"key": API_KEY},
        json=data,
        timeout=15
    )

    print("Nessie status:", response.status_code)

    if response.status_code != 201:
        print("Funding record failed:", response.text)
        return

    transaction = response.json()["objectCreated"]

    record = {
        "transaction_id": transaction["_id"],
        "amount": amount,
        "date": date.today().isoformat(),
        "status": "allocated",
        "bank_transfer_completed": False
    }

    records.append(record)

    with open(LEDGER_FILE, "w") as file:
        json.dump(records, file, indent=4)

    print("Retrofit funding allocated: $" + str(amount))
    print("Nessie transaction ID:", transaction["_id"])
    print("Bank balances unchanged")


if __name__ == "__main__":
    answer = input("Approve $10,000 retrofit allocation? (yes/no): ")

    if answer.lower() == "yes":
        fund_retrofit(10000, approved=True)
    else:
        print("Funding not approved")
