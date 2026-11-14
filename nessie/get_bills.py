
import requests
import json
from client import API_KEY, BASE_URL

ACCOUNT_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"

def get_bills():
    url = BASE_URL + "/accounts/" + ACCOUNT_ID + "/bills"

    response = requests.get(
        url,
        params={"key": API_KEY},
        timeout=15
    )

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    bills = get_bills()
    print(json.dumps(bills, indent=4))
