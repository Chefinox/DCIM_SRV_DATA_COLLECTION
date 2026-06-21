from src.tools.messaging.kafka_client import KafkaClient
import time
import json

client = KafkaClient()
consumer = client.get_consumer("dcim.raw.hardware.server", "test-raw-server-" + str(int(time.time())))

for msg in consumer:
    try:
        val = msg.value()
        if isinstance(val, dict):
            name = val.get("name", "")
            if name == "server_redfish_util":
                print("Found in dcim.raw.hardware.server:", json.dumps(val, indent=2))
                break
    except Exception as e:
        pass
