import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

servers = [
    {"ip": "10.50.0.3", "user": "hndept", "name": "FALAH01-SERVER-HCI-02"},
    {"ip": "10.50.0.4", "user": "hndept", "name": "FALAH01-SERVER-HCI-03"},
    {"ip": "10.50.0.5", "user": "hndept", "name": "FALAH01-SERVER-RENDER-01"},
    {"ip": "10.50.0.6", "user": "hndept", "name": "FALAH01-SERVER-RENDER-02"}, # Try hndept for .6 too
    {"ip": "10.50.0.6", "user": "root", "name": "FALAH01-SERVER-RENDER-02"} # Try root
]

pwd = "F!tech@0918"

for s in servers:
    try:
        r = requests.get(f"https://{s['ip']}/redfish/v1/Systems/1", auth=(s['user'], pwd), verify=False, timeout=5)
        if r.status_code == 200:
            data = r.json()
            cpu = data.get('ProcessorSummary', {}).get('Model', 'Unknown')
            ram = data.get('MemorySummary', {}).get('TotalSystemMemoryGiB', 0)
            sn = data.get('SerialNumber', 'Unknown')
            print(f"[OK] {s['ip']} ({s['user']}): CPU={cpu}, RAM={ram}GB, SN={sn}")
        else:
            print(f"[FAIL] {s['ip']} ({s['user']}): {r.status_code}")
    except Exception as e:
        print(f"[ERROR] {s['ip']} ({s['user']}): {e}")
