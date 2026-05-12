import requests
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

RALPH_API_URL = os.getenv("RALPH_API_URL", "http://192.168.101.73:8088/api/data-center-assets/")
RALPH_TOKEN   = os.getenv("RALPH_API_TOKEN", "")

def check_ralph_api(sn):
    headers = {"Authorization": f"Token {RALPH_TOKEN}"}
    for endpoint in ["data-center-assets", "back-office-assets"]:
        url = f"http://192.168.101.73:8088/api/{endpoint}/?sn={sn}"
        r = requests.get(url, headers=headers, verify=False)
        if r.status_code == 200:
            results = r.json().get("results", [])
            if results:
                return endpoint, results[0]
    return None, None

sn = "9E2133T16585"
endpoint, asset = check_ralph_api(sn)
if asset:
    print(f"Found in {endpoint}: {asset.get('hostname')} (ID: {asset.get('id')})")
else:
    print(f"SN {sn} NOT FOUND IN RALPH API")
