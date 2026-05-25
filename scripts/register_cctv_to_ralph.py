#!/usr/bin/env python3
"""
Register full CCTV inventory to Ralph Back Office Assets.

Alur:
  1. Buat category "CCTV" jika belum ada
  2. Buat model per tipe kamera (DS-2CD1121-I, DS-2CD1043G0E-I, dll)
  3. Register setiap CCTV yang belum ada di Ralph sebagai Back Office asset
    4. Reconcile 31 monitored CCTV IP dari CCTV_STATUS.md
    5. Register missing CCTV dengan SN asli atau placeholder berbasis IP

Prerequisite:
  - Manufacturer Hikvision sudah ada (id=8)
  - Region Headquarters (id=1)
  - Warehouse FIT-Head-Office (id=1)
"""

import argparse
import ipaddress
import re

import requests
import psycopg2
import logging
from psycopg2.extras import RealDictCursor

# --- CONFIG ---
RALPH_API_BASE = "http://192.168.100.115:8088/api"
RALPH_TOKEN = "1cd05b8d36e258399a52c59f1a4016addb2346a3"
RALPH_HEADERS = {
    "Authorization": f"Token {RALPH_TOKEN}",
    "Content-Type": "application/json"
}

DB_CONFIG = {
    "host": "192.168.100.115",
    "port": 5432,
    "dbname": "dcim_sot",
    "user": "sot_admin",
    "password": "Inovasi@0918"
}

MANUFACTURER_HIKVISION_ID = 8
REGION_ID = 1
WAREHOUSE_ID = 1
CCTV_DEFAULT_MODEL = "DS-2CD1121-I"
CCTV_TARGETS = {
    "192.168.1.2": "R. Content 2 View2",
    "192.168.1.3": "R. Content 2 View1",
    "192.168.1.4": "Koridor Mess Lt.2",
    "192.168.1.5": "R. Server",
    "192.168.1.6": "Gate In",
    "192.168.1.7": "R. Resepsionis",
    "192.168.1.8": "R. Meeting Lt.1",
    "192.168.1.9": "R. Lead Content",
    "192.168.1.10": "R. Content 4 Lt.2",
    "192.168.1.11": "Musholla",
    "192.168.1.12": "View Gudang & Toilet Lt.1",
    "192.168.1.13": "R. Infra",
    "192.168.1.14": "View FAT & CEO Lt.2",
    "192.168.1.15": "View Koridor Lt.2",
    "192.168.1.16": "Gate Out 2",
    "192.168.1.17": "R. SD 1 Lt.2",
    "192.168.1.18": "Pantry",
    "192.168.1.19": "Gate Out 1",
    "192.168.1.20": "Showroom 1",
    "192.168.1.21": "R. Project Lt.1",
    "192.168.1.22": "Showroom 2",
    "192.168.1.23": "R. Procurement",
    "192.168.1.24": "Break Room",
    "192.168.1.25": "Gudang Lt.2",
    "192.168.1.26": "R. Project Lt.2",
    "192.168.1.27": "R.BD",
    "192.168.1.28": "R.SD 2 Lt.2",
    "192.168.1.29": "R.Content 1 Lt.2",
    "192.168.1.30": "R. HRD",
    "192.168.1.31": "View Tangga",
    "192.168.1.33": "R. Security",
}

LOG_FILE = "/home/infra/dcim_metrics_project/logs/register_cctv.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)
# Also print to console
console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger('').addHandler(console)


def ralph_get_all(url):
    """Fetch semua halaman dari endpoint Ralph."""
    results = []
    next_url = f"{url}&limit=200" if "?" in url else f"{url}?limit=200"
    while next_url:
        resp = requests.get(next_url, headers=RALPH_HEADERS, verify=False)
        if not resp.ok:
            logging.error(f"Ralph GET gagal: {next_url} → {resp.status_code}")
            break
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = data.get("next")
    return results


def ensure_category_cctv():
    """Buat category CCTV jika belum ada, return category_id."""
    cats = ralph_get_all(f"{RALPH_API_BASE}/categories/")
    for c in cats:
        if c.get("name", "").upper() == "CCTV":
            logging.info(f"Category CCTV sudah ada (id={c['id']})")
            return c["id"]

    # Buat baru
    payload = {"name": "CCTV"}
    r = requests.post(f"{RALPH_API_BASE}/categories/", headers=RALPH_HEADERS,
                      json=payload, verify=False)
    if r.ok:
        cat_id = r.json()["id"]
        logging.info(f"Category CCTV dibuat (id={cat_id})")
        return cat_id
    else:
        logging.error(f"Gagal buat category CCTV: {r.status_code} {r.text[:200]}")
        return None


def ensure_model(model_name, category_id):
    """Buat model kamera jika belum ada, return model_id."""
    # Cari existing
    models = ralph_get_all(f"{RALPH_API_BASE}/assetmodels/?name={model_name}")
    for m in models:
        if m.get("name") == model_name:
            logging.info(f"  Model '{model_name}' sudah ada (id={m['id']})")
            return m["id"]

    # Buat baru
    payload = {
        "name": model_name,
        "manufacturer": MANUFACTURER_HIKVISION_ID,
        "category": category_id,
        "type": "back office"
    }
    r = requests.post(f"{RALPH_API_BASE}/assetmodels/", headers=RALPH_HEADERS,
                      json=payload, verify=False)
    if r.ok:
        model_id = r.json()["id"]
        logging.info(f"  Model '{model_name}' dibuat (id={model_id})")
        return model_id
    else:
        logging.error(f"  Gagal buat model '{model_name}': {r.status_code} {r.text[:200]}")
        return None


def get_cctv_sn_ip_mapping():
    """Build CCTV data dari SN pattern yang diketahui missing.
    
    Skip PostgreSQL query karena tabel dcim_events terlalu besar tanpa index.
    Model di-extract dari SN pattern. IP/hostname akan di-update oleh
    ralph_cmdb_sync.py pada run berikutnya.
    """
    import re
    
    # 20 CCTV yang diketahui missing dari Ralph (dari log sync)
    MISSING_SNS = [
        "DS-2CD1021-I20201119AAWRE99707505",
        "DS-2CD1021-I20201209AAWRF24677466",
        "DS-2CD1021-I20201209AAWRF24677518",
        "DS-2CD1021-I20201209AAWRF24677607",
        "DS-2CD1043G0E-I20200427AAWRE30076719",
        "DS-2CD1043G0E-I20200427AAWRE30076984",
        "DS-2CD1043G0E-I20210317AAWRF49947112",
        "DS-2CD1121-I20200308AAWRE17568170",
        "DS-2CD1121-I20200308AAWRE17568965",
        "DS-2CD1143G0E-I20210227AAWRF58406171",
        "DS-2CD1143G0E-I20210227AAWRF58406177",
        "DS-2CD1143G0E-I20210227AAWRF58406190",
        "DS-2CD1143G0E-I20210227AAWRF58406198",
        "DS-2CD1143G0E-I20210227AAWRF58406256",
        "DS-2CD1143G0E-I20210227AAWRF58406282",
        "DS-2CD1143G0E-I20210227AAWRF58406296",
        "DS-2CD1143G0E-I20210227AAWRF58406460",
        "DS-2CD1143G0E-I20210227AAWRF58406500",
        "DS-2CD3121G0-I20230113AAWRL20737837",
        "DS-2CD3121G0-I20230113AAWRL20737848",
    ]

    mapping = {}
    for sn in MISSING_SNS:
        m = re.match(r'(DS-\w+-\w)', sn)
        model_name = m.group(1) if m else "Unknown"
        mapping[sn] = {
            "ip": None,
            "hostname": None,
            "model": model_name,
            "firmware": None
        }
    
    logging.info(f"Loaded {len(mapping)} CCTV dari hardcoded list (skip slow DB query)")
    return mapping

def normalize_ip(ip_value):
    """Normalize PostgreSQL inet value to plain IPv4 string."""
    if not ip_value:
        return None
    return str(ipaddress.ip_interface(str(ip_value)).ip)

def placeholder_sn(ip):
    """Build stable placeholder SN for cameras with blocked/unknown direct ISAPI SN."""
    return f"CCTV-IP-{ip.replace('.', '-')}"

def clean_hostname(value, location):
    """Prefer human location name over generic/unknown camera hostname."""
    if not value or value.lower() in {"unknown", "ip_camera", "ip camera", "no_hostname"}:
        return f"CCTV {location}"
    return value

def get_latest_cctv_by_ip():
    """Fetch latest CCTV telemetry by IP from PostgreSQL."""
    sql = """
        WITH latest AS (
            SELECT DISTINCT ON (ip)
                ip::text AS ip,
                hostname,
                serial_number,
                COALESCE(NULLIF(model, 'Unknown'), NULLIF(raw_tags->>'model', 'unknown')) AS model,
                firmware,
                event_time
            FROM dcim_events
            WHERE device_type = 'cctv'
              AND ip IS NOT NULL
              AND event_time > NOW() - INTERVAL '24 hours'
            ORDER BY ip, event_time DESC
        )
        SELECT * FROM latest
    """
    mapping = {}
    with psycopg2.connect(**DB_CONFIG) as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(sql)
            for row in cur.fetchall():
                ip = normalize_ip(row.get("ip"))
                if ip:
                    mapping[ip] = dict(row)
    logging.info(f"Loaded latest telemetry for {len(mapping)} CCTV IPs")
    return mapping

def get_existing_backoffice_cctv():
    """Fetch existing CCTV-like Back Office assets."""
    assets = ralph_get_all(f"{RALPH_API_BASE}/back-office-assets/")
    cctv_assets = []
    for asset in assets:
        text = str(asset).lower()
        if any(marker in text for marker in ["ds-2cd", "cctv", "ip_camera", "ip camera", "hikvision"]):
            cctv_assets.append(asset)
    logging.info(f"Found {len(cctv_assets)} CCTV-like Back Office assets")
    return cctv_assets

def build_full_cctv_inventory():
    """Build 31 target CCTV records from status map + latest telemetry."""
    telemetry = get_latest_cctv_by_ip()
    records = []
    for ip, location in sorted(CCTV_TARGETS.items(), key=lambda item: ipaddress.ip_address(item[0])):
        sn = data.get("serial_number")
        has_real_sn = bool(sn and sn not in {"NO_SN", "NO_IDENTIFIER", "unknown"} and not sn.startswith("CCTV-IP-"))
        sn = sn if has_real_sn else placeholder_sn(ip)
        model = data.get("model") if data.get("model") and data.get("model") != "unknown" else CCTV_DEFAULT_MODEL
        records.append({
            "ip": ip,
            "location": location,
            "hostname": clean_hostname(data.get("hostname"), location),
            "sn": sn,
            "model": model,
            "firmware": data.get("firmware"),
            "placeholder": not has_real_sn,
        })
    return records


def find_asset_by_sn(sn):
    """Cek apakah SN sudah ada di Ralph (DC atau BO)."""
    results = ralph_get_all(f"{RALPH_API_BASE}/data-center-assets/?sn={sn}")
    if results:
        return True
    results = ralph_get_all(f"{RALPH_API_BASE}/back-office-assets/?sn={sn}")
    if results:
        return True
    return False


def register_cctv(sn, model_id, hostname, ip, firmware, location=None, placeholder=False):
    """Register satu CCTV sebagai Back Office asset."""
    payload = {
        "sn": sn,
        "model": model_id,
        "region": REGION_ID,
        "warehouse": WAREHOUSE_ID,
        "property_of": 1,  # Facility Management Department
        "status": "in use",
        "hostname": hostname or f"CCTV-{sn[-6:]}",
        "remarks": f"IP: {ip or 'N/A'} | Location: {location or 'Back Office'} | Auto-registered from 31-CCTV reconciliation",
    }
    if firmware:
        payload["remarks"] += f" | FW: {firmware}"
    if placeholder:
        payload["remarks"] += " | SN pending camera credential fix"

    r = requests.post(f"{RALPH_API_BASE}/back-office-assets/",
                      headers=RALPH_HEADERS, json=payload, verify=False)
    if r.ok:
        asset_id = r.json().get("id")
        logging.info(f"  ✅ Registered: {payload['hostname']} (SN:{sn[-12:]}) → id={asset_id}")
        return asset_id
    else:
        logging.error(f"  ❌ Gagal register {sn}: {r.status_code} {r.text[:200]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Reconcile 31 CCTV Back Office assets in Ralph")
    parser.add_argument("--apply", action="store_true", help="Create missing Back Office assets")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    logging.info(f"=== REGISTER FULL CCTV TO RALPH: START ({mode}) ===")

    # 1. Ensure category
    category_id = ensure_category_cctv()
    if not category_id:
        logging.error("Tidak bisa buat category CCTV, abort.")
        return

    # 2. Build 31 target inventory
    logging.info("Building 31 CCTV inventory from CCTV_STATUS.md target map + PostgreSQL telemetry...")
    inventory = build_full_cctv_inventory()

    # 3. Determine unique models needed
    model_names = set()
    for data in inventory:
        model_name = data.get("model")
        if model_name:
            model_names.add(model_name)

    logging.info(f"Model unik: {model_names}")

    # 4. Ensure all models exist
    model_id_map = {}
    for model_name in model_names:
        mid = ensure_model(model_name, category_id)
        if mid:
            model_id_map[model_name] = mid

    # 5. Register each CCTV
    logging.info(f"\n--- Reconciling {len(inventory)} CCTV ---")
    registered = 0
    skipped = 0
    failed = 0

    for data in inventory:
        sn = data["sn"]
        # Check if already in Ralph
        if find_asset_by_sn(sn):
            logging.info(f"  ⏭️  Skip (sudah ada): {data['ip']} {sn[-18:]}")
            skipped += 1
            continue

        # Determine model
        model_name = data.get("model")
        if not model_name:
            m = re.match(r'(DS-\w+-\w)', sn)
            if m:
                model_name = m.group(1)

        model_id = model_id_map.get(model_name)
        if not model_id:
            logging.warning(f"  ⚠️  Model '{model_name}' tidak ada, skip {sn}")
            failed += 1
            continue

        hostname = data.get("hostname")
        ip = data.get("ip")
        firmware = data.get("firmware")

        if not args.apply:
            logging.info(f"  📝 Dry-run create: {ip} {hostname} SN={sn} model={model_name}")
            registered += 1
            continue

        asset_id = register_cctv(sn, model_id, hostname, ip, firmware, data.get("location"), data.get("placeholder"))
        if asset_id:
            registered += 1
        else:
            failed += 1

    logging.info(f"\n=== SUMMARY ===")
    logging.info(f"  {'Would register' if not args.apply else 'Registered'}: {registered}")
    logging.info(f"  Skipped (already exists): {skipped}")
    logging.info(f"  Failed: {failed}")
    logging.info(f"  Total processed: {registered + skipped + failed}")
    logging.info("=== REGISTER MISSING CCTV TO RALPH: DONE ===")


if __name__ == "__main__":
    main()
