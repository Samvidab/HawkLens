import requests
import os
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("NESSIE_API_KEY")
BASE_URL = "https://api.nessieisreal.com"

def get_customers():
    url = BASE_URL + "/customers"
    response = requests.get(url, params={"key": API_KEY}, timeout=15)

    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    print(get_customers())