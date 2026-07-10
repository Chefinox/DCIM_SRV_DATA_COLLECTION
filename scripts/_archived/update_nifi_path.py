import requests

requests.packages.urllib3.disable_warnings()

BASE_URL = 'https://localhost:8443/nifi-api'
headers = {'Content-Type': 'application/json'}

res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
token = res.text
headers['Authorization'] = f'Bearer {token}'

# Find the Server Inventory Poller Process Group
res = requests.get(f"{BASE_URL}/flow/process-groups/root", headers=headers, verify=False)
root_pg_id = res.json()['processGroupFlow']['id']

res = requests.get(f"{BASE_URL}/process-groups/{root_pg_id}/process-groups", headers=headers, verify=False)
target_pg_id = None
for pg in res.json()['processGroups']:
    if pg['component']['name'] == 'Server Inventory Poller':
        target_pg_id = pg['id']
        break

if not target_pg_id:
    print("PG not found")
    exit(1)

# Find the ExecuteProcess processor
res = requests.get(f"{BASE_URL}/process-groups/{target_pg_id}/processors", headers=headers, verify=False)
exec_proc = None
for p in res.json()['processors']:
    if p['component']['name'] == 'Run server_inventory_collector':
        exec_proc = p
        break

if not exec_proc:
    print("Processor not found")
    exit(1)

# Stop the processor
stop_payload = {
    "revision": exec_proc["revision"],
    "state": "STOPPED",
    "component": {"id": exec_proc["id"]}
}
requests.put(f"{BASE_URL}/processors/{exec_proc['id']}/run-status", json=stop_payload, headers=headers, verify=False)

import time
time.sleep(2)

# Re-fetch revision after stopping
res = requests.get(f"{BASE_URL}/processors/{exec_proc['id']}", headers=headers, verify=False)
exec_proc = res.json()

# Update the processor's Command Arguments
update_payload = {
    "revision": exec_proc["revision"],
    "component": {
        "id": exec_proc["id"],
        "config": {
            "properties": {
                "Command Arguments": "/opt/nifi/nifi-current/server_inventory_collector.py"
            }
        }
    }
}
res = requests.put(f"{BASE_URL}/processors/{exec_proc['id']}", json=update_payload, headers=headers, verify=False)
if res.status_code == 200:
    print("Successfully updated processor path!")
else:
    print(f"Failed to update processor: {res.status_code} {res.text}")

# Start the processor again
# Re-fetch revision after updating
res = requests.get(f"{BASE_URL}/processors/{exec_proc['id']}", headers=headers, verify=False)
exec_proc = res.json()

start_payload = {
    "revision": exec_proc["revision"],
    "state": "RUNNING",
    "component": {"id": exec_proc["id"]}
}
requests.put(f"{BASE_URL}/processors/{exec_proc['id']}/run-status", json=start_payload, headers=headers, verify=False)
print("Started processor!")
