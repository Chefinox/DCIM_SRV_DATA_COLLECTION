from kafka import KafkaConsumer
import json

def check_topic(topic):
    print(f"Checking topic: {topic}")
    try:
        consumer = KafkaConsumer(topic, bootstrap_servers='127.0.0.1:9092', auto_offset_reset='earliest', consumer_timeout_ms=3000)
        count = 0
        for msg in consumer:
            print(msg.value.decode('utf-8'))
            count += 1
            if count >= 2: break
        if count == 0:
            print("No data found.")
    except Exception as e:
        print("Error:", e)
    print("-" * 40)

check_topic('dcim.raw.storage.nas')
check_topic('dcim.raw.device.isapi')
