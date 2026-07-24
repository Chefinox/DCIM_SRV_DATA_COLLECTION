import requests, json
ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
data = {"auth_user": "admin", "auth_pwd": "Inovasi@0918", "json_data": json.dumps({"operation": "core/get", "class": "Peripheral", "key": "SELECT Peripheral WHERE name='FALAH01-CM-01'", "output_fields": "*"}) }
r = requests.post(ITOP_URL, data=data).json()
print(json.dumps(r, indent=2))
