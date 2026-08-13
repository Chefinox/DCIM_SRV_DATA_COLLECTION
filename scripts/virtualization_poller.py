import requests
import json
import time
from datetime import datetime, timezone
from confluent_kafka import Producer
import os
import uuid

# Kafka configuration
KAFKA_BROKERS = "10.70.0.56:9092,10.70.0.56:9093,10.70.0.56:9094"
TOPIC = "dcim.events.raw"

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
    api_url = "http://localhost:8081/api2/json/cluster/resources"
    
    try:
        response = requests.get(api_url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            
            # Simple python-based normalization acting as Jolt substitute for Python environment
            vms = data.get('data', [])
            
            for vm in vms:
                # Basic Normalization matching vm-normalize.jolt logic
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
                
                # Publish to Kafka
                producer.produce(TOPIC, key=normalized_event["hostname"], value=json.dumps(normalized_event))
                
            producer.flush()
            print(f"[{datetime.now().isoformat()}] Published {len(vms)} VM events to {TOPIC}")
        else:
            print(f"[{datetime.now().isoformat()}] Failed to poll Mock API: Status {response.status_code}")
    except Exception as e:
        print(f"[{datetime.now().isoformat()}] Error polling Mock API: {e}")

if __name__ == "__main__":
    poll_and_publish()
