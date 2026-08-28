import sys
sys.path.append("/opt/nifi/nifi-current")
import requests
import json
from datetime import datetime, timezone
import uuid
import sys

def poll_and_print():
    # URL of our Mock API (Port 8085)
    api_url = "http://localhost:8085/api2/json/cluster/resources"
    
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            vms = data.get('data', [])
            
            for vm in vms:
                # Telegraf Standard JSON Format (tags & fields) for Normalizer compatibility
                status_val = 1 if vm.get("status") == "running" else 0
                cpu_pct = float(vm.get("cpu", 0.0)) * 100.0
                
                telegraf_payload = {
                    "name": "dcim_virtualization_utilization",
                    "tags": {
                        "hostname": vm.get("name", "unknown_vm"),
                        "device_type": "virtual_machine",
                        "category": "virtualization",
                        "source_system": "proxmox-mock-api",
                        "ip": vm.get("ip", "10.70.0.30")
                    },
                    "fields": {
                        "status": status_val,
                        "cpu_utilization": cpu_pct,
                        "memory_used_bytes": int(vm.get("mem", 0)),
                        "memory_total_bytes": int(vm.get("maxmem", 0)),
                        "disk_used_bytes": int(vm.get("disk", 0)),
                        "disk_total_bytes": int(vm.get("maxdisk", 0)),
                        "uptime_seconds": int(vm.get("uptime", 0))
                    },
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Print to STDOUT so NiFi ExecuteProcess / Pipeline can capture it
                print(json.dumps(telegraf_payload))
            
            sys.stdout.flush()
        else:
            pass
    except Exception as e:
        pass

if __name__ == "__main__":
    poll_and_print()
