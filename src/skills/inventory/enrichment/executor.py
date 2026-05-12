from fastapi import FastAPI
import redis
import json
import logging
import psycopg2
import sys
import os

# Menyesuaikan path agar bisa mengimport tools modular
sys.path.append("/home/infra/dcim_metrics_project")

# Import dari struktur modular yang baru
from src.configs.database import get_db_config
from src.schemas.transformers.asset_metadata import extract_metadata

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="DCIM Enrichment API (v3.4 Logic in v4.0 Structure)")

DB_CONFIG = get_db_config()

# Connect to Redis
try:
    redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    redis_client.ping()
    logger.info("Connected to Redis successfully.")
except Exception as e:
    logger.error(f"Failed to connect to Redis: {e}")

def lookup_sql_fallback(serial_number: str):
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        query = """
            SELECT hostname, serial_number, site, manufacturer, model, 
                   rack_name, rack_position, asset_status, business_unit, environment
            FROM unified_assets 
            WHERE LOWER(serial_number) = %s OR LOWER(hostname) = %s
            LIMIT 1
        """
        cur.execute(query, (serial_number.lower(), serial_number.lower()))
        row = cur.fetchone()
        if row:
            # Menggunakan logika ekstraksi v3.4 yang tersimpan di schemas
            meta = extract_metadata(row)
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
            "enrichment_match_confidence": "none"
        }
    data_str = redis_client.get(f"asset:{ident_clean.lower()}")
    data = json.loads(data_str) if data_str else None
    method = "serial_number"
    confidence = "high"
    if not data:
        data = lookup_sql_fallback(ident_clean)
        if data:
            method = "sql_fallback"
            confidence = "medium"
    status = determine_enrichment_status(ident_clean, data)
    if data:
        data["enrichment_status"] = status
        data["enrichment_match_method"] = method
        data["enrichment_match_confidence"] = confidence
        return data
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

@app.get("/unknown-assets")
def unknown_assets():
    assets = redis_client.smembers("unknown_assets")
    return {"unknown_assets": list(assets), "count": len(assets)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
