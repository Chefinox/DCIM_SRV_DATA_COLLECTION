import requests
import json

ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
auth = {"auth_user": "admin", "auth_pwd": "Inovasi@0918"}

print("Getting device ID...")
q1 = {"operation": "core/get", "class": "NetworkDevice", "key": "SELECT NetworkDevice WHERE name='FALAH01-FIT-DIST-SW-SERVER1'", "output_fields": "id,name"}
auth["json_data"] = json.dumps(q1)
r1 = requests.post(ITOP_URL, data=auth).json()
dev_id = list(r1["objects"].keys())[0].split("::")[-1]

print(f"Getting lnkConnectableCIToNetworkDevice for device ID {dev_id}...")
q2 = {"operation": "core/get", "class": "lnkConnectableCIToNetworkDevice", "key": f"SELECT lnkConnectableCIToNetworkDevice WHERE networkdevice_id={dev_id}", "output_fields": "id"}
auth["json_data"] = json.dumps(q2)
r2 = requests.post(ITOP_URL, data=auth).json()

links = []
if "objects" in r2 and r2["objects"]:
    for obj in r2["objects"].values():
        links.append(obj["key"].split("::")[-1])

print(f"Found {len(links)} links. Deleting...")

for i, link_id in enumerate(links, 1):
    del_q = {"operation": "core/delete", "class": "lnkConnectableCIToNetworkDevice", "key": link_id, "comment": "Deleting orphaned links after Mikrotik migration"}
    auth["json_data"] = json.dumps(del_q)
    r = requests.post(ITOP_URL, data=auth).json()
    if r.get("code") == 0:
        print(f"[{i}/{len(links)}] Deleted Link ID: {link_id}")
    else:
        print(f"[{i}/{len(links)}] Failed to delete {link_id}: {r}")

print("Done!")
