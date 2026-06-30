import psycopg2
import redis
import json
import os
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def read_secret(name: str, fallback: str = None) -> str:
    secret_path = f"/run/secrets/dcim/{name.lower()}"
    try:
        with open(secret_path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return os.getenv(name, fallback)

DB_CONFIG = {
    "host":     read_secret("SOT_DB_HOST", "localhost"),  # Migrated: was 192.168.101.73, now dcim_sot_postgres container
    "dbname":   read_secret("SOT_DB_NAME", "dcim_sot"),
    "user":     read_secret("SOT_DB_USER", "sot_admin"),
    "password": read_secret("SOT_DB_PASS", "Inovasi@0918")
}

try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0)
    redis_client.ping()
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")
    exit(1)

def sync_cache():
    logger.info("Starting CMDB to Redis Sync...")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        cur.execute("""
            SELECT hostname,
                   ip::text as ip,
                   serial_number, site,
                   rack_name as rack,
                   manufacturer,
                   model,
                   device_type,
                   asset_status,
                   ralph_endpoint
            FROM unified_assets
        """)
        
        count = 0
        for row in cur.fetchall():
            host, ip_raw, sn, site, rack, manu, model, device_type, asset_status, ralph_endpoint = row
            meta = {
                "site": site or "Unknown",
                "rack_name": rack or "Unknown",
                "manufacturer": manu or "Unknown",
                "model": model or "Unknown",
                "serial_number": sn or "Unknown",
                "ip": str(ip_raw).split('/')[0].strip() if ip_raw else None,
                "device_type": device_type,
                "asset_status": asset_status,
                "ralph_endpoint": ralph_endpoint,
            }
            
            # Map by Serial Number
            if sn:
                sn_clean = str(sn).lower().strip()
                redis_client.setex(f"asset:sn:{sn_clean}", 3600, json.dumps(meta))
                redis_client.setex(f"asset:{sn_clean}", 3600, json.dumps(meta))
                count += 1
            
            # Map by Hostname
            if host:
                host_clean = str(host).lower().strip()
                redis_client.setex(f"asset:sn:{host_clean}", 3600, json.dumps(meta))
                redis_client.setex(f"asset:{host_clean}", 3600, json.dumps(meta))
                
                # Also without prefix if it exists
                no_prefix = host_clean.replace("falah01-", "").strip()
                if no_prefix != host_clean:
                    redis_client.setex(f"asset:sn:{no_prefix}", 3600, json.dumps(meta))
                    redis_client.setex(f"asset:{no_prefix}", 3600, json.dumps(meta))
            
            # Map by IP Address
            if ip_raw:
                ip_clean = str(ip_raw).split('/')[0].strip().lower()
                redis_client.setex(f"asset:sn:{ip_clean}", 3600, json.dumps(meta))
                redis_client.setex(f"asset:{ip_clean}", 3600, json.dumps(meta))
                
        logger.info(f"Successfully synced {count} primary assets to Redis Cache.")
        cur.close()
        conn.close()
        
    except Exception as e:
        logger.error(f"Error during sync: {e}")

if __name__ == "__main__":
    while True:
        sync_cache()
        # Refresh every 60 seconds
        time.sleep(60)
