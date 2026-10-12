import os
import requests
from dotenv import load_dotenv

load_dotenv()

token = os.getenv("HUBSPOT_ACCESS_TOKEN")

if not token:
    raise ValueError("HUBSPOT_ACCESS_TOKEN is missing from .env")

response = requests.get(
    "https://api.hubapi.com/crm/v3/objects/deals",
    headers={"Authorization": f"Bearer {token}"},
    params={"limit": 5},
    timeout=30,
)

print("Status code:", response.status_code)

if response.ok:
    data = response.json()
    print("Connection successful!")
    print("Deals returned:", len(data.get("results", [])))
else:
    print("Request failed:", response.text)