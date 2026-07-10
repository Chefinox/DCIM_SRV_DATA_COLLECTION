import requests
requests.packages.urllib3.disable_warnings()
BASE_URL = 'https://localhost:8443/nifi-api'
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
headers = {'Authorization': f'Bearer {res.text}', 'Content-Type': 'application/json'}
res = requests.get(f"{BASE_URL}/flow/process-groups/177683c0-019f-1000-2160-756322652776/processors", headers=headers, verify=False).json()
for p in res['processors']:
    if p['status']['aggregateSnapshot']['runStatus'] == 'Invalid':
        print(f"Processor: {p['component']['name']}")
        for err in p['component'].get('validationErrors', []):
            print(f"  - {err}")
