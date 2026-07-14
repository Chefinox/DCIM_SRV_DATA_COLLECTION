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


def determine_enrichment_status(serial_number: str, data: dict) -> str:
    """Determine enrichment completeness status.
    Supports both iTop-sourced metadata (v4.0) and legacy PG-sourced metadata (v3.x).
    """
    if not serial_number or serial_number.upper() in ("NO_IDENTIFIER", "NO_SN", "UNKNOWN", ""):
        return "NO_IDENTIFIER"
    if not data or data.get("is_fallback_placeholder"):
        return "NOT_IN_CMDB"
    # v4.0 (iTop): 'location', 'rack', 'brand', 'model', 'ci_class'
    # v3.x (legacy): 'site', 'rack_name', 'manufacturer', 'model', 'device_type'
    has_site = bool(data.get("location") or data.get("site"))
    has_rack = bool(data.get("rack") or (data.get("rack_name") and data.get("rack_name") != "Unknown"))
    has_identity = bool(
        (data.get("brand") and data.get("model"))
        or (data.get("manufacturer") and data.get("manufacturer") != "Unknown" and data.get("model"))
    )
    ci_class = data.get("ci_class") or data.get("device_type") or ""
    if ci_class.lower() in ("peripheral", "cctv") or data.get("ralph_endpoint") == "back-office-assets":
        return "FULL" if (has_site and has_identity) else "PARTIAL"
    return "FULL" if (has_site and has_rack and has_identity) else "PARTIAL"

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
    # Try with sn: prefix first (primary lookup)
    data_str = redis_client.get(f"asset:sn:{ident_clean.lower()}")
    data = json.loads(data_str) if data_str else None
    method = "serial_number"
    confidence = "high"
    
    # Fallback to old format without sn: prefix (legacy compatibility)
    if not data:
        data_str = redis_client.get(f"asset:{ident_clean.lower()}")
        data = json.loads(data_str) if data_str else None
        if data:
            method = "cache_fallback"

    # Fallback for IP Address lookup (SIEM Enrichment via agent.ip)
    if not data:
        data_str = redis_client.get(f"asset:ip:{ident_clean.lower()}")
        data = json.loads(data_str) if data_str else None
        if data:
            method = "ip_address"
            confidence = "high"

    # Cache miss — return empty enrichment (no SQL fallback, v4.0 iTop metadata authority)
    if not data:
        logger.warning(f"Cache miss for SN: {ident_clean} — returning empty enrichment")
        redis_client.sadd("unknown_assets", ident_clean.lower())
        return {
            "sn": ident_clean,
            "enriched": False,
            "enrichment_status": "NOT_IN_CMDB",
            "enrichment_match_method": "none",
            "enrichment_match_confidence": "none",
            "reason": "cache_miss"
        }

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
