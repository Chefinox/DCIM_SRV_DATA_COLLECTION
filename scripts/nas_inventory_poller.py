#!/usr/bin/env python3
"""
Synology NAS Poller — Unified DCIM Inventory & Metrics
======================================================
Polls all Synology NAS devices via DSM REST API and outputs
JSON compatible with Telegraf inputs.exec + json_v2 parser.

Outputs TWO measurement types:
  - nas_inventory  : identity/asset data -> dcim-inventory-*
  - nas_metrics    : operational metrics  -> telegraf-nas-*

Author  : DCIM Team
Version : 1.0.0
"""

import json
import logging
import sys
import urllib.request
import urllib.parse
import ssl
import concurrent.futures
import re
from datetime import datetime, timezone

from dotenv import load_dotenv
import os

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

# ─── CONFIG ────────────────────────────────────────────────────────────────────
NAS_HOSTS = [
    {"hostname": "NAS-INFRA",  "ip": "10.50.0.106"},
    {"hostname": "NAS-FAT",   "ip": "10.50.0.107"},
    {"hostname": "NAS-SD01",  "ip": "10.50.0.108"},
    {"hostname": "NAS-CD01",  "ip": "10.50.0.109"},
    {"hostname": "NAS-CD02",  "ip": "10.50.0.110"},
    {
        "hostname": "NAS-FIT",
        "ip": "10.50.0.105",
        "method": "snmp",
        "snmp_user": os.getenv("NAS_USER", "hndept"),
        "snmp_pass": os.getenv("NAS_PASS_SNMP", "")
    },
]

NAS_USERNAME = os.getenv("NAS_USER", "hndept")
NAS_PASSWORD = os.getenv("NAS_PASS_REST", "")
NAS_PORT     = 5001   # DSM HTTPS port
TIMEOUT      = 15     # seconds

# ─── HELPERS ──────────────────────────────────────────────────────────────────
logging.basicConfig(level=logging.WARNING, stream=sys.stderr)
log = logging.getLogger("nas_poller")

# Disable SSL verification globally (self-signed certs)
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode    = ssl.CERT_NONE


import subprocess

# ─── SNMP OIDS (Synology) ──────────────────────────────────────────────────────
OID_MODEL    = ".1.3.6.1.4.1.6574.1.5.1.0"
OID_SERIAL   = ".1.3.6.1.4.1.6574.1.5.2.0"
OID_VERSION  = ".1.3.6.1.4.1.6574.1.5.3.0"
OID_TEMP     = ".1.3.6.1.4.1.6574.1.2.0"
OID_UPTIME   = ".1.3.6.1.2.1.1.3.0"
# Storage OIDs
OID_VOL_NAME = ".1.3.6.1.4.1.6574.3.1.1.2"
OID_VOL_TOTAL = ".1.3.6.1.4.1.6574.3.1.1.5"
OID_VOL_USED  = ".1.3.6.1.4.1.6574.3.1.1.4"
OID_VOL_STATUS = ".1.3.6.1.4.1.6574.3.1.1.3"
# Disk OIDs
OID_DISK_ID     = ".1.3.6.1.4.1.6574.2.1.1.2"
OID_DISK_MODEL  = ".1.3.6.1.4.1.6574.2.1.1.3"
OID_DISK_STATUS = ".1.3.6.1.4.1.6574.2.1.1.5"
OID_DISK_TEMP   = ".1.3.6.1.4.1.6574.2.1.1.6"

def _get_snmp(ip: str, user: str, password: str, oid: str, walk: bool = False) -> str | list:
    """Run snmpget or snmpwalk and return result."""
    cmd = ["snmpwalk" if walk else "snmpget", "-v", "3", "-u", user, "-l", "authPriv", 
           "-a", "SHA", "-A", password, "-x", "AES", "-X", password, ip, oid]
    try:
        res = subprocess.check_output(cmd, stderr=subprocess.DEVNULL).decode()
        if not walk:
            # Extract value after = and handle various formats
            raw_val = res.split("=")[-1].strip()
            # Remove "STRING: ", "INTEGER: ", etc.
            clean_val = re.sub(r'^[A-Za-z0-9]+:\s+', '', raw_val)
            # Remove surrounding quotes
            return clean_val.strip('"')
        
        # For walk, return list of clean values
        lines = res.strip().split("\n")
        return [re.sub(r'^[A-Za-z0-9]+:\s+', '', l.split("=")[-1].strip()).strip('"') for l in lines]
    except Exception:
        return "" if not walk else []


def poll_nas_snmp(host: dict) -> list[dict]:
    """Poll NAS via SNMPv3 (fallback for NAS-FIT with 2FA)."""
    ip       = host["ip"]
    hostname = host["hostname"]
    user     = host.get("snmp_user", "hndept")
    pw       = host.get("snmp_pass", "F!tech0918")
    results  = []
    ts       = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    model    = _get_snmp(ip, user, pw, OID_MODEL)
    if not model:
        # Offline fallback
        results.append({
            "measurement": "nas_inventory",
            "tags": {"serial_number": hostname, "hostname": hostname, "ip": ip, "device_type": "nas", "category": "infrastructure"},
            "fields": {"status": "Offline", "manufacturer": "Synology"},
            "timestamp": ts
        })
        return results

    serial   = _get_snmp(ip, user, pw, OID_SERIAL)
    version  = _get_snmp(ip, user, pw, OID_VERSION)
    temp     = int(_get_snmp(ip, user, pw, OID_TEMP) or 0)
    uptime   = _get_snmp(ip, user, pw, OID_UPTIME)

    # Volumes
    vol_names  = _get_snmp(ip, user, pw, OID_VOL_NAME, walk=True)
    vol_totals = _get_snmp(ip, user, pw, OID_VOL_TOTAL, walk=True)
    vol_useds  = _get_snmp(ip, user, pw, OID_VOL_USED, walk=True)
    vol_stats  = _get_snmp(ip, user, pw, OID_VOL_STATUS, walk=True)

    agg_total = agg_used = agg_free = 0
    vol_count = 0
    
    # Parse walk output
    for i in range(len(vol_names)):
        try:
            v_name = vol_names[i].split("=")[-1].strip().strip('"').replace("STRING: ", "")
            v_total = int(vol_totals[i].split("=")[-1].strip().replace("Counter64: ", ""))
            v_used  = int(vol_useds[i].split("=")[-1].strip().replace("Counter64: ", ""))
            v_status = vol_stats[i].split("=")[-1].strip().replace("INTEGER: ", "")
            status_map = {"1": "normal", "2": "degraded", "3": "crashed"}
            v_status_str = status_map.get(v_status, "normal")
            
            agg_total += v_total
            agg_used  += v_used
            vol_count += 1
            
            results.append({
                "measurement": "nas_volume",
                "serial_number": serial, "hostname": hostname, "ip": ip, "device_type": "nas", "volume_id": v_name,
                "total_bytes": v_total, "used_bytes": v_used, "free_bytes": v_total - v_used, "status": v_status_str,
                "timestamp": ts
            })
        except: continue

    # Disks
    disk_ids   = _get_snmp(ip, user, pw, OID_DISK_ID, walk=True)
    disk_mods  = _get_snmp(ip, user, pw, OID_DISK_MODEL, walk=True)
    disk_temps = _get_snmp(ip, user, pw, OID_DISK_TEMP, walk=True)
    disk_stats = _get_snmp(ip, user, pw, OID_DISK_STATUS, walk=True)
    
    for i in range(len(disk_ids)):
        try:
            d_id = disk_ids[i]
            d_mod = disk_mods[i]
            d_temp = int(disk_temps[i])
            results.append({
                "measurement": "nas_disk",
                "serial_number": serial, "hostname": hostname, "ip": ip, "device_type": "nas", "disk_id": d_id, "disk_model": d_mod,
                "temp_celsius": d_temp, "status": "normal",
                "timestamp": ts
            })
        except: continue

    # Inventory
    results.insert(0, {
        "measurement": "nas_inventory",
        "serial_number": serial, "hostname": hostname, "ip": ip, "device_type": "nas", "category": "infrastructure",
        "model": model, "firmware": version, "manufacturer": "Synology", "temp_celsius": temp, "uptime": uptime, "status": "Online",
        "volumes_total_bytes": agg_total, "volumes_used_bytes": agg_used, "volumes_free_bytes": agg_total - agg_used,
        "disk_count": len(disk_ids),
        "timestamp": ts
    })
    return results

def _get(ip: str, path: str, params: dict, port: int = NAS_PORT) -> dict:
    """Make an HTTPS GET request to the DSM API."""
    qs  = urllib.parse.urlencode(params)
    url = f"https://{ip}:{port}/webapi/{path}?{qs}"
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req, context=SSL_CTX, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode())
    except Exception as exc:
        log.warning("GET %s failed: %s", url, exc)
        return {}


def _login(ip: str, username: str = NAS_USERNAME, password: str = NAS_PASSWORD, port: int = NAS_PORT) -> str | None:
    """Authenticate and return a session ID (sid)."""
    res = _get(ip, "auth.cgi", {
        "api":     "SYNO.API.Auth",
        "version": "3",
        "method":  "login",
        "account": username,
        "passwd":  password,
        "format":  "sid",
    }, port=port)
    if res.get("success"):
        return res["data"]["sid"]
    log.error("Login failed for %s: %s", ip, res.get("error"))
    return None


def _logout(ip: str, sid: str, port: int = NAS_PORT):
    """Invalidate session."""
    _get(ip, "auth.cgi", {
        "api":     "SYNO.API.Auth",
        "version": "1",
        "method":  "logout",
        "_sid":    sid,
    }, port=port)


# ─── POLL ONE NAS ─────────────────────────────────────────────────────────────
def poll_nas(host: dict) -> list[dict]:
    """Poll a single NAS, return a list of Telegraf measurement dicts."""
    ip       = host["ip"]
    hostname = host["hostname"]
    username = host.get("username", NAS_USERNAME)
    password = host.get("password", NAS_PASSWORD)
    port     = host.get("port", NAS_PORT)
    results  = []
    ts       = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    sid = _login(ip, username, password, port=port)
    if not sid:
        # Emit an offline record so the device still appears in inventory
        results.append({
            "measurement": "nas_inventory",
            "tags": {
                "serial_number": hostname,   # best-effort fallback key
                "hostname":      hostname,
                "ip":            ip,
                "device_type":   "nas",
                "category":      "infrastructure",
            },
            "fields": {
                "model":          "",
                "firmware":       "",
                "manufacturer":   "Synology",
                "ram_mb":         0,
                "cpu_cores":      0,
                "temp_celsius":   0,
                "status":         "Offline",
            },
            "timestamp": ts,
        })
        return results

    # ── 1. System Info ────────────────────────────────────────────────────────
    sys_info = {}
    try:
        res = _get(ip, "entry.cgi", {
            "api":     "SYNO.Core.System",
            "version": "1",
            "method":  "info",
            "_sid":    sid,
        }, port=port)
        if res.get("success"):
            sys_info = res["data"]
    except Exception as exc:
        log.warning("[%s] System info error: %s", hostname, exc)

    model         = sys_info.get("model", "")
    serial        = sys_info.get("serial", hostname)
    firmware      = sys_info.get("firmware_ver", "")
    ram_mb        = int(sys_info.get("ram_size", 0))
    sys_temp      = int(sys_info.get("sys_temp", 0))
    cpu_vendor    = sys_info.get("cpu_vendor", "Intel")
    cpu_series    = sys_info.get("cpu_series", "")
    cpu_cores_raw = sys_info.get("cpu_cores", "0")
    cpu_cores     = int(cpu_cores_raw) if str(cpu_cores_raw).isdigit() else 0
    up_time       = sys_info.get("up_time", "")

    # ── 2. Utilization (CPU / RAM / Network / Disk IO) ────────────────────────
    cpu_user = cpu_sys = cpu_other = mem_usage = net_rx = net_tx = 0
    disk_read_bytes = disk_write_bytes = 0
    try:
        res = _get(ip, "entry.cgi", {
            "api":     "SYNO.Core.System.Utilization",
            "version": "1",
            "method":  "get",
            "_sid":    sid,
        }, port=port)
        if res.get("success"):
            u = res["data"]
            cpu_user  = u.get("cpu", {}).get("user_load",  0)
            cpu_sys   = u.get("cpu", {}).get("system_load", 0)
            cpu_other = u.get("cpu", {}).get("other_load", 0)
            mem_usage = u.get("memory", {}).get("real_usage", 0)
            # network total
            for net in u.get("network", []):
                if net.get("device") == "total":
                    net_rx = net.get("rx", 0)
                    net_tx = net.get("tx", 0)
                    break
            # disk total IO
            disk_total = u.get("disk", {}).get("total", {})
            disk_read_bytes  = disk_total.get("read_byte",  0)
            disk_write_bytes = disk_total.get("write_byte", 0)
    except Exception as exc:
        log.warning("[%s] Utilization error: %s", hostname, exc)

    # ── 3. Storage (Volumes + Disks) ──────────────────────────────────────────
    volumes_total_bytes = volumes_used_bytes = volumes_free_bytes = 0
    disk_records = []
    volume_status = "normal"
    try:
        res = _get(ip, "entry.cgi", {
            "api":     "SYNO.Storage.CGI.Storage",
            "version": "1",
            "method":  "load_info",
            "_sid":    sid,
        }, port=port)
        if res.get("success"):
            data = res["data"]
            for vol in data.get("volumes", []):
                sz = vol.get("size", {})
                total = int(sz.get("total", 0))
                used  = int(sz.get("used",  0))
                free  = total - used
                volumes_total_bytes += total
                volumes_used_bytes  += used
                volumes_free_bytes  += free
                vstatus = vol.get("status", "unknown")
                if vstatus != "normal":
                    volume_status = vstatus   # escalate if any volume is degraded
                # per-volume metric record
                results.append({
                    "measurement": "nas_volume",
                    "serial_number": serial,
                    "hostname":      hostname,
                    "ip":            ip,
                    "device_type":   "nas",
                    "category":      "infrastructure",
                    "volume_id":     vol.get("id", ""),
                    "fs_type":       vol.get("fs_type", ""),
                    "raid_type":     vol.get("device_type", ""),
                    "total_bytes": total,
                    "used_bytes":  used,
                    "free_bytes":  free,
                    "status":      vstatus,
                    "timestamp": ts,
                })

            for disk in data.get("disks", []):
                disk_id = disk.get("id", "")
                disk_model = disk.get("model", "")
                disk_status = disk.get("status", "unknown")
                disk_temp = int(disk.get("temp", 0))
                disk_serial = disk.get("serial", "")
                
                disk_records.append({
                    "name": disk_id, "model": disk_model, "status": disk_status, "temp": disk_temp, "serial": disk_serial
                }) 
                # per-disk metric record
                results.append({
                    "measurement": "nas_disk",
                    "serial_number": serial,
                    "hostname":      hostname,
                    "ip":            ip,
                    "device_type":   "nas",
                    "category":      "infrastructure",
                    "disk_id":       disk_id,
                    "disk_model":    disk_model,
                    "temp_celsius":  disk_temp,
                    "status":        disk_status,
                    "timestamp": ts,
                })
    except Exception as exc:
        log.warning("[%s] Storage error: %s", hostname, exc)

    # ── 4. Build Inventory Record (dcim-inventory-*) ──────────────────────────
    results.insert(0, {
        "measurement": "nas_inventory",
        "serial_number": serial,
        "hostname":      hostname,
        "ip":            ip,
        "device_type":   "nas",
        "category":      "infrastructure",
        "model":          model,
        "firmware":       firmware,
        "manufacturer":   "Synology",
        "cpu_vendor":     cpu_vendor,
        "cpu_series":     cpu_series,
        "cpu_cores":      cpu_cores,
        "ram_mb":         ram_mb,
        "temp_celsius":   sys_temp,
        "uptime":         up_time,
        "status":         "Online" if volume_status == "normal" else volume_status,
        "cpu_user_pct":   cpu_user,
        "cpu_sys_pct":    cpu_sys,
        "cpu_other_pct":  cpu_other,
        "mem_usage_pct":  mem_usage,
        "net_rx_kbps":    net_rx,
        "net_tx_kbps":    net_tx,
        "disk_read_bytes":  disk_read_bytes,
        "disk_write_bytes": disk_write_bytes,
        "volumes_total_bytes": volumes_total_bytes,
        "volumes_used_bytes":  volumes_used_bytes,
        "volumes_free_bytes":  volumes_free_bytes,
        "disk_count":          len(disk_records),
        "timestamp": ts,
    })

    _logout(ip, sid, port=port)
    return results


# ─── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    all_results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
        futures = {}
        for host in NAS_HOSTS:
            if host.get("method") == "snmp":
                futures[executor.submit(poll_nas_snmp, host)] = host
            else:
                futures[executor.submit(poll_nas, host)] = host
        
    all_results = []
    for future in concurrent.futures.as_completed(futures):
        host = futures[future]
        try:
            all_results.extend(future.result())
        except Exception as exc:
            log.error("Fatal error polling %s: %s", host["hostname"], exc)

    print(json.dumps(all_results, indent=2))

if __name__ == "__main__":
    main()
