from locust import HttpUser, task, between
import json
import uuid
import random
from datetime import datetime, timezone

class DCIMTelemetryLoadTest(HttpUser):
    # This assumes an HTTP endpoint exists for ingesting telemetry, or that we're
    # just sending payloads to the pipeline entrypoint. 
    # For a purely Kafka-based ingestion, we'd need a custom Locust client, 
    # but since NiFi typically offers an HTTP ingestion endpoint (e.g. for Webhooks),
    # we simulate the load towards that endpoint or the mock ones.
    
    wait_time = between(0.1, 0.5) # Simulate rapid firing to approach 430 eps if scaled

    @task(3)
    def post_valid_telemetry(self):
        payload = {
            "hostname": f"srv-load-{random.randint(1, 100)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metrics": {
                "cpu_usage": random.uniform(0, 100),
                "memory_usage": random.uniform(0, 100)
            }
        }
        # In a real environment, this goes to the NiFi ListenHTTP endpoint.
        # Since we don't have the exact NiFi URL in this script, we'll mock hitting localhost:8080
        # for structural verification purposes.
        self.client.post("/", json=payload)

    @task(1)
    def post_invalid_telemetry(self):
        payload = {
            "hostname": "srv-invalid",
            # Missing timestamp
            "metrics": {
                "cpu_usage": 150 # Out of bounds
            }
        }
        self.client.post("/", json=payload)
