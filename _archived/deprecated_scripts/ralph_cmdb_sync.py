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
import sys
if "/home/infra/dcim_metrics_project" not in sys.path:
    sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger
import os
import requests
import psycopg2
import urllib3
import re
from datetime import datetime, timedelta
from psycopg2.extras import RealDictCursor

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
# MIGRATION NOTE (2026-06-01): Ralph dan PostgreSQL SOT sudah dimigrasi ke server ini (10.70.0.56)
# Host lama: 192.168.100.115:8088 (Ralph) / 192.168.100.115:5432 (PostgreSQL)
# Host baru: localhost:8082 (ralph_nginx container) / localhost:5432 (dcim_sot_postgres container)
RALPH_API_BASE = os.getenv("RALPH_API_BASE", "http://localhost:8082/api")
RALPH_TOKEN    = "1cd05b8d36e258399a52c59f1a4016addb2346a3"

DB_CONFIG = {
    "host":     os.getenv("SOT_DB_HOST", "localhost"),  # Migrated: was 192.168.100.115, now dcim_sot_postgres container
    "port":     5432,
    "dbname":   os.getenv("SOT_DB_NAME", "dcim_sot"),
    "user":     os.getenv("SOT_DB_USER", "sot_admin"),
    "password": os.getenv("SOT_DB_PASS", "Inovasi@0918")
}

LOG_FILE = "/home/infra/dcim_metrics_project/logs/ralph_cmdb_sync.log"
logger = setup_logger("ralph_cmdb_sync", LOG_FILE)
logging = loggers %(levelname)s: %(message)s'
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
    """Cari aset Ralph berdasarkan serial number di DC dan Back Office."""
    # Cari di Data Center
    results = ralph_get_all(f"{RALPH_API_BASE}/data-center-assets/?sn={sn}")
    if results:
        return results[0], "data-center-assets"
    
    # Cari di Back Office (CCTV, etc)
    results = ralph_get_all(f"{RALPH_API_BASE}/back-office-assets/?sn={sn}")
    if results:
        return results[0], "back-office-assets"
        
    return None, None


# --- AUTO-REGISTER: Model & Rack mapping for new devices ---
DEVICE_TYPE_MODEL_MAP = {
    "server": 26,         # ThinkSystem SR650 V3 (generic)
    "ups": 34,            # APC Easy UPS 3S 30kVA
    "nas": 16,            # RS2423RP (generic Synology)
    "network_switch": 6,  # CCR2004-16G-2S+ (generic MikroTik)
    "nvr": 18,            # DS-7732NXI-K4
}
DEFAULT_RACK = 3  # Rack Server 1


def auto_register_dc_asset(sn, hostname, device_type, model_name=None, ip=None):
    """Auto-register device baru ke Ralph DC Assets jika belum ada.

    Dipanggil ketika find_ralph_asset_by_sn() return None.
    Hanya register dengan info minimal — detail di-update oleh sync berikutnya.
    """
    model_id = DEVICE_TYPE_MODEL_MAP.get(device_type)
    if not model_id:
        logging.warning(f"  [AUTO-REG] Tidak ada model mapping untuk device_type={device_type}, skip SN={sn}")
        return None, None

    payload = {
        "sn": sn,
        "hostname": hostname or f"AUTO-{device_type.upper()}-{sn[-6:]}",
        "model": model_id,
        "rack": DEFAULT_RACK,
        "status": "in use",
        "remarks": f"Auto-registered by ralph_cmdb_sync.py | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    }

    r = requests.post(f"{RALPH_API_BASE}/data-center-assets/",
                      headers=RALPH_HEADERS, json=payload, verify=False)
    if r.ok:
        asset = r.json()
        asset_id = asset["id"]
        logging.info(f"  [AUTO-REG] NEW {device_type}: {hostname} (SN:{sn}) -> id={asset_id}")
        return asset, "data-center-assets"
    else:
        logging.error(f"  [AUTO-REG] FAIL register {sn}: {r.status_code} {r.text[:200]}")
        return None, None


def _ensure_management_ethernet(asset_id):
    """Pastikan ada minimal 1 ethernet untuk asset; kembalikan eth_id atau None."""
    eths = ralph_get_all(f"{RALPH_API_BASE}/ethernets/?base_object={asset_id}")
    if eths:
        # Prefer ethernet yang labelnya mengandung "management" (case-insensitive)
        for e in eths:
            if (e.get("label") or "").lower().startswith("management"):
                return e["id"]
        return eths[0]["id"]

    # Tidak ada ethernet sama sekali → buat default "Management"
    eth_payload = {"base_object": asset_id, "label": "Management"}
    r_eth = requests.post(f"{RALPH_API_BASE}/ethernets/", headers=RALPH_HEADERS, json=eth_payload, verify=False)
    if r_eth.ok:
        eth_id = r_eth.json().get("id")
        logging.info(f"  [ETH] POST management ethernet → HTTP {r_eth.status_code} (id={eth_id})")
        return eth_id
    logging.warning(f"  [ETH] POST management ethernet GAGAL → HTTP {r_eth.status_code}: {r_eth.text[:200]}")
    return None


def _ip_belongs_to_asset(ip_obj, asset_id):
    """Cek apakah objek IPAddress sudah terikat ke asset ini via ethernet."""
    eth_ref = ip_obj.get("ethernet")
    if not eth_ref:
        return False
    # Field "ethernet" bisa berupa dict (detail) atau int (id) tergantung serializer
    if isinstance(eth_ref, dict):
        # Coba cari base_object di dalamnya, atau ambil id lalu lookup
        bo = eth_ref.get("base_object")
        if isinstance(bo, dict):
            return bo.get("id") == asset_id
        if isinstance(bo, int):
            return bo == asset_id
        eth_id = eth_ref.get("id")
    else:
        eth_id = eth_ref
    if not eth_id:
        return False
    # Lookup ethernet ke base_object
    r = requests.get(f"{RALPH_API_BASE}/ethernets/{eth_id}/", headers=RALPH_HEADERS, verify=False)
    if not r.ok:
        return False
    bo = r.json().get("base_object")
    if isinstance(bo, dict):
        return bo.get("id") == asset_id
    return bo == asset_id


def update_management_ip(asset_id, ip, hostname, endpoint_type="data-center-assets"):
    """Update atau buat objek IPAddress is_management=True untuk aset.

    Robust flow:
      1. Cari IPAddress by address (handle IP orphan / duplikat dari run sebelumnya).
      2. Pastikan asset punya ethernet (buat default 'Management' kalau belum ada).
      3. Jika IP sudah ada:
           - terikat ke asset ini → PATCH (update hostname/is_management).
           - orphan (ethernet=null) → PATCH attach ke ethernet asset ini.
           - terikat ke asset lain → WARN, skip (jangan timpa).
      4. Jika IP belum ada → POST baru dengan ethernet terikat.
      5. Log body error untuk respons non-2xx.
    """
    if not ip:
        logging.warning(f"  [IP] IP kosong untuk asset {asset_id}, skip.")
        return

    # 1. Cari IP existing berdasarkan address (lebih reliable dari filter ethernet).
    existing = ralph_get_all(f"{RALPH_API_BASE}/ipaddresses/?address={ip}")
    eth_id = _ensure_management_ethernet(asset_id)

    if existing:
        ip_obj = existing[0]
        ip_id = ip_obj["id"]

        if _ip_belongs_to_asset(ip_obj, asset_id):
            # Sudah terikat ke asset yang benar → cukup update hostname & flag
            payload = {"hostname": hostname, "is_management": True}
            r = requests.patch(
                f"{RALPH_API_BASE}/ipaddresses/{ip_id}/",
                headers=RALPH_HEADERS, json=payload, verify=False
            )
            if r.ok:
                logging.info(f"  [IP] PATCH (linked) management IP {ip} → HTTP {r.status_code}")
            else:
                logging.warning(f"  [IP] PATCH gagal {ip} → HTTP {r.status_code}: {r.text[:200]}")
            return

        if ip_obj.get("ethernet") is None:
            # Orphan IP (dibuat oleh run sebelumnya tanpa ethernet) → attach ke asset ini
            payload = {"hostname": hostname, "is_management": True}
            if eth_id:
                payload["ethernet"] = eth_id
            r = requests.patch(
                f"{RALPH_API_BASE}/ipaddresses/{ip_id}/",
                headers=RALPH_HEADERS, json=payload, verify=False
            )
            if r.ok:
                logging.info(f"  [IP] PATCH (attach orphan) management IP {ip} → HTTP {r.status_code}")
            else:
                logging.warning(f"  [IP] PATCH attach gagal {ip} → HTTP {r.status_code}: {r.text[:200]}")
            return

        # IP terikat ke asset lain → jangan ganggu
        logging.warning(
            f"  [IP] {ip} sudah terikat ke asset lain (ethernet={ip_obj.get('ethernet')}). "
            f"Skip update untuk asset {asset_id}."
        )
        return

    # 2. IP belum ada → buat baru
    payload = {"address": ip, "hostname": hostname, "is_management": True}
    if eth_id:
        payload["ethernet"] = eth_id
    r = requests.post(
        f"{RALPH_API_BASE}/ipaddresses/",
        headers=RALPH_HEADERS, json=payload, verify=False
    )
    if r.ok:
        logging.info(f"  [IP] POST management IP {ip} → HTTP {r.status_code}")
    else:
        logging.warning(f"  [IP] POST gagal {ip} → HTTP {r.status_code}: {r.text[:200]}")


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

    # Prune (proteksi ethernet "Management" agar tidak terhapus)
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}")
    seen_labels = set()
    for eth in final_existing:
        lbl = eth.get("label") or ""
        # NEVER prune Management ethernet — dipakai untuk management IP
        if lbl.lower().startswith("management"):
            seen_labels.add(lbl)
            continue
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

    asset, endpoint = find_ralph_asset_by_sn(sn)
    if not asset:
        # Auto-register device baru
        asset, endpoint = auto_register_dc_asset(sn, hostname, "server", ip=ip)
        if not asset:
            return

    asset_id = asset["id"]
    logging.info(f"  [SERVER] Sync {hostname} (SN:{sn}, ID:{asset_id}) via {endpoint}")

    # Basic Info
    last_sync_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    basic_payload = {
        "hostname": hostname,
        "firmware_version": row.get("srv_firmware"),
        "bios_version": row.get("srv_bios_version"),
        "remarks": f"Last Sync: {last_sync_str}",
        "management_ip": ip,
        "management_hostname": hostname,
        "custom_fields": {"power_consumption": None, "device_temperature": None}
    }
    r = requests.patch(f"{RALPH_API_BASE}/{endpoint}/{asset_id}/",
                       headers=RALPH_HEADERS, json=basic_payload, verify=False)
    logging.info(f"  [BASIC] PATCH asset → HTTP {r.status_code}")

    # Management IP (ensure IP object linked via ethernet)
    update_management_ip(asset_id, ip, hostname, endpoint)

    # Components (dari JSONB columns di dcim_events — tabel relational kosong)
    disks = row.get("srv_disk_components") or []
    memory = row.get("srv_memory_components") or []
    cpus = row.get("srv_cpu_components") or []
    raw_tags = row.get("raw_tags") or {}
    nics = raw_tags.get("nics") or []

    sync_server_disks(asset_id, disks)
    sync_server_ethernets(asset_id, nics)
    sync_generic_components(asset_id, "memory", memory)
    sync_generic_components(asset_id, "processors", cpus)


# --- UPS SYNC ---

def sync_ups(row):
    """Sync satu UPS dari baris PostgreSQL ke Ralph.

    Catatan: Telegraf SNMP UPS menulis seluruh data ke ``raw_fields`` (JSONB),
    bukan ke kolom dedicated ``ups_*``. Karena itu fungsi ini melakukan fallback
    berurutan: kolom dedicated → ``raw_fields`` → ``raw_tags``.
    """
    raw_fields = row.get("raw_fields") or {}
    raw_tags = row.get("raw_tags") or {}

    sn = (
        row.get("ups_serial_snmp")
        or row.get("serial_number")
        or raw_fields.get("serial_number")
    )
    hostname = (row.get("hostname")
                or raw_fields.get("system_name")
                or raw_fields.get("system_description"))
    if hostname:
        hostname = hostname.strip()

    # IP: kolom inet → raw_tags.ip → raw_tags.agent_host (Telegraf default)
    ip_val = row.get("ip") or raw_tags.get("ip") or raw_tags.get("agent_host")
    ip = str(ip_val) if ip_val else None

    firmware = (
        row.get("ups_firmware")
        or raw_fields.get("firmware_version")
        or raw_fields.get("agent_firmware")
    )
    model = row.get("ups_model_snmp") or raw_fields.get("model")
    if model:
        model = model.strip()

    if not sn:
        logging.warning(f"  [UPS] Serial number kosong untuk IP {ip}, skip.")
        return

    asset, endpoint = find_ralph_asset_by_sn(sn)
    if not asset:
        asset, endpoint = auto_register_dc_asset(sn, hostname, "ups", ip=ip)
        if not asset:
            return

    asset_id = asset["id"]
    logging.info(f"  [UPS] Sync {hostname} (SN:{sn}, ID:{asset_id}) via {endpoint}")

    # Basic Info
    last_sync_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "hostname": hostname,
    }
    if firmware:
        payload["firmware_version"] = firmware
    if ip:
        payload["management_ip"] = ip
        payload["management_hostname"] = hostname

    remarks_parts = []
    if model:
        remarks_parts.append(f"Model: {model}")
    remarks_parts.append(f"Last Sync: {last_sync_str}")
    payload["remarks"] = " | ".join(remarks_parts)

    r = requests.patch(f"{RALPH_API_BASE}/{endpoint}/{asset_id}/",
                       headers=RALPH_HEADERS, json=payload, verify=False)
    logging.info(f"  [BASIC] PATCH asset → HTTP {r.status_code}")

    # Management IP (skip kalau IP tidak tersedia di sumber)
    if ip:
        update_management_ip(asset_id, ip, hostname, endpoint)
    else:
        logging.warning(f"  [UPS] IP tidak tersedia untuk SN {sn}, skip update management IP.")


# --- NAS & NETWORK SWITCH SYNC ---

def sync_network_storage(row):
    """Sync NAS atau Network Switch dari PostgreSQL ke Ralph."""
    sn = row.get("serial_number")
    hostname = row.get("hostname")
    ip = str(row["ip"])
    tags = row.get("raw_tags", {})
    firmware = row.get("tag_fw") or tags.get("firmware")
    model = row.get("model")
    if not model or model == "Unknown":
        model = tags.get("model")
    manufacturer = row.get("manufacturer")
    device_type = row.get("device_type").upper()

    if not sn or sn == 'NO_SN':
        logging.warning(f"  [{device_type}] Serial number kosong/valid untuk IP {ip}, skip.")
        return

    asset, endpoint = find_ralph_asset_by_sn(sn)
    if not asset:
        # Auto-register (skip CCTV — handled by register_cctv_to_ralph.py)
        if row.get("device_type") == "cctv":
            logging.warning(f"  [{device_type}] CCTV SN {sn} tidak di Ralph, skip (gunakan register_cctv_to_ralph.py).")
            return
        asset, endpoint = auto_register_dc_asset(sn, hostname, row.get("device_type"), ip=ip)
        if not asset:
            return

    asset_id = asset["id"]
    logging.info(f"  [{device_type}] Sync {hostname} (SN:{sn}, ID:{asset_id}) via {endpoint}")

    # Basic Info
    last_sync_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    payload = {
        "hostname": hostname,
        "management_ip": ip,
        "management_hostname": hostname,
    }
    if firmware:
        payload["firmware_version"] = firmware

    # Update remarks dengan detail: IP, model, manufacturer, Last Sync
    remarks_parts = []
    remarks_parts.append(f"IP: {ip}")
    if manufacturer:
        remarks_parts.append(f"Manufacturer: {manufacturer}")
    if model:
        remarks_parts.append(f"Model: {model}")
    remarks_parts.append(f"Last Sync: {last_sync_str}")
    payload["remarks"] = " | ".join(remarks_parts)

    r = requests.patch(f"{RALPH_API_BASE}/{endpoint}/{asset_id}/",
                       headers=RALPH_HEADERS, json=payload, verify=False)
    logging.info(f"  [BASIC] PATCH asset → HTTP {r.status_code}")

    # Management IP
    update_management_ip(asset_id, ip, hostname, endpoint)


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
                srv_firmware, srv_bios_version, srv_system_name, srv_management_ip,
                srv_cpu_components, srv_memory_components, srv_disk_components, raw_tags
            FROM dcim_events
            WHERE device_type = 'server'
              AND metric_name = 'inventory_snapshot'
              AND serial_number IS NOT NULL
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
        # Telegraf SNMP UPS menulis SN/firmware/model ke raw_fields (JSONB),
        # bukan ke kolom dedicated. Kolom inet `ip` juga selalu NULL untuk UPS,
        # jadi kita kelompokkan berdasarkan serial_number dan ambil semua
        # raw_fields/raw_tags untuk fallback.
        logging.info("--- Syncing UPS ---")
        cur.execute("""
            SELECT DISTINCT ON (serial_number)
                event_time, hostname, ip, serial_number,
                ups_serial_snmp, ups_firmware, ups_model_snmp,
                raw_fields, raw_tags
            FROM dcim_events
            WHERE device_type = 'ups'
              AND serial_number IS NOT NULL
              AND serial_number NOT IN ('NO_IDENTIFIER', 'NO_SN', 'unknown')
            ORDER BY serial_number, event_time DESC
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
