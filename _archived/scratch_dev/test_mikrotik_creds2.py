import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

IP = "172.16.35.5"
user = "netbox"
pwd = "netbox123"

print(f"Trying HTTPS REST API with {user}:{pwd}")
try:
    r = requests.get(f"https://{IP}/rest/interface", auth=(user, pwd), verify=False, timeout=5)
    if r.status_code == 200:
        print(f"SUCCESS! Fetched {len(r.json())} interfaces.")
        # print first interface
        if len(r.json()) > 0:
            print(json.dumps(r.json()[0], indent=2))
    elif r.status_code == 401:
        print("401 Unauthorized")
    else:
        print(f"Status: {r.status_code}")
except Exception as e:
    print(f"HTTPS Error: {e}")

print(f"Trying HTTP REST API with {user}:{pwd}")
try:
    r = requests.get(f"http://{IP}/rest/interface", auth=(user, pwd), verify=False, timeout=5)
    if r.status_code == 200:
        print(f"SUCCESS! Fetched {len(r.json())} interfaces.")
    elif r.status_code == 401:
        print("401 Unauthorized")
    else:
        print(f"Status: {r.status_code}")
except Exception as e:
    print(f"HTTP Error: {e}")
