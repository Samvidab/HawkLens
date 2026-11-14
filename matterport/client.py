
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MATTERPORT_API_KEY")
API_TOKEN = os.getenv("MATTERPORT_API_TOKEN")

url = "https://api.matterport.com/api/models/graph"

query = """
{
    rootFolder {
        name
        modelCountSummary(includeModelsInSubfolders: true)
    }
}
"""

if not API_KEY or not API_TOKEN:
    raise ValueError("Missing Matterport credentials in .env")

response = requests.post(
    url,
    auth=(API_KEY, API_TOKEN),
    json={"query": query},
    timeout=30
)

print("Status:", response.status_code)

if response.status_code == 200:
    print(response.json())
else:
    print("Request failed:", response.text[:500])
