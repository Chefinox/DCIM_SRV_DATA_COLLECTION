import requests
import json

NETBOX_URL = "http://10.70.0.20:9008"
NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

headers = {"Authorization": f"Token {NETBOX_TOKEN}"}
server_name = "FALAH01-FIT-DIST-SW-SERVER1"

print(f"--- Fetching device: {server_name} ---")
r = requests.get(f"{NETBOX_URL}/api/dcim/devices/?name={server_name}", headers=headers)
res = r.json().get('results', [])
if not res:
    print("Device not found")
    exit(1)

dev = res[0]
dev_id = dev['id']
print("Device info:")
print(json.dumps(dev, indent=2))

print(f"\n--- Fetching interfaces for device ID {dev_id} ---")
r = requests.get(f"{NETBOX_URL}/api/dcim/interfaces/?device_id={dev_id}&limit=100", headers=headers)
interfaces = r.json().get('results', [])
print(f"Found {len(interfaces)} interfaces.")
for intf in interfaces:
    name = intf['name']
    mac = intf.get('mac_address', '')
    peers = intf.get('link_peers', [])
    uplink_device = None
    uplink_port = None
    if peers:
        peer = peers[0]
        uplink_device = peer.get('device', {}).get('name')
        uplink_port = peer.get('name')
    print(f"Interface: {name}, MAC: {mac}, Connected to: {uplink_device}:{uplink_port}")
