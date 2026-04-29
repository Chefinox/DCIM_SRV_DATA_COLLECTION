#!/usr/bin/env python3
"""
DCIM Unified Enrichment Service
Fungsi: 
  1. Konsumsi data mentah dari Kafka (dcim.metrics.raw)
  2. Lookup metadata identitas & lokasi dari DB Inventaris
  3. Standarisasi tag (location, manufacturer, state)
  4. Produksi data diperkaya ke Kafka (dcim.metrics.enriched.v2)
"""

import json
import logging
import os
import re
import time
import psycopg2
from kafka import KafkaConsumer, KafkaProducer
from dotenv import load_dotenv

# Konfigurasi Logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)
# Redam log internal Kafka
logging.getLogger('kafka').setLevel(logging.WARNING)

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

# Kafka & DB Config
KAFKA_BROKER = os.getenv("KAFKA_BROKER", "localhost:9092")
RAW_TOPIC = "dcim.metrics.raw"
ENRICHED_TOPIC = "dcim.metrics.enriched.v2"
DB_CONFIG = {
    "host": os.getenv("SOT_DB_HOST", "192.168.101.73"),
    "dbname": os.getenv("SOT_DB_NAME", "dcim_sot"),
    "user": os.getenv("SOT_DB_USER", "sot_admin"),
    "password": os.getenv("SOT_DB_PASS", "Inovasi@0918")
}

class EnrichmentEngine:
    def __init__(self):
        self.location_map = {}
        self.last_refresh = 0
        self.refresh_interval = 60 # Perkecil ke 1 menit untuk sinkronisasi cepat
        self.refresh_map()

    def refresh_map(self):
        """Memuat ulang mapping inventaris dari PostgreSQL"""
        logger.info("Refreshing Inventory Map from Database...")
        new_map = {}
        try:
            conn = psycopg2.connect(**DB_CONFIG)
            cur = conn.cursor()
            
            # 1. Map by Hostname & IP (Normalisasi NetBox & Ralph)
            cur.execute("""
                SELECT hostname, 
                       raw_payload->'primary_ip'->>'address' as ip,
                       serial_number, site, 
                       COALESCE(raw_payload->'rack'->>'name', 'Unknown') as rack,
                       COALESCE(
                           raw_payload->'device_type'->'manufacturer'->>'name',
                           raw_payload->'model'->'manufacturer'->>'name',
                           'Unknown'
                       ) as manufacturer,
                       COALESCE(
                           raw_payload->'device_type'->>'model',
                           raw_payload->'model'->>'name',
                           'Unknown'
                       ) as model,
                       source_system
                FROM unified_assets
            """)
            
            for row in cur.fetchall():
                host, ip_raw, sn, site, rack, manu, model, source_system = row
                meta = {
                    "source_system": source_system or "Unknown",
                    "site": site or "FIT-Head-Office",
                    "rack_name": rack or "Unknown",
                    "manufacturer": manu or "Unknown",
                    "model": model or "Unknown",
                    "serial_number": sn or "Unknown"
                }
                # Store with multiple lowercase keys for flexible lookup
                if host:
                    h_lower = host.lower().strip()
                    new_map[h_lower] = meta
                    # Also store without prefix if exists
                    h_no_prefix = h_lower.replace("falah01-", "").strip()
                    if h_no_prefix != h_lower:
                        new_map[h_no_prefix] = meta
                
                if ip_raw:
                    ip = ip_raw.split('/')[0].strip().lower()
                    new_map[ip] = meta
                
                if sn:
                    sn_lower = sn.strip().lower()
                    new_map[sn_lower] = meta
            
            cur.close()
            conn.close()
            self.location_map = new_map
            self.last_refresh = time.time()
            
            # Count sources for debugging
            sources = {}
            for m in new_map.values():
                s = m.get('source_system', 'Unknown')
                sources[s] = sources.get(s, 0) + 1
            
            logger.info(f"Successfully loaded {len(new_map)} entries into mapping. Distribution: {sources}")
        except Exception as e:
            logger.error(f"Failed to refresh mapping: {e}")

    def normalize_state(self, val):
        if val is None:
            return "Unknown"
        
        v = str(val).lower().strip()
        # Normalisasi ke "OK"
        if v in ["1", "online", "up", "normal", "ok", "healthy"]:
            return "OK"
        # Normalisasi ke "CRITICAL"
        if v in ["2", "offline", "down", "failed", "critical", "non-recoverable"]:
            return "CRITICAL"
        # Normalisasi ke "WARNING"
        if v in ["warning", "degraded", "minor"]:
            return "WARNING"
            
        return val # Kembalikan nilai asli jika tidak dikenal

    def enrich(self, data):
        """Menambahkan metadata ke pesan tunggal"""
        if time.time() - self.last_refresh > self.refresh_interval:
            self.refresh_map()

        # Identifier utama: hostname, ip, atau serial
        # Note: Telegraf Line Protocol diubah ke JSON biasanya punya field 'tags'
        tags = data.get("tags", {})
        fields = data.get("fields", {})
        
        # Try SN first (most unique), then IP, then Hostname
        identifiers = [
            tags.get("serial_number"),
            tags.get("ip"),
            tags.get("hostname")
        ]
        
        meta = {}
        for id_val in identifiers:
            if id_val:
                meta = self.location_map.get(str(id_val).lower().strip(), {})
                if meta: break
        
        # --- Mandatory Unified Tags ---
        tags["site"]              = meta.get("site", "FIT-Head-Office")
        tags["rack_name"]         = meta.get("rack_name", "Unknown")
        tags["location"]          = tags["rack_name"] # Align with Telegraf 'location'
        tags["manufacturer"]      = meta.get("manufacturer", tags.get("manufacturer", "Unknown"))
        tags["model"]             = meta.get("model", tags.get("model", "Unknown"))
        tags["serial_number"]     = meta.get("serial_number", tags.get("serial_number", "Unknown"))
        tags["enrichment_status"] = "FULL" if meta else "PARTIAL"
        
        # --- State Mapping (Improved & Normalized) ---
        raw_state = (
            tags.get("health") or 
            tags.get("status") or 
            fields.get("status") or 
            fields.get("health") or
            tags.get("ifOperStatus") or
            "Unknown"
        )
        tags["state"] = self.normalize_state(raw_state)

        data["tags"] = tags
        return data

def main():
    logger.info(f"Starting DCIM Enrichment Service on {KAFKA_BROKER}...")
    
    # Initialize Kafka
    try:
        consumer = KafkaConsumer(
            RAW_TOPIC,
            bootstrap_servers=KAFKA_BROKER,
            group_id='dcim-enrichment-v3',
            value_deserializer=lambda m: json.loads(m.decode('utf-8'))
        )
        
        producer = KafkaProducer(
            bootstrap_servers=KAFKA_BROKER
        )
        
        engine = EnrichmentEngine()
        
        for message in consumer:
            raw_data = message.value
            logger.info(f"Received message from topic {RAW_TOPIC}")
            
            # Helper to convert JSON back to Influx Line Protocol
            def to_influx(p):
                try:
                    # Sanitize tags (remove None/empty)
                    tags_str = ",".join([f"{k}={str(v).replace(' ', '_')}" for k, v in p['tags'].items() if v])
                    # Sanitize fields (handle strings vs numbers)
                    fields_list = []
                    for k, v in p['fields'].items():
                        if v is None: continue
                        if isinstance(v, (int, float)):
                            fields_list.append(f"{k}={v}")
                        else:
                            val = str(v).replace('"', '\\"')
                            fields_list.append(f'{k}="{val}"')
                    fields_str = ",".join(fields_list)
                    
                    timestamp = p.get('timestamp', int(time.time()))
                    # Ensure timestamp is in nanoseconds if it's in seconds
                    if timestamp < 2000000000: timestamp = timestamp * 1000000000
                    
                    full_tags = f",{tags_str}" if tags_str else ""
                    line = f"{p['name']}{full_tags} {fields_str} {timestamp}"
                    logger.debug(f"Generated Influx line: {line[:100]}...")
                    return line
                except Exception as e:
                    logger.error(f"Serialization error for {p.get('name')}: {e}")
                    return None

            if isinstance(raw_data, list):
                logger.info(f"Processing batch of {len(raw_data)} points")
                enriched_batch = [engine.enrich(p) for p in raw_data]
                for p in enriched_batch:
                    line = to_influx(p)
                    if line: 
                        producer.send(ENRICHED_TOPIC, value=line.encode('utf-8'))
                        logger.info(f"Sent enriched point: {p['name']}")
            else:
                logger.info("Processing single point")
                p = engine.enrich(raw_data)
                line = to_influx(p)
                if line: 
                    producer.send(ENRICHED_TOPIC, value=line.encode('utf-8'))
                    logger.info(f"Sent enriched point: {p['name']}")
                
            producer.flush()
            logger.info(f"Sent enriched data to {ENRICHED_TOPIC}")
            
    except Exception as e:
        logger.error(f"Critical error in service: {e}")
        time.sleep(10)

if __name__ == "__main__":
    main()
