
import requests
import json
import os
from client import API_KEY, BASE_URL

ACCOUNT_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"

def upload_bills():
    with open("nessie/sample_bills.json", "r") as file:
        bills = json.load(file)

    # Keep track of bills already uploaded
    if os.path.exists("nessie/uploaded_bills.json"):
        with open("nessie/uploaded_bills.json", "r") as file:
            uploaded = json.load(file)
    else:
        uploaded = {}

    for bill in bills:
        building_id = bill["building_id"]
        utility = bill["utility"]
        month = bill["month"]

        nickname = f"{building_id}_{utility}_{month:02d}"

        if nickname in uploaded:
            print("Already uploaded:", nickname)
            continue

        # This bill was created in the previous test
        if nickname == "sample_001_electricity_01":
            uploaded[nickname] = "2b289131-061b-47ae-91d9-ca1a92e39454"
            continue

        if utility == "electricity":
            payee = "Hawk Lens Electric Utility"
        else:
            payee = "Hawk Lens Gas Utility"

        data = {
            "status": "pending",
            "payee": payee,
            "nickname": nickname,
            "payment_date": f"2026-{month:02d}-15",
            "recurring_date": 1,
            "payment_amount": bill["amount"]
        }

        url = BASE_URL + "/accounts/" + ACCOUNT_ID + "/bills"

        response = requests.post(
            url,
            params={"key": API_KEY},
            json=data,
            timeout=15
        )

        if response.status_code == 201:
            result = response.json()
            bill_id = result["objectCreated"]["_id"]

            uploaded[nickname] = bill_id

            # Save after every successful upload
            with open("nessie/uploaded_bills.json", "w") as file:
                json.dump(uploaded, file, indent=4)

            print("Created:", nickname)
        else:
            print("Failed:", nickname, response.status_code)
            print(response.text)
            break

    with open("nessie/uploaded_bills.json", "w") as file:
        json.dump(uploaded, file, indent=4)

    print("Total tracked bills:", len(uploaded))


if __name__ == "__main__":
    upload_bills()
