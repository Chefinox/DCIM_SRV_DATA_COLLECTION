import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER = "admin"
ITOP_PASS = "Inovasi@0918"

# Data to update
update_data = {
    "managementip": "10.50.0.2",
    "cpu": "2x Intel(R) Xeon(R) Gold 5416S",
    "ram": "256GB",
    "nb_u": "2",
    "serialnumber": "J901GKXY",
    "asset_number": "J901GKXY" # Using serial as asset tag since asset tag was empty
}

payload = {
    "operation": "core/update",
    "class": "Server",
    "key": "SELECT Server WHERE name='FALAH01-SERVER-HCI-01'",
    "output_fields": "id, name, cpu, ram, serialnumber",
    "fields": update_data,
    "comment": "Update from Redfish via AI agent"
}

response = requests.post(
    ITOP_URL,
    data={
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload)
    }
)

print(response.json())
