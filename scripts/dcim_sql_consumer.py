import json
import os
import psycopg2
from kafka import KafkaConsumer
from dotenv import load_dotenv
import re
import datetime

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
KAFKA_TOPIC  = os.getenv("KAFKA_TOPIC", "dcim.enriched.events")

DB_CONFIG = {
    "host":     read_secret("SOT_DB_HOST", "192.168.101.73"),
    "database": read_secret("SOT_DB_NAME", "dcim_sot"),
    "user":     read_secret("SOT_DB_USER", "sot_admin"),
    "password": read_secret("SOT_DB_PASS", "Inovasi@0918")
}

def update_db(data):
    if not data: return
    
    # Extract the nested attributes payload if present
    attrs = data.get('attributes', {})
    inner_data = attrs.get('0', data) if '0' in attrs else data

    # Filter: Hanya proses measurement yang relevan untuk SQL SOT
    measurement = inner_data.get('name') or inner_data.get('measurement')
    if measurement not in ['dcim_inventory', 'cctv_metrics']:
        return

    t = inner_data.get('tags', {})
    f = inner_data.get('fields', {})

    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()

        # Mapping data ke kolom device_metrics
        hostname      = t.get('hostname') or f.get('hostname', 'unknown')
        sn            = t.get('serial_number') or f.get('serial_number', 'unknown')
        ip            = t.get('ip') or f.get('ip_address', '0.0.0.0')
        dev_type      = t.get('device_type') or f.get('device_type', 'unknown')
        category      = t.get('category') or f.get('category', 'infrastructure')
        model         = t.get('model') or f.get('model', '')
        firmware      = t.get('firmware') or f.get('firmware_version', '')
        site          = f.get('site') or t.get('site', 'FIT-Head-Office')
        rack          = f.get('rack_name') or t.get('rack_name', 'Unknown')
        
        status        = f.get('status_text') or f.get('status', 'Unknown')
        power_state   = f.get('power_state', 'Unknown')
        enrich_status = f.get('enrichment_status') or t.get('enrichment_status', 'FULL')

        # Metrik Numerik
        util          = f.get('metric_utilization') or f.get('cpu_utilization', '')
        temp          = f.get('metric_temperature', '')
        power_w       = f.get('metric_power_watts', '')
        health        = f.get('metric_health') or t.get('state', 'OK')

        sql = """
            INSERT INTO device_metrics (
                collected_at, hostname, serial_number, ip_address,
                device_type, category, model, firmware_version,
                site, rack_name, status, power_state, enrichment_status,
                metric_utilization, metric_temperature, metric_power_watts,
                metric_health, metrics_raw
            ) VALUES (
                NOW(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
        """
        
        cur.execute(sql, (
            hostname, sn, ip, dev_type, category, model, firmware,
            site, rack, status, power_state, enrich_status,
            util, temp, power_w, health, json.dumps(data)
        ))
        
        conn.commit()
        cur.close()
        conn.close()
        print(f"[{datetime.datetime.now()}] Persisted to Postgres: {hostname} ({dev_type})")
        
    except Exception as e:
        print(f"DB Error: {e}")

def main():
    print(f"Starting JSON SQL Consumer for topic: {KAFKA_TOPIC}")
    
    def safe_json_decode(v):
        if v is None or len(v) == 0:
            return None
        try:
            return json.loads(v.decode('utf-8'))
        except Exception as e:
            print(f"JSON Decode Error: {e} | Raw data: {v}")
            return None

    consumer = KafkaConsumer(
        KAFKA_TOPIC,
        bootstrap_servers=[KAFKA_BROKER],
        auto_offset_reset='latest',
        enable_auto_commit=True,
        group_id='dcim_sql_persistence_group_v3',
        value_deserializer=safe_json_decode
    )

    for message in consumer:
        if message.value:
            update_db(message.value)

if __name__ == "__main__":
    main()
