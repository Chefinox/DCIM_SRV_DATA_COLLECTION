import requests, os, json
from dotenv import load_dotenv
load_dotenv("/home/infra/dcim_metrics_project/configs/.env")
token = os.getenv("RALPH_API_TOKEN")
headers = {"Authorization": f"Token {token}", "Content-Type": "application/json"}
# Test asset 141
payload = {
    "remarks": "API Test BIOS/Year",
    "firmware_version": "KAX322Z 2.31 2024-01-19",
    "bios_version": "KAE116K",
    "production_year": 2024
}
try:
    r = requests.patch("http://192.168.101.73:8088/api/data-center-assets/141/", headers=headers, json=payload, verify=False, timeout=10)
    print(f"Status: {r.status_code}")
    if not r.ok:
        print(f"Response: {r.text}")
    else:
        print("Success!")
except Exception as e:
    print(f"Error: {e}")
