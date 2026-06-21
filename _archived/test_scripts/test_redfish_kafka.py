from src.tools.messaging.kafka_client import KafkaClient
import time
import json

client = KafkaClient()
consumer = client.get_consumer("dcim-metrics", "test-redfish-" + str(int(time.time())))
print("Listening to dcim-metrics for server_redfish_util...")

count = 0
for msg in consumer:
    try:
        val = msg.value()
        if isinstance(val, dict):
            name = val.get("name", "")
            if name == "server_redfish_util":
                print("Found server_redfish_util in Kafka:", json.dumps(val, indent=2))
                count += 1
                if count >= 2:
                    break
    except Exception as e:
        print("Error processing msg:", e)
