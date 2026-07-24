import requests
import json

ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
auth = {"auth_user": "admin", "auth_pwd": "Inovasi@0918"}

# get device id
q1 = {"operation": "core/get", "class": "NetworkDevice", "key": "SELECT NetworkDevice WHERE name='FALAH01-FIT-DIST-SW-SERVER1'", "output_fields": "id,name"}
auth["json_data"] = json.dumps(q1)
r1 = requests.post(ITOP_URL, data=auth).json()
dev_id = list(r1["objects"].keys())[0].split("::")[-1]

# get interfaces
q2 = {"operation": "core/get", "class": "PhysicalInterface", "key": f"SELECT PhysicalInterface WHERE connectableci_id={dev_id}", "output_fields": "name"}
auth["json_data"] = json.dumps(q2)
r2 = requests.post(ITOP_URL, data=auth).json()

interfaces = []
if "objects" in r2 and r2["objects"]:
    for obj in r2["objects"].values():
        interfaces.append({"id": obj["key"], "name": obj["fields"]["name"]})

print(json.dumps(interfaces, indent=2))
