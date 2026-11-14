
import requests
from client import API_KEY, BASE_URL

def create_merchant(name, category):
    url = BASE_URL + "/merchants"

    merchant = {
        "name": name,
        "category": category,
        "address": {
            "street_number": "100",
            "street_name": "Main Street",
            "city": "Houston",
            "state": "TX",
            "zip": "77002"
        },
        "geocode": {
            "lat": 29.7604,
            "lng": -95.3698
        }
    }

    response = requests.post(
        url,
        params={"key": API_KEY},
        json=merchant,
        timeout=15
    )

    print("Status:", response.status_code)
    print("Response:", response.text)

    response.raise_for_status()
    return response.json()


if __name__ == "__main__":
    create_merchant("Hawk Lens Electric Utility", "Utilities")
    create_merchant("Hawk Lens Gas Utility", "Utilities")

