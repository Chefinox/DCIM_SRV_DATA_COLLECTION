import requests, json
ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
data = {"auth_user": "admin", "auth_pwd": "literal:<SET_LOCALLY>", "json_data": json.dumps({"operation": "core/get", "class": "Peripheral", "key": "SELECT Peripheral", "output_fields": "*", "limit": 1}) }
r = requests.post(ITOP_URL, data=data).json()
print(json.dumps(r, indent=2))
