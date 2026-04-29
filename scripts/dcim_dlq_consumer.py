import json
import os
import psycopg2
from kafka import KafkaConsumer
from dotenv import load_dotenv
import datetime
import time

# Load configuration (optional fallback)
load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

def read_secret(name: str, fallback: str = None) -> str:
    secret_path = f"/run/secrets/dcim/{name.lower()}"
    try:
        with open(secret_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.getenv(name, fallback)

KAFKA_BROKER = os.getenv("KAFKA_BROKER", "127.0.0.1:9092")
DLQ_TOPICS = [
    "dcim.dlq.parse-failure",
    "dcim.dlq.enrichment-failure",
    "dcim.dlq.delivery-failure"
]

DB_CONFIG = {
    "host":     read_secret("SOT_DB_HOST", "192.168.101.73"),
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
        print(json.dumps(log_entry))
        
    except Exception as e:
        error_entry = {
            "timestamp": str(datetime.datetime.now()),
            "level": "ERROR",
            "message": f"DB Logging Error: {e}",
            "topic": topic
        }
        print(json.dumps(error_entry))

def main():
    print(f"Starting DCIM DLQ Consumer for topics: {DLQ_TOPICS}")
    
    while True:
        try:
            consumer = KafkaConsumer(
                *DLQ_TOPICS,
                bootstrap_servers=[KAFKA_BROKER],
                auto_offset_reset='earliest',
                enable_auto_commit=True,
                group_id='dcim_dlq_persistence_group',
                value_deserializer=lambda x: x.decode('utf-8') if x else None
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
                
        except Exception as e:
            error_entry = {
                "timestamp": str(datetime.datetime.now()),
                "level": "CRITICAL",
                "message": f"Kafka Consumer Error: {e}. Reconnecting in 5s..."
            }
            print(json.dumps(error_entry))
            time.sleep(5)

if __name__ == "__main__":
    main()
