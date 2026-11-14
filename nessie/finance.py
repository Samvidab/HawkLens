
import requests
from client import API_KEY, BASE_URL

CUSTOMER_ID = "4dba3d91-00ae-405b-bdf1-aac090f66996"
OPERATING_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"


def get_accounts():
    url = BASE_URL + "/customers/" + CUSTOMER_ID + "/accounts"

    response = requests.get(
        url,
        params={"key": API_KEY},
        timeout=15
    )

    response.raise_for_status()
    return response.json()


def create_reserve_account():
    accounts = get_accounts()

    for account in accounts:
        if account["nickname"] == "Hawk Lens Retrofit Reserve":
            print("Reserve account already exists")
            return account

    url = BASE_URL + "/customers/" + CUSTOMER_ID + "/accounts"

    data = {
        "type": "Savings",
        "nickname": "Hawk Lens Retrofit Reserve",
        "rewards": 0,
        "balance": 0
    }

    response = requests.post(
        url,
        params={"key": API_KEY},
        json=data,
        timeout=15
    )

    response.raise_for_status()

    print("Reserve account created")
    return response.json()["objectCreated"]


def get_balances():
    accounts = get_accounts()

    balances = {}

    for account in accounts:
        balances[account["nickname"]] = account["balance"]

    return balances


if __name__ == "__main__":
    balances = get_balances()

    for name in balances:
        print(name + ": $" + str(balances[name]))
