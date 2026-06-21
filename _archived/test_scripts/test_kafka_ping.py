from src.tools.messaging.kafka_client import KafkaClient
import time
client = KafkaClient()
consumer = client.get_consumer("dcim.raw.device.ping", "test-debug-group-" + str(int(time.time())))
print("Listening to dcim.raw.device.ping...")
for msg in consumer:
    print("Found ping message:", msg.value())
