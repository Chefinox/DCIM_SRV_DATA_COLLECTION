import requests
import json
import uuid

requests.packages.urllib3.disable_warnings()

BASE_URL = 'https://localhost:8443/nifi-api'

# 1. Login
data = {'username': 'admin', 'password': 'Inovasi@0918'}
res = requests.post(f"{BASE_URL}/access/token", data=data, verify=False)
token = res.text
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# 2. Get Root PG
res = requests.get(f"{BASE_URL}/flow/process-groups/root", headers=headers, verify=False)
root_pg_id = res.json()['processGroupFlow']['id']

# 3. Create Mikrotik PG
pg_payload = {
    "revision": {"version": 0},
    "component": {
        "name": "Mikrotik SNMP Ingestion",
        "position": {"x": 500, "y": 500}
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{root_pg_id}/process-groups", json=pg_payload, headers=headers, verify=False)
pg_id = res.json()['id']

# 4. Create GetSNMPs
ips = ["172.16.35.1", "172.16.35.2", "172.16.35.3", "172.16.35.5", "172.16.35.6"]
get_snmps = []
for i, ip in enumerate(ips):
    p_payload = {
        "revision": {"version": 0},
        "component": {
            "type": "org.apache.nifi.snmp.processors.GetSNMP",
            "name": f"GetSNMP {ip}",
            "position": {"x": 0, "y": i * 200},
            "config": {
                "schedulingPeriod": "60 sec",
                "properties": {
                    "snmp-hostname": ip,
                    "snmp-port": "161",
                    "snmp-version": "SNMPv2c",
                    "snmp-community": "public",
                    "snmp-strategy": "WALK",
                    "snmp-oid": ".1.3.6.1.2.1"
                }
            }
        }
    }
    res = requests.post(f"{BASE_URL}/process-groups/{pg_id}/processors", json=p_payload, headers=headers, verify=False)
    get_snmps.append(res.json()['id'])

# 5. Create AttributesToJSON
p_payload = {
    "revision": {"version": 0},
    "component": {
        "type": "org.apache.nifi.processors.standard.AttributesToJSON",
        "name": "AttributesToJSON",
        "position": {"x": 500, "y": 200},
        "config": {
            "properties": {
                "Destination": "flowfile-content",
                "Include Core Attributes": "false"
            }
        }
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{pg_id}/processors", json=p_payload, headers=headers, verify=False)
attr_json_id = res.json()['id']

# 6. Create ExecuteStreamCommand
p_payload = {
    "revision": {"version": 0},
    "component": {
        "type": "org.apache.nifi.processors.standard.ExecuteStreamCommand",
        "name": "Parse Mikrotik",
        "position": {"x": 1000, "y": 200},
        "config": {
            "properties": {
                "Command Path": "python3",
                "Command Arguments": "/opt/nifi/nifi-current/nifi_mikrotik_parser.py"
            }
        }
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{pg_id}/processors", json=p_payload, headers=headers, verify=False)
exec_cmd_id = res.json()['id']

# 7. Create PublishKafka
p_payload = {
    "revision": {"version": 0},
    "component": {
        "type": "org.apache.nifi.processors.kafka.pubsub.PublishKafka_2_6",
        "name": "PublishKafka_2_6",
        "position": {"x": 1500, "y": 200},
        "config": {
            "properties": {
                "bootstrap.servers": "127.0.0.1:9092,127.0.0.1:9095,127.0.0.1:9097",
                "topic": "dcim.raw.network.snmp",
                "security.protocol": "PLAINTEXT",
                "use-transactions": "false"
            }
        }
    }
}
res = requests.post(f"{BASE_URL}/process-groups/{pg_id}/processors", json=p_payload, headers=headers, verify=False)
pub_kafka_id = res.json()['id']

# 8. Create Connections
def create_connection(src_id, dest_id, relationships):
    c_payload = {
        "revision": {"version": 0},
        "component": {
            "source": {"id": src_id, "groupId": pg_id, "type": "PROCESSOR"},
            "destination": {"id": dest_id, "groupId": pg_id, "type": "PROCESSOR"},
            "selectedRelationships": relationships
        }
    }
    requests.post(f"{BASE_URL}/process-groups/{pg_id}/connections", json=c_payload, headers=headers, verify=False)

for get_snmp_id in get_snmps:
    create_connection(get_snmp_id, attr_json_id, ["success"])
create_connection(attr_json_id, exec_cmd_id, ["success"])
create_connection(exec_cmd_id, pub_kafka_id, ["output stream"])

# 9. Start PG
start_payload = {
    "id": pg_id,
    "state": "RUNNING"
}
requests.put(f"{BASE_URL}/flow/process-groups/{pg_id}", json=start_payload, headers=headers, verify=False)

print("Flow created and started")
