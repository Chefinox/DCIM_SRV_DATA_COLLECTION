#!/usr/bin/env python3
"""
Ralph CMDB Unified Sync — Baca dari PostgreSQL → Sync ke Ralph
Mendukung device type: server, ups

Alur:
  1. Ambil snapshot terbaru setiap device dari dcim_events (PostgreSQL)
  2. Cocokkan dengan aset di Ralph via serial_number / ip
  3. Update Basic Info (hostname, firmware, bios, management IP)
  4. Update Components untuk server (disk, RAM, CPU, NIC)
  5. Prune data lama/duplikat di Ralph

Gunakan fungsi ralph_get_all() untuk menghindari bug paginasi Ralph (default limit=10).
"""

import json
import logging
import requests
import psycopg2
import urllib3
import re
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
RALPH_API_BASE = "http://192.168.101.73:8088/api"
RALPH_TOKEN    = "60bcedc875ec7b03b983082655e473e9519d40d5"

DB_CONFIG = {
    "host":     "192.168.101.73",
    "port":     5432,
    "dbname":   "dcim_sot",
    "user":     "sot_admin",
    "password": "Inovasi@0918"
}

LOG_FILE = "/home/infra/dcim_metrics_project/logs/ralph_cmdb_sync.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

RALPH_HEADERS = {
    "Authorization": f"Token {RALPH_TOKEN}",
    "Content-Type": "application/json"
}


# --- HELPERS ---

def ralph_get_all(url):
    """Fetch semua halaman dari endpoint Ralph (handle pagination)."""
    results = []
    next_url = f"{url}&limit=200" if "?" in url else f"{url}?limit=200"
    while next_url:
        resp = requests.get(next_url, headers=RALPH_HEADERS, verify=False)
        if not resp.ok:
            logging.error(f"Ralph GET gagal: {next_url} → {resp.status_code} {resp.text[:200]}")
            break
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = data.get("next")
    return results


def find_ralph_asset_by_sn(sn):
    """Cari aset Ralph berdasarkan serial number."""
    results = ralph_get_all(f"{RALPH_API_BASE}/data-center-assets/?sn={sn}")
    return results[0] if results else None


def update_management_ip(asset_id, ip, hostname):
    """Update atau buat objek IPAddress is_management=True untuk aset."""
    url = f"{RALPH_API_BASE}/ipaddresses/?ethernet__base_object={asset_id}&is_management=True"
    existing = ralph_get_all(url)
    if existing:
        ip_id = existing[0]["id"]
        r = requests.patch(
            f"{RALPH_API_BASE}/ipaddresses/{ip_id}/",
            headers=RALPH_HEADERS,
            json={"address": ip, "hostname": hostname},
            verify=False
        )
        logging.info(f"  [IP] PATCH management IP {ip} → HTTP {r.status_code}")
    else:
        # Perlu ethernet ID untuk membuat IP baru
        eths = ralph_get_all(f"{RALPH_API_BASE}/ethernets/?base_object={asset_id}")
        eth_id = eths[0]["id"] if eths else None
        payload = {"address": ip, "hostname": hostname, "is_management": True}
        if eth_id:
            payload["ethernet"] = eth_id
        r = requests.post(
            f"{RALPH_API_BASE}/ipaddresses/",
            headers=RALPH_HEADERS,
            json=payload,
            verify=False
        )
        logging.info(f"  [IP] POST management IP {ip} → HTTP {r.status_code}")


# --- SERVER SYNC ---

def sync_server_disks(asset_id, disk_components):
    """Sync disk components dari JSONB PostgreSQL ke Ralph."""
    endpoint = f"{RALPH_API_BASE}/disks/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    current_sns = {d["serial_number"]: d for d in disk_components if d.get("serial_number")}

    # Update or Create
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
            requests.patch(f"{endpoint}{match['id']}/", headers=RALPH_HEADERS, json=payload, verify=False)
        else:
            requests.post(endpoint, headers=RALPH_HEADERS, json=payload, verify=False)

    # Prune: hapus entri yang tidak ada di scan saat ini
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    seen_sns = set()
    for disk in final_existing:
        sn = disk["serial_number"]
        if sn not in current_sns or sn in seen_sns:
            r = requests.delete(f"{endpoint}{disk['id']}/", headers=RALPH_HEADERS, verify=False)
            logging.info(f"  [DISK] Prune ID {disk['id']} (SN:{sn}) → HTTP {r.status_code}")
        else:
            seen_sns.add(sn)

    logging.info(f"  [DISK] Sync selesai: {len(disk_components)} disk aktual")


def sync_server_ethernets(asset_id, nic_components):
    """Sync NIC components dari JSONB PostgreSQL ke Ralph."""
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
            requests.patch(f"{endpoint}{match['id']}/", headers=RALPH_HEADERS, json=payload, verify=False)
        else:
            requests.post(endpoint, headers=RALPH_HEADERS, json=payload, verify=False)

    # Prune
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    seen_labels = set()
    for eth in final_existing:
        lbl = eth.get("label")
        if lbl not in current_labels or lbl in seen_labels:
            r = requests.delete(f"{endpoint}{eth['id']}/", headers=RALPH_HEADERS, verify=False)
            logging.info(f"  [NIC] Prune ID {eth['id']} (Label:{lbl}) → HTTP {r.status_code}")
        else:
            seen_labels.add(lbl)


def sync_generic_components(asset_id, category, redfish_items):
    """Sync komponen generik (memory, processors) berdasarkan urutan index."""
    endpoint = f"{RALPH_API_BASE}/{category}/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")

    for i, item in enumerate(redfish_items):
        payload = {k: v for k, v in item.items()}
        payload["base_object"] = asset_id
        if i < len(existing):
            requests.patch(f"{endpoint}{existing[i]['id']}/", headers=RALPH_HEADERS, json=payload, verify=False)
        else:
            requests.post(endpoint, headers=RALPH_HEADERS, json=payload, verify=False)

    # Prune kelebihan
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    for i in range(len(redfish_items), len(final_existing)):
        r = requests.delete(f"{endpoint}{final_existing[i]['id']}/", headers=RALPH_HEADERS, verify=False)
        logging.info(f"  [{category.upper()}] Prune ID {final_existing[i]['id']} → HTTP {r.status_code}")


def sync_server(row):
    """Sync satu server dari baris PostgreSQL ke Ralph."""
    sn = row["serial_number"]
    hostname = row["srv_system_name"] or row["hostname"]
    ip = str(row["ip"])

    asset = find_ralph_asset_by_sn(sn)
    if not asset:
        logging.warning(f"  [SERVER] Aset SN {sn} tidak ditemukan di Ralph, skip.")
        return

    asset_id = asset["id"]
    logging.info(f"  [SERVER] Sync {hostname} (SN:{sn}, ID:{asset_id})")

    # Basic Info
    last_sync_str = row.get("event_time").strftime("%Y-%m-%d %H:%M:%S") if row.get("event_time") else "Unknown"
    basic_payload = {
        "hostname": hostname,
        "firmware_version": row.get("srv_firmware"),
        "bios_version": row.get("srv_bios_version"),
        "remarks": f"Last Sync: {last_sync_str}",
        "custom_fields": {"power_consumption": None, "device_temperature": None}
    }
    r = requests.patch(f"{RALPH_API_BASE}/data-center-assets/{asset_id}/",
                       headers=RALPH_HEADERS, json=basic_payload, verify=False)
    logging.info(f"  [BASIC] PATCH asset → HTTP {r.status_code}")

    # Management IP
    update_management_ip(asset_id, ip, hostname)

    # Components (dari Tabel Relasional)
    with psycopg2.connect(**DB_CONFIG) as subconn:
        with subconn.cursor(cursor_factory=RealDictCursor) as subcur:
            subcur.execute("SELECT serial_number, model_name, size_gb as size, firmware_version, slot FROM dcim_server_disks WHERE server_ip = %s", (ip,))
            disks = subcur.fetchall()
            
            subcur.execute("SELECT label, mac_address as mac, speed_gbps as speed, model_name FROM dcim_server_nics WHERE server_ip = %s", (ip,))
            nics = subcur.fetchall()
            
            subcur.execute("SELECT model_name, size_mb as size, speed_mhz as speed FROM dcim_server_ram WHERE server_ip = %s", (ip,))
            memory = subcur.fetchall()
            
            subcur.execute("SELECT model_name, cores, logical_cores, speed_mhz as speed FROM dcim_server_processors WHERE server_ip = %s", (ip,))
            cpus = subcur.fetchall()

    sync_server_disks(asset_id, disks)
    sync_server_ethernets(asset_id, nics)
    sync_generic_components(asset_id, "memory", memory)
    sync_generic_components(asset_id, "processors", cpus)


# --- UPS SYNC ---

def sync_ups(row):
    """Sync satu UPS dari baris PostgreSQL ke Ralph."""
    sn = row.get("ups_serial_snmp") or row.get("serial_number")
    hostname = row.get("hostname")
    ip = str(row["ip"])
    firmware = row.get("ups_firmware")
    model = row.get("ups_model_snmp")

    if not sn:
        logging.warning(f"  [UPS] Serial number kosong untuk IP {ip}, skip.")
        return

    asset = find_ralph_asset_by_sn(sn)
    if not asset:
        logging.warning(f"  [UPS] Aset SN {sn} tidak ditemukan di Ralph, skip.")
        return

    asset_id = asset["id"]
    logging.info(f"  [UPS] Sync {hostname} (SN:{sn}, ID:{asset_id})")

    # Basic Info
    last_sync_str = row.get("event_time").strftime("%Y-%m-%d %H:%M:%S") if row.get("event_time") else "Unknown"
    payload = {
        "hostname": hostname,
        "firmware_version": firmware,
    }
    remarks = f"Last Sync: {last_sync_str}"
    if model:
        remarks = f"Model SNMP: {model} | " + remarks
    payload["remarks"] = remarks

    r = requests.patch(f"{RALPH_API_BASE}/data-center-assets/{asset_id}/",
                       headers=RALPH_HEADERS, json=payload, verify=False)
    logging.info(f"  [BASIC] PATCH asset → HTTP {r.status_code}")

    # Management IP
    update_management_ip(asset_id, ip, hostname)


# --- NAS & NETWORK SWITCH SYNC ---

def sync_network_storage(row):
    """Sync NAS atau Network Switch dari PostgreSQL ke Ralph."""
    sn = row.get("serial_number")
    hostname = row.get("hostname")
    ip = str(row["ip"])
    firmware = row.get("tag_fw")
    model = row.get("model")
    device_type = row.get("device_type").upper()

    if not sn or sn == 'NO_SN':
        logging.warning(f"  [{device_type}] Serial number kosong/valid untuk IP {ip}, skip.")
        return

    asset = find_ralph_asset_by_sn(sn)
    if not asset:
        logging.warning(f"  [{device_type}] Aset SN {sn} tidak ditemukan di Ralph, skip.")
        return

    asset_id = asset["id"]
    logging.info(f"  [{device_type}] Sync {hostname} (SN:{sn}, ID:{asset_id})")

    # Basic Info
    last_sync_str = row.get("event_time").strftime("%Y-%m-%d %H:%M:%S") if row.get("event_time") else "Unknown"
    payload = {
        "hostname": hostname,
    }
    if firmware:
        payload["firmware_version"] = firmware

    # Update remarks dengan detail model asli
    remarks = f"Last Sync: {last_sync_str}"
    if model:
        remarks = f"Model SNMP: {model} | " + remarks
    payload["remarks"] = remarks

    r = requests.patch(f"{RALPH_API_BASE}/data-center-assets/{asset_id}/",
                       headers=RALPH_HEADERS, json=payload, verify=False)
    logging.info(f"  [BASIC] PATCH asset → HTTP {r.status_code}")

    # Management IP
    update_management_ip(asset_id, ip, hostname)


# --- PRUNE STALE ASSETS ---
def prune_stale_assets():
    """Hapus tulisan 'Last Sync' dari remarks jika Last Sync > 7 hari (bukan hapus aset)."""
    logging.info("--- Pruning Stale 'Last Sync' Remarks (>7 Days) ---")
    assets = ralph_get_all(f"{RALPH_API_BASE}/data-center-assets/")
    now = datetime.now()
    count = 0
    for asset in assets:
        remarks = asset.get("remarks") or ""
        match = re.search(r"Last Sync:\s*(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", remarks)
        if match:
            date_str = match.group(1)
            try:
                last_sync = datetime.strptime(date_str, "%Y-%m-%d %H:%M:%S")
                if (now - last_sync).days > 7:
                    # Hapus tulisan Last Sync dari remarks
                    new_remarks = re.sub(r"\|\s*Last Sync:\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "", remarks)
                    new_remarks = re.sub(r"Last Sync:\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", "", new_remarks).strip()
                    
                    payload = {"remarks": new_remarks}
                    r = requests.patch(f"{RALPH_API_BASE}/data-center-assets/{asset['id']}/", headers=RALPH_HEADERS, json=payload, verify=False)
                    logging.info(f"  [PRUNE] Cleared 'Last Sync' for {asset['hostname']} (Last Sync was: {date_str}) → HTTP {r.status_code}")
                    count += 1
            except Exception as e:
                pass
    logging.info(f"  Total {count} stale remarks cleared.")


# --- MAIN ---

def run():
    logging.info("=== RALPH CMDB UNIFIED SYNC: START ===")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logging.error(f"Gagal koneksi ke PostgreSQL: {e}")
        return

    with conn.cursor(cursor_factory=RealDictCursor) as cur:

        # === SYNC SERVER ===
        logging.info("--- Syncing SERVERS ---")
        cur.execute("""
            SELECT DISTINCT ON (serial_number)
                event_time, hostname, ip, serial_number, model,
                srv_firmware, srv_bios_version, srv_system_name, srv_management_ip
            FROM dcim_events
            WHERE device_type = 'server'
              AND serial_number IS NOT NULL
              AND srv_system_name IS NOT NULL
            ORDER BY serial_number, event_time DESC
        """)
        servers = cur.fetchall()
        logging.info(f"  Ditemukan {len(servers)} server unik di PostgreSQL")
        for row in servers:
            try:
                sync_server(row)
            except Exception as e:
                logging.error(f"  ERROR server {row['ip']}: {e}")

        # === SYNC UPS ===
        logging.info("--- Syncing UPS ---")
        cur.execute("""
            SELECT DISTINCT ON (ip)
                event_time, hostname, ip, serial_number,
                ups_serial_snmp, ups_firmware, ups_model_snmp
            FROM dcim_events
            WHERE device_type = 'ups'
              AND ip IS NOT NULL
            ORDER BY ip, event_time DESC
        """)
        ups_list = cur.fetchall()
        logging.info(f"  Ditemukan {len(ups_list)} UPS unik di PostgreSQL")
        for row in ups_list:
            try:
                sync_ups(row)
            except Exception as e:
                logging.error(f"  ERROR UPS {row['ip']}: {e}")

        # === SYNC NAS, NETWORK SWITCH, CCTV & NVR ===
        logging.info("--- Syncing NAS, NETWORK SWITCH, CCTV, & NVR ---")
        cur.execute("""
            SELECT DISTINCT ON (ip)
                event_time, device_type, hostname, ip, serial_number,
                model, manufacturer, raw_tags->>'firmware' as tag_fw
            FROM dcim_events
            WHERE device_type IN ('nas', 'network_switch', 'cctv', 'nvr')
              AND ip IS NOT NULL
              AND serial_number IS NOT NULL
              AND serial_number != 'NO_SN'
            ORDER BY ip, event_time DESC
        """)
        net_list = cur.fetchall()
        logging.info(f"  Ditemukan {len(net_list)} NAS/Network/CCTV/NVR unik di PostgreSQL")
        for row in net_list:
            try:
                sync_network_storage(row)
            except Exception as e:
                logging.error(f"  ERROR {row['device_type']} {row['ip']}: {e}")

    conn.close()
    
    # Prune stale assets
    prune_stale_assets()
    
    logging.info("=== RALPH CMDB UNIFIED SYNC: DONE ===")


if __name__ == "__main__":
    run()
