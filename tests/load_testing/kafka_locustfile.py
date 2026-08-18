import time
import json
import random
import uuid
from datetime import datetime, timezone
from locust import User, task, between
from confluent_kafka import Producer

KAFKA_BROKERS = "10.70.0.56:9092,10.70.0.56:9093,10.70.0.56:9094"
TOPIC = "dcim.events.raw"

class KafkaClient:
    def __init__(self, brokers):
        self.producer = Producer({'bootstrap.servers': brokers})

    def send(self, topic, key, value):
        self.producer.produce(topic, key=key, value=value)
        self.producer.poll(0) # trigger delivery reports

    def flush(self):
        self.producer.flush()

class KafkaUser(User):
    abstract = True
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.client = KafkaClient(KAFKA_BROKERS)

class DCIMKafkaLoadTest(KafkaUser):
    wait_time = between(0.01, 0.05) # Very fast to reach high EPS
    
    @task(3)
    def send_valid_telemetry(self):
        start_time = time.time()
        hostname = f"srv-load-{random.randint(1, 100)}"
        payload = {
            "event_id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": hostname,
            "source_system": "load-test-generator",
            "resource_type": "server",
            "event_type": "telemetry",
            "metrics": {
                "cpu_usage": random.uniform(0, 100),
                "memory_usage": random.uniform(0, 100)
            }
        }
        
        try:
            self.client.send(TOPIC, key=hostname, value=json.dumps(payload))
            self.client.flush() # Wait for delivery report for true latency
            # Report success to locust
            self.environment.events.request.fire(
                request_type="Kafka",
                name="Produce Valid Event",
                response_time=(time.time() - start_time) * 1000,
                response_length=len(json.dumps(payload)),
                exception=None
            )
        except Exception as e:
            self.environment.events.request.fire(
                request_type="Kafka",
                name="Produce Valid Event",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e
            )

    @task(1)
    def send_invalid_telemetry(self):
        start_time = time.time()
        payload = {
            "event_id": str(uuid.uuid4()),
            # "timestamp": missing on purpose for validation testing
            "hostname": "srv-invalid-1",
            "source_system": "load-test-generator",
            "resource_type": "server",
            "event_type": "telemetry",
            "metrics": {
                "cpu_usage": 200, # Out of bounds (0-100)
                "memory_usage": -10 
            }
        }
        
        try:
            self.client.send(TOPIC, key="srv-invalid", value=json.dumps(payload))
            self.client.flush()
            self.environment.events.request.fire(
                request_type="Kafka",
                name="Produce Invalid Event",
                response_time=(time.time() - start_time) * 1000,
                response_length=len(json.dumps(payload)),
                exception=None
            )
        except Exception as e:
             self.environment.events.request.fire(
                request_type="Kafka",
                name="Produce Invalid Event",
                response_time=(time.time() - start_time) * 1000,
                response_length=0,
                exception=e
            )

    def on_stop(self):
        self.client.flush()
