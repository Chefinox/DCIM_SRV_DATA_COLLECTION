import requests
import json
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

RALPH_API_URL = os.getenv("RALPH_API_URL", "http://192.168.101.73:8088/api/data-center-assets/")
RALPH_TOKEN   = os.getenv("RALPH_API_TOKEN", "")

def check_asset_in_ralph(sn):
    headers = {
        "Authorization": f"Token {RALPH_TOKEN}",
        "Content-Type": "application/json"
    }
    search_url = f"{RALPH_API_URL}?sn={sn}"
    try:
        resp = requests.get(search_url, headers=headers, verify=False, timeout=10)
        if resp.status_code == 200:
            results = resp.json().get("results", [])
            if results:
                return results[0]
    except Exception as e:
        print(f"Error checking SN {sn}: {e}")
    return None

# Check a few devices from the inventory
test_sns = [
    "DS-7732NI-K41620220216CCRRJ50925843WCVU", # NVR
    "J901F8KE", # Server
    "HC707RR1T60", # Mikrotik
    "2410V3RCZJ09K", # NAS
    "9E2133T16585" # UPS
]

for sn in test_sns:
    asset = check_asset_in_ralph(sn)
    if asset:
        print(f"SN: {sn}")
        print(f"  Model: {asset.get('model', {}).get('name')}")
        print(f"  Firmware: {asset.get('firmware_version')}")
        print(f"  Remarks: {asset.get('remarks')}")
        print(f"  Custom Fields: {asset.get('custom_fields')}")
    else:
        print(f"SN: {sn} NOT FOUND")
