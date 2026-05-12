import json
from kafka import KafkaConsumer

KAFKA_BROKER = 'localhost:9092'
TOPICS = ['dcim.metrics.raw', 'dcim.metrics.enriched']

for topic in TOPICS:
    print(f"\n--- Peeking into {topic} ---")
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset='earliest',
        enable_auto_commit=False,
        consumer_timeout_ms=5000
    )
    
    count = 0
    for message in consumer:
        print(f"Key: {message.key}, Value: {message.value[:100]}...")
        count += 1
        if count >= 5: break
    
    if count == 0:
        print("No messages found.")
