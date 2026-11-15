
import requests
from datetime import date
from client import API_KEY, BASE_URL
from finance import get_accounts

RESERVE_ID = "37f8e523-1f9d-435d-8102-eef7f8dfc05b"

print("Balances before:")
for account in get_accounts():
    print(account["nickname"], account["balance"])

data = {
    "medium": "balance",
    "transaction_date": date.today().isoformat(),
    "status": "completed",
    "amount": 1,
    "description": "Hawk Lens deposit test"
}

response = requests.post(
    BASE_URL + "/accounts/" + RESERVE_ID + "/deposits",
    params={"key": API_KEY},
    json=data,
    timeout=15
)

print("Status:", response.status_code)
print("Response:", response.text)

print("Balances after:")
for account in get_accounts():
    print(account["nickname"], account["balance"])
