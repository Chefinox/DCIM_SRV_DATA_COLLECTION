import requests
import json
requests.packages.urllib3.disable_warnings()
BASE_URL = 'https://localhost:8443/nifi-api'
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
headers = {'Authorization': f'Bearer {res.text}', 'Content-Type': 'application/json'}

def list_pg(pg_id, indent=""):
    pg = requests.get(f"{BASE_URL}/flow/process-groups/{pg_id}", headers=headers, verify=False).json()
    print(f"{indent}Process Group: {pg['processGroupFlow']['breadcrumb']['breadcrumb']['name']}")
    for p in pg['processGroupFlow']['flow']['processors']:
        print(f"{indent}  Processor: {p['component']['name']} ({p['component']['type']})")
        if 'Kafka' in p['component']['type'] or 'Kafka' in p['component']['name']:
            props = p['component']['config'].get('properties', {})
            print(f"{indent}    Brokers: {props.get('bootstrap.servers', 'N/A')}")
            print(f"{indent}    Security: {props.get('security.protocol', 'N/A')}")
            print(f"{indent}    Topic: {props.get('topic', 'N/A')}")
    for child in pg['processGroupFlow']['flow']['processGroups']:
        list_pg(child['id'], indent + "  ")

list_pg('root')
