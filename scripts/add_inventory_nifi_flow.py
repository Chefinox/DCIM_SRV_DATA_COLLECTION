import requests
import json
import uuid

requests.packages.urllib3.disable_warnings()

BASE_URL = 'https://localhost:8443/nifi-api'
headers = {'Content-Type': 'application/json'}

print("Logging in to NiFi...")
res = requests.post(f"{BASE_URL}/access/token", data={'username': 'admin', 'password': 'Inovasi@0918'}, verify=False)
if res.status_code != 201:
    print(f"Login failed: {res.status_code} {res.text}")
    exit(1)
    
token = res.text
headers['Authorization'] = f'Bearer {token}'

res = requests.get(f"{BASE_URL}/flow/process-groups/root", headers=headers, verify=False)
root_pg_id = res.json()['processGroupFlow']['id']

print("Creating Process Group...")
pg_payload = {
    "revision": {"version": 0},
    "component": {
        "name": "Server Inventory Poller",
        "position": {"x": 1000, "y": 800}
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{root_pg_id}/process-groups", json=pg_payload, headers=headers, verify=False)
pg_id = res.json()['id']

print("Creating ExecuteProcess...")
p_payload = {
    "revision": {"version": 0},
    "component": {
        "type": "org.apache.nifi.processors.standard.ExecuteProcess",
        "name": "Run server_inventory_collector",
        "position": {"x": 0, "y": 0},
        "config": {
            "schedulingPeriod": "1 days",
            "properties": {
                "Command": "python3",
                "Command Arguments": "/home/infra/dcim_metrics_project/scripts/server_inventory_collector.py"
            }
        }
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{pg_id}/processors", json=p_payload, headers=headers, verify=False)
exec_proc_id = res.json()['id']

print("Creating PublishKafka_2_6...")
p_payload = {
    "revision": {"version": 0},
    "component": {
        "type": "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6",
        "name": "Publish to dcim.raw.hardware.server.inventory",
        "position": {"x": 500, "y": 0},
        "config": {
            "properties": {
                "bootstrap.servers": "127.0.0.1:9092,127.0.0.1:9095,127.0.0.1:9097",
                "topic": "dcim.raw.hardware.server.inventory",
                "security.protocol": "PLAINTEXT",
                "use-transactions": "false"
            }
        }
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{pg_id}/processors", json=p_payload, headers=headers, verify=False)
pub_kafka_id = res.json()['id']

print("Connecting processors...")
c_payload = {
    "revision": {"version": 0},
    "component": {
        "source": {"id": exec_proc_id, "groupId": pg_id, "type": "PROCESSOR"},
        "destination": {"id": pub_kafka_id, "groupId": pg_id, "type": "PROCESSOR"},
        "selectedRelationships": ["success"]
    }
}
requests.post(f"{BASE_URL}/process-groups/{pg_id}/connections", json=c_payload, headers=headers, verify=False)

print("Starting Process Group...")
start_payload = {
    "id": pg_id,
    "state": "RUNNING"
}
requests.put(f"{BASE_URL}/flow/process-groups/{pg_id}", json=start_payload, headers=headers, verify=False)

print("NiFi setup complete!")
