import requests
import json
requests.packages.urllib3.disable_warnings()
BASE_URL = 'https://localhost:8443/nifi-api'
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
headers = {'Authorization': f'Bearer {res.text}', 'Content-Type': 'application/json'}

def search_pg(pg_id):
    pg = requests.get(f"{BASE_URL}/flow/process-groups/{pg_id}", headers=headers, verify=False).json()
    if pg['processGroupFlow']['breadcrumb']['breadcrumb']['name'] == 'Security SIEM Ingestion':
        for conn in pg['processGroupFlow']['flow']['connections']:
            c = conn['component']
            print(f"Connection: {c['name']} from {c['source']['name']} to {c['destination']['name']}")
            status = requests.get(f"{BASE_URL}/flow/connections/{c['id']}/status", headers=headers, verify=False).json()
            q = status['connectionStatus']['aggregateSnapshot']
            print(f"  Queued: {q['queuedCount']} objects, {q['queuedSize']}")
    for child in pg['processGroupFlow']['flow']['processGroups']:
        search_pg(child['id'])

search_pg('root')
