import requests
requests.packages.urllib3.disable_warnings()
BASE_URL = 'https://localhost:8443/nifi-api'
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
headers = {'Authorization': f'Bearer {res.text}', 'Content-Type': 'application/json'}
res = requests.get(f"{BASE_URL}/flow/process-groups/root", headers=headers, verify=False).json()
for pg in res['processGroupFlow']['flow']['processGroups']:
    if pg['component']['name'] == 'Mikrotik SNMP Ingestion':
        pg_id = pg['id']
        break
status = requests.get(f"{BASE_URL}/flow/process-groups/{pg_id}/status", headers=headers, verify=False).json()
print("PG Status:", status['processGroupStatus']['aggregateSnapshot']['bytesRead'])
procs = requests.get(f"{BASE_URL}/flow/process-groups/{pg_id}/processors", headers=headers, verify=False).json()
for p in procs['processors']:
    print(p['component']['name'], p['status']['aggregateSnapshot']['runStatus'], "Out:", p['status']['aggregateSnapshot']['flowFilesOut'])
