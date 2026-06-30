#!/usr/bin/env python3
"""Refresh unified_assets cache from Ralph API.

Keeps PostgreSQL asset cache aligned with current Ralph Data Center and Back
Office assets, including CCTV Back Office assets whose IP is stored in remarks.
"""

import os
import re
from datetime import datetime, timezone

import psycopg2
import requests
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def read_secret(name: str, fallback: str = None) -> str:
    candidates = [
        f"/run/secrets/dcim/{name.lower()}",
        f"/run/secrets/dcim/{name.lower().replace('_', '-')}",
    ]
    if name.startswith("RALPH_"):
        candidates.append(f"/run/secrets/dcim/{name.lower().replace('ralph_', 'ralph-')}")
    for secret_path in candidates:
        try:
            with open(secret_path, encoding="utf-8") as secret_file:
                value = secret_file.read().strip()
                if value:
                    return value
        except FileNotFoundError:
            continue
    return os.getenv(name, fallback)


RALPH_API_BASE = read_secret("RALPH_API_BASE", "http://localhost:8082/api")
RALPH_TOKEN = read_secret("RALPH_TOKEN") or read_secret("RALPH_API_TOKEN")
DB_CONFIG = {
    "host": read_secret("SOT_DB_HOST", "localhost"),
    "port": int(read_secret("SOT_DB_PORT", "5432")),
    "dbname": read_secret("SOT_DB_NAME", "dcim_sot"),
    "user": read_secret("SOT_DB_USER", "sot_admin"),
    "password": read_secret("SOT_DB_PASS"),
}

if not RALPH_TOKEN:
    raise SystemExit("RALPH_TOKEN/RALPH_API_TOKEN not set in env or secret store")
if not DB_CONFIG["password"]:
    raise SystemExit("SOT_DB_PASS not set in env or secret store")

RALPH_HEADERS = {"Authorization": f"Token {RALPH_TOKEN}"}


def ralph_get_all(endpoint: str):
    url = f"{RALPH_API_BASE.rstrip('/')}/{endpoint}/?limit=200"
    results = []
    while url:
        response = requests.get(url, headers=RALPH_HEADERS, timeout=30, verify=False)
        response.raise_for_status()
        payload = response.json()
        results.extend(payload.get("results", []))
        url = payload.get("next")
    return results


def model_metadata(asset: dict):
    model_obj = asset.get("model") or {}
    if not isinstance(model_obj, dict):
        return None, None, None
    manufacturer_obj = model_obj.get("manufacturer") or {}
    category_obj = model_obj.get("category") or {}
    manufacturer = manufacturer_obj.get("name") if isinstance(manufacturer_obj, dict) else None
    category = category_obj.get("name") if isinstance(category_obj, dict) else None
    return manufacturer, model_obj.get("name"), category


def extract_ip(asset: dict):
    ipaddresses = asset.get("ipaddresses") or []
    if isinstance(ipaddresses, list) and ipaddresses:
        first = ipaddresses[0]
        address = first.get("address") if isinstance(first, dict) else str(first)
        if address:
            return address.split("/")[0]
    remarks = asset.get("remarks") or ""
    match = re.search(r"IP:\s*([0-9.]+)", remarks)
    return match.group(1) if match else None


def infer_device_type(endpoint: str, asset: dict, manufacturer: str, model: str, category: str):
    sn = asset.get("sn") or ""
    model_upper = (model or "").upper()
    category_upper = (category or "").upper()

    if endpoint == "back-office-assets" and (
        category_upper == "CCTV" or model_upper.startswith("DS-") or sn.startswith("CCTV-IP-")
    ):
        return "cctv"

    if endpoint == "data-center-assets":
        if category_upper == "SERVER" or "SERVER" in model_upper or "THINKSYSTEM" in model_upper:
            return "server"
        if category_upper == "UPS" or "UPS" in model_upper:
            return "ups"
        if category_upper == "STORAGE" or any(token in model_upper for token in ("SYNOLOGY", "RS2423", "NAS")):
            return "nas"
        if category_upper == "NVR" or model_upper.startswith("DS-77"):
            return "nvr"
        if "SWITCH" in category_upper or "ROUTER" in category_upper or any(token in model_upper for token in ("CCR", "CRS", "MIKROTIK", "SWITCH")):
            return "network_switch"
        if category_upper == "ACCESS POINT" or "AP" in model_upper:
            return "access_point"
        if category_upper == "PATCH PANEL":
            return "patch_panel"
        if category_upper:
            return category_upper.lower().replace(" ", "_").replace("-", "_")
        return "data-center-assets"

    return "back-office-assets"


def build_rows():
    rows = []
    for endpoint in ("data-center-assets", "back-office-assets"):
        for asset in ralph_get_all(endpoint):
            manufacturer, model, category = model_metadata(asset)
            
            # Extract location: prioritize server_room name, fallback to data_center name, then default
            location_name = "FIT-Head-Office"
            rack_obj = asset.get("rack")
            if isinstance(rack_obj, dict):
                server_room = rack_obj.get("server_room")
                if isinstance(server_room, dict):
                    location_name = server_room.get("name") or location_name
                    
            rows.append(
                {
                    "serial_number": asset.get("sn"),
                    "hostname": asset.get("hostname"),
                    "ip": extract_ip(asset),
                    "device_type": infer_device_type(endpoint, asset, manufacturer, model, category),
                    "manufacturer": manufacturer,
                    "model": model,
                    "site": location_name,
                    "rack_name": rack_obj.get("name") if isinstance(rack_obj, dict) else None,
                    "rack_position": asset.get("position"),
                    "asset_status": asset.get("status"),
                    "ralph_id": asset.get("id"),
                    "ralph_endpoint": endpoint,
                    "last_synced_at": datetime.now(timezone.utc),
                }
            )
    return rows

def normalize_existing_cache():
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                UPDATE unified_assets
                SET device_type = CASE
                        WHEN ralph_endpoint = 'back-office-assets'
                         AND (COALESCE(model, '') LIKE 'DS-%' OR COALESCE(serial_number, '') LIKE 'CCTV-IP-%') THEN 'cctv'
                        WHEN ralph_endpoint = 'data-center-assets'
                         AND upper(COALESCE(model, '')) LIKE '%UPS%' THEN 'ups'
                        ELSE device_type
                    END,
                    manufacturer = CASE
                        WHEN (manufacturer IS NULL OR manufacturer IN ('Unknown', 'unknown', ''))
                         AND COALESCE(model, '') LIKE 'DS-%' THEN 'Hikvision'
                        ELSE manufacturer
                    END,
                    last_synced_at = NOW()
            """)
            cur.execute("""
                UPDATE unified_assets
                SET device_type = 'cctv'
                WHERE ralph_endpoint = 'back-office-assets'
                  AND (COALESCE(model, '') LIKE 'DS-%' OR COALESCE(serial_number, '') LIKE 'CCTV-IP-%')
            """)
            cur.execute("""
                UPDATE unified_assets
                SET device_type = 'ups'
                WHERE ralph_endpoint = 'data-center-assets'
                  AND upper(COALESCE(model, '')) LIKE '%UPS%'
            """)
            cur.execute("SELECT COUNT(*) FROM unified_assets")
            return cur.fetchone()[0]


def refresh_cache(rows):
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE TABLE unified_assets")
            cur.executemany(
                """
                INSERT INTO unified_assets (
                    serial_number, hostname, ip, device_type, manufacturer, model,
                    site, rack_name, rack_position, asset_status, ralph_id,
                    ralph_endpoint, last_synced_at
                ) VALUES (
                    %(serial_number)s, %(hostname)s, %(ip)s, %(device_type)s,
                    %(manufacturer)s, %(model)s, %(site)s, %(rack_name)s,
                    %(rack_position)s, %(asset_status)s, %(ralph_id)s,
                    %(ralph_endpoint)s, %(last_synced_at)s
                )
                """,
                rows,
            )


def main():
    try:
        rows = build_rows()
        refresh_cache(rows)
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 401:
            count = normalize_existing_cache()
            print(f"ralph_auth_failed=true normalized_existing_cache={count}")
            return
        raise
    counts = {}
    for row in rows:
        key = row["device_type"]
        counts[key] = counts.get(key, 0) + 1
    print(f"refreshed={len(rows)} counts={counts}")


if __name__ == "__main__":
    main()
