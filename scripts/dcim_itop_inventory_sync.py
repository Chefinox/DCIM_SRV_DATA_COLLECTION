#!/usr/bin/env python3
"""
DCIM iTop Inventory Sync Script
Tugas: Membaca inventory dari PostgreSQL (dikumpulkan dari Redfish)
lalu mensinkronisasikan (auto-fill) atribut CPU, RAM, Network Interfaces (NIC),
dan Logical Volumes (Disk) ke iTop CMDB.
"""

import sys
import os
import json
import logging
import requests
import psycopg2
from collections import Counter

if "/home/infra/dcim_metrics_project" not in sys.path:
    sys.path.append("/home/infra/dcim_metrics_project")

from src.observability.logging.dcim_logger import setup_logger

# --- Configuration ---
ITOP_URL  = os.getenv("ITOP_API_URL", "http://localhost:8080/webservices/rest.php?version=1.3")
ITOP_USER = os.getenv("ITOP_API_USER", "admin")
ITOP_PASS = os.getenv("ITOP_API_PASS", "Inovasi@0918")

DB_CONFIG = {
    "host": os.getenv("SOT_DB_HOST", "localhost"),
    "dbname": os.getenv("SOT_DB_NAME", "dcim_sot"),
    "user": os.getenv("SOT_DB_USER", "sot_admin"),
    "password": os.getenv("SOT_DB_PASS", "Inovasi@0918")
}

LOG_FILE = "/home/infra/dcim_metrics_project/logs/dcim_itop_inventory_sync.log"
logger = setup_logger("dcim_itop_inventory_sync", LOG_FILE)

# --- iTop Client ---
class ITopClient:
    def __init__(self):
        self.session = requests.Session()

    def _post(self, payload: dict) -> dict:
        if "comment" not in payload and payload.get("operation") in ("core/create", "core/update", "core/delete"):
            payload["comment"] = "Auto-sync from PostgreSQL hardware inventory"
            
        data = {
            "auth_user": ITOP_USER,
            "auth_pwd":  ITOP_PASS,
            "json_data": json.dumps(payload),
        }
        r = self.session.post(ITOP_URL, data=data, timeout=15)
        r.raise_for_status()
        resp = r.json()
        if resp.get("code") != 0:
            logger.error(f"iTop API Error: {resp.get('message')} for payload {payload}")
        return resp

    def get_server_id(self, hostname: str):
        # Try exact match first
        body = self._post({
            "operation": "core/get",
            "class": "Server",
            "key": f"SELECT Server WHERE name = '{hostname}'",
            "output_fields": "id,name,cpu,ram"
        })
        objs = body.get("objects", {})
        if objs:
            key = list(objs.keys())[0]
            numeric_id = key.split("::")[1] if "::" in key else key
            return numeric_id, objs[key].get("fields", {})

        # Case-insensitive fallback: get all servers and match in Python
        body2 = self._post({
            "operation": "core/get",
            "class": "Server",
            "key": "SELECT Server",
            "output_fields": "id,name,cpu,ram"
        })
        for k, v in (body2.get("objects") or {}).items():
            if v.get("fields", {}).get("name", "").upper() == hostname.upper():
                numeric_id = k.split("::")[1] if "::" in k else k
                return numeric_id, v.get("fields", {})

        return None, None

    def update_server_fields(self, server_id, fields_to_update):
        return self._post({
            "operation": "core/update",
            "class": "Server",
            "key": server_id,
            "fields": fields_to_update
        })

    def get_or_create_location(self, name, org_id="1"):
        if not name or name == "Unknown":
            return "0"
        body = self._post({
            "operation": "core/get",
            "class": "Location",
            "key": f"SELECT Location WHERE name='{name}'",
            "output_fields": "id"
        })
        objs = body.get("objects", {})
        if objs:
            return list(objs.keys())[0].split("::")[1]
            
        res = self._post({
            "operation": "core/create",
            "class": "Location",
            "fields": {
                "name": name,
                "org_id": org_id,
                "status": "active"
            }
        })
        return list(res.get("objects", {}).keys())[0].split("::")[1]

    def get_or_create_rack(self, name, location_id, org_id="1"):
        if not name or name == "Unknown":
            return "0"
        body = self._post({
            "operation": "core/get",
            "class": "Rack",
            "key": f"SELECT Rack WHERE name='{name}'",
            "output_fields": "id"
        })
        objs = body.get("objects", {})
        if objs:
            return list(objs.keys())[0].split("::")[1]
            
        res = self._post({
            "operation": "core/create",
            "class": "Rack",
            "fields": {
                "name": name,
                "org_id": org_id,
                "location_id": location_id
            }
        })
        return list(res.get("objects", {}).keys())[0].split("::")[1]

    def get_network_interfaces(self, server_id):
        body = self._post({
            "operation": "core/get",
            "class": "PhysicalInterface",
            "key": f"SELECT PhysicalInterface WHERE connectableci_id = '{server_id}'",
            "output_fields": "macaddress,name"
        })
        return body.get("objects") or {}

    def create_network_interface(self, server_id, name, mac, speed_mbps, ip="", mask="", gateway=""):
        return self._post({
            "operation": "core/create",
            "class": "PhysicalInterface",
            "fields": {
                "connectableci_id": server_id,
                "name": name,
                "macaddress": mac,
                "speed": str(speed_mbps),
                "ipaddress": ip,
                "ipmask": mask,
                "ipgateway": gateway
            }
        })
        
    def update_network_interface(self, interface_id, name, speed_mbps, ip="", mask="", gateway=""):
        return self._post({
            "operation": "core/update",
            "class": "PhysicalInterface",
            "key": interface_id,
            "fields": {
                "name": name,
                "speed": str(speed_mbps),
                "ipaddress": ip,
                "ipmask": mask,
                "ipgateway": gateway
            }
        })

    def get_or_create_local_storage_system(self, hostname, org_id, location_id="0"):
        name = f"Local Storage - {hostname}"
        body = self._post({
            "operation": "core/get",
            "class": "StorageSystem",
            "key": f"SELECT StorageSystem WHERE name = '{name}'",
            "output_fields": "id,location_id"
        })
        objs = body.get("objects", {})
        if objs:
            key = list(objs.keys())[0]
            obj_id = key.split("::")[1] if "::" in key else key
            current_loc = objs[key]["fields"].get("location_id")
            if location_id != "0" and current_loc != location_id:
                self._post({
                    "operation": "core/update",
                    "class": "StorageSystem",
                    "key": obj_id,
                    "fields": {"location_id": location_id}
                })
            return obj_id
            
        res = self._post({
            "operation": "core/create",
            "class": "StorageSystem",
            "fields": {
                "name": name,
                "org_id": org_id,
                "location_id": location_id,
                "status": "production"
            }
        })
        objs = res.get("objects", {})
        key = list(objs.keys())[0]
        return key.split("::")[1] if "::" in key else key

    def get_logical_volumes_for_storage(self, storage_id):
        body = self._post({
            "operation": "core/get",
            "class": "LogicalVolume",
            "key": f"SELECT LogicalVolume WHERE storagesystem_id = '{storage_id}'",
            "output_fields": "name,size,description"
        })
        return body.get("objects") or {}

    def create_logical_volume(self, storage_id, name, size_gb, description):
        res = self._post({
            "operation": "core/create",
            "class": "LogicalVolume",
            "fields": {
                "storagesystem_id": storage_id,
                "name": name,
                "size": str(size_gb),
                "description": description,
                "lun_id": name.split(" ")[-1] if " " in name else "0"
            }
        })
        objs = res.get("objects", {})
        key = list(objs.keys())[0]
        return key.split("::")[1] if "::" in key else key
        
    def update_logical_volume(self, volume_id, size_gb, description):
        return self._post({
            "operation": "core/update",
            "class": "LogicalVolume",
            "key": volume_id,
            "fields": {
                "size": str(size_gb),
                "description": description
            }
        })

    def link_server_to_volume(self, server_id, volume_id, size_gb=0):
        body = self._post({
            "operation": "core/get",
            "class": "lnkServerToVolume",
            "key": f"SELECT lnkServerToVolume WHERE server_id='{server_id}' AND volume_id='{volume_id}'",
            "output_fields": "id,size_used"
        })
        objs = body.get("objects", {})
        if not objs:
            self._post({
                "operation": "core/create",
                "class": "lnkServerToVolume",
                "fields": {
                    "server_id": server_id,
                    "volume_id": volume_id,
                    "size_used": str(size_gb)
                }
            })
            logger.info(f"    ↳ Created Link ServerToVolume: size_used={size_gb}")
        else:
            key = list(objs.keys())[0]
            obj_id = key.split("::")[1] if "::" in key else key
            current_size = objs[key]["fields"].get("size_used", "0")
            if str(current_size) != str(size_gb):
                self._post({
                    "operation": "core/update",
                    "class": "lnkServerToVolume",
                    "key": obj_id,
                    "fields": {
                        "size_used": str(size_gb)
                    }
                })
                logger.info(f"    ↳ Updated Link ServerToVolume: size_used={current_size} -> {size_gb}")
            else:
                logger.info(f"    ↳ Link ServerToVolume already up-to-date (size_used={current_size})")

# --- Formatters ---
def format_cpu(cpu_components):
    """
    Format: 2x Intel Xeon Gold 6342 24C/48T @ 2.8GHz
    """
    if not cpu_components:
        return ""
    
    # Filter out NULL/empty CPU entries (Redfish may return empty processor slots)
    valid_cpus = [c for c in cpu_components if c.get("model_name") and c.get("cores")]
    if not valid_cpus:
        return ""
        
    # Asumsikan semua CPU di server sama, ambil yang pertama
    base_cpu = valid_cpus[0]
    model = base_cpu.get("model_name", "Unknown CPU")
    model = model.replace(" CPU", "").replace(" Processor", "").strip()
    
    cores = base_cpu.get("cores", 0)
    threads = base_cpu.get("threads", 0)
    speed_mhz = base_cpu.get("speed", 0) or base_cpu.get("speed_mhz", 0)
    speed_ghz = round(speed_mhz / 1000.0, 1) if speed_mhz else 0
    
    count = len(valid_cpus)
    
    cpu_str = f"{count}x {model}"
    if cores > 0 and threads > 0:
        cpu_str += f" {cores}C/{threads}T"
    if speed_ghz > 0:
        cpu_str += f" @ {speed_ghz}GHz"
        
    return cpu_str

def format_ram(memory_components):
    """
    Format: 512 GB
    """
    if not memory_components:
        return ""
        
    total_mib = sum(m.get("size", 0) for m in memory_components)
    if total_mib == 0:
        return ""
        
    total_gb = total_mib / 1024.0
    return f"{int(total_gb)} GB"

# --- Main Sync Logic ---
def get_latest_inventory_from_db():
    """Mengambil data inventory server terakhir yang masuk ke tabel dcim_events."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Query langsung ke parent table dcim_events — PostgreSQL partition routing
        # akan otomatis mengarahkan ke partisi yang benar.
        # Gunakan DISTINCT ON untuk ambil data terbaru per hostname.
        # Filter by metric_name='inventory_snapshot' to only get Redfish data (with CPU/RAM)
        query = """
            SELECT DISTINCT ON (e.hostname) 
                e.hostname, e.srv_cpu_components, e.srv_memory_components, e.srv_disk_components, e.raw_tags, u.site, u.rack_name
            FROM dcim_events e
            LEFT JOIN unified_assets u ON (u.hostname = e.hostname OR u.hostname = REPLACE(e.hostname, 'SERVER-', 'SRV-'))
            WHERE e.device_type = 'server' 
              AND e.metric_name = 'inventory_snapshot' 
              AND e.srv_cpu_components IS NOT NULL
              AND e.event_time > NOW() - INTERVAL '24 hours'
            ORDER BY e.hostname, e.event_time DESC
        """
        cur.execute("SET statement_timeout = 30000;")
        cur.execute(query)
        rows = cur.fetchall()
        cur.execute("SET statement_timeout = 0;")
        conn.close()
        return rows
    except Exception as e:
        logger.error(f"DB Error: {e}")
        return []

def sync_inventory():
    logger.info("Starting iTop Inventory Sync...")
    rows = get_latest_inventory_from_db()
    if not rows:
        logger.info("No server inventory data found in DB.")
        return
        
    itop = ITopClient()
    speed_map_mbps = {1: 10, 2: 100, 3: 1000, 4: 10000, 5: 40000, 6: 100000, 7: 25000}
    
    for row in rows:
        raw_hostname = row[0]
        # Use raw hostname as-is — matches iTop CI names from dcim_events
        hostname = raw_hostname
            
        cpu_comps = row[1] or []
        mem_comps = row[2] or []
        disk_comps = row[3] or []
        raw_tags = row[4] or {}
        nic_comps = raw_tags.get("nics", [])
        
        logger.info(f"Processing {hostname}...")
        
        # 1. Cari server di iTop
        server_id, server_fields = itop.get_server_id(hostname)
        if not server_id:
            logger.warning(f"Server {hostname} not found in iTop, skipping...")
            continue
            
        # 2. Update CPU & RAM & Rack Units & Location
        new_cpu = format_cpu(cpu_comps)
        new_ram = format_ram(mem_comps)
        model_name = server_fields.get("model_name", "")
        rack_units = "1" if "SR630" in model_name or "7D76CTO1WW" in model_name else "2"
        org_id = server_fields.get("org_id", "1")
        
        server_updates = {}
        if new_cpu and server_fields.get("cpu") != new_cpu:
            server_updates["cpu"] = new_cpu
        if new_ram and server_fields.get("ram") != new_ram:
            server_updates["ram"] = new_ram
        if server_fields.get("nb_u") != rack_units:
            server_updates["nb_u"] = rack_units
            
        # Get Location & Rack
        site = row[5] if len(row) > 5 else ""
        rack_name = row[6] if len(row) > 6 else ""
        loc_id = "0"
        
        if site:
            loc_id = itop.get_or_create_location(site, org_id)
            if server_fields.get("location_id") != loc_id and loc_id != "0":
                server_updates["location_id"] = loc_id
                
            if rack_name and loc_id != "0":
                rack_id = itop.get_or_create_rack(rack_name, loc_id, org_id)
                if server_fields.get("rack_id") != rack_id and rack_id != "0":
                    server_updates["rack_id"] = rack_id
            
        if server_updates:
            logger.info(f"  -> Updating Server {hostname}: {server_updates}")
            itop.update_server_fields(server_id, server_updates)
            
        # 3. Sync Network Interfaces (NICs)
        existing_nics = itop.get_network_interfaces(server_id)
        existing_macs = {v['fields'].get('macaddress', '').lower(): k for k, v in existing_nics.items()}
        
        for nic in nic_comps:
            mac = (nic.get("mac") or "").strip().lower()
            if not mac:
                continue
                
            label = nic.get("label", "NIC")
            speed_enum = nic.get("speed", 11)
            speed_mbps = speed_map_mbps.get(speed_enum, 0)
            ip = nic.get("ip_address", "")
            mask = nic.get("ip_mask", "")
            gateway = nic.get("ip_gateway", "")
            
            if mac in existing_macs:
                nic_id = existing_macs[mac]
                nic_data = next((v['fields'] for k, v in existing_nics.items() if (k.split("::")[1] if "::" in k else k) == nic_id.split("::")[-1]), {})
                if str(nic_data.get("speed")) != f"{speed_mbps}.00" or nic_data.get("ipaddress") != ip:
                    logger.info(f"  -> Updating NIC {label} for {hostname}")
                    itop.update_network_interface(nic_id.split("::")[-1] if "::" in nic_id else nic_id, label, speed_mbps, ip, mask, gateway)
            else:
                logger.info(f"  -> Creating NIC {label} ({mac}) for {hostname}")
                itop.create_network_interface(server_id, label, mac, speed_mbps, ip, mask, gateway)
                
        # 4. Sync Logical Volumes (Disks)
        storage_id = itop.get_or_create_local_storage_system(hostname, server_fields.get("org_id", "1"), loc_id)
        existing_vols = itop.get_logical_volumes_for_storage(storage_id)
        existing_vol_names = {v['fields'].get('name', ''): k.split("::")[1] if "::" in k else k for k, v in existing_vols.items()}
        
        for disk in disk_comps:
            slot = disk.get("slot", "")
            slot_str = str(slot).zfill(2) if str(slot).isdigit() else slot
            name = f"Slot {slot_str}" if slot else disk.get("model_name", "Drive")
            size_gb = disk.get("size", 0)
            model = disk.get("model_name", "Unknown")
            sn = disk.get("serial_number", "Unknown")
            desc = f"Model: {model}, SN: {sn}"
            lun_id = slot_str if slot_str else "0"
            
            vol_id = None
            if name in existing_vol_names:
                vol_id = existing_vol_names[name]
                # Try to get existing data safely
                vol_data = next((v['fields'] for k, v in existing_vols.items() if (k.split("::")[1] if "::" in k else k) == vol_id), {})
                if str(vol_data.get("size")) != str(size_gb) or vol_data.get("description") != desc:
                     logger.info(f"  -> Updating Volume {name} for {hostname}")
                     itop.update_logical_volume(vol_id, size_gb, desc)
            else:
                logger.info(f"  -> Creating Volume {name} ({size_gb}GB) for {hostname}")
                # Create with specific lun_id padding
                res = itop._post({
                    "operation": "core/create",
                    "class": "LogicalVolume",
                    "fields": {
                        "storagesystem_id": storage_id,
                        "name": name,
                        "size": str(size_gb),
                        "description": desc,
                        "lun_id": lun_id
                    }
                })
                objs_res = res.get("objects", {})
                if objs_res:
                    res_key = list(objs_res.keys())[0]
                    vol_id = res_key.split("::")[1] if "::" in res_key else res_key
                
            if vol_id:
                itop.link_server_to_volume(server_id, vol_id, size_gb)

    logger.info("iTop Inventory Sync completed.")

if __name__ == "__main__":
    sync_inventory()
