import requests
import json
requests.packages.urllib3.disable_warnings()
BASE_URL = 'https://localhost:8443/nifi-api'
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
headers = {'Authorization': f'Bearer {res.text}', 'Content-Type': 'application/json'}

def list_pg(pg_id, indent=""):
    pg = requests.get(f"{BASE_URL}/flow/process-groups/{pg_id}/processors", headers=headers, verify=False).json()
    for p in pg['processors']:
        if 'SIEM' in p['component']['name'] or 'siem' in p['component']['name'].lower():
            print(f"Processor: {p['component']['name']}")
            print(f"  Run Status: {p['status']['aggregateSnapshot']['runStatus']}")
            print(f"  FlowFiles Out: {p['status']['aggregateSnapshot']['flowFilesOut']}")
            print(f"  Tasks: {p['status']['aggregateSnapshot']['taskCount']}")
            # Check for bulletins (errors)
            bulletins = requests.get(f"{BASE_URL}/flow/bulletin-board?sourceId={p['id']}", headers=headers, verify=False).json()
            for b in bulletins.get('bulletinBoard', {}).get('bulletins', []):
                print(f"  ERROR: {b['bulletin']['message']}")
            print("-" * 20)

list_pg('root')
# Need to recurse to all process groups
res = requests.get(f"{BASE_URL}/flow/process-groups/root", headers=headers, verify=False).json()
for child in res['processGroupFlow']['flow']['processGroups']:
    list_pg(child['id'], "  ")
