import psycopg2
import os
import requests
import urllib3
import logging

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logger = logging.getLogger(__name__)

DB_CONFIG = {
    "host": os.getenv("SOT_DB_HOST", "localhost"),
    "dbname": os.getenv("SOT_DB_NAME", "dcim_sot"),
    "user": os.getenv("SOT_DB_USER", "sot_admin"),
    "password": os.getenv("SOT_DB_PASS", "Inovasi@0918")
}

RALPH_API_URL = os.getenv("RALPH_API_URL", "http://localhost:8082/api/data-center-assets/")
RALPH_TOKEN   = os.getenv("RALPH_API_TOKEN", "1cd05b8d36e258399a52c59f1a4016addb2346a3")

def get_latest_table(cur):
    cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public' AND table_name LIKE 'dcim_events_%' ORDER BY table_name DESC LIMIT 1")
    tbl = cur.fetchone()
    return tbl[0] if tbl else None

def get_server_hardware(hostname):
    """Ambil data hardware dari Postgres (Redfish) dan Ralph (Fallback Location)."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        # Search by both SRV- and SERVER- prefix variations
        alt_host = hostname.replace('SRV-', 'SERVER-') if hostname.startswith('SRV-') else hostname.replace('SERVER-', 'SRV-')
        
        query_events = f"""
            SELECT 
                e.srv_cpu_components, e.srv_memory_components, e.srv_disk_components, e.raw_tags, e.serial_number
            FROM dcim_events e
            WHERE e.hostname ILIKE %s
            ORDER BY e.event_time DESC LIMIT 1
        """
        cur.execute("SET statement_timeout = 10000;")
        cur.execute(query_events, (hostname,))
        row = cur.fetchone()
        
        site, rack = None, None
        cur.execute("SELECT site, rack_name, ip FROM unified_assets WHERE hostname ILIKE %s OR hostname ILIKE %s LIMIT 1", (hostname, alt_host))
        u_row = cur.fetchone()
        if u_row:
            site, rack = u_row[0], u_row[1]
        
        cur.execute("SET statement_timeout = 0;")
        conn.close()
        
        cpu_comps, mem_comps, disk_comps, nic_comps, serial = None, None, None, [], None
        if row:
            cpu_comps, mem_comps, disk_comps, raw_tags, serial = row
            nic_comps = raw_tags.get("nics", []) if raw_tags else []
        
        # Format CPU & RAM
        new_cpu = ""
        if cpu_comps:
            from collections import Counter
            c = Counter([f"{cpu.get('model_name', 'Unknown CPU')} {cpu.get('cores', 0)}C/{cpu.get('threads', 0)}T @ {cpu.get('speed_mhz', 0)/1000.0}GHz" for cpu in cpu_comps])
            new_cpu = " + ".join([f"{count}x {model}" for model, count in c.items()])
            
        new_ram = ""
        if mem_comps:
            # Memory 'size' is in MiB (from server_inventory_to_pg.py)
            total_ram_mb = sum([m.get("size", 0) or m.get("size_mb", 0) or m.get("capacity_bytes", 0) // (1024*1024) for m in mem_comps])
            total_ram_gb = int(total_ram_mb / 1024)
            if total_ram_gb > 0:
                new_ram = f"{total_ram_gb} GB"
                
        # Ralph Fallback for Location & Rack (and serial if missing)
        if (not site or not rack or not serial) and RALPH_TOKEN:
            headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
            try:
                sn_param = serial or ""
                hostname_param = hostname if not serial else ""
                if serial:
                    url = f"http://localhost:8082/api/data-center-assets/?sn={serial}"
                else:
                    url = f"http://localhost:8082/api/data-center-assets/?hostname={hostname}"
                resp = requests.get(url, headers=headers, verify=False, timeout=5)
                if resp.ok and resp.json().get("results"):
                    asset = resp.json()["results"][0]
                    if not rack and asset.get("rack"):
                        rack = asset["rack"].get("name")
                    if not site and asset.get("rack", {}).get("server_room"):
                        site = asset["rack"]["server_room"].get("name", "")
                    if not serial and asset.get("sn"):
                        serial = asset["sn"]
            except Exception as e:
                logger.error(f"Ralph API error: {e}")
                    
        # Always return data even if partial (location/rack from unified_assets or Ralph)
        return {
            "cpu": new_cpu,
            "ram": new_ram,
            "site": site,
            "rack": rack,
            "disk_comps": disk_comps or [],
            "nic_comps": nic_comps,
            "mem_comps": mem_comps or [],
            "serial_number": serial,
            "nb_u": "2"
        }
    except Exception as e:
        logger.error(f"DB Error get_server_hardware: {e}")
        return None

def get_network_hardware(hostname, ip):
    """Ambil data hardware untuk Network Device dari Postgres."""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        cur = conn.cursor()
        
        query = """
            SELECT site, rack_name, serial_number 
            FROM unified_assets 
            WHERE hostname ILIKE %s OR ip::text = %s 
            LIMIT 1
        """
        cur.execute("SET statement_timeout = 10000;")
        cur.execute(query, (hostname, ip))
        row = cur.fetchone()
        cur.execute("SET statement_timeout = 0;")
        conn.close()
        
        if not row:
            return None
            
        site, rack, serial = row
        return {
            "site": site,
            "rack": rack,
            "serial_number": serial
        }
    except Exception as e:
        logger.error(f"DB Error get_network_hardware: {e}")
        return None
