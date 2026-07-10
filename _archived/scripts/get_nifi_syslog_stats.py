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
            print(f"  Bytes Read: {p['status']['aggregateSnapshot']['bytesRead']}")
            print(f"  Bytes Written: {p['status']['aggregateSnapshot']['bytesWritten']}")
            print(f"  FlowFiles Received: {p['status']['aggregateSnapshot']['flowFilesReceived'] if 'flowFilesReceived' in p['status']['aggregateSnapshot'] else p['status']['aggregateSnapshot'].get('bytesReceived', 'N/A')}")
            # print all aggregate properties
            print(json.dumps(p['status']['aggregateSnapshot'], indent=2))
            print("-" * 20)
    for child in pg['processGroupFlow']['flow']['processGroups']:
        search_pg(child['id'])

search_pg('root')
