import requests
import json
requests.packages.urllib3.disable_warnings()
BASE_URL = 'https://localhost:8443/nifi-api'
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
headers = {'Authorization': f'Bearer {res.text}', 'Content-Type': 'application/json'}

def search_pg(pg_id):
    pg = requests.get(f"{BASE_URL}/flow/process-groups/{pg_id}", headers=headers, verify=False).json()
    for p in pg['processGroupFlow']['flow']['processors']:
        if 'ListenSyslog' in p['component']['name'] or 'Syslog' in p['component']['name']:
            print(f"Processor: {p['component']['name']}")
            print(f"  Run Status: {p['status']['aggregateSnapshot']['runStatus']}")
            print(f"  FlowFiles Out: {p['status']['aggregateSnapshot']['flowFilesOut']}")
            # bulletins
            b_res = requests.get(f"{BASE_URL}/flow/bulletin-board?sourceId={p['id']}", headers=headers, verify=False)
            if b_res.status_code == 200:
                bulletins = b_res.json()
                for b in bulletins.get('bulletinBoard', {}).get('bulletins', []):
                    print(f"  ERROR: {b['bulletin']['message']}")
            print("-" * 20)
    for child in pg['processGroupFlow']['flow']['processGroups']:
        search_pg(child['id'])

search_pg('root')
