
import requests
from client import API_KEY, BASE_URL

ACCOUNT_ID = "3e4f8885-befb-4d0f-85ad-545b776f0888"
ELECTRIC_MERCHANT_ID = "08d68f61-ec2a-4363-af90-7622a7929a8f"

def test_bill():
    url = BASE_URL + "/accounts/" + ACCOUNT_ID + "/bills"

    bill = {
        "status": "pending",
        "payee": "Hawk Lens Electric Utility",
        "nickname": "sample_001_electricity_01",
        "payment_date": "2026-01-15",
        "recurring_date": 1,
        "payment_amount": 12500
    }

    response = requests.post(
        url,
        params={"key": API_KEY},
        json=bill,
        timeout=15
    )

    print("Status:", response.status_code)
    print("Response:", response.text)

if __name__ == "__main__":
    test_bill()
