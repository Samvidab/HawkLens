
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
        subfolders {
            results {
                id
                name
                modelCountSummary(includeModelsInSubfolders: true)
            }
        }
    }
}
"""

response = requests.post(
    url,
    auth=(API_KEY, API_TOKEN),
    json={"query": query},
    timeout=30
)

print("Status:", response.status_code)

if response.status_code == 200:
    result = response.json()

    if result.get("errors"):
        print("GraphQL errors:", result["errors"])
    else:
        folders = result["data"]["rootFolder"]["subfolders"]["results"]

        for folder in folders:
            print("Folder:", folder["name"])
            print("ID:", folder["id"])
            print("Models:", folder["modelCountSummary"])
            print()
else:
    print("Request failed:", response.text[:500])
