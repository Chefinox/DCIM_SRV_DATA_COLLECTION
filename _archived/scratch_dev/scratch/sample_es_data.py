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

indices = [
    "dcim-inventory-*",
    "telegraf-ups-*",
    "telegraf-server-*",
    "telegraf-mikrotik-*",
    "telegraf-nas-*",
    "cctv-metrics-*"
]

def get_latest_data(index_pattern):
    query = {
        "size": 1,
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
            hits = r.json().get("hits", {}).get("hits", [])
            if hits:
                return hits[0]["_source"]
    except Exception as e:
        return f"Error: {e}"
    return "No data found"

print("--- Latest Processed Data in Elasticsearch ---")
for idx in indices:
    print(f"\nIndex: {idx}")
    data = get_latest_data(idx)
    if isinstance(data, dict):
        # Print key fields for brevity
        relevant_keys = ["@timestamp", "hostname", "serial_number", "device_type", "site", "rack_name", "status"]
        summary = {k: data.get(k) for k in relevant_keys if k in data}
        # Add a few metrics if available
        if "reading_celsius" in data: summary["reading_celsius"] = data["reading_celsius"]
        if "cpu_usage_percent" in data: summary["cpu_usage_percent"] = data["cpu_usage_percent"]
        if "battery_capacity" in data: summary["battery_capacity"] = data["battery_capacity"]
        
        print(json.dumps(summary, indent=2))
    else:
        print(f"  {data}")
