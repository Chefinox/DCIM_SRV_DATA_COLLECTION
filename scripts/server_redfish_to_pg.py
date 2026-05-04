#!/usr/bin/env python3
"""
Server Redfish Deep Scanner → PostgreSQL Writer
Melakukan deep scan Redfish pada semua server dan menyimpan hasilnya
ke tabel dcim_events (PostgreSQL) sebagai sumber kebenaran tunggal.

Kolom yang diisi:
  - Basic: hostname, ip, device_type, serial_number, model
  - Server-specific: srv_firmware, srv_bios_version, srv_system_name, srv_management_ip
  - Components (JSONB): srv_disk_components, srv_nic_components,
                        srv_memory_components, srv_cpu_components
"""

import json
import uuid
import logging
import urllib3
import requests
import psycopg2
from datetime import datetime, timezone
from psycopg2.extras import Json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
REDFISH_SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
REDFISH_USER = "poller"
REDFISH_PASS = "F!tech0918"

DB_CONFIG = {
    "host":     "192.168.101.73",
    "port":     5432,
    "dbname":   "dcim_sot",
    "user":     "sot_admin",
    "password": "Inovasi@0918"
}

LOG_FILE = "/home/infra/dcim_metrics_project/logs/server_redfish_to_pg.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

SPEED_MAP = {10: 1, 100: 2, 1000: 3, 10000: 4, 25000: 7, 40000: 5, 100000: 6}


# --- REDFISH UTILITIES ---

def get_redfish(url, auth):
    try:
        r = requests.get(url, auth=auth, verify=False, timeout=10)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        logging.warning(f"Redfish error {url}: {e}")
    return None


def deep_collect_server(ip):
    """Kumpulkan semua data hardware dari satu server via Redfish."""
    auth = (REDFISH_USER, REDFISH_PASS)
    base = f"https://{ip}/redfish/v1"

    result = {
        "ip": ip,
        "hostname": None, "serial_number": None,
        "model": None, "firmware": None, "bios_version": None,
        "system_name": None,
        "processors": [], "memory": [], "ethernets": [], "disks": []
    }

    # Systems/1 — Serial Number, BIOS, Model
    sys_data = get_redfish(f"{base}/Systems/1", auth)
    if sys_data:
        result["serial_number"] = sys_data.get("SerialNumber")
        result["bios_version"] = sys_data.get("BiosVersion")
        result["model"] = sys_data.get("Model")

    # Chassis/1 — System Name (dari Location.PostalAddress.Name)
    chassis_data = get_redfish(f"{base}/Chassis/1", auth)
    if chassis_data:
        loc_name = chassis_data.get("Location", {}).get("PostalAddress", {}).get("Name")
        if loc_name:
            result["system_name"] = loc_name.strip()
            result["hostname"] = loc_name.strip()

    # Managers/1 — Firmware XCC
    mgr_data = get_redfish(f"{base}/Managers/1", auth)
    if mgr_data:
        result["firmware"] = mgr_data.get("FirmwareVersion")

    # Processors
    proc_coll = get_redfish(f"{base}/Systems/1/Processors", auth)
    if proc_coll:
        for m in proc_coll.get("Members", []):
            p = get_redfish(f"https://{ip}{m['@odata.id']}", auth)
            if p and p.get("Status", {}).get("State") != "Absent" and p.get("Model"):
                result["processors"].append({
                    "model_name": p.get("Model"),
                    "cores": p.get("TotalCores"),
                    "logical_cores": p.get("TotalThreads"),
                    "speed": p.get("MaxSpeedMHz")
                })

    # Memory
    mem_coll = get_redfish(f"{base}/Systems/1/Memory", auth)
    if mem_coll:
        for m in mem_coll.get("Members", []):
            mem = get_redfish(f"https://{ip}{m['@odata.id']}", auth)
            if mem and (mem.get("CapacityMiB") or 0) > 0 \
               and mem.get("Status", {}).get("State") != "Absent":
                result["memory"].append({
                    "model_name": mem.get("VendorID") or mem.get("Manufacturer"),
                    "size": mem.get("CapacityMiB"),
                    "speed": mem.get("OperatingSpeedMhz")
                })

    # Ethernets
    eth_coll = get_redfish(f"{base}/Systems/1/EthernetInterfaces", auth)
    if eth_coll:
        for m in eth_coll.get("Members", []):
            e = get_redfish(f"https://{ip}{m['@odata.id']}", auth)
            if e and e.get("MACAddress") and e.get("Id") != "ToManager":
                result["ethernets"].append({
                    "label": e.get("Id"),
                    "mac": e.get("MACAddress"),
                    "speed": SPEED_MAP.get(e.get("SpeedMbps", 0), 11),
                    "model_name": e.get("Description") or "Ethernet Interface"
                })

    # Storage / Disks
    storage_coll = get_redfish(f"{base}/Systems/1/Storage", auth)
    if storage_coll:
        for ctrl in storage_coll.get("Members", []):
            c_data = get_redfish(f"https://{ip}{ctrl['@odata.id']}", auth)
            if c_data:
                for drive in c_data.get("Drives", []):
                    d = get_redfish(f"https://{ip}{drive['@odata.id']}", auth)
                    if d and d.get("SerialNumber") \
                       and d.get("Status", {}).get("State") != "Absent":
                        part_loc = d.get("PhysicalLocation", {}).get("PartLocation", {})
                        slot = part_loc.get("LocationOrdinalValue") or d.get("Id")
                        result["disks"].append({
                            "model_name": d.get("Name") or d.get("Model"),
                            "serial_number": d.get("SerialNumber"),
                            "size": int(d.get("CapacityBytes", 0) / (1024 ** 3)),
                            "firmware_version": d.get("Revision"),
                            "slot": str(slot) if slot is not None else None
                        })

    return result


# --- POSTGRESQL WRITER ---

def upsert_to_postgres(conn, data):
    """
    Upsert satu baris snapshot server ke dcim_events.
    Gunakan serial_number + ip sebagai kunci deduplikasi via raw_fields.
    """
    now = datetime.now(timezone.utc)
    event_id = str(uuid.uuid4())

    sql = """
        INSERT INTO dcim_events (
            event_id, event_time, inserted_at,
            device_type, hostname, ip, serial_number, model,
            srv_firmware, srv_bios_version, srv_system_name, srv_management_ip,
            srv_cpu_components, srv_memory_components,
            srv_nic_components, srv_disk_components,
            raw_fields, raw_tags
        ) VALUES (
            %(event_id)s, %(event_time)s, %(inserted_at)s,
            %(device_type)s, %(hostname)s, %(ip)s::inet, %(serial_number)s, %(model)s,
            %(srv_firmware)s, %(srv_bios_version)s, %(srv_system_name)s, %(srv_management_ip)s::inet,
            %(srv_cpu_components)s, %(srv_memory_components)s,
            %(srv_nic_components)s, %(srv_disk_components)s,
            %(raw_fields)s, %(raw_tags)s
        )
    """

    params = {
        "event_id": event_id,
        "event_time": now,
        "inserted_at": now,
        "device_type": "server",
        "hostname": data["hostname"],
        "ip": data["ip"],
        "serial_number": data["serial_number"],
        "model": data["model"],
        "srv_firmware": data["firmware"],
        "srv_bios_version": data["bios_version"],
        "srv_system_name": data["system_name"],
        "srv_management_ip": data["ip"],
        "srv_cpu_components": Json(data["processors"]),
        "srv_memory_components": Json(data["memory"]),
        "srv_nic_components": Json(data["ethernets"]),
        "srv_disk_components": Json(data["disks"]),
        "raw_fields": Json({
            "processors": data["processors"],
            "memory": data["memory"],
            "ethernets": data["ethernets"],
            "disks": data["disks"]
        }),
        "raw_tags": Json({
            "device_type": "server",
            "ip": data["ip"],
            "hostname": data["hostname"],
            "serial_number": data["serial_number"]
        })
    }

    with conn.cursor() as cur:
        cur.execute(sql, params)
    conn.commit()


def run():
    logging.info("=== SERVER REDFISH TO POSTGRES: START ===")
    try:
        conn = psycopg2.connect(**DB_CONFIG)
    except Exception as e:
        logging.error(f"Gagal koneksi ke PostgreSQL: {e}")
        return

    for ip in REDFISH_SERVERS:
        logging.info(f"Scanning {ip}...")
        try:
            data = deep_collect_server(ip)
            if not data["serial_number"]:
                logging.warning(f"  {ip}: Serial number tidak ditemukan, skip.")
                continue
            upsert_to_postgres(conn, data)
            logging.info(f"  {ip}: {data['hostname']} (SN:{data['serial_number']}) berhasil disimpan ke PostgreSQL.")
        except Exception as e:
            logging.error(f"  {ip}: Error — {e}")

    conn.close()
    logging.info("=== SERVER REDFISH TO POSTGRES: DONE ===")


if __name__ == "__main__":
    run()
