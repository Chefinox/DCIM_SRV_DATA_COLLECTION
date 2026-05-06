import psycopg2
import redis
import json
import os
import time
import logging
from datetime import datetime
from tenacity import retry, stop_after_attempt, wait_exponential
from dcim_common import DB_CONFIG, extract_metadata

# Structured Logging
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module
        }
        if hasattr(record, "extra_data"):
            log_entry.update(record.extra_data)
        return json.dumps(log_entry)

logger = logging.getLogger("dcim_sync")
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

@retry(stop=stop_after_attempt(5), wait=wait_exponential(multiplier=1, min=2, max=10))
def get_redis_client():
    client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    client.ping()
    return client

def sync_assets(full_sync=False):
    start_time = time.time()
    r = get_redis_client()
    
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        query = "SELECT hostname, serial_number, site, raw_payload FROM unified_assets"
        if not full_sync:
            query += " WHERE last_synced >= NOW() - INTERVAL '10 minutes'"
            mode = "delta"
        else:
            mode = "full"
            
        cur.execute(query)
        rows = cur.fetchall()
        
        count = 0
        for row in rows:
            meta = extract_metadata(row)
            sn = meta["serial_number"]
            if not sn: continue
            
            sn_clean = str(sn).lower().strip()
            # Set with 12 hour TTL
            r.setex(f"asset:{sn_clean}", 43200, json.dumps(meta))
            count += 1
            
        duration = time.time() - start_time
        logger.info(f"{mode.capitalize()} sync complete", extra={"extra_data": {
            "mode": mode,
            "count": count,
            "duration_seconds": round(duration, 2)
        }})
        
        meta_key = "sync:metadata"
        health = r.get(meta_key)
        health_data = json.loads(health) if health else {}
        health_data[f"last_{mode}_sync"] = datetime.utcnow().isoformat()
        health_data[f"last_{mode}_count"] = count
        health_data["consecutive_failures"] = 0
        r.set(meta_key, json.dumps(health_data))
        
        cur.close()
        conn.close()
        return count
        
    except Exception as e:
        logger.error(f"Sync failed: {e}")
        r = get_redis_client()
        health = r.get("sync:metadata")
        health_data = json.loads(health) if health else {}
        health_data["consecutive_failures"] = health_data.get("consecutive_failures", 0) + 1
        health_data["last_error"] = str(e)
        r.set("sync:metadata", json.dumps(health_data))
        raise

if __name__ == "__main__":
    logger.info("Starting DCIM Unified Sync Service (Opsi 1: Delta Sync)")
    try:
        sync_assets(full_sync=True)
    except: pass
    
    last_full_sync = datetime.now()
    while True:
        try:
            now = datetime.now()
            is_full = (now - last_full_sync).total_seconds() > 3600
            sync_assets(full_sync=is_full)
            if is_full: last_full_sync = now
            time.sleep(300)
        except KeyboardInterrupt: break
        except Exception: time.sleep(30)
