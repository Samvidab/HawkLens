
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MATTERPORT_API_KEY")
API_TOKEN = os.getenv("MATTERPORT_API_TOKEN")

url = "https://api.matterport.com/api/models/graph"

query = """
query GetModels($folderId: ID!, $offset: String, $pageSize: Int) {
    folder(id: $folderId) {
        models(offset: $offset, pageSize: $pageSize, recursive: true) {
            results {
                id
                name
                visibility
            }
        }
    }
}
"""

keywords = [
    "office",
    "warehouse",
    "retail",
    "commercial",
    "industrial",
    "business",
    "store",
    "building"
]

checked = 0
matches = 0

for page in range(10):
    response = requests.post(
        url,
        auth=(API_KEY, API_TOKEN),
        json={
            "query": query,
            "variables": {
                "folderId": "modNEmUQx5D",
                "offset": str(page * 100),
                "pageSize": 100
            }
        },
        timeout=30
    )

    response.raise_for_status()
    result = response.json()

    if result.get("errors"):
        print("GraphQL errors:", result["errors"])
        break

    models = result["data"]["folder"]["models"]["results"]

    if len(models) == 0:
        break

    for model in models:
        checked += 1
        name = model["name"].lower()

        if any(word in name for word in keywords):
            print("Name:", model["name"])
            print("ID:", model["id"])
            print()
            matches += 1

    print("Page", page + 1, "- checked", checked, "models")

print()
print("Total models checked:", checked)
print("Matching models:", matches)
