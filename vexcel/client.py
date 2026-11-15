
import os
import requests
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("VEXCEL_API_KEY")

url = "https://api.vexcelgroup.com/v2/ortho/extract"

polygon = (
    "POLYGON(("
    "-95.3581 29.8860,"
    "-95.3569 29.8860,"
    "-95.3569 29.8871,"
    "-95.3581 29.8871,"
    "-95.3581 29.8860"
    "))"
)

data = {
    "wkt": polygon,
    "srid": 4326,
    "layer": "urban,urban-r,wide-area,urban-g",
    "crop": "bounding_box",
    "image-format": "jpeg",
    "destination-dimensions": "1400,1400",
    "attribution": "false"
}

if not API_KEY:
    raise ValueError("Missing VEXCEL_API_KEY in .env")

response = requests.post(
    url,
    headers={"X-API-KEY": API_KEY},
    json=data,
    timeout=30
)

print("Status:", response.status_code)

if response.status_code == 200:
    with open("vexcel/houston_building.jpg", "wb") as file:
        file.write(response.content)

    print("Saved aerial image to vexcel/houston_building.jpg")
else:
    print("Request failed:", response.text[:500])
