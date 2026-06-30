#!/usr/bin/env python3
"""
iTop → Ralph CMDB Sync Script (v4.0)

Sinkronisasi aset dari iTop (metadata authority) ke Ralph Asset Management.
Menggantikan ralph_cmdb_sync.py yang membaca dari PostgreSQL.

Alur:
  1. Ambil semua CI dari iTop REST API (Server, NetworkDevice, StorageSystem, Peripheral, PowerSource)
  2. Enrichment hardware dari PostgreSQL unified_assets (RAM, CPU, disk) jika tersedia
  3. Sync ke Ralph: cari by SN → PATCH/POST

Usage:
  python3 scripts/itop_to_ralph_sync.py

Cron:
  0 2 * * * python3 scripts/itop_to_ralph_sync.py
"""

import json
import logging
import os
import sys
import re
import requests
import urllib3
from datetime import datetime

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

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
LOG_FILE = "/home/infra/dcim_metrics_project/logs/itop_to_ralph_sync.log"
logger = setup_logger("itop-ralph-sync", LOG_FILE)

# ---------------------------------------------------------------------------
# Secrets / Config
# ---------------------------------------------------------------------------
def read_secret(name: str, fallback: str = None) -> str:
    secret_path = f"/run/secrets/dcim/{name.lower()}"
    try:
        if os.path.exists(secret_path):
            with open(secret_path) as f:
                return f.read().strip()
    except Exception as e:
        logger.warning(f"Could not read secret {secret_path}: {e}")
    return os.getenv(name, fallback)


# Load .env if python-dotenv available
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

# Ralph config
RALPH_API_BASE = os.getenv("RALPH_API_BASE", "http://localhost:8082/api")
RALPH_TOKEN    = read_secret("RALPH_API_TOKEN", os.getenv("RALPH_API_TOKEN_NEW", "1cd05b8d36e258399a52c59f1a4016addb2346a3"))
RALPH_HEADERS  = {
    "Authorization": f"Token {RALPH_TOKEN}",
    "Content-Type": "application/json",
}

# PostgreSQL config (for hardware enrichment)
DB_CONFIG = {
    "host":     read_secret("SOT_DB_HOST", os.getenv("SOT_DB_HOST", "localhost")),
    "dbname":   read_secret("SOT_DB_NAME", os.getenv("SOT_DB_NAME", "dcim_sot")),
    "user":     read_secret("SOT_DB_USER", os.getenv("SOT_DB_USER", "sot_admin")),
    "password": read_secret("SOT_DB_PASS", os.getenv("SOT_DB_PASS", "Inovasi@0918")),
}

# Device type mapping: iTop class → Ralph device_type
ITOP_TO_DEVICE_TYPE = {
    "Server": "server",
    "NetworkDevice": "network_switch",
    "StorageSystem": "nas",
    "Peripheral": "peripheral",
    "PowerSource": "ups",
}

# Ralph model IDs for auto-registration
DEVICE_TYPE_MODEL_MAP = {
    "server": 26,           # ThinkSystem SR650 V3
    "ups": 34,              # APC Easy UPS 3S
    "nas": 16,              # RS2423RP
    "network_switch": 6,    # CCR2004
    "peripheral": None,     # Skip auto-register
}
DEFAULT_RACK = 3  # Rack Server 1

# iTop classes to sync
ITOP_CLASSES = [
    {"class": "Server", "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,managementip"},
    {"class": "NetworkDevice", "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,managementip"},
    {"class": "StorageSystem", "fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status"},
    {"class": "Peripheral", "fields": "name,serialnumber,location_name,brand_name,model_name,status"},
    {"class": "PowerSource", "fields": "name,serialnumber,location_name,brand_name,model_name,status"},
]


# ---------------------------------------------------------------------------
# iTop API Client
# ---------------------------------------------------------------------------
def itop_get_all(ci_class: str, output_fields: str) -> list:
    """Fetch all CIs from iTop class. Returns list of {id, class, fields}."""
    all_objects = []
    page = 1
    while True:
        payload = {
            "operation": "core/get",
            "class": ci_class,
            "key": f"SELECT {ci_class}",
            "output_fields": output_fields,
            "limit": 200,
            "page": page,
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
                break
        except requests.exceptions.RequestException as e:
            logger.error(f"iTop HTTP error for {ci_class}: {e}")
            break

        objects = result.get("objects", {})
        if not objects:
            break

        for key, ci in objects.items():
            if ci.get("code", -1) != 0:
                continue
            all_objects.append({
                "id": key.split("::")[1] if "::" in key else key,
                "class": ci.get("class", ci_class),
                "fields": ci.get("fields", {}),
            })
        page += 1
    return all_objects


# ---------------------------------------------------------------------------
# Ralph API Helpers
# ---------------------------------------------------------------------------
def ralph_get_all(url: str) -> list:
    """Fetch all pages from Ralph endpoint (handle pagination)."""
    results = []
    next_url = f"{url}&limit=200" if "?" in url else f"{url}?limit=200"
    while next_url:
        try:
            resp = requests.get(next_url, headers=RALPH_HEADERS, verify=False, timeout=15)
            if not resp.ok:
                logger.error(f"Ralph GET failed: {next_url} → {resp.status_code} {resp.text[:200]}")
                break
            data = resp.json()
            results.extend(data.get("results", []))
            next_url = data.get("next")
        except requests.exceptions.RequestException as e:
            logger.error(f"Ralph GET error: {next_url} → {e}")
            break
    return results


def find_ralph_asset_by_sn(sn: str):
    """Find Ralph asset by serial number in DC and Back Office."""
    results = ralph_get_all(f"{RALPH_API_BASE}/data-center-assets/?sn={sn}")
    if results:
        return results[0], "data-center-assets"
    results = ralph_get_all(f"{RALPH_API_BASE}/back-office-assets/?sn={sn}")
    if results:
        return results[0], "back-office-assets"
    return None, None


def auto_register_dc_asset(sn: str, hostname: str, device_type: str, ip: str = None):
    """Auto-register new device in Ralph DC Assets."""
    model_id = DEVICE_TYPE_MODEL_MAP.get(device_type)
    if not model_id:
        logger.warning(f"  [AUTO-REG] No model mapping for device_type={device_type}, skip SN={sn}")
        return None, None

    payload = {
        "sn": sn,
        "hostname": hostname or f"AUTO-{device_type.upper()}-{sn[-6:]}",
        "model": model_id,
        "rack": DEFAULT_RACK,
        "status": "in use",
        "remarks": f"Auto-registered by itop_to_ralph_sync.py | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
    }
    try:
        r = requests.post(f"{RALPH_API_BASE}/data-center-assets/",
                          headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)
        if r.ok:
            asset = r.json()
            logger.info(f"  [AUTO-REG] NEW {device_type}: {hostname} (SN:{sn}) → id={asset['id']}")
            return asset, "data-center-assets"
        else:
            logger.error(f"  [AUTO-REG] FAIL register {sn}: {r.status_code} {r.text[:200]}")
    except requests.exceptions.RequestException as e:
        logger.error(f"  [AUTO-REG] HTTP error for {sn}: {e}")
    return None, None


def update_management_ip(asset_id: int, ip: str, hostname: str, endpoint_type: str = "data-center-assets"):
    """Update or create management IP for an asset in Ralph."""
    if not ip:
        return

    # Check if ethernet exists
    eths = ralph_get_all(f"{RALPH_API_BASE}/ethernets/?base_object={asset_id}")
    eth_id = None
    for e in eths:
        if (e.get("label") or "").lower().startswith("management"):
            eth_id = e["id"]
            break
    if not eth_id and eths:
        eth_id = eths[0]["id"]
    if not eth_id:
        eth_payload = {"base_object": asset_id, "label": "Management"}
        try:
            r_eth = requests.post(f"{RALPH_API_BASE}/ethernets/", headers=RALPH_HEADERS,
                                  json=eth_payload, verify=False, timeout=15)
            if r_eth.ok:
                eth_id = r_eth.json().get("id")
        except Exception:
            pass

    # Check existing IP
    existing = ralph_get_all(f"{RALPH_API_BASE}/ipaddresses/?address={ip}")
    if existing:
        ip_obj = existing[0]
        eth_ref = ip_obj.get("ethernet")
        if isinstance(eth_ref, dict):
            bo = eth_ref.get("base_object")
            if isinstance(bo, dict) and bo.get("id") == asset_id:
                payload = {"hostname": hostname, "is_management": True}
                requests.patch(f"{RALPH_API_BASE}/ipaddresses/{ip_obj['id']}/",
                               headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)
                return
    else:
        if eth_id:
            ip_payload = {
                "address": ip,
                "hostname": hostname,
                "is_management": True,
                "ethernet": eth_id,
            }
            requests.post(f"{RALPH_API_BASE}/ipaddresses/", headers=RALPH_HEADERS,
                          json=ip_payload, verify=False, timeout=15)


# ---------------------------------------------------------------------------
# PostgreSQL Hardware Enrichment
# ---------------------------------------------------------------------------
def load_hardware_data() -> dict:
    """Load hardware data from PostgreSQL dcim_events.
    Returns dict keyed by serial_number (lowercase).
    """
    hw_data = {}
    try:
        import psycopg2
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT ON (serial_number)
                serial_number,
                srv_cpu_components, 
                srv_memory_components, 
                srv_disk_components, 
                raw_tags,
                srv_firmware,
                srv_bios_version
            FROM dcim_events
            WHERE device_type = 'server'
              AND metric_name = 'inventory_snapshot'
              AND serial_number IS NOT NULL
            ORDER BY serial_number, event_time DESC
        """)
        for row in cur.fetchall():
            sn = (row[0] or "").strip().lower()
            if not sn:
                continue
            
            cpus = row[1] or []
            memory = row[2] or []
            disks = row[3] or []
            raw_tags = row[4] or {}
            nics = raw_tags.get("nics", [])
            firmware = row[5]
            bios = row[6]
            
            cpu_count = len(cpus)
            cpu_model = cpus[0].get("model_name") if cpu_count > 0 else None
            ram_total_mb = sum([int(m.get("size", 0)) for m in memory])
            ram_total_gb = int(ram_total_mb / 1024) if ram_total_mb > 0 else None
            
            hw_data[sn] = {
                "ram_total_gb": ram_total_gb,
                "cpu_count": cpu_count,
                "cpu_model": cpu_model,
                "cpus": cpus,
                "memory": memory,
                "disks": disks,
                "nics": nics,
                "firmware_version": firmware,
                "bios_version": bios
            }
        cur.close()
        conn.close()
        logger.info(f"Loaded {len(hw_data)} hardware entries from PostgreSQL")
    except Exception as e:
        logger.warning(f"PostgreSQL hardware enrichment unavailable: {e}")
    return hw_data


# ---------------------------------------------------------------------------
# Component Sync Logic (Restored from v3)
# ---------------------------------------------------------------------------
def sync_server_disks(asset_id, disk_components):
    endpoint = f"{RALPH_API_BASE}/disks/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    current_sns = {d["serial_number"]: d for d in disk_components if d.get("serial_number")}

    for d in disk_components:
        sn = d.get("serial_number")
        if not sn:
            continue
        payload = {
            "base_object": asset_id,
            "model_name": d.get("model_name"),
            "serial_number": sn,
            "size": d.get("size"),
            "firmware_version": d.get("firmware_version"),
            "slot": d.get("slot")
        }
        match = next((e for e in existing if e["serial_number"] == sn), None)
        if match:
            requests.patch(f"{endpoint}{match['id']}/", headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)
        else:
            requests.post(endpoint, headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)

    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    seen_sns = set()
    for disk in final_existing:
        sn = disk["serial_number"]
        if sn not in current_sns or sn in seen_sns:
            requests.delete(f"{endpoint}{disk['id']}/", headers=RALPH_HEADERS, verify=False, timeout=15)
        else:
            seen_sns.add(sn)

def sync_server_ethernets(asset_id, nic_components):
    endpoint = f"{RALPH_API_BASE}/ethernets/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    current_labels = {e["label"]: e for e in nic_components if e.get("label")}

    for e in nic_components:
        label = e.get("label")
        if not label:
            continue
        payload = {
            "base_object": asset_id,
            "label": label,
            "mac": e.get("mac"),
            "speed": e.get("speed"),
            "model_name": e.get("model_name")
        }
        match = next((ex for ex in existing if ex.get("label") == label), None)
        if match:
            requests.patch(f"{endpoint}{match['id']}/", headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)
        else:
            requests.post(endpoint, headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)

    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    seen_labels = set()
    for eth in final_existing:
        lbl = eth.get("label") or ""
        if lbl.lower().startswith("management"):
            seen_labels.add(lbl)
            continue
        if lbl not in current_labels or lbl in seen_labels:
            requests.delete(f"{endpoint}{eth['id']}/", headers=RALPH_HEADERS, verify=False, timeout=15)
        else:
            seen_labels.add(lbl)

def sync_generic_components(asset_id, category, redfish_items):
    endpoint = f"{RALPH_API_BASE}/{category}/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")

    for i, item in enumerate(redfish_items):
        payload = {k: v for k, v in item.items()}
        payload["base_object"] = asset_id
        if i < len(existing):
            requests.patch(f"{endpoint}{existing[i]['id']}/", headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)
        else:
            requests.post(endpoint, headers=RALPH_HEADERS, json=payload, verify=False, timeout=15)

    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    for i in range(len(redfish_items), len(final_existing)):
        requests.delete(f"{endpoint}{final_existing[i]['id']}/", headers=RALPH_HEADERS, verify=False, timeout=15)


# ---------------------------------------------------------------------------
# Ralph Status Mapping
# ---------------------------------------------------------------------------
STATUS_MAP = {
    "production": "in use",
    "stock": "free",
    "obsolete": "liquidated",
    "implementation": "in use",
}


# ---------------------------------------------------------------------------
# Core Sync Logic
# ---------------------------------------------------------------------------
def sync_ci_to_ralph(ci: dict, ci_class: str, hw_data: dict, summary: dict):
    """Sync one CI from iTop to Ralph."""
    fields = ci["fields"]
    sn = (fields.get("serialnumber") or "").strip()
    hostname = fields.get("name", "")
    location = fields.get("location_name", "")
    rack = fields.get("rack_name", "")
    brand = fields.get("brand_name", "")
    model = fields.get("model_name", "")
    status_raw = fields.get("status", "production")
    ip = fields.get("managementip", "")
    device_type = ITOP_TO_DEVICE_TYPE.get(ci_class, "unknown")

    if not sn:
        summary["skipped_no_sn"] += 1
        return

    # Find or create in Ralph
    asset, endpoint = find_ralph_asset_by_sn(sn)
    if not asset:
        if device_type == "peripheral":
            summary["skipped_peripheral"] += 1
            return
        asset, endpoint = auto_register_dc_asset(sn, hostname, device_type, ip=ip)
        if not asset:
            summary["failed"] += 1
            return
        summary["created"] += 1
        action = "POST"
    else:
        summary["updated"] += 1
        action = "PATCH"

    asset_id = asset["id"]

    # Build PATCH payload
    last_sync = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "hostname": hostname,
        "status": STATUS_MAP.get(status_raw, "in use"),
        "remarks": f"iTop sync | Last Sync: {last_sync}",
    }

    if ip:
        payload["management_ip"] = ip
        payload["management_hostname"] = hostname
    if brand:
        payload["manufacturer"] = brand
    if model:
        payload["model_name"] = model

    # Enrich with PostgreSQL hardware data
    hw = hw_data.get(sn.lower(), {})
    if hw.get("ram_total_gb"):
        payload["memory"] = f"{hw['ram_total_gb']} GB"
    if hw.get("cpu_count"):
        payload["cpu_cores"] = hw["cpu_count"]
    if hw.get("cpu_model"):
        payload["cpu_model"] = hw["cpu_model"]
    if hw.get("firmware_version"):
        payload["firmware_version"] = hw["firmware_version"]
    if hw.get("bios_version"):
        payload["bios_version"] = hw["bios_version"]

    # PATCH to Ralph
    try:
        r = requests.patch(
            f"{RALPH_API_BASE}/{endpoint}/{asset_id}/",
            headers=RALPH_HEADERS, json=payload, verify=False, timeout=15,
        )
        if r.ok:
            logger.info(f"  [{action}] {hostname} (SN: {sn}) → HTTP {r.status_code} OK")
        else:
            logger.error(f"  [{action}] {hostname} (SN: {sn}) → HTTP {r.status_code}: {r.text[:200]}")
            summary["failed"] += 1
    except requests.exceptions.RequestException as e:
        logger.error(f"  [{action}] {hostname} (SN: {sn}) → HTTP error: {e}")
        summary["failed"] += 1

    # Update management IP
    if ip and endpoint == "data-center-assets":
        try:
            update_management_ip(asset_id, ip, hostname, endpoint)
        except Exception as e:
            logger.warning(f"  [IP] Failed to update management IP for {hostname}: {e}")

    # Sync physical components if it's a server
    if device_type == "server" and hw:
        try:
            sync_server_disks(asset_id, hw.get("disks", []))
            sync_server_ethernets(asset_id, hw.get("nics", []))
            sync_generic_components(asset_id, "memory", hw.get("memory", []))
            sync_generic_components(asset_id, "processors", hw.get("cpus", []))
            logger.info(f"  [COMPONENTS] Synced disks, NICs, memory, processors for {hostname}")
        except Exception as e:
            logger.warning(f"  [COMPONENTS] Failed to sync components for {hostname}: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def run():
    logger.info("=" * 60)
    logger.info("iTop → Ralph CMDB Sync (v4.0) — START")
    logger.info(f"iTop URL: {ITOP_URL}")
    logger.info(f"Ralph URL: {RALPH_API_BASE}")
    logger.info(f"Log file: {LOG_FILE}")

    # Verify Ralph is reachable
    try:
        r = requests.get(f"{RALPH_API_BASE}/data-center-assets/?limit=1",
                         headers=RALPH_HEADERS, verify=False, timeout=10)
        if not r.ok:
            logger.error(f"Ralph API not reachable: HTTP {r.status_code}. Aborting.")
            return
    except requests.exceptions.RequestException as e:
        logger.error(f"Ralph API connection failed: {e}. Aborting.")
        return

    # Load PostgreSQL hardware enrichment
    hw_data = load_hardware_data()

    summary = {
        "updated": 0,
        "created": 0,
        "failed": 0,
        "skipped_no_sn": 0,
        "skipped_peripheral": 0,
        "total_cis": 0,
    }

    # Sync each iTop class
    for cls_cfg in ITOP_CLASSES:
        ci_class = cls_cfg["class"]
        fields = cls_cfg["fields"]
        logger.info(f"--- Syncing {ci_class} ---")

        cis = itop_get_all(ci_class, fields)
        logger.info(f"  Found {len(cis)} {ci_class} CIs in iTop")
        summary["total_cis"] += len(cis)

        for ci in cis:
            try:
                sync_ci_to_ralph(ci, ci_class, hw_data, summary)
            except Exception as e:
                logger.error(f"  ERROR syncing {ci.get('fields', {}).get('name', '?')}: {e}")
                summary["failed"] += 1

    # Summary
    logger.info("=" * 60)
    logger.info("SYNC SUMMARY:")
    logger.info(f"  Total CIs from iTop: {summary['total_cis']}")
    logger.info(f"  Updated in Ralph:    {summary['updated']}")
    logger.info(f"  Created in Ralph:    {summary['created']}")
    logger.info(f"  Failed:              {summary['failed']}")
    logger.info(f"  Skipped (no SN):     {summary['skipped_no_sn']}")
    logger.info(f"  Skipped (peripheral):{summary['skipped_peripheral']}")
    logger.info("iTop → Ralph CMDB Sync (v4.0) — DONE")
    logger.info("=" * 60)


if __name__ == "__main__":
    run()
