import requests
import json
import urllib3
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ITOP_URL = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER = "admin"
ITOP_PASS = "Inovasi@0918"

servers = [
    {"ip": "10.50.0.3", "name": "FALAH01-SERVER-HCI-02"},
    {"ip": "10.50.0.4", "name": "FALAH01-SERVER-HCI-03"},
    {"ip": "10.50.0.5", "name": "FALAH01-SERVER-RENDER-01"},
    {"ip": "10.50.0.6", "name": "FALAH01-SERVER-RENDER-02"}
]

BMC_USER = "hndept"
BMC_PASS = "F!tech@0918"

def get_redfish_data(ip):
    # Get System Info
    r = requests.get(f"https://{ip}/redfish/v1/Systems/1", auth=(BMC_USER, BMC_PASS), verify=False, timeout=10)
    sys_data = r.json()
    
    cpu_model = sys_data.get('ProcessorSummary', {}).get('Model', '')
    cpu_count = sys_data.get('ProcessorSummary', {}).get('Count', 1)
    cpu_str = f"{cpu_count}x {cpu_model}" if cpu_count > 1 else cpu_model
    
    ram_gb = sys_data.get('MemorySummary', {}).get('TotalSystemMemoryGiB', '')
    ram_str = f"{ram_gb}GB" if ram_gb else ""
    
    serial = sys_data.get('SerialNumber', '')
    
    # Get Chassis Info for RU
    r_chassis = requests.get(f"https://{ip}/redfish/v1/Chassis/1", auth=(BMC_USER, BMC_PASS), verify=False, timeout=10)
    chassis_data = r_chassis.json()
    height = chassis_data.get('HeightMm', 0)
    # Assume 1U is ~44.45mm
    if height:
        ru = round(float(height) / 44.45)
    else:
        ru = ""
        
    return {
        "managementip": ip,
        "cpu": cpu_str,
        "ram": ram_str,
        "serialnumber": serial,
        "asset_number": serial,
        "nb_u": str(ru) if ru else ""
    }

for s in servers:
    print(f"Processing {s['name']} ({s['ip']})...")
    try:
        data = get_redfish_data(s['ip'])
        
        payload = {
            "operation": "core/update",
            "class": "Server",
            "key": f"SELECT Server WHERE name='{s['name']}'",
            "output_fields": "id, name",
            "fields": data,
            "comment": "Batch update from Redfish via AI agent"
        }

        response = requests.post(
            ITOP_URL,
            data={
                "auth_user": ITOP_USER,
                "auth_pwd": ITOP_PASS,
                "json_data": json.dumps(payload)
            }
        )
        print(f"Update Result for {s['name']}: {response.json()}")
    except Exception as e:
        print(f"Error processing {s['name']}: {e}")
    time.sleep(1)
