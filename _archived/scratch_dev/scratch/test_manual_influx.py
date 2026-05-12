from kafka import KafkaProducer
import time

KAFKA_BROKER = 'localhost:9092'
TOPIC = 'dcim.metrics.enriched'

producer = KafkaProducer(bootstrap_servers=KAFKA_BROKER)

# Simple valid influx line
# measurement,tag1=v1 field1=1.0 timestamp(ns)
ts = int(time.time() * 1000000000)
line = f"test_measurement,site=Manual_Test value=100.0 {ts}"

print(f"Sending manual line: {line}")
producer.send(TOPIC, value=line.encode('utf-8'))
producer.flush()
print("Sent.")
