
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("MATTERPORT_API_KEY")
API_TOKEN = os.getenv("MATTERPORT_API_TOKEN")

MODEL_ID = "zvKHR9DHNjJ"

url = "https://api.matterport.com/api/models/graph"

query = """
query GetModel($id: ID!) {
    model(id: $id) {
        id
        name
        visibility
        address {
            address
        }
        geolocation {
            lat
            long
        }
        floors {
            id
        }
        rooms {
            id
        }
        panoLocations {
            id
        }
    }
}
"""

response = requests.post(
    url,
    auth=(API_KEY, API_TOKEN),
    json={
        "query": query,
        "variables": {"id": MODEL_ID}
    },
    timeout=30
)

print("Status:", response.status_code)

if response.status_code == 200:
    result = response.json()

    if result.get("errors"):
        print("GraphQL errors:", result["errors"])
    else:
        model = result["data"]["model"]

        if model is None:
            print("Model not found")
        else:
            print("Building:", model["name"])
            print("Address:", model["address"]["address"])
            print("Visibility:", model["visibility"])
            print("Floors:", len(model["floors"]))
            print("Rooms:", len(model["rooms"]))
            print("Panoramas:", len(model["panoLocations"]))

            if model["visibility"] == "public":
                print(
                    "3D Viewer:",
                    "https://my.matterport.com/show/?m=" + MODEL_ID
                )
else:
    print("Request failed:", response.text[:500])
