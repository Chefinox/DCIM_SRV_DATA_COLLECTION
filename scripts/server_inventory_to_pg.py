#!/usr/bin/env python3
"""
Server Inventory to PostgreSQL — Unified Pipeline Compliant
Mengumpulkan inventory lengkap dari Redfish API dan menulis ke PostgreSQL dcim_events.

Alur:
  1. Poll Redfish API untuk setiap server (firmware, BIOS, processors, memory, disks, NICs)
  2. Transform ke format dcim_events schema (JSONB components)
  3. Insert ke PostgreSQL dcim_events table
  4. ralph_cmdb_sync.py akan membaca dari PostgreSQL dan sync ke Ralph

Schedule: Daily 01:00 WIB (via cron)
"""

import requests
import json
import urllib3
import logging
import psycopg2
import uuid
from datetime import datetime
from psycopg2.extras import Json

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
REDFISH_SERVERS = [
    {"ip": "10.50.0.2", "hostname": "SERVER-HCI-01"},
    {"ip": "10.50.0.3", "hostname": "SERVER-HCI-02"},
    {"ip": "10.50.0.4", "hostname": "SERVER-HCI-03"},
    {"ip": "10.50.0.5", "hostname": "SERVER-RENDER-01"},
    {"ip": "10.50.0.6", "hostname": "SERVER-RENDER-02"}
]
REDFISH_USER = "hndept"
REDFISH_PASS = "F!tech@0918"

DB_CONFIG = {
    "host": "192.168.101.73",
    "port": 5432,
    "dbname": "dcim_sot",
    "user": "sot_admin",
    "password": "Inovasi@0918"
}

LOG_FILE = "/home/infra/dcim_metrics_project/logs/server_inventory_to_pg.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

# --- REDFISH UTILITIES ---

def get_redfish_data(url, auth):
    """Fetch data from Redfish API endpoint."""
    try:
        resp = requests.get(url, auth=auth, verify=False, timeout=10)
        if resp.status_code == 200:
            return resp.json()
        else:
            logging.warning(f"Redfish {url} returned {resp.status_code}")
    except Exception as e:
        logging.error(f"Redfish error on {url}: {e}")
    return None

def collect_server_inventory(ip, hostname):
    """Collect complete server inventory from Redfish API."""
    auth = (REDFISH_USER, REDFISH_PASS)
    base_url = f"https://{ip}/redfish/v1"
    
    inventory = {
        "ip": ip,
        "hostname": hostname,
        "serial_number": None,
        "bios_version": None,
        "firmware_version": None,
        "processors": [],
        "memory": [],
        "disks": [],
        "nics": []
    }
    
    # 1. System Info (Serial Number, BIOS)
    sys_url = f"{base_url}/Systems/1"
    sys_data = get_redfish_data(sys_url, auth)
    if sys_data:
        inventory["serial_number"] = sys_data.get("SerialNumber")
        inventory["bios_version"] = sys_data.get("BiosVersion")
        logging.info(f"  {ip}: SN={inventory['serial_number']}, BIOS={inventory['bios_version']}")
    
    # 2. Manager Info (Firmware Version)
    mgr_url = f"{base_url}/Managers/1"
    mgr_data = get_redfish_data(mgr_url, auth)
    if mgr_data:
        inventory["firmware_version"] = mgr_data.get("FirmwareVersion")
        logging.info(f"  {ip}: Firmware={inventory['firmware_version']}")
    
    # 3. Processors
    proc_coll = get_redfish_data(f"{sys_url}/Processors", auth)
    if proc_coll:
        for member in proc_coll.get("Members", []):
            p = get_redfish_data(f"https://{ip}{member['@odata.id']}", auth)
            if p and p.get("Status", {}).get("State") != "Absent":
                inventory["processors"].append({
                    "model_name": p.get("Model"),
                    "cores": p.get("TotalCores"),
                    "threads": p.get("TotalThreads"),
                    "speed": p.get("MaxSpeedMHz")
                })
        logging.info(f"  {ip}: Found {len(inventory['processors'])} processors")
    
    # 4. Memory
    mem_coll = get_redfish_data(f"{sys_url}/Memory", auth)
    if mem_coll:
        for member in mem_coll.get("Members", []):
            m = get_redfish_data(f"https://{ip}{member['@odata.id']}", auth)
            if m:
                capacity = m.get("CapacityMiB") or 0
                if capacity > 0 and m.get("Status", {}).get("State") != "Absent":
                    inventory["memory"].append({
                        "model_name": m.get("VendorID") or m.get("Manufacturer") or m.get("PartNumber"),
                        "size": capacity,
                        "speed": m.get("OperatingSpeedMhz")
                    })
        logging.info(f"  {ip}: Found {len(inventory['memory'])} memory modules")
    
    # 5. Disks
    storage_coll = get_redfish_data(f"{sys_url}/Storage", auth)
    if storage_coll:
        for controller in storage_coll.get("Members", []):
            c_data = get_redfish_data(f"https://{ip}{controller['@odata.id']}", auth)
            if c_data:
                for drive in c_data.get("Drives", []):
                    d = get_redfish_data(f"https://{ip}{drive['@odata.id']}", auth)
                    if d and d.get("SerialNumber") and d.get("Status", {}).get("State") != "Absent":
                        # Extract slot number
                        slot = d.get("Id")
                        phys_loc = d.get("PhysicalLocation", {})
                        part_loc = phys_loc.get("PartLocation", {})
                        if part_loc.get("LocationOrdinalValue") is not None:
                            slot = str(part_loc.get("LocationOrdinalValue"))
                        
                        inventory["disks"].append({
                            "model_name": d.get("Name") or d.get("Model"),
                            "serial_number": d.get("SerialNumber"),
                            "size": int(d.get("CapacityBytes", 0) / (1024**3)),  # Convert to GiB
                            "firmware_version": d.get("Revision"),
                            "slot": slot
                        })
        logging.info(f"  {ip}: Found {len(inventory['disks'])} disks")
    
    # 6. NICs
    eth_coll = get_redfish_data(f"{sys_url}/EthernetInterfaces", auth)
    if eth_coll:
        for member in eth_coll.get("Members", []):
            e = get_redfish_data(f"https://{ip}{member['@odata.id']}", auth)
            if e and e.get("MACAddress") and e.get("Id") != "ToManager":
                # Map speed to Ralph enum (1=10M, 2=100M, 3=1G, 4=10G, 5=40G, 6=100G, 7=25G, 11=unknown)
                speed_mbps = e.get("SpeedMbps", 0)
                speed_map = {10: 1, 100: 2, 1000: 3, 10000: 4, 25000: 7, 40000: 5, 100000: 6}
                speed_enum = speed_map.get(speed_mbps, 11)
                
                inventory["nics"].append({
                    "label": e.get("Id"),
                    "mac": e.get("MACAddress"),
                    "speed": speed_enum,
                    "model_name": e.get("Description") or "Ethernet Interface"
                })
        logging.info(f"  {ip}: Found {len(inventory['nics'])} NICs")
    
    return inventory

# --- POSTGRESQL UTILITIES ---

def write_to_postgresql(inventory):
    """Write server inventory to PostgreSQL dcim_events table."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        event_id = str(uuid.uuid4())
        event_time = datetime.utcnow()
        
        # Prepare JSONB components
        cpu_components = Json(inventory["processors"]) if inventory["processors"] else None
        memory_components = Json(inventory["memory"]) if inventory["memory"] else None
        disk_components = Json(inventory["disks"]) if inventory["disks"] else None
        
        # Store NICs in raw_tags for now (no srv_nic_components column exists)
        raw_tags = Json({"nics": inventory["nics"]}) if inventory["nics"] else None
        
        # Insert into dcim_events
        insert_query = """
        INSERT INTO dcim_events (
            event_id, event_time, device_type, hostname, ip, serial_number,
            srv_firmware, srv_bios_version, 
            srv_cpu_components, srv_memory_components, srv_disk_components,
            raw_tags, metric_name, metric_value
        ) VALUES (
            %s, %s, %s, %s, %s, %s,
            %s, %s,
            %s, %s, %s,
            %s, %s, %s
        )
        """
        
        cur.execute(insert_query, (
            event_id,
            event_time,
            'server',
            inventory["hostname"],
            inventory["ip"],
            inventory["serial_number"],
            inventory["firmware_version"],
            inventory["bios_version"],
            cpu_components,
            memory_components,
            disk_components,
            raw_tags,
            'inventory_snapshot',  # metric_name
            1  # metric_value (dummy value)
        ))
        
        conn.commit()
        logging.info(f"  {inventory['ip']}: Written to PostgreSQL (event_id={event_id})")
        
        cur.close()
        conn.close()
        return True
        
    except Exception as e:
        logging.error(f"  {inventory['ip']}: PostgreSQL write failed — {e}")
        return False

# --- MAIN ---

def run():
    logging.info("=== SERVER INVENTORY TO POSTGRESQL: START ===")
    
    success_count = 0
    fail_count = 0
    
    for server in REDFISH_SERVERS:
        ip = server["ip"]
        hostname = server["hostname"]
        
        logging.info(f"Processing {hostname} ({ip})...")
        
        try:
            # Step 1: Collect inventory from Redfish
            inventory = collect_server_inventory(ip, hostname)
            
            if not inventory["serial_number"]:
                logging.warning(f"  {ip}: No serial number found, skipping")
                fail_count += 1
                continue
            
            # Step 2: Write to PostgreSQL
            if write_to_postgresql(inventory):
                success_count += 1
            else:
                fail_count += 1
                
        except Exception as e:
            logging.error(f"  {ip}: Pipeline crash — {e}")
            fail_count += 1
    
    logging.info(f"=== SERVER INVENTORY TO POSTGRESQL: DONE (Success: {success_count}, Failed: {fail_count}) ===")

if __name__ == "__main__":
    run()
