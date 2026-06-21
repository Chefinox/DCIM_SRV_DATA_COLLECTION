from src.tools.messaging.kafka_client import KafkaClient
import time
client = KafkaClient()
consumer = client.get_consumer("dcim.raw.device.isapi", "test-debug-group-" + str(int(time.time())))
print("Listening to dcim.raw.device.isapi...")
for msg in consumer:
    val = msg.value()
    if isinstance(val, dict):
        tags = val.get("tags", {})
        if "CCTV-IP-" in str(tags.get("serial_number", "")):
            print("Found CCTV-IP message:", val)
