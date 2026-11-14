
import requests
from client import API_KEY, BASE_URL
from finance import get_accounts

OPERATING_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"

print("Balances before:")
for account in get_accounts():
    print(account["nickname"], account["balance"])

data = {
    "medium": "balance",
    "amount": 1
}

response = requests.post(
    BASE_URL + "/accounts/" + OPERATING_ID + "/withdrawals",
    params={"key": API_KEY},
    json=data,
    timeout=15
)

print("Status:", response.status_code)
print("Response:", response.text)

print("Balances after:")
for account in get_accounts():
    print(account["nickname"], account["balance"])
