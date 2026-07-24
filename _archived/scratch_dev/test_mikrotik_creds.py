import requests
import json

IP = "172.16.35.5"
creds = [
    ("admin", "Inovasi@0918"),
    ("admin", "F!tech@0918"),
    ("admin", "admin"),
    ("admin", "")
]

for user, pwd in creds:
    print(f"Trying {user}:{pwd}")
    try:
        r = requests.get(f"http://{IP}/rest/system/resource", auth=(user, pwd), verify=False, timeout=5)
        if r.status_code == 200:
            print(f"SUCCESS! {user}:{pwd}")
            print(json.dumps(r.json(), indent=2))
            
            # also fetch health for power
            r2 = requests.get(f"http://{IP}/rest/system/health", auth=(user, pwd), verify=False, timeout=5)
            print("HEALTH:")
            print(json.dumps(r2.json(), indent=2))
            break
        elif r.status_code == 401:
            print("401 Unauthorized")
        else:
            print(f"Status: {r.status_code}")
    except Exception as e:
        print(f"Error: {e}")
        
    try:
        r = requests.get(f"https://{IP}/rest/system/resource", auth=(user, pwd), verify=False, timeout=5)
        if r.status_code == 200:
            print(f"HTTPS SUCCESS! {user}:{pwd}")
            print(json.dumps(r.json(), indent=2))
            
            # also fetch health for power
            r2 = requests.get(f"https://{IP}/rest/system/health", auth=(user, pwd), verify=False, timeout=5)
            print("HTTPS HEALTH:")
            print(json.dumps(r2.json(), indent=2))
            break
    except Exception as e:
        print(f"HTTPS Error: {e}")
