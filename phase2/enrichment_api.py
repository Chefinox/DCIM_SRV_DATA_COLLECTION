from fastapi import FastAPI
import redis
import json
import logging
import psycopg2
from dcim_common import DB_CONFIG, extract_metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DCIM Enrichment API (Hybrid Fallback)")

# Connect to Redis
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis successfully.")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")

def lookup_sql_fallback(serial_number: str):
    """
    Opsi 2: Hybrid Fallback.
    If Redis Miss, query PostgreSQL unified_assets directly.
    """
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Check by serial_number (case insensitive) or hostname
        query = """
            SELECT hostname, serial_number, site, raw_payload 
            FROM unified_assets 
            WHERE LOWER(serial_number) = %s OR LOWER(hostname) = %s
            LIMIT 1
        """
        cur.execute(query, (serial_number.lower(), serial_number.lower()))
        row = cur.fetchone()
        
        if row:
            meta = extract_metadata(row)
            # Cache it immediately for 1 hour
            redis_client.setex(f"asset:{serial_number.lower()}", 3600, json.dumps(meta))
            logger.info(f"Fallback Hit: Asset {serial_number} found in SQL and cached.")
            return meta
            
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"SQL Fallback failed: {e}")
    
    return None

def determine_enrichment_status(serial_number: str, data: dict) -> str:
    if not serial_number or serial_number.upper() in ("NO_IDENTIFIER", "NO_SN", "UNKNOWN", ""):
        return "NO_IDENTIFIER"
    if not data or data.get("is_fallback_placeholder"):
        return "NOT_IN_CMDB"
    
    has_site = bool(data.get("site") and data.get("site") != "Unknown")
    has_rack = bool(data.get("rack_name") and data.get("rack_name") != "Unknown")
    
    return "FULL" if (has_site and has_rack) else "PARTIAL"

@app.get("/enrich/{identifier}")
def get_enrichment(identifier: str):
    """
    Lookup an asset by serial number in Redis, with SQL fallback.
    """
    ident_clean = identifier.strip()
    ident_upper = ident_clean.upper()
    is_no_id = ident_upper in ("NO_IDENTIFIER", "NO_SN", "UNKNOWN", "")
    if is_no_id:
        redis_client.sadd("assets:no_identifier", ident_clean)
        return {
            "site": None,
            "rack_name": None,
            "manufacturer": None,
            "model": None,
            "serial_number": identifier,
            "enrichment_status": "NO_IDENTIFIER",
            "enrichment_match_method": "blocked",
            "enrichment_match_confidence": "none",
            "note": "hostname fallback disabled for unknown devices"
        }

    # 2. Fast Path: Redis
    data_str = redis_client.get(f"asset:{ident_clean.lower()}")
    data = json.loads(data_str) if data_str else None
    method = "serial_number"
    confidence = "high"

    # 3. SQL Fallback if not in Redis
    if not data:
        data = lookup_sql_fallback(ident_clean)
        if data:
            method = "sql_fallback"
            confidence = "medium"

    # 4. Final Status Determination
    status = determine_enrichment_status(ident_clean, data)
    
    if data:
        data["enrichment_status"] = status
        data["enrichment_match_method"] = method
        data["enrichment_match_confidence"] = confidence
        return data
    
    # 5. Not Found in CMDB
    redis_client.sadd("unknown_assets", ident_clean.lower())
    return {
        "site": "Unknown",
        "rack_name": "Unknown",
        "manufacturer": "Unknown",
        "model": "Unknown",
        "serial_number": identifier,
        "enrichment_status": "NOT_IN_CMDB",
        "enrichment_match_method": "none",
        "enrichment_match_confidence": "none"
    }

@app.get("/sync/status")
def sync_status():
    meta = redis_client.get("sync:metadata")
    return json.loads(meta) if meta else {"error": "no sync metadata found"}

@app.get("/unknown-assets")
def unknown_assets():
    assets = redis_client.smembers("unknown_assets")
    return {"unknown_assets": list(assets), "count": len(assets)}
