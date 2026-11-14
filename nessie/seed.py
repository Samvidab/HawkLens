
import requests
from client import API_KEY, BASE_URL

def create_customer():
    url = BASE_URL + "/customers"

    customer = {
        "first_name": "Hawk",
        "last_name": "Lens",
        "address": {
            "street_number": "100",
            "street_name": "Main Street",
            "city": "Houston",
            "state": "TX",
            "zip": "77002"
        }
    }

    response = requests.post(
        url,
        params={"key": API_KEY},
        json=customer,
        timeout=15
    )

    print("Status:", response.status_code)
    print("Response:", response.text)

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    create_customer()
