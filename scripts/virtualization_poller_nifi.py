import sys
sys.path.append("/opt/nifi/nifi-current")
import requests
import json
from datetime import datetime, timezone
import uuid
import sys

def poll_and_print():
    # URL of our Mock API
    # Since NiFi runs with network_mode: host, it can reach localhost:8081
    api_url = "http://localhost:8081/api2/json/cluster/resources"
    
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            vms = data.get('data', [])
            
            for vm in vms:
                # Basic Normalization 
                normalized_event = {
                    "event_id": str(uuid.uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "hostname": vm.get("name", "unknown"),
                    "source_system": "proxmox-mock-api",
                    "resource_type": "virtualization",
                    "event_type": "telemetry",
                    "metrics": {
                        "status": vm.get("status"),
                        "cpu_usage": vm.get("cpu"),
                        "memory_usage": vm.get("mem"),
                        "memory_total": vm.get("maxmem"),
                        "disk_usage": vm.get("disk"),
                        "disk_total": vm.get("maxdisk"),
                        "uptime": vm.get("uptime")
                    }
                }
                
                # Print to STDOUT so NiFi ExecuteProcess can capture it as FlowFile content
                print(json.dumps(normalized_event))
            
            # Flush stdout to ensure NiFi gets the data immediately
            sys.stdout.flush()
        else:
            # Print empty or error to avoid breaking pipeline, or handle silently like redfish_inventory_poller
            pass
    except Exception as e:
        pass

if __name__ == "__main__":
    poll_and_print()
