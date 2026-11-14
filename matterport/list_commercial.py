
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MATTERPORT_API_KEY")
API_TOKEN = os.getenv("MATTERPORT_API_TOKEN")

url = "https://api.matterport.com/api/models/graph"

query = """
query GetModels($folderId: ID!) {
    folder(id: $folderId) {
        name
        models {
            results {
                id
                name
                visibility
            }
        }
    }
}
"""

response = requests.post(
    url,
    auth=(API_KEY, API_TOKEN),
    json={
        "query": query,
        "variables": {"folderId": "modNEmUQx5D"}
    },
    timeout=30
)

print("Status:", response.status_code)

if response.status_code == 200:
    result = response.json()

    if result.get("errors"):
        print("GraphQL errors:", result["errors"])
    else:
        folder = result["data"]["folder"]
        models = folder["models"]["results"]

        print("Folder:", folder["name"])
        print()

        for model in models[:10]:
            print("Name:", model["name"])
            print("ID:", model["id"])
            print("Visibility:", model["visibility"])
            print()
else:
    print("Request failed:", response.text[:500])
