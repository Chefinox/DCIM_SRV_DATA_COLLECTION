import json
import sys
if "/home/infra/dcim_metrics_project" not in sys.path:
    sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger
logger = setup_logger("dcim_dlq_consumer", "/home/infra/dcim_metrics_project/logs/dcim_dlq_consumer.log")

import os
import psycopg2
from kafka import KafkaConsumer
from dotenv import load_dotenv
import datetime
import time
from src.utils.lineage import track_lineage

# Load configuration (optional fallback)
load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

def read_secret(name: str, fallback: str = None) -> str:
    secret_path = f"/run/secrets/dcim/{name.lower()}"
    try:
        with open(secret_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.getenv(name, fallback)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "127.0.0.1:9094")
ssl_kwargs = {}
if "9094" in KAFKA_BROKER:
    ssl_kwargs = {
        "security_protocol": "SSL",
        "ssl_cafile": "/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem",
        "ssl_check_hostname": False
    }
DLQ_TOPICS = [
    "dcim.dlq.parse-failure",
    "dcim.dlq.enrichment-failure",
    "dcim.dlq.delivery-failure"
]

DB_CONFIG = {
    "host":     read_secret("SOT_DB_HOST", "localhost"),  # Migrated: was 192.168.101.73, now dcim_sot_postgres container
    "database": read_secret("SOT_DB_NAME", "dcim_sot"),
    "user":     read_secret("SOT_DB_USER", "sot_admin"),
    "password": read_secret("SOT_DB_PASS", "Inovasi@0918")
}

def log_to_db(topic, payload, reason):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        sql = """
            INSERT INTO dlq_records (topic, original_payload, failure_reason)
            VALUES (%s, %s, %s)
        """
        cur.execute(sql, (topic, payload, reason))
        conn.commit()
        cur.close()
        conn.close()
        
        log_entry = {
            "timestamp": str(datetime.datetime.now()),
            "level": "INFO",
            "topic": topic,
            "status": "LOGGED_TO_DB",
            "reason": reason
        }
        logger.info(json.dumps(log_entry))
        
    except Exception as e:
        error_entry = {
            "timestamp": str(datetime.datetime.now()),
            "level": "ERROR",
            "message": f"DB Logging Error: {e}",
            "topic": topic
        }
        logger.info(json.dumps(error_entry))

def main():
    logger.info(f"Starting DCIM DLQ Consumer for topics: {DLQ_TOPICS}")
    
    while True:
        try:
            consumer = KafkaConsumer(
                *DLQ_TOPICS,
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='dcim_dlq_persistence_group',
                value_deserializer=lambda x: x.decode('utf-8') if x else None,
                **ssl_kwargs
            )

            for message in consumer:
                topic = message.topic
                payload = message.value
                # Try to extract failure reason from headers if available
                reason = f"Failure from {topic}"
                if message.headers:
                    for key, val in message.headers:
                        if key == 'error.message' or key == 'failure.reason':
                            reason = val.decode('utf-8')
                            break
                            
                log_to_db(topic, payload, reason)
                
                try:
                    payload_dict = json.loads(payload)
                    event_id = payload_dict.get("event_id")
                    if event_id:
                        track_lineage(
                            event_id=event_id,
                            stage="stored",
                            status="dlq",
                            target_topic=topic,
                            error_message=reason
                        )
                except Exception:
                    pass
                
        except Exception as e:
            error_entry = {
                "timestamp": str(datetime.datetime.now()),
                "level": "CRITICAL",
                "message": f"Kafka Consumer Error: {e}. Reconnecting in 5s..."
            }
            logger.info(json.dumps(error_entry))
            time.sleep(5)

if __name__ == "__main__":
    main()
