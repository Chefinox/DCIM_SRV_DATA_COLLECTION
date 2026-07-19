#!/usr/bin/env python3
"""
iTop → Redis Cache Sync Script (v4.0)

Menarik data CI dari iTop REST API dan menyimpannya ke Redis sebagai enrichment cache.
Menggantikan cmdb_to_cache_sync.py (PostgreSQL → Redis) dengan iTop sebagai metadata authority.

Arsitektur:
  iTop REST API → Parse CI → Redis (asset:sn:{serialnumber})

Usage:
  python3 scripts/itop_to_cache_sync.py

Systemd:
  systemctl start dcim-itop-redis-sync.service
"""

import json
import os
import sys
import time
import logging
import requests
import redis
from datetime import datetime, timezone

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
if "/home/infra/dcim_metrics_project" not in sys.path:
    sys.path.append("/home/infra/dcim_metrics_project")

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

from src.observability.logging.dcim_logger import setup_logger
logger = setup_logger("itop-redis-sync", "/home/infra/dcim_metrics_project/logs/itop_to_cache_sync.log")

# ---------------------------------------------------------------------------
# Secrets / Config
# ---------------------------------------------------------------------------
def read_secret(name: str, fallback: str = None) -> str:
    """Read secret from /run/secrets/dcim/ or environment variable."""
    secret_path = f"/run/secrets/dcim/{name.lower()}"
    try:
        if os.path.exists(secret_path):
            with open(secret_path) as f:
                return f.read().strip()
    except Exception as e:
        logger.warning(f"Could not read secret {secret_path}: {e}")
    return os.getenv(name, fallback)


# Load .env if python-dotenv available (optional, not required)
try:
    from dotenv import load_dotenv
    _env_path = os.path.join(os.path.dirname(__file__), "..", "configs", ".env")
    if os.path.exists(_env_path):
        load_dotenv(_env_path)
except ImportError:
    pass

# iTop config
ITOP_URL  = os.getenv("ITOP_API_URL", "http://localhost:8080/webservices/rest.php?version=1.3")
ITOP_USER = read_secret("ITOP_API_USER", os.getenv("ITOP_API_USER", "admin"))
ITOP_PASS = read_secret("ITOP_API_PASS", os.getenv("ITOP_API_PASS", "Inovasi@0918"))

# Redis config
REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
REDIS_DB   = int(os.getenv("REDIS_DB", "0"))
CACHE_TTL  = int(os.getenv("CACHE_TTL", "3600"))  # 1 hour

# iTop CI classes to sync
ITOP_CLASSES = [
    {
        "class": "Server",
        "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,managementip,business_criticity,org_id_friendlyname",
    },
    {
        "class": "NetworkDevice",
        "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,managementip,business_criticity,org_id_friendlyname",
    },
    {
        "class": "StorageSystem",
        "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,business_criticity,org_id_friendlyname",
    },
    {
        "class": "NAS",
        "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,business_criticity,org_id_friendlyname",
    },
    {
        "class": "Peripheral",
        "fields": "name,serialnumber,location_name,brand_name,model_name,status,business_criticity,org_id_friendlyname",
    },
    {
        "class": "PowerSource",
        "fields": "name,serialnumber,location_name,brand_name,model_name,status,business_criticity,org_id_friendlyname",
    },
]

# ---------------------------------------------------------------------------
# Ralph Asset Repository config (for asset_id lookup)
# ---------------------------------------------------------------------------
RALPH_API_BASE = os.getenv("RALPH_API_BASE", "http://localhost:8082/api")

# Token resolution: env var (if real value) > secrets file > hardcoded default
_ralph_token_env = os.getenv("RALPH_API_TOKEN_NEW", "")
if _ralph_token_env and "<see_docker_secrets>" not in _ralph_token_env:
    RALPH_TOKEN = _ralph_token_env
else:
    RALPH_TOKEN    = read_secret("ralph_api_token") or "1cd05b8d36e258399a52c59f1a4016addb2346a3"
RALPH_HEADERS  = {"Authorization": f"Token {RALPH_TOKEN}"}

RALPH_ENDPOINTS = [
    "data-center-assets",
    "back-office-assets",
]


def get_ralph_asset_id(serial_number: str, hostname: str = "") -> str | None:
    """Look up Ralph Asset ID by serial_number, fallback to hostname.

    Returns Ralph asset ID as UUID string, or None if not found.
    Ralph natively uses integer IDs; we convert to UUID format for
    TimescaleDB compatibility (same approach as iTop ci_id).
    """
    import uuid

    if not serial_number or serial_number.upper() in ("NO_IDENTIFIER", "NO_SN", "UNKNOWN", ""):
        return None

    for endpoint in RALPH_ENDPOINTS:
        try:
            url = f"{RALPH_API_BASE}/{endpoint}/?sn={serial_number}"
            r = requests.get(url, headers=RALPH_HEADERS, timeout=5)
            if r.ok:
                data = r.json()
                results = data.get("results", [])
                if results:
                    ralph_int_id = results[0]["id"]
                    ralph_uuid = str(uuid.UUID(int=int(ralph_int_id)))
                    logger.debug(f"Ralph lookup OK: sn={serial_number} → ralph_id={ralph_int_id} (UUID: {ralph_uuid}) via {endpoint}")
                    return ralph_uuid
        except Exception as e:
            logger.debug(f"Ralph lookup failed for sn={serial_number} via {endpoint}: {e}")
            continue

    # Fallback: search by hostname
    if hostname:
        for endpoint in RALPH_ENDPOINTS:
            try:
                url = f"{RALPH_API_BASE}/{endpoint}/?hostname={hostname}"
                r = requests.get(url, headers=RALPH_HEADERS, timeout=5)
                if r.ok:
                    data = r.json()
                    results = data.get("results", [])
                    if results:
                        ralph_int_id = results[0]["id"]
                        ralph_uuid = str(uuid.UUID(int=int(ralph_int_id)))
                        logger.debug(f"Ralph lookup OK (hostname): host={hostname} → ralph_id={ralph_int_id} via {endpoint}")
                        return ralph_uuid
            except Exception as e:
                logger.debug(f"Ralph hostname lookup failed for {hostname}: {e}")
                continue

    return None


# ---------------------------------------------------------------------------
# iTop API Client
# ---------------------------------------------------------------------------
def itop_get(ci_class: str, output_fields: str, limit: int = 200) -> dict:
    """Execute core/get query against iTop REST API. Returns raw response dict."""
    payload = {
        "operation": "core/get",
        "class": ci_class,
        "key": f"SELECT {ci_class}",
        "output_fields": output_fields,
        "limit": limit,
    }
    data = {
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload),
    }
    try:
        r = requests.post(ITOP_URL, data=data, timeout=30)
        r.raise_for_status()
        result = r.json()
        if result.get("code", 0) != 0:
            logger.error(f"iTop API error for {ci_class}: {result.get('message')}")
            return {}
        return result
    except requests.exceptions.RequestException as e:
        logger.error(f"iTop HTTP error for {ci_class}: {e}")
        return {}
    except json.JSONDecodeError as e:
        logger.error(f"iTop JSON decode error for {ci_class}: {e}")
        return {}


# ---------------------------------------------------------------------------
# Redis Client
# ---------------------------------------------------------------------------
redis_client = None


def get_redis() -> redis.Redis:
    """Get or create Redis connection."""
    global redis_client
    if redis_client is None:
        redis_client = redis.Redis(
            host=REDIS_HOST, port=REDIS_PORT, db=REDIS_DB,
            decode_responses=True, socket_timeout=5,
        )
    return redis_client


# ---------------------------------------------------------------------------
# Core Sync Logic
# ---------------------------------------------------------------------------
def build_metadata(ci_class: str, fields: dict, ci_key: str) -> dict:
    """Build Redis metadata dict from iTop CI fields.

    ci_id is sourced from iTop CMDB (integer key → UUID).
    asset_id is sourced from Ralph Asset Repository (integer ID → UUID).
    If Ralph has no matching asset, asset_id is None (no fallback to ci_id).
    """
    import uuid
    try:
        # Convert iTop integer ID to a valid UUID format (e.g., 3096 -> 00000000-0000-0000-0000-000000000c18)
        # This is required because the PostgreSQL metrics table uses the UUID type for these columns.
        ci_uuid = str(uuid.UUID(int=int(ci_key)))
    except (ValueError, TypeError):
        ci_uuid = None

    # Look up Ralph Asset ID by serial_number, fallback to hostname
    serial_number = (fields.get("serialnumber") or "").strip()
    hostname      = (fields.get("name") or "").strip()
    ralph_asset_uuid = get_ralph_asset_id(serial_number, hostname)

    return {
        "sn": serial_number,
        "name": hostname,
        "location": fields.get("location_name", ""),
        "rack": fields.get("rack_name", ""),
        "brand": fields.get("brand_name", ""),
        "model": fields.get("model_name", ""),
        "status": fields.get("status", ""),
        "managementip": fields.get("managementip", ""),
        "ci_class": ci_class,
        "criticality": fields.get("business_criticity", ""),
        "org": fields.get("org_id_friendlyname", ""),
        "ci_id": ci_uuid,
        "asset_id": ralph_asset_uuid,   # from Ralph Asset Repository, NOT iTop
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }


def sync_one_class(ci_class: str, output_fields: str, r: redis.Redis) -> tuple[int, int]:
    """Sync all CIs of one class to Redis. Returns (synced, skipped)."""
    synced = 0
    skipped = 0

    result = itop_get(ci_class, output_fields)
    if not result:
        logger.warning(f"No response from iTop for class {ci_class}, skipping")
        return 0, 0

    objects = result.get("objects", {})
    if not objects:
        logger.info(f"No CIs found for class {ci_class}")
        return 0, 0

    for key, ci in objects.items():
        ci_code = ci.get("code", -1)
        if ci_code != 0:
            logger.warning(f"CI {key} returned code {ci_code}: {ci.get('message', '')}")
            skipped += 1
            continue

        fields = ci.get("fields", {})
        serial_number = (fields.get("serialnumber") or "").strip()
        hostname = (fields.get("name") or "").strip()
        management_ip = (fields.get("managementip") or "").strip()

        if not serial_number and not hostname and not management_ip:
            skipped += 1
            continue

        try:
            meta = build_metadata(ci_class, fields, str(ci.get("key", "")))
            
            # Map by Serial Number
            if serial_number:
                sn_key = f"asset:sn:{serial_number.lower()}"
                r.setex(sn_key, CACHE_TTL, json.dumps(meta))
            
            # Map by Hostname (simulate legacy behavior for enrichment via hostname)
            if hostname:
                host_key = f"asset:sn:{hostname.lower()}"
                r.setex(host_key, CACHE_TTL, json.dumps(meta))
                
                no_prefix = hostname.lower().replace("falah01-", "").strip()
                if no_prefix != hostname.lower():
                    r.setex(f"asset:sn:{no_prefix}", CACHE_TTL, json.dumps(meta))
            
            # Map by IP Address
            if management_ip:
                ip_key = f"asset:ip:{management_ip}"
                r.setex(ip_key, CACHE_TTL, json.dumps(meta))
                
                # SIEM/Legacy uses IP in the SN field
                r.setex(f"asset:sn:{management_ip}", CACHE_TTL, json.dumps(meta))
                
            synced += 1
        except Exception as e:
            logger.error(f"Failed to write CI {key} to Redis: {e}")
            skipped += 1

    return synced, skipped


def run_sync():
    """Run one sync iteration: fetch all classes from iTop → write to Redis."""
    r = get_redis()

    # Verify Redis is reachable before doing anything
    try:
        r.ping()
    except Exception as e:
        logger.error(f"Redis not reachable: {e}. Skipping this iteration.")
        return

    # Verify iTop is reachable with a lightweight call
    test = itop_get("Server", "name", limit=1)
    if not test:
        logger.error("iTop API not reachable. Skipping this iteration. Redis NOT flushed.")
        return

    total_synced = 0
    total_skipped = 0

    for cls_cfg in ITOP_CLASSES:
        ci_class = cls_cfg["class"]
        fields = cls_cfg["fields"]
        synced, skipped = sync_one_class(ci_class, fields, r)
        total_synced += synced
        total_skipped += skipped
        logger.info(f"  [{ci_class}] Synced: {synced}, Skipped: {skipped}")

    # Count current Redis keys matching our pattern
    try:
        redis_keys = len(r.keys("asset:sn:*"))
    except Exception:
        redis_keys = -1

    logger.info(
        f"Sync complete — Synced: {total_synced}, Skipped: {total_skipped}, "
        f"Redis keys (asset:sn:*): {redis_keys}"
    )


# ---------------------------------------------------------------------------
# Main Loop
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    logger.info("Starting iTop → Redis Cache Sync (v4.0)")
    logger.info(f"iTop URL: {ITOP_URL}")
    logger.info(f"Redis: {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}, TTL: {CACHE_TTL}s")
    logger.info(f"Classes: {[c['class'] for c in ITOP_CLASSES]}")

    while True:
        try:
            run_sync()
        except Exception as e:
            logger.error(f"Unexpected error in sync loop: {e}", exc_info=True)
        time.sleep(60)
