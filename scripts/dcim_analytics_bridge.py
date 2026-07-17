#!/usr/bin/env python3
"""
DCIM Analytics Bridge — Read from dcim.enriched.events (Avro), push to dcim.analytics.metrics (JSON)
Fallback enrichment: calls enrichment API when ci_id is None from NiFi.
"""
import json
import logging
import os
import signal
import sys
import time
import urllib.request

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
ENRICHMENT_API_URL = os.getenv('ENRICHMENT_API_URL', 'http://127.0.0.1:8000')

running = True
fallback_enrich_cache = {}  # simple in-memory cache to avoid hammering API

def enrich_fallback(sn, hostname=None):
    """Fallback: call enrichment API directly when NiFi didn't populate ci_id/asset_id.
    Supports both serial_number and hostname-based lookup."""
    if sn and sn not in ('NO_IDENTIFIER', 'NO_SN', 'Unknown_Host'):
        if sn in fallback_enrich_cache:
            return fallback_enrich_cache[sn]
        try:
            url = f"{ENRICHMENT_API_URL}/enrich/{sn}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                ci = data.get('ci_id')
                aid = data.get('asset_id')
                fallback_enrich_cache[sn] = (ci, aid)
                if ci:
                    log.info(f"Fallback enrichment (sn): sn={sn} → ci_id={ci}")
                return (ci, aid)
        except Exception as e:
            log.debug(f"Fallback enrichment failed for sn={sn}: {e}")

    # Hostname-based fallback for devices with NO_IDENTIFIER
    if hostname and hostname not in ('Unknown_Host', 'NO_IDENTIFIER', ''):
        cache_key = f"hn:{hostname}"
        if cache_key in fallback_enrich_cache:
            return fallback_enrich_cache[cache_key]
        try:
            url = f"{ENRICHMENT_API_URL}/enrich/{hostname}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode())
                ci = data.get('ci_id')
                aid = data.get('asset_id')
                fallback_enrich_cache[cache_key] = (ci, aid)
                if ci:
                    log.info(f"Fallback enrichment (hostname): host={hostname} → ci_id={ci}")
                return (ci, aid)
        except Exception as e:
            log.debug(f"Fallback enrichment failed for host={hostname}: {e}")

    return (None, None)

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
        msgs = consumer.consume(num_messages=500, timeout=1.0)
        
        now = time.time()
        if now - last_log_time >= 60.0:
            log.info(f"Bridge status: forwarded {processed_count} events in the last minute.")
            processed_count = 0
            last_log_time = now
            producer.flush()

        if not msgs:
            continue
            
        for msg in msgs:
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
                
                # Extract value from metric_value or raw_fields
                val = msg_val.get("metric_value")
                metric_name = msg_val.get("metric_name", "")
                
                if val is None and isinstance(msg_val.get("raw_fields"), dict):
                    raw_fields = msg_val["raw_fields"]
                    if metric_name in raw_fields:
                        val = raw_fields[metric_name]
                    else:
                        # Fallbacks for known NiFi mappings
                        if metric_name == "interface_status" and "if_oper_status" in raw_fields:
                            val = raw_fields["if_oper_status"]
                        elif "temperature" in metric_name and "temperature_celsius" in raw_fields:
                            val = raw_fields["temperature_celsius"]
                        else:
                            # Try to find a matching key
                            for k, v in raw_fields.items():
                                if k.replace('_', '') in metric_name.replace('_', '') or metric_name.replace('_', '') in k.replace('_', ''):
                                    val = v
                                    break
                            # If still None, just take the first numeric value
                            if val is None:
                                for v in raw_fields.values():
                                    if isinstance(v, (int, float)):
                                        val = v
                                        break

                # Get ci_id/asset_id from NiFi enrichment, fallback to direct API call
                ci_id = msg_val.get("ci_id")
                asset_id = msg_val.get("asset_id")
                sn = msg_val.get("serial_number")
                hostname = msg_val.get("hostname")
                if not ci_id:
                    fallback_ci, fallback_ai = enrich_fallback(sn, hostname)
                    if fallback_ci:
                        ci_id = fallback_ci
                        asset_id = fallback_ai

                payload = {
                    "timestamp": msg_val.get("event_time"),
                    "metric_name": msg_val.get("metric_name"),
                    "ci_id": ci_id,
                    "asset_id": asset_id,
                    "source_system": msg_val.get("source_system"),
                    "device_type": msg_val.get("device_type"),
                    "metric_unit": msg_val.get("metric_unit"),
                    "payload": {
                        "value": val,
                        "value_txt": msg_val.get("metric_value_txt")
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
        
        producer.poll(0)
            
    producer.flush()
    consumer.close()
    log.info("Analytics Bridge stopped gracefully.")

if __name__ == "__main__":
    run()
