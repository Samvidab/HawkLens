
import requests
from datetime import date
from client import API_KEY, BASE_URL
from finance import get_accounts

OPERATING_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"

data = {
    "transaction_date": date.today().isoformat(),
    "status": "completed",
    "amount": 1,
    "description": "Hawk Lens transfer test"
}

print("Balances before:")
for account in get_accounts():
    print(account["nickname"], account["balance"])

response = requests.post(
    BASE_URL + "/accounts/" + OPERATING_ID + "/transfers",
    params={"key": API_KEY},
    json=data,
    timeout=15
)

print("Status:", response.status_code)
print("Response:", response.text)

print("Balances after:")
for account in get_accounts():
    print(account["nickname"], account["balance"])
