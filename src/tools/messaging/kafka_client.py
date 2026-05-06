from kafka import KafkaProducer, KafkaConsumer
import json
import os
import logging

class KafkaClient:
    def __init__(self):
        self.bootstrap_servers = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

    def get_producer(self):
        try:
            return KafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                acks='all',
                retries=3
            )
        except Exception as e:
            logging.error(f"Kafka Producer Error: {e}")
            raise

    def get_consumer(self, topic, group_id):
        try:
            return KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                group_id=group_id,
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                value_deserializer=lambda x: json.loads(x.decode('utf-8'))
            )
        except Exception as e:
            logging.error(f"Kafka Consumer Error: {e}")
            raise
