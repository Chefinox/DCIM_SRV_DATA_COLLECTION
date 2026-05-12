import json
import time
from kafka import KafkaConsumer

KAFKA_BROKER = 'localhost:9092'
TOPICS = ['dcim.metrics.raw', 'dcim.metrics.enriched']

for topic in TOPICS:
    print(f"\n--- Peeking into {topic} (LATEST) ---")
    consumer = KafkaConsumer(
        topic,
        bootstrap_servers=KAFKA_BROKER,
        auto_offset_reset='latest',
        enable_auto_commit=False,
        consumer_timeout_ms=10000
    )
    
    # Pre-poll to move to end
    consumer.poll(timeout_ms=1000)
    
    print("Waiting for new messages...")
    count = 0
    for message in consumer:
        print(f"Key: {message.key}, Value: {message.value[:200]}...")
        count += 1
        if count >= 3: break
    
    if count == 0:
        print("No new messages found within 10s.")
