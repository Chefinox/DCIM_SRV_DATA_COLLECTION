import requests, json
ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
data = {"auth_user": "admin", "auth_pwd": "Inovasi@0918", "json_data": json.dumps({"operation": "core/get", "class": "Peripheral", "key": "SELECT Peripheral", "output_fields": "name,serialnumber"})}
r = requests.post(ITOP_URL, data=data).json()
for k,v in r.get("objects",{}).items():
    if not v["fields"]["serialnumber"]:
        print("Missing SN:", v["fields"]["name"])
