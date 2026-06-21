from kafka import KafkaConsumer
import json
import time

consumer = KafkaConsumer(
    "dcim.enriched.events",
    bootstrap_servers="localhost:9092",
    group_id="test-debug-" + str(int(time.time())),
    auto_offset_reset="latest",
    consumer_timeout_ms=10000
)

print("Listening to dcim.enriched.events for 10s...")
for msg in consumer:
    try:
        val = json.loads(msg.value.decode('utf-8'))
        print("Message:", val.get("hostname"), val.get("serial_number"))
    except Exception as e:
        print("Error decoding:", e)
