#!/usr/bin/env python3
"""
DCIM Elasticsearch Consumer — Read from Avro, push to ES
"""
import json, logging, os, time, urllib3
import requests
from datetime import datetime
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField
import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.schemas.avro_schemas import ENRICHED_EVENT_SCHEMA
from src.utils.secrets import get_secret

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

ES_URL = "https://10.70.0.56:9200/_bulk"

def get_es_auth():
    passw = get_secret("elastic_pass", fallback_env="ELASTIC_PASSWORD")
    if not passw:
        secret_path = "/run/secrets/dcim/elastic_pass"
        if os.path.exists(secret_path):
            try:
                with open(secret_path, "r") as f:
                    passw = f.read().strip()
            except Exception:
                pass
    return ("elastic", passw or "")

def send_bulk_to_es(payload):
    auth = get_es_auth()
    resp = requests.post(ES_URL, auth=auth, data=payload, headers={'Content-Type': 'application/x-ndjson'}, verify=False)
    if resp.status_code == 401:
        log.warning("Received 401 from ES, retrying secret lookup...")
        auth = get_es_auth()
        resp = requests.post(ES_URL, auth=auth, data=payload, headers={'Content-Type': 'application/x-ndjson'}, verify=False)
    return resp

def run():
    schema_registry_conf = {'url': 'http://localhost:8081'}
    schema_registry_client = SchemaRegistryClient(schema_registry_conf)
    avro_deserializer = AvroDeserializer(schema_registry_client, ENRICHED_EVENT_SCHEMA)
    
    consumer_conf = {
        'bootstrap.servers': '10.70.0.56:9094,10.70.0.56:9096,10.70.0.56:9098',
        'group.id': 'dcim-es-consumer',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': False,
        'security.protocol': 'SSL',
        'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
        'enable.ssl.certificate.verification': False
    }
    consumer = Consumer(consumer_conf)
    consumer.subscribe(["dcim.enriched.events"])
    
    log.info(json.dumps({"event": "es_consumer_started", "topic": "dcim.enriched.events"}))
    batch_size = 50
    batch = []
    
    last_flush_time = time.time()
    
    while True:
        msg = consumer.poll(1.0)
        
        now = time.time()
        # Flush if we have something and 5 seconds passed
        if len(batch) > 0 and now - last_flush_time > 5.0:
            payload = "\n".join(batch) + "\n"
            resp = send_bulk_to_es(payload)
            if resp.status_code in (200, 201):
                consumer.commit(asynchronous=False)
                log.info(json.dumps({"event": "batch_committed_es_timeout", "count": len(batch)//2}))
            else:
                log.error(f"ES indexing failed: {resp.status_code} {resp.text}")
            batch.clear()
            last_flush_time = time.time()

        if msg is None:
            continue
        if msg.error():
            log.error(f"Consumer error: {msg.error()}")
            continue
            
        try:
            val = msg.value()
            ctx = SerializationContext("dcim.enriched.events", MessageField.VALUE)
            msg_val = None
            
            # Check for Avro magic byte (0x00)
            if val and val.startswith(b'\x00'):
                try:
                    msg_val = avro_deserializer(val, ctx)
                except Exception as de_err:
                    log.error(json.dumps({"event": "avro_deserialization_error", "error": str(de_err)}))
                    continue
            else:
                # Fallback to pure JSON if no magic byte
                try:
                    msg_val = json.loads(val.decode('utf-8', errors='replace'))
                except Exception as je_err:
                    log.error(json.dumps({"event": "json_deserialization_error", "error": str(je_err)}))
                    continue

            if not msg_val or not isinstance(msg_val, dict): 
                continue
            
            # Parse raw JSON strings back to dict safely
            if 'raw_fields' in msg_val and isinstance(msg_val['raw_fields'], str):
                try:
                    msg_val['raw_fields'] = json.loads(msg_val['raw_fields'])
                except Exception:
                    pass
                    
            if 'raw_tags' in msg_val and isinstance(msg_val['raw_tags'], str):
                try:
                    msg_val['raw_tags'] = json.loads(msg_val['raw_tags'])
                except Exception:
                    pass
                
            event_time = msg_val.get("event_time")
            if not event_time:
                timestamp_val = msg_val.get("timestamp")
                if timestamp_val:
                    try:
                        event_time = datetime.utcfromtimestamp(float(timestamp_val)).isoformat() + "+00:00"
                    except Exception:
                        continue
                else:
                    continue
                
            try:
                dt = datetime.fromisoformat(event_time.replace('Z', '+00:00'))
                index_date = dt.strftime("%Y.%m.%d")
                msg_val["@timestamp"] = event_time
            except Exception:
                index_date = datetime.utcnow().strftime("%Y.%m.%d")
                msg_val["@timestamp"] = datetime.utcnow().isoformat() + "Z"
                
            index_name = f"dcim-metrics-unified-{index_date}"
            
            action = {"index": {"_index": index_name}}
            batch.append(json.dumps(action))
            batch.append(json.dumps(msg_val))
            
            if len(batch) >= batch_size * 2:
                payload = "\n".join(batch) + "\n"
                resp = send_bulk_to_es(payload)
                if resp.status_code in (200, 201):
                    consumer.commit(asynchronous=False)
                    log.info(json.dumps({"event": "batch_committed_es", "count": len(batch)//2}))
                else:
                    log.error(f"ES indexing failed: {resp.status_code} {resp.text}")
                batch.clear()
                last_flush_time = time.time()
        except Exception as e:
            log.error(json.dumps({"event": "insert_error", "error": str(e)}))

if __name__ == "__main__":
    run()

