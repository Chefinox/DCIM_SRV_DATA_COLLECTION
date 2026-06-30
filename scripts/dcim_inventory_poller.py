#!/usr/bin/env python3
"""
DCIM Unified Inventory Poller
Mengumpulkan Serial Number, Model, dan Firmware dari semua perangkat infrastruktur:
  - Server Lenovo (via Redfish HTTP)
  - UPS APC (via SNMP v3)
  - MikroTik Switch (via SNMP v2c)
  - Hikvision NVR & CCTV Camera (via ISAPI HTTP)

Output: JSON Array dengan skema seragam, siap dikonsumsi oleh Telegraf inputs.exec
"""

import json
import sys
import requests
import urllib3
import concurrent.futures
import subprocess
import re
import ssl
import psycopg2
from datetime import datetime, timezone
import urllib.parse
import urllib.request

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from dotenv import load_dotenv
import os

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

# ============================================================
# CREDENTIAL & DEVICE CONFIGURATION
# ============================================================

# Redfish (Server Lenovo BMC/XCC)
REDFISH_SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
REDFISH_USER = os.getenv("REDFISH_USER", "poller")
REDFISH_PASS = os.getenv("REDFISH_PASS", "F!tech0918")

# SNMP v3 (UPS APC)
UPS_HOSTS = [{"ip": "192.168.100.140", "name": "UPS-APC-30K"}]
UPS_SNMP_USER = os.getenv("UPS_SNMP_USER", "poller")
UPS_SNMP_AUTH_PASS = os.getenv("UPS_SNMP_AUTH_PASS", "F!tech0918")
UPS_SNMP_PRIV_PASS = os.getenv("UPS_SNMP_PRIV_PASS", "F!tech0918")

# Fallback Map from Excel (Used if Device Actual Name is empty)
SERVER_FALLBACK_MAP = {
    "10.50.0.2": "SRV-HCI-01",
    "10.50.0.3": "SRV-HCI-02",
    "10.50.0.4": "SRV-HCI-03",
    "10.50.0.5": "SRV-Render-01",
    "10.50.0.6": "SRV-Render-02",
}

# SNMP v2c (MikroTik) - Aligned with Excel
MIKROTIK_HOSTS = [
    {"ip": "172.16.35.1", "name": "FIT-Core-RTR"},
    {"ip": "172.16.35.2", "name": "FIT-Core-SW"},
    {"ip": "172.16.35.3", "name": "FIT-DIST-SW-LAN1"},
    {"ip": "172.16.35.5", "name": "FIT-DIST-SW-SERVER1"},
    {"ip": "172.16.35.6", "name": "FIT-DIST-SW-SERVER2"},
]
MIKROTIK_COMMUNITY = "public"

# Synology NAS - Aligned with Excel
NAS_HOSTS = [
    {"hostname": "NAS-INFRA", "ip": "10.50.0.106", "method": "snmp"},
    {"hostname": "NAS-FAT",   "ip": "10.50.0.107", "method": "snmp"},
    {"hostname": "NAS-SD01",  "ip": "10.50.0.108", "method": "snmp"},
    {"hostname": "NAS-CD01",  "ip": "10.50.0.109", "method": "snmp"},
    {"hostname": "NAS-CD02",  "ip": "10.50.0.110", "method": "snmp"},
    {"hostname": "NAS-FIT",   "ip": "10.50.0.105", "method": "snmp"}
]
NAS_USER = os.getenv("NAS_USER", "hndept")
NAS_PASS_REST = os.getenv("NAS_PASS_REST", "F!tech0918")
NAS_PASS_SNMP = os.getenv("NAS_PASS_SNMP", "F!tech0918")

# SSL Context for legacy NAS
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode    = ssl.CERT_NONE
HIKVISION_NVR = {"ip": "192.168.1.254", "user": os.getenv("HIKVISION_NVR_USER", "admin"), "password": os.getenv("HIKVISION_NVR_PASS", "qRvbi883=Zk[Q)@5")}
HIKVISION_CAMERAS = [
    {"ip": f"192.168.1.{i}"} for i in list(range(2, 32)) + [33]
]
HIKVISION_CAM_USER = os.getenv("HIKVISION_CAM_USER", "admin")
HIKVISION_CAM_PASS = os.getenv("HIKVISION_CAM_PASS", "qRvbi883=Zk[Q)@5")

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def get_historical_data(ip):
    """Fetch the last known hostname and serial_number from Postgres V1 as a fallback."""
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
            user=os.getenv("SOT_DB_USER", "sot_admin"),
            password=os.getenv("SOT_DB_PASS", "Inovasi@0918"),
            host=os.getenv("SOT_DB_HOST", "localhost"),
            port=os.getenv("SOT_DB_PORT", "5432")
        )
        cur = conn.cursor()
        cur.execute("SELECT hostname, serial_number FROM dcim_events WHERE ip = %s ORDER BY event_time DESC LIMIT 1", (ip,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            return {"hostname": row[0], "serial_number": row[1]}
    except:
        pass
    return None


def run_snmpget(ip, version, oids, community=None, user=None, auth_pass=None, priv_pass=None):
    results = {}
    for name, oid in oids.items():
        if version == "2c":
            cmd = ["snmpget", "-v2c", "-c", community, ip, oid]
        elif version == "3":
            cmd = [
                "snmpget", "-v3", "-u", user, "-l", "authPriv",
                "-a", "SHA", "-A", auth_pass, "-x", "AES", "-X", priv_pass,
                ip, oid
            ]
        
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                # Extract value between quotes or after colon
                match = re.search(r'STRING: "?([^"]+)"?|INTEGER: (\d+)', res.stdout)
                if match:
                    val = (match.group(1) or match.group(2) or "").strip()
                    results[name] = val
        except:
            pass
    return results

# ============================================================
# POLLER FUNCTIONS
# ============================================================

def poll_server(ip):
    """
    Mengambil data server terbaru dari PostgreSQL (V1 dcim_events).
    Sumber data ini adalah hasil polling Telegraf, bukan Redfish langsung.
    """
    rec = {
        "serial_number": "", "device_type": "server", "category": "infrastructure",
        "ip_address": ip, "model": "", "product_name": "", "manufacturer": "Lenovo",
        "processor_count": 0, "processor_logical_count": 0,
        "firmware_version": "", "hostname": "", "status": "Unknown", "power_state": "Unknown",
        "inventory_source": "telegraf_via_db"
    }

    try:
        conn = psycopg2.connect(
            dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
            user=os.getenv("SOT_DB_USER", "sot_admin"),
            password=os.getenv("SOT_DB_PASS", "Inovasi@0918"),
            host=os.getenv("SOT_DB_HOST", "localhost"),
            port=os.getenv("SOT_DB_PORT", "5432")
        )
        cur = conn.cursor()
        # Ambil data terbaru (V1 Flat Schema)
        cur.execute("""
            SELECT hostname, serial_number, model, firmware, status, power_state,
                   srv_cpu_count, srv_memory_total_mb,
                   srv_temp_ambient, srv_power_consumption_watts,
                   event_time
            FROM dcim_events
            WHERE ip = %s 
              AND device_type IN ('server', 'server_redfish')
            ORDER BY event_time DESC LIMIT 1
        """, (ip,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            # Map database columns to poller record
            rec["hostname"]         = row[0] or ""
            rec["serial_number"]    = row[1] or ""
            rec["model"]            = row[2] or ""
            rec["product_name"]     = rec["model"]
            rec["firmware_version"] = row[3] or ""
            rec["firmware"]         = rec["firmware_version"]
            rec["status"]           = row[4] or "OK"
            rec["power_state"]      = row[5] or "On"
            rec["processor_count"]  = row[6] or 0
            
            # Unified Metrics mapping (from DB values)
            rec["metrics"] = {
                "Temperature": f"{row[8] or 0} C",
                "Utilization": "N/A (Historical)",
                "Power_Watts": f"{row[9] or 0} W",
                "Health_Summary": rec["status"],
                "Status_Detail": f"{rec['power_state']} (RAM: {row[7] or 0} MB)",
                "last_poll": str(row[10])
            }
            return rec
    except Exception as e:
        pass

    # FALLBACK: Jika DB kosong, gunakan data historis global atau excel
    hist = get_historical_data(ip)
    if hist:
        rec["hostname"]      = hist["hostname"]
        rec["serial_number"] = hist["serial_number"]
    
    if not rec["hostname"] or rec["hostname"].lower() == "none":
        rec["hostname"] = SERVER_FALLBACK_MAP.get(ip, "")
        
    rec["metrics"] = {"Status": "Waiting for Telegraf sync"}
    return rec

def poll_ups(host_info):
    rec = {
        "serial_number": "", "device_type": "ups", "category": "infrastructure",
        "ip_address": host_info["ip"], "model": "", "product_name": "", "manufacturer": "APC",
        "processor_count": 0, "processor_logical_count": 0,
        "firmware_version": "", "hostname": "", "status": "OK", "power_state": "On",
        "inventory_source": "snmp"
    }
    oids = {
        "sys_name":               ".1.3.6.1.2.1.1.5.0",
        "serial_number":          ".1.3.6.1.2.1.33.1.1.1.0",
        "model":                  ".1.3.6.1.4.1.935.1.1.1.1.1.1.0",
        "firmware_version":       ".1.3.6.1.2.1.33.1.1.3.0",
        "ups_load":               ".1.3.6.1.4.1.318.1.1.1.4.3.3.0",
        "ups_battery":            ".1.3.6.1.4.1.318.1.1.1.2.2.1.0",
        "battery_runtime_remain": ".1.3.6.1.4.1.318.1.1.1.2.2.3.0",
        "input_voltage":          ".1.3.6.1.4.1.318.1.1.1.3.2.1.0",
        "output_status":          ".1.3.6.1.4.1.318.1.1.1.4.1.1.0",
        "battery_health":         ".1.3.6.1.4.1.318.1.1.1.2.2.4.0",
    }
    data = run_snmpget(host_info["ip"], "3", oids, user=UPS_SNMP_USER,
                       auth_pass=UPS_SNMP_AUTH_PASS, priv_pass=UPS_SNMP_PRIV_PASS)
    rec.update(data)
    rec["hostname"] = data.get("sys_name") or host_info["name"]
    rec["product_name"] = rec.get("model", "").strip()
    rec["model"]        = rec.get("model", "").strip()
    rec["firmware"]     = rec.get("firmware_version", "").strip()

    status_map = {"2": "On Line", "3": "On Battery", "4": "On Boost", "5": "Sleeping", "6": "On Bypass"}
    health_map = {"1": "OK", "2": "Needs Replacing"}

    rec["metrics"] = {
        "Temperature": "N/A",
        "Utilization": f"{data.get('ups_load', '0')}%",
        "Power_Watts": f"{data.get('ups_load', '0')}% Load",
        "Health_Summary": health_map.get(data.get("battery_health"), "Unknown"),
        "Status_Detail": f"{status_map.get(data.get('output_status'), 'Unknown')} (Bat: {data.get('ups_battery', '0')}%)"
    }
    return rec

def poll_mikrotik(host_info):
    rec = {
        "serial_number": "", "device_type": "mikrotik", "category": "infrastructure",
        "ip_address": host_info["ip"], "model": "", "product_name": "", "manufacturer": "MikroTik",
        "processor_count": 0, "processor_logical_count": 0,
        "firmware_version": "", "hostname": "", "status": "OK", "power_state": "On",
        "inventory_source": "snmp"
    }
    oids = {
        "sys_name": ".1.3.6.1.2.1.1.5.0",
        "serial_number": ".1.3.6.1.4.1.14988.1.1.7.3.0",
        "firmware_version": ".1.3.6.1.4.1.14988.1.1.7.4.0",
        "model_raw": ".1.3.6.1.2.1.1.1.0",
        "cpu_load": ".1.3.6.1.2.1.25.3.3.1.2.1",
        "temp_new": ".1.3.6.1.4.1.14988.1.1.3.100.1.3.51"
    }
    data = run_snmpget(host_info["ip"], "2c", oids, community=MIKROTIK_COMMUNITY)
    temp_val = data.get("temp_new") or 0
    if "model_raw" in data:
        match = re.search(r'RouterOS (\S+)', data["model_raw"])
        data["model"] = match.group(1) if match else data["model_raw"]
        data["product_name"] = data["model"]
    rec.update(data)
    rec["hostname"] = data.get("sys_name") or host_info["name"]
    
    rec["metrics"] = {
        "Temperature": f"{float(temp_val)/10 if temp_val else '0'} C",
        "Utilization": f"{data.get('cpu_load', '0')}%",
        "Power_Watts": "N/A",
        "Health_Summary": rec.get("status", "OK"),
        "Status_Detail": f"CPU Load: {data.get('cpu_load', '0')}%"
    }
    return rec

def poll_nas(host):
    ip = host["ip"]
    hostname = host["hostname"]
    rec = {
        "serial_number": "", "device_type": "nas", "category": "storage",
        "ip_address": ip, "model": "", "product_name": "", "manufacturer": "Synology",
        "processor_count": 0, "processor_logical_count": 0,
        "firmware_version": "", "hostname": hostname.strip(), "status": "Online", "power_state": "On",
        "inventory_source": "snmp"
    }

    if host.get("method") == "snmp" or True: # Try SNMP first, then fallback
        oids = {
            "model": ".1.3.6.1.4.1.6574.1.5.1.0",
            "serial_number": ".1.3.6.1.4.1.6574.1.5.2.0",
            "firmware_version": ".1.3.6.1.4.1.6574.1.5.3.0",
            "status": ".1.3.6.1.4.1.6574.1.1.0",
            "temp": ".1.3.6.1.4.1.6574.1.2.0",
            "hrStorageSize": ".1.3.6.1.2.1.25.2.3.1.5.1",
            "hrStorageUsed": ".1.3.6.1.2.1.25.2.3.1.6.1",
            "hrStorageUnits": ".1.3.6.1.2.1.25.2.3.1.4.1"
        }
        res = run_snmpget(ip, "3", oids, user=NAS_USER, auth_pass=NAS_PASS_SNMP, priv_pass=NAS_PASS_SNMP)
        if not res.get("serial_number"):
            # Try SNMP v2c as fallback
            res = run_snmpget(ip, "2c", oids, community="public")
        
        if res.get("serial_number"):
            rec.update(res)
            status_map = {"1": "Normal", "2": "Failed"}
            
            # Calculate Disk Usage %
            size = float(res.get("hrStorageSize", 0))
            used = float(res.get("hrStorageUsed", 0))
            units = float(res.get("hrStorageUnits", 1))
            
            total_gb = (size * units) / (1024**3)
            used_gb = (used * units) / (1024**3)
            disk_pct = (used / size * 100) if size > 0 else 0

            # Unified Metrics mapping for NAS
            rec["metrics"] = {
                "Temperature": f"{res.get('temp', '0')} C",
                "Utilization": f"{disk_pct:.1f}% Disk Used",
                "Power_Watts": "N/A",
                "Health_Summary": status_map.get(res.get("status"), "Unknown"),
                "Status_Detail": f"Storage: {used_gb:.1f}/{total_gb:.1f} GB"
            }
            # Sync firmware fields
            rec["firmware"] = rec.get("firmware_version", "")
            return rec

    # API REST Fallback
    try:
        # 1. Login
        params = {"api": "SYNO.API.Auth", "version": "3", "method": "login", "account": NAS_USER, "passwd": NAS_PASS_REST, "format": "sid"}
        qs = urllib.parse.urlencode(params)
        url = f"https://{ip}:5001/webapi/auth.cgi?{qs}"
        with urllib.request.urlopen(url, context=SSL_CTX, timeout=5) as r:
            auth = json.loads(r.read())
            sid = auth.get("data", {}).get("sid")
        
        if sid:
            # 2. Get Info
            url = f"https://{ip}:5001/webapi/entry.cgi?api=SYNO.Core.System&version=1&method=info&_sid={sid}"
            with urllib.request.urlopen(url, context=SSL_CTX, timeout=5) as r:
                resp = json.loads(r.read())
                data = resp.get("data", {})
                rec["serial_number"] = data.get("serial", rec.get("serial_number"))
                rec["model"]         = data.get("model", rec.get("model"))
                
                # Robust Firmware/DSM Version Detection
                fw_ver = data.get("firmware") or data.get("version") or data.get("buildnumber") or "DSM (Detected)"
                rec["firmware_version"] = fw_ver
                rec["firmware"]         = fw_ver
                rec["product_name"]     = rec["model"]
                rec["inventory_source"] = "api"
                
                # Unified Metrics mapping for NAS (API Fallback)
                rec["metrics"] = {
                    "Temperature": f"{data.get('temperature', '0')} C",
                    "Utilization": "N/A (API)",
                    "Power_Watts": "N/A",
                    "Health_Summary": "Online",
                    "Status_Detail": f"Model: {rec['model']}"
                }
    except:
        pass
    
    return rec

def poll_hikvision(ip, user, password, device_type):
    rec = {
        "serial_number": "", "device_type": device_type, "category": "security",
        "ip_address": ip, "model": "", "product_name": "", "manufacturer": "Hikvision",
        "processor_count": 0, "processor_logical_count": 0,
        "firmware_version": "", "hostname": "", "status": "Online", "power_state": "On",
        "inventory_source": "isapi"
    }
    try:
        from requests.auth import HTTPDigestAuth
        for auth_method in [HTTPDigestAuth(user, password), (user, password)]:
            try:
                r = requests.get(f"http://{ip}/ISAPI/System/deviceInfo", auth=auth_method, timeout=5)
                if r.ok:
                    xml = r.text
                    # Robust XML Regex
                    sn = re.search(r'<(?:serialNumber|SerialNumber)>(.*?)</', xml)
                    md = re.search(r'<(?:model|Model)>(.*?)</', xml)
                    fw = re.search(r'<(?:firmwareVersion|FirmwareVersion)>(.*?)</', xml)
                    nm = re.search(r'<(?:deviceName|DeviceName)>(.*?)</', xml)
                    
                    if sn: rec["serial_number"] = sn.group(1)
                    if md: rec["model"] = md.group(1)
                    if fw: rec["firmware_version"] = fw.group(1)
                    if nm: rec["hostname"] = nm.group(1)
                    rec["product_name"] = rec["model"]
                    break
            except:
                continue
        else:
            rec["status"] = "Offline"
    except:
        rec["status"] = "Offline"
    
    # Unified Metrics mapping for CCTV/NVR
    rec["metrics"] = {
        "Temperature": "N/A",
        "Utilization": "N/A",
        "Power_Watts": "N/A",
        "Health_Summary": rec.get("status", "Unknown"),
        "Status_Detail": f"Source: {rec.get('inventory_source', 'isapi')}"
    }
    return rec

# ============================================================
# MAIN
# ============================================================

# ============================================================
# DATABASE & PERSISTENCE
# ============================================================

def save_to_db(results):
    try:
        conn = psycopg2.connect(
            host=os.getenv("SOT_DB_HOST", "localhost"),
            port=os.getenv("SOT_DB_PORT", "5432"),
            dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
            user=os.getenv("SOT_DB_USER", "sot_admin"),
            password=os.getenv("SOT_DB_PASS", "Inovasi@0918")
        )
        cur = conn.cursor()

        # --- 1. Existing table (JSONB metrics) ---
        sql_history = """
            INSERT INTO dcim_telemetry_history (
                serial_number, hostname, ip_address, device_type,
                site, rack_name, model, firmware, metrics,
                inventory_source, enrichment_status
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """

        # --- 2. New centralized flat metrics table ---
        sql_metrics = """
            INSERT INTO device_metrics (
                collected_at,
                hostname, serial_number, ip_address,
                device_type, category, manufacturer,
                model, firmware_version, inventory_source,
                site, rack_name,
                status, power_state, enrichment_status,
                metric_utilization, metric_temperature,
                metric_power_watts, metric_health, metric_status_detail,
                metrics_raw
            ) VALUES (
                NOW(),
                %s, %s, %s,
                %s, %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s
            )
        """

        for res in results:
            m = res.get("metrics", {})

            # Write to history table
            cur.execute(sql_history, (
                res.get("serial_number"),
                res.get("hostname"),
                res.get("ip_address"),
                res.get("device_type"),
                res.get("site"),
                res.get("rack_name"),
                res.get("model"),
                res.get("firmware"),
                json.dumps(m),
                res.get("inventory_source"),
                res.get("enrichment_status")
            ))

            # Write flat row to device_metrics
            cur.execute(sql_metrics, (
                res.get("hostname"),
                res.get("serial_number"),
                res.get("ip_address"),
                res.get("device_type"),
                res.get("category"),
                res.get("manufacturer"),
                res.get("model"),
                res.get("firmware_version") or res.get("firmware"),
                res.get("inventory_source"),
                res.get("site"),
                res.get("rack_name"),
                res.get("status"),
                res.get("power_state"),
                res.get("enrichment_status"),
                m.get("Utilization"),
                m.get("Temperature"),
                m.get("Power_Watts"),
                m.get("Health_Summary"),
                m.get("Status_Detail"),
                json.dumps(m)
            ))

        conn.commit()
        cur.close()
        conn.close()
    except Exception as e:
        # Fail silently to not break Telegraf ingestion
        pass

def build_location_map():
    # Base: Static Map khusus (Source of Truth Manual jika DB kosong/salah)
    location_map = {
        # SYNOLOGY NAS
        "10.50.0.105": {"site": "Unknown", "rack": "Unknown", "category": "Storage"},
        "10.50.0.106": {"site": "Unknown", "rack": "Unknown", "category": "Storage"},
        "10.50.0.107": {"site": "Unknown", "rack": "Unknown", "category": "Storage"},
        "10.50.0.108": {"site": "Unknown", "rack": "Unknown", "category": "Storage"},
        "10.50.0.109": {"site": "Unknown", "rack": "Unknown", "category": "Storage"},
        "10.50.0.110": {"site": "Unknown", "rack": "Unknown", "category": "Storage"},
        
        # SERVERS (HCI in Rack 2, Render in Rack 2 based on DB)
        "10.50.0.2": {"site": "Unknown", "rack": "Unknown", "category": "Infrastructure"},
        "10.50.0.3": {"site": "Unknown", "rack": "Unknown", "category": "Infrastructure"},
        "10.50.0.4": {"site": "Unknown", "rack": "Unknown", "category": "Infrastructure"},
        "10.50.0.5": {"site": "Unknown", "rack": "Unknown", "category": "Infrastructure"},
        "10.50.0.6": {"site": "Unknown", "rack": "Unknown", "category": "Infrastructure"},

        # UPS (Manual mapping due to SN mismatch with NetBox)
        "192.168.100.140": {"site": "Unknown", "rack": "Unknown", "category": "Infrastructure"},

        # SECURITY (NVR in Rack 1)
        "192.168.1.254": {"site": "Unknown", "rack": "Unknown", "category": "Security"},
    }
    
    # Isi sisa kamera dengan "Wall Mount CCTV Room"
    cam_ips = [f"192.168.1.{i}" for i in list(range(3, 32)) + [33]]
    for ip in cam_ips:
        if ip not in location_map:
            location_map[ip] = {"site": "Unknown", "rack": "Unknown", "category": "Security"}

    # Override dgn SoT PostgreSQL (Dynamic Mapping)
    try:
        conn = psycopg2.connect(
            host=os.getenv("SOT_DB_HOST", "localhost"),
            port=os.getenv("SOT_DB_PORT", "5432"),
            dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
            user=os.getenv("SOT_DB_USER", "sot_admin"),
            password=os.getenv("SOT_DB_PASS", "Inovasi@0918")
        )
        cur = conn.cursor()
        
        # 1. Map by Hostname (Normalisasi: buang prefix FALAH01-)
        cur.execute("""
            SELECT hostname, site, raw_payload->'rack'->>'name' 
            FROM unified_assets WHERE source_system='NetBox'
        """)
        for host, site, rack in cur.fetchall():
            if host:
                norm_host = host.replace("FALAH01-", "").strip()
                location_map[norm_host] = {
                    "site": site or "Unknown",
                    "rack": rack or "Unknown"
                }

        # 2. Map by IP
        cur.execute("""
            SELECT raw_payload->'primary_ip'->>'address', site, raw_payload->'rack'->>'name' 
            FROM unified_assets WHERE source_system='NetBox' AND raw_payload->'primary_ip' IS NOT NULL
        """)
        for ip_raw, site, rack in cur.fetchall():
            if ip_raw:
                ip = ip_raw.split('/')[0]
                location_map[ip] = {
                    "site": site or "Unknown",
                    "rack": rack or "Unknown"
                }
        
        # 3. Map by Serial Number (Paling Stabil)
        cur.execute("""
            SELECT serial_number, site, raw_payload->'rack'->>'name' 
            FROM unified_assets WHERE source_system='NetBox' AND serial_number IS NOT NULL
        """)
        for sn, site, rack in cur.fetchall():
            if sn:
                location_map[sn.strip()] = {
                    "site": site or "Unknown",
                    "rack": rack or "Unknown"
                }
                    
        conn.close()
    except:
        pass
    
    return location_map


results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=30) as ex:
    futures = []
    for ip in REDFISH_SERVERS: futures.append(ex.submit(poll_server, ip))
    for h in UPS_HOSTS: futures.append(ex.submit(poll_ups, h))
    for h in MIKROTIK_HOSTS: futures.append(ex.submit(poll_mikrotik, h))
    for h in NAS_HOSTS: futures.append(ex.submit(poll_nas, h))
    futures.append(ex.submit(poll_hikvision, HIKVISION_NVR["ip"], HIKVISION_NVR["user"], HIKVISION_NVR["password"], "nvr"))
    for h in HIKVISION_CAMERAS: futures.append(ex.submit(poll_hikvision, h["ip"], HIKVISION_CAM_USER, HIKVISION_CAM_PASS, "cctv"))

    for f in concurrent.futures.as_completed(futures):
        res = f.result()
        ip_addr = res.get("ip_address")
        
        # --- Mandatory Fields Recovery (Historical Fallback) ---
        if not res.get("serial_number") or not res.get("hostname"):
            hist = get_historical_data(ip_addr)
            if hist:
                if not res.get("serial_number"): res["serial_number"] = hist["serial_number"]
                if not res.get("hostname"): res["hostname"] = hist["hostname"]

        # Final safety check for hostname (Excel Fallback)
        if not res.get("hostname") or res.get("hostname").lower() == "none":
            res["hostname"] = SERVER_FALLBACK_MAP.get(ip_addr, "")

        if res.get("serial_number") or res.get("hostname"):
            # --- Data Quality: Strip semua whitespace/newline ---
            for key in ["hostname", "model", "product_name", "manufacturer",
                        "firmware_version", "serial_number", "status", "power_state"]:
                if isinstance(res.get(key), str):
                    res[key] = res[key].strip()

            # --- Standarisasi field names ---
            res["ci_id"]      = res.get("serial_number") or f"TEMP-{ip_addr}"
            res["firmware"]   = res.get("firmware_version", "")
            res["ip"]         = ip_addr
            
            res["manufacturer"] = res.get("manufacturer", "Unknown")
            res["state"]        = res.get("status", "Unknown")
            results.append(res)

loc_map = build_location_map()

for res in results:
    host_id = res.get("hostname", "")
    ip_addr = res.get("ip_address", "")

    # Normalisasi Hostname untuk matching (XCC-7D76-J901GKXY -> SERVER-HCI-01 mapping logic)
    # Jika hostname mengandung serial, coba cari mapping serial ke OS hostname
    match_found = False
    
    # 1. Cari berdasarkan IP (Paling Akurat jika IP unik)
    loc_info = loc_map.get(ip_addr)
    
    # 2. Cari berdasarkan Hostname asli
    if not loc_info:
        loc_info = loc_map.get(host_id)
        
    # 3. Cari berdasarkan Serial Number (Langsung)
    if not loc_info:
        loc_info = loc_map.get(res.get("serial_number", ""))
        
    # 4. Cari berdasarkan Serial Number yang diekstrak dari Hostname (Misal: XCC-7D76-J901GKXY -> J901GKXY)
    if not loc_info:
        sn_match = re.search(r'([A-Z0-9]{7,})', host_id)
        if sn_match:
            loc_info = loc_map.get(sn_match.group(1))

    if loc_info:
        res["site"]              = loc_info.get("site", "").strip()
        res["rack_name"]         = loc_info.get("rack", "Unknown").strip()
        res["location"]          = res["rack_name"] # Align with Telegraf tag 'location'
        res["enrichment_status"] = "FULL"
    else:
        # FIT041 Req 2.2.3: Enrichment gagal → field diberi status, data tidak di-drop
        res["site"]              = "Unknown"
        res["rack_name"]         = "Unknown"
        res["location"]          = "Unknown" # Align with Telegraf tag 'location'
        res["enrichment_status"] = "PARTIAL"

# Save to Centralized Telemetry DB (Disabled for Kafka-first architecture)
# save_to_db(results)

print(json.dumps(results))
