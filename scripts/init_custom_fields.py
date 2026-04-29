import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')
RALPH_API_URL = "http://192.168.101.73:8088/api/custom-fields/"
RALPH_TOKEN = os.getenv("RALPH_API_TOKEN", "")

headers = {
    "Authorization": f"Token {RALPH_TOKEN}",
    "Content-Type": "application/json"
}

fields_to_create = [
    {"name": "CPU Load Snapshot", "attribute_name": "cpu_load_snapshot", "type": "string", "choices": [""]},
    {"name": "Device Temperature", "attribute_name": "device_temperature", "type": "string", "choices": [""]},
    {"name": "Power Consumption", "attribute_name": "power_consumption", "type": "string", "choices": [""]},
    {"name": "UPS Load Status", "attribute_name": "ups_load_status", "type": "string", "choices": [""]},
    {"name": "UPS Battery Capacity", "attribute_name": "ups_battery_capacity", "type": "string", "choices": [""]},
    {"name": "UPS Output Status", "attribute_name": "ups_status", "type": "string", "choices": [""]},
    {"name": "UPS Battery Health", "attribute_name": "ups_health", "type": "string", "choices": [""]},
    {"name": "UPS Power Source", "attribute_name": "ups_source", "type": "string", "choices": [""]},
    {"name": "NAS Volume Status", "attribute_name": "nas_volume_status", "type": "string", "choices": [""]},
    {"name": "NAS Temperature", "attribute_name": "nas_temperature", "type": "string", "choices": [""]},
    {"name": "NAS CPU Load", "attribute_name": "nas_cpu_load", "type": "string", "choices": [""]},
    {"name": "Monitoring Link", "attribute_name": "monitoring_link", "type": "url", "choices": [""]}
]

# Check existing
resp = requests.get(RALPH_API_URL, headers=headers)
existing_fields = []
if resp.ok:
    existing_fields = [f["attribute_name"] for f in resp.json().get("results", [])]

for f in fields_to_create:
    if f["attribute_name"] not in existing_fields:
        r = requests.post(RALPH_API_URL, headers=headers, json=f)
        if r.ok:
            print(f"Created: {f['name']}")
        else:
            print(f"Failed to create {f['name']}: {r.text}")
    else:
        print(f"Already exists: {f['name']}")
