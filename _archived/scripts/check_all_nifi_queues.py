import requests
import json
requests.packages.urllib3.disable_warnings()
with open("/run/secrets/nifi_password", "r") as f:
    pw = f.read().strip()
resp = requests.post('https://localhost:8443/nifi-api/access/token', data={'username':'admin','password':pw}, verify=False)
token = resp.text
headers = {'Authorization': f'Bearer {token}'}
resp = requests.get('https://localhost:8443/nifi-api/flow/process-groups/root/connections', headers=headers, verify=False)
for conn in resp.json().get('connections', []):
    status = conn.get('status', {}).get('aggregateSnapshot', {})
    name = conn.get('component', {}).get('name', 'unnamed')
    queued = status.get('queued', '0')
    queued_count = status.get('queuedCount', 0)
    if queued_count > 0:
        print(f"{name}: {queued}")
