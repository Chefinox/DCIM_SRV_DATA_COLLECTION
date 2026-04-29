import requests
import json
import urllib3
import sys

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
USER = "hndept"
PASS = "F!tech@0918"

for ip in SERVERS:
    metrics = {
        "address": ip,
        "device_type": "server",
        "host": "srv-rnd-dcim"
    }
    
    # Systems/1
    try:
        r = requests.get(f"https://{ip}/redfish/v1/Systems/1", auth=(USER, PASS), verify=False, timeout=2)
        if r.status_code == 200:
            d = r.json()
            metrics["SerialNumber"] = d.get("SerialNumber", "")
            metrics["HostName"] = d.get("HostName", "")
            metrics["BiosVersion"] = d.get("BiosVersion", "")
            metrics["PowerState"] = d.get("PowerState", "")
            metrics["Status_Health"] = d.get("Status", {}).get("Health", "")
            metrics["ProcessorSummary_Count"] = d.get("ProcessorSummary", {}).get("Count", 0)
            metrics["ProcessorSummary_LogicalProcessorCount"] = d.get("ProcessorSummary", {}).get("LogicalProcessorCount", 0)
            metrics["MemorySummary_TotalSystemMemoryGiB"] = d.get("MemorySummary", {}).get("TotalSystemMemoryGiB", 0)
            metrics["Oem_Lenovo_TotalPowerOnHours"] = d.get("Oem", {}).get("Lenovo", {}).get("TotalPowerOnHours", 0)
    except Exception as e:
        pass
        
    # Chassis/1
    try:
        r = requests.get(f"https://{ip}/redfish/v1/Chassis/1", auth=(USER, PASS), verify=False, timeout=2)
        if r.status_code == 200:
            d = r.json()
            metrics["Model"] = d.get("Model", "")
            metrics["Manufacturer"] = d.get("Manufacturer", "Lenovo")
            metrics["Oem_Lenovo_ProductName"] = d.get("Oem", {}).get("Lenovo", {}).get("ProductName", "")
            if d.get("PowerState"): metrics["PowerState"] = d.get("PowerState")
            if d.get("Status", {}).get("Health"): metrics["Status_Health"] = d.get("Status", {}).get("Health")
    except Exception as e:
        pass
        
    # Managers/1
    try:
        r = requests.get(f"https://{ip}/redfish/v1/Managers/1", auth=(USER, PASS), verify=False, timeout=2)
        if r.status_code == 200:
            d = r.json()
            metrics["FirmwareVersion"] = d.get("FirmwareVersion", "")
    except Exception as e:
        pass
        
    # Map Universal Tags (8 Points - Clean Naming)
    metrics["model"] = metrics.get("Model", "")
    metrics["manufacturer"] = metrics.get("Manufacturer", "Lenovo")
    metrics["serial_number"] = metrics.get("SerialNumber", "")
    metrics["hostname"] = metrics.get("HostName", "")
    metrics["firmware"] = metrics.get("FirmwareVersion", "")
    metrics["ip"] = metrics["address"]
    metrics["device_type"] = "server"
    metrics["category"] = "infrastructure"
    
    print(json.dumps(metrics))
    sys.stdout.flush()
