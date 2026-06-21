import json
import os
import psycopg2
from kafka import KafkaConsumer
from datetime import datetime, timedelta

# Configuration
KAFKA_BROKER = "127.0.0.1:9092"
KAFKA_TOPIC  = "dcim.enriched.events"
DB_CONFIG = {
    "host":     "192.168.101.73",
    "database": "dcim_sot",
    "user":     "sot_admin",
    "password": "Inovasi@0918"
}

# In-memory cache to track last saved hour per device
# Key: hostname, Value: last_saved_hour (YYYY-MM-DD-HH)
last_saved_cache = {}

def insert_snapshot(data):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        sql = """
            INSERT INTO dcim_enriched_snapshots (
                event_time, hostname, ip_address, serial_number,
                device_type, site, rack_name, metric_name, 
                metric_value, enrichment_status, full_payload
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.execute(sql, (
            data.get('event_time'),
            data.get('hostname'),
            data.get('ip'),
            data.get('serial_number'),
            data.get('device_type'),
            data.get('site'),
            data.get('rack_name'),
            data.get('metric_name'),
            data.get('metric_value'),
            data.get('enrichment_status'),
            json.dumps(data)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"[{datetime.now()}] Snapshot saved for: {data.get('hostname')}")
    except Exception as e:
        print(f"DB Error: {e}")

def main():
    print(f"Starting SQL Snapshot Consumer (1 record/device/hour)")
    
    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id='dcim_sql_snapshot_group_v1',
        value_deserializer=lambda v: json.loads(v.decode('utf-8'))
    )

    for message in consumer:
        data = message.value
        if not data: continue
        
        hostname = data.get('hostname', 'unknown')
        current_hour = datetime.now().strftime("%Y-%m-%d-%H")
        
        # Logic: Save only if this hour hasn't been saved for this device
        if last_saved_cache.get(hostname) != current_hour:
            insert_snapshot(data)
            last_saved_cache[hostname] = current_hour

if __name__ == "__main__":
    main()
