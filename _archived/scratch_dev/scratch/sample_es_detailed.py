import requests
import json
import os
from dotenv import load_dotenv
import urllib3
urllib3.disable_warnings()

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

ES_URL  = os.getenv("ES_URL", "https://10.70.0.56:9200")
ES_USER = os.getenv("ES_USER", "elastic")
ES_PASS = os.getenv("ES_PASS", "C+H+pFb*aIAqWcOo-X8q")

def get_latest_docs(index_pattern, size=3):
    query = {
        "size": size,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {"match_all": {}}
    }
    try:
        r = requests.post(
            f"{ES_URL}/{index_pattern}/_search",
            auth=(ES_USER, ES_PASS),
            json=query,
            verify=False,
            timeout=5
        )
        if r.status_code == 200:
            return [hit["_source"] for hit in r.json().get("hits", {}).get("hits", [])]
    except Exception as e:
        return [f"Error: {e}"]
    return []

print("--- Detailed Sample from Elasticsearch ---")

# 1. DCIM Inventory (Unified Metadata)
print("\n[DCIM-INVENTORY-*] - Unified Aset Metadata")
docs = get_latest_docs("dcim-inventory-*", 2)
for d in docs:
    print(json.dumps(d, indent=2))

# 2. Server Metrics (Normalized Redfish)
print("\n[TELEGRAF-SERVER-*] - Server Health (Redfish)")
docs = get_latest_docs("telegraf-server-*", 1)
for d in docs:
    print(json.dumps(d, indent=2))

# 3. UPS Metrics (Normalized SNMP)
print("\n[TELEGRAF-UPS-*] - UPS Power Status (SNMP)")
docs = get_latest_docs("telegraf-ups-*", 1)
for d in docs:
    print(json.dumps(d, indent=2))
