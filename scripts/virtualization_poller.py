import sys
sys.path.append("/opt/nifi/nifi-current")
import requests
import json
import time
from datetime import datetime, timezone
from confluent_kafka import Producer
import os
import uuid

# Kafka configuration
KAFKA_BROKERS = "10.70.0.56:9092"
TOPIC = "dcim.raw.virtualization"

def get_kafka_producer():
    conf = {
        'bootstrap.servers': KAFKA_BROKERS,
        'client.id': 'virtualization-poller'
    }
    return Producer(conf)

def poll_and_publish():
    # Setup Kafka Producer
    producer = get_kafka_producer()
    
    # URL of our Mock API
    api_url = "http://localhost:8085/api2/json/cluster/resources"
    
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Simple python-based normalization acting as Jolt substitute for Python environment
            vms = data.get('data', [])
            
            for vm in vms:
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
                
                # Publish to Kafka
                producer.produce(TOPIC, key=telegraf_payload["tags"]["hostname"], value=json.dumps(telegraf_payload))
                
            producer.flush()
            print(f"[{datetime.now().isoformat()}] Published {len(vms)} VM events to {TOPIC}")
        else:
            print(f"[{datetime.now().isoformat()}] Failed to poll Mock API: Status {response.status_code}")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error polling Mock API: {e}")

if __name__ == "__main__":
    poll_and_publish()
