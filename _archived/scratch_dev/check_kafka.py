from kafka import KafkaConsumer
import json

topics = ['dcim.raw.hardware.server', 'dcim.raw.power.ups', 'dcim.raw.storage.nas', 'dcim.raw.device.isapi']
for t in topics:
    try:
        consumer = KafkaConsumer(t, bootstrap_servers='127.0.0.1:9092', auto_offset_reset='earliest', consumer_timeout_ms=1000)
        messages = list(consumer)
        print(f"Topic {t} has {len(messages)} messages")
        consumer.close()
    except Exception as e:
        print(f"Error checking topic {t}: {e}")
