#!/usr/bin/env python3
"""
DCIM Analytics Bridge — Read from dcim.enriched.events (Avro), push to dcim.analytics.metrics (JSON)
"""
import json
import logging
import os
import signal
import sys
import time

from confluent_kafka import Consumer, Producer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

sys.path.append("/home/infra/dcim_metrics_project")
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

KAFKA_BOOTSTRAP_SERVERS = os.getenv('KAFKA_BOOTSTRAP_SERVERS', 'localhost:9094')
SCHEMA_REGISTRY_URL = os.getenv('SCHEMA_REGISTRY_URL', 'http://localhost:8081')
SOURCE_TOPIC = 'dcim.enriched.events'
TARGET_TOPIC = 'dcim.analytics.metrics'

running = True

def signal_handler(signum, frame):
    global running
    log.info(f"Received signal {signum}, shutting down...")
    running = False

def run():
    global running
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    schema_registry_conf = {'url': SCHEMA_REGISTRY_URL}
    schema_registry_client = SchemaRegistryClient(schema_registry_conf)
    avro_deserializer = AvroDeserializer(schema_registry_client, ENRICHED_EVENT_SCHEMA)
    
    consumer_conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'group.id': 'dcim-analytics-bridge',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True,
        'security.protocol': 'SSL',
        'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
        'enable.ssl.certificate.verification': False
    }
    
    producer_conf = {
        'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
        'security.protocol': 'SSL',
        'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
        'enable.ssl.certificate.verification': False
    }
    
    consumer = Consumer(consumer_conf)
    consumer.subscribe([SOURCE_TOPIC])
    producer = Producer(producer_conf)
    
    log.info(f"Analytics Bridge started. Forwarding from {SOURCE_TOPIC} (Avro) to {TARGET_TOPIC} (JSON)")
    
    processed_count = 0
    last_log_time = time.time()
    
    while running:
        msg = consumer.poll(1.0)
        
        now = time.time()
        if now - last_log_time >= 60.0:
            log.info(f"Bridge status: forwarded {processed_count} events in the last minute.")
            processed_count = 0
            last_log_time = now
            producer.flush()

        if msg is None:
            continue
        if msg.error():
            log.error(f"Consumer error: {msg.error()}")
            continue
            
        try:
            ctx = SerializationContext(SOURCE_TOPIC, MessageField.VALUE)
            msg_val = avro_deserializer(msg.value(), ctx)
            if not msg_val: 
                continue
            
            # Parse raw JSON strings back to dict if needed
            if isinstance(msg_val.get('raw_fields'), str):
                try:
                    msg_val['raw_fields'] = json.loads(msg_val['raw_fields'])
                except json.JSONDecodeError:
                    pass
            if isinstance(msg_val.get('raw_tags'), str):
                try:
                    msg_val['raw_tags'] = json.loads(msg_val['raw_tags'])
                except json.JSONDecodeError:
                    pass
            
            payload = {
                "timestamp": msg_val.get("event_time"),
                "metric_name": msg_val.get("metric_name"),
                "ci_id": msg_val.get("ci_id"),
                "asset_id": msg_val.get("asset_id"),
                "source_system": msg_val.get("source_system"),
                "device_type": msg_val.get("device_type"),
                "payload": {
                    "value": msg_val.get("field_value"),
                    "value_txt": msg_val.get("field_value_txt")
                },
                "metadata": {
                    "tags": msg_val.get("raw_tags", {})
                }
            }
            
            if msg_val.get("hostname"):
                payload["metadata"]["tags"]["hostname"] = msg_val["hostname"]
            if msg_val.get("serial_number"):
                payload["metadata"]["tags"]["serial_number"] = msg_val["serial_number"]
            if msg_val.get("model"):
                payload["metadata"]["tags"]["model"] = msg_val["model"]
            
            producer.produce(TARGET_TOPIC, value=json.dumps(payload).encode('utf-8'))
            processed_count += 1
            
        except Exception as e:
            log.error(f"Error bridging message: {e}")
            
    producer.flush()
    consumer.close()
    log.info("Analytics Bridge stopped gracefully.")

if __name__ == "__main__":
    run()
