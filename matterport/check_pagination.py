
import os
import requests
from dotenv import load_dotenv

load_dotenv()

url = "https://api.matterport.com/api/models/graph"

query = """
{
    __type(name: "Folder") {
        fields {
            name
            args {
                name
                type {
                    kind
                    name
                    ofType {
                        name
                    }
                }
            }
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
    json={"query": query},
    timeout=30
)

print("Status:", response.status_code)

result = response.json()

if result.get("errors"):
    print("Errors:", result["errors"])
else:
    for field in result["data"]["__type"]["fields"]:
        if field["name"] == "models":
            print("Supported pagination arguments:")

            for arg in field["args"]:
                print(arg["name"], arg["type"])
