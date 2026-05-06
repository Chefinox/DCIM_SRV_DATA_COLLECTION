#!/usr/bin/env python3
import requests
import json
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import urllib3
import logging
from dotenv import load_dotenv

urllib3.disable_warnings()

# Configuration
load_dotenv('/home/infra/dcim_metrics_project/configs/.env')
RALPH_API_URL = os.getenv("RALPH_API_URL", "http://192.168.101.73:8088/api/data-center-assets/")
RALPH_TOKEN   = os.getenv("RALPH_API_TOKEN", "")

# Logging setup
logging.basicConfig(
    filename='/home/infra/dcim_metrics_project/logs/dcim_ralph_sync.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

def get_recent_dcim_data():
    """Mengambil data terbaru per serial_number dari dcim_events."""
    try:
        conn = psycopg2.connect(
            dbname="dcim_sot",
            user="sot_admin",
            password="Inovasi@0918",
            host="192.168.101.73",
            port=5432
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        # Ambil data terbaru untuk setiap serial number dalam 24 jam terakhir
        query = """
        SELECT DISTINCT ON (serial_number) 
            serial_number, hostname, ip, model, device_type, 
            srv_firmware, ups_firmware, enrichment_status, raw_fields
        FROM dcim_events
        WHERE event_time > NOW() - INTERVAL '24 hours'
        ORDER BY serial_number, event_time DESC;
        """
        cur.execute(query)
        rows = cur.fetchall()
        cur.close()
        conn.close()
        return rows
    except Exception as e:
        logging.error(f"Gagal mengambil data dari Postgres: {e}")
        return []

def get_ralph_asset(sn):
    """Mencari asset di Ralph berdasarkan SN."""
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    for endpoint in ["data-center-assets", "back-office-assets"]:
        url = f"http://192.168.101.73:8088/api/{endpoint}/?sn={sn}"
        try:
            resp = requests.get(url, headers=headers, verify=False, timeout=5)
            if resp.ok and resp.json().get("results"):
                return resp.json()["results"][0], endpoint
        except: continue
    return None, None

def sync():
    logging.info("=== Memulai Sinkronisasi Harian DCIM -> Ralph ===")
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    dcim_data = get_recent_dcim_data()
    
    for row in dcim_data:
        sn = row['serial_number']
        hostname = row['hostname']
        device_type = row['device_type']
        
        # 1. FILTER VALIDASI (STEP 3)
        if not sn or sn in ["NO_SN", "unknown", "Unknown"]:
            logging.warning(f"SKIP: Serial Number tidak valid ({sn}) untuk host {hostname}")
            continue
        if hostname == "unknown":
            logging.warning(f"SKIP: Hostname 'unknown' untuk SN {sn}")
            continue
        if device_type == "server" and row['model'] == "Unknown":
            logging.warning(f"SKIP: Data Server belum valid (Model Unknown) untuk SN {sn}")
            continue

        # 2. LOOKUP RALPH
        asset, endpoint = get_ralph_asset(sn)
        if not asset:
            logging.info(f"SKIP: SN {sn} tidak ditemukan di Ralph.")
            continue

        asset_id = asset['id']
        payload = {}
        changes = []

        # 3. MAPPING & CLASSIFICATION (STEP 2)
        
        # AUTO_UPDATE: Hostname (Cleanup prefix)
        clean_hostname = hostname.replace("FALAH01-", "").strip()
        if clean_hostname and asset.get('hostname') != clean_hostname:
            payload['hostname'] = clean_hostname
            changes.append("hostname")

        # AUTO_UPDATE: Firmware
        firmware = row.get('srv_firmware') or row.get('ups_firmware')
        if not firmware and row.get('raw_fields'):
            firmware = row['raw_fields'].get('firmware')
        if firmware and asset.get('firmware_version') != firmware:
            payload['firmware_version'] = firmware
            changes.append("firmware_version")

        # UPDATE_IF_EMPTY: Model
        if not asset.get('model') and row['model'] and row['model'] != "Unknown":
            # Catatan: Ralph biasanya menggunakan model sebagai foreign key, 
            # di sini kita hanya update jika Ralph mengizinkan string atau metadata terkait.
            pass 

        # 4. LOGIKA REMARKS (UPDATE SETIAP RUN)
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if changes:
            payload['remarks'] = f"Last Sync: {timestamp} | Updated: {', '.join(changes)}"
        else:
            payload['remarks'] = f"Last Sync: {timestamp} | Tidak ada perubahan terjadi"

        # 5. EKSEKUSI UPDATE
        update_url = f"http://192.168.101.73:8088/api/{endpoint}/{asset_id}/"
        try:
            resp = requests.patch(update_url, headers=headers, json=payload, verify=False, timeout=5)
            if resp.ok:
                status_msg = f"Berhasil update {sn}: {payload['remarks']}"
                logging.info(status_msg)
                print(status_msg)
            else:
                logging.error(f"Gagal update {sn}: {resp.status_code} - {resp.text}")
        except Exception as e:
            logging.error(f"Error saat update {sn}: {e}")

    logging.info("=== Sinkronisasi Selesai ===")

if __name__ == "__main__":
    sync()
