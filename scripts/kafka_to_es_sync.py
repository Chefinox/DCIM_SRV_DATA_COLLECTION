import json
import os
import requests
from confluent_kafka import Consumer, KafkaError
from elasticsearch import Elasticsearch
from datetime import datetime
from functools import lru_cache

# Config
KAFKA_BROKER = '127.0.0.1:9092'
KAFKA_TOPIC = 'dcim.normalized.events'  # BYPASS NIFI (Enriched)
ES_URL = 'https://10.70.0.56:9200'
ES_USER = 'elastic'
ES_PASS = 'C+H+pFb*aIAqWcOo-X8q'
ENRICH_URL = 'http://127.0.0.1:8000/enrich'

# Initialize ES
es = Elasticsearch(
    [ES_URL],
    basic_auth=(ES_USER, ES_PASS),
    verify_certs=False
)

@lru_cache(maxsize=2000)
def get_enrichment(serial_number):
    if not serial_number or serial_number == "NO_SN":
        return {}
    try:
        resp = requests.get(f"{ENRICH_URL}/{serial_number}", timeout=2.0)
        if resp.status_code == 200:
            return resp.json()
    except:
        pass
    return {}

# Initialize Kafka Consumer
conf = {
    'bootstrap.servers': KAFKA_BROKER,
    'group.id': 'dcim_python_es_final_v3',
    'auto.offset.reset': 'latest'
}
consumer = Consumer(conf)
consumer.subscribe([KAFKA_TOPIC])

print(f"Starting Python Kafka-to-ES Consumer (Direct Enrichment) for {KAFKA_TOPIC}...")

try:
    while True:
        msg = consumer.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            if msg.error().code() == KafkaError._PARTITION_EOF:
                continue
            else:
                print(f"Kafka Error: {msg.error()}")
                break

        try:
            data = json.loads(msg.value().decode('utf-8'))
            
            # --- Normalize Top Level Fields (since NiFi is bypassed) ---
            raw_tags = data.get('raw_tags', {})
            for field in ['hostname', 'ip', 'serial_number', 'device_type', 'measurement', 'source_topic']:
                if not data.get(field) and raw_tags.get(field):
                    data[field] = raw_tags[field]
                    
            # --- DIRECT ENRICHMENT (Bypass NiFi) ---
            sn = data.get('serial_number')
            enrich = get_enrichment(sn)
            if enrich:
                data.update(enrich)
                data['enrichment_status'] = 'FULL'
            else:
                data['enrichment_status'] = 'PARTIAL'

            # Index name based on current date
            index_name = f"dcim-metrics-unified-{datetime.utcnow().strftime('%Y.%m.%d')}"
            
            # Preserve original @timestamp from source data
            # Only fill if field is genuinely missing or empty
            if not data.get("@timestamp"):
                data["@timestamp"] = datetime.utcnow().isoformat() + "Z"

            # Index to ES
            res = es.index(index=index_name, document=data)
            # print(f"Indexed: {data.get('hostname')} ({data['enrichment_status']})")

        except Exception as e:
            print(f"Error processing/indexing: {e}")

except KeyboardInterrupt:
    pass
finally:
    consumer.close()
