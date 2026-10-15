# import os
# import requests
# from dotenv import load_dotenv

# load_dotenv()

# token = os.getenv("HUBSPOT_ACCESS_TOKEN")

# if not token:
#     raise ValueError("HUBSPOT_ACCESS_TOKEN is missing from .env")

# response = requests.get(
#     "https://api.hubapi.com/crm/v3/objects/deals",
#     headers={"Authorization": f"Bearer {token}"},
#     params={"limit": 5},
#     timeout=30,
# )

# print("Status code:", response.status_code)

# if response.ok:
#     data = response.json()
#     print("Connection successful!")
#     print("Deals returned:", len(data.get("results", [])))
# else:
#     print("Request failed:", response.text)

import logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from services.hubspot_api_service import HubSpotAPIService

props = ["dealname", "amount", "dealstage", "closedate", "description"]

svc = HubSpotAPIService()
print("Valid:", svc.validate_credentials())

deals = svc.get_deals(properties=props)
print("Count:", len(deals))
for d in deals:
    print(d["id"], d["properties"].get("dealname"), d["properties"].get("amount"))

# Pagination check: expect one "Retrieved deals page" log line per deal
print("Paged count:", len(svc.get_deals(limit=1, properties=props)))
svc.close()

# Bad token check: expect False plus a 401 hint in the log
bad = HubSpotAPIService(access_token="pat-na2-invalid")
print("Bad token valid:", bad.validate_credentials())
bad.close()