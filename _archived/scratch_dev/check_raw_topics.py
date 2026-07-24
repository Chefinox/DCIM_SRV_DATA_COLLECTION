from confluent_kafka import Consumer
import json

c = Consumer({
    'bootstrap.servers': 'localhost:9092',
    'group.id': 'debug-raw-topics-1',
    'auto.offset.reset': 'earliest'
})

topics = c.list_topics().topics
raw_topics = [t for t in topics if t.startswith('dcim.raw.')]
print(f"Found raw topics: {raw_topics}")

for t in raw_topics:
    c.subscribe([t])
    msg = c.poll(3.0)
    if msg is None:
        print(f"[{t}] No message found.")
    elif msg.error():
        print(f"[{t}] Error: {msg.error()}")
    else:
        val = msg.value()
        try:
            parsed = json.loads(val.decode('utf-8'))
            print(f"[{t}] OK: Valid JSON")
        except Exception as e:
            print(f"[{t}] INVALID JSON: {val[:50]}... Error: {e}")

c.close()
