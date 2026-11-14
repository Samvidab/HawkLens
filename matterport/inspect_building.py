
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = "https://api.matterport.com/api/models/graph"

query = """
query GetModel($id: ID!) {
    model(id: $id) {
        id
        name
        description
        visibility
        address {
            address
            locality
            administrativeArea
            postalCode
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
        image {
            url
        }
    }
}
"""

response = requests.post(
    url,
    auth=(
        os.getenv("MATTERPORT_API_KEY"),
        os.getenv("MATTERPORT_API_TOKEN")
    ),
    json={
        "query": query,
        "variables": {"id": "9yBnBD3ievg"}
    },
    timeout=30
)

print("Status:", response.status_code)

response.raise_for_status()
result = response.json()

if result.get("errors"):
    print("GraphQL errors:", result["errors"])
else:
    model = result["data"]["model"]

    if model is None:
        print("Model not found")
    else:
        print("Name:", model["name"])
        print("Description:", model["description"])
        print("Address:", model["address"])
        print("Coordinates:", model["geolocation"])
        print("Floors:", len(model["floors"] or []))
        print("Rooms:", len(model["rooms"] or []))
        print("Panoramas:", len(model["panoLocations"] or []))
        print("Preview image:", model["image"])
        print("3D Tour:", "https://my.matterport.com/show/?m=" + model["id"])
