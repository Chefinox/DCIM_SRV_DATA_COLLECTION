from kafka import KafkaConsumer
import json
try:
    consumer = KafkaConsumer('dcim.raw.hardware.server', bootstrap_servers='127.0.0.1:9092', auto_offset_reset='earliest', consumer_timeout_ms=5000)
    for msg in consumer:
        print(msg.value.decode('utf-8'))
        break
except Exception as e:
    print("Error:", e)
