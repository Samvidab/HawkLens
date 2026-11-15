
import requests
from client import API_KEY, BASE_URL

CUSTOMER_ID = "4dba3d91-00ae-405b-bdf1-aac090f66996"

def create_account():
    url = BASE_URL + "/customers/" + CUSTOMER_ID + "/accounts"

    account = {
        "type": "Checking",
        "nickname": "Hawk Lens Operating",
        "rewards": 0,
        "balance": 500000
    }

    response = requests.post(
        url,
        params={"key": API_KEY},
        json=account,
        timeout=15
    )

    print("Status:", response.status_code)
    print("Response:", response.text)

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    create_account()
