#!/usr/bin/env python3
"""
DCIM SIEM Elasticsearch Consumer — Read from dcim.siem.alerts, push to ES
"""
import json, logging, time, urllib3
import requests
from datetime import datetime
from confluent_kafka import Consumer

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger(__name__)

ES_URL = "https://10.70.0.56:9200/_bulk"
ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def run():
    consumer_conf = {
        'bootstrap.servers': 'localhost:9094',
        'group.id': 'dcim-siem-es-consumer-2',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': False,
        'security.protocol': 'SSL',
        'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
        'enable.ssl.certificate.verification': False
    }
    consumer = Consumer(consumer_conf)
    consumer.subscribe(["dcim.siem.alerts"])
    
    log.info(json.dumps({"event": "siem_es_consumer_started", "topic": "dcim.siem.alerts"}))
    batch_size = 50
    batch = []
    
    last_flush_time = time.time()
    
    while True:
        msg = consumer.poll(1.0)
        
        now = time.time()
        # Flush if we have something and 5 seconds passed
        if len(batch) > 0 and now - last_flush_time > 5.0:
            payload = "\n".join(batch) + "\n"
            resp = requests.post(ES_URL, auth=ES_AUTH, data=payload, headers={'Content-Type': 'application/x-ndjson'}, verify=False)
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
            # We expect msg.value() to be a raw string (syslog) or JSON byte array
            raw_msg = msg.value().decode('utf-8', errors='replace').strip()
            if not raw_msg:
                continue

            event_time = datetime.utcnow()
            index_date = event_time.strftime("%Y.%m.%d")
            
            # Try to parse as JSON in case it's structured, else store as raw message
            try:
                parsed_msg = json.loads(raw_msg)
                if isinstance(parsed_msg, dict):
                    msg_val = parsed_msg
                    if "@timestamp" not in msg_val:
                        msg_val["@timestamp"] = event_time.isoformat() + "Z"
                else:
                    msg_val = {"@timestamp": event_time.isoformat() + "Z", "message": raw_msg}
            except json.JSONDecodeError:
                msg_val = {"@timestamp": event_time.isoformat() + "Z", "message": raw_msg}
                
            index_name = f"dcim-siem-alerts-{index_date}"
            
            action = {"index": {"_index": index_name}}
            batch.append(json.dumps(action))
            batch.append(json.dumps(msg_val))
            
            if len(batch) >= batch_size * 2:
                payload = "\n".join(batch) + "\n"
                resp = requests.post(ES_URL, auth=ES_AUTH, data=payload, headers={'Content-Type': 'application/x-ndjson'}, verify=False)
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
