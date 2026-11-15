
import json
import os

LEDGER_FILE = os.path.join(os.path.dirname(__file__), "funding_ledger.json")

with open(LEDGER_FILE, "r") as file:
    records = json.load(file)

total = 0

for record in records:
    if record["status"] == "allocated":
        total += record["amount"]

print("Hawk Lens Funding Summary")
print("Total allocated: $" + str(total))
print("Number of allocations:", len(records))

for record in records:
    print("Transaction:", record["transaction_id"])
    print("Amount: $" + str(record["amount"]))
    print("Status:", record["status"])
