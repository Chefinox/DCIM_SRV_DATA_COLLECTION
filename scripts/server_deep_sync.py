#!/usr/bin/env python3
import requests
import json
import urllib3
import logging
import os
from datetime import datetime
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIGURATION ---
load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

REDFISH_SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
REDFISH_USER = "poller"
REDFISH_PASS = "F!tech0918"

RALPH_API_BASE = "http://192.168.101.73:8088/api"
RALPH_TOKEN = "60bcedc875ec7b03b983082655e473e9519d40d5"

LOG_FILE = "/home/infra/dcim_metrics_project/logs/server_deep_sync.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

SPEED_MAP = {10: 1, 100: 2, 1000: 3, 10000: 4, 25000: 7, 40000: 5, 100000: 6}

# --- REDFISH UTILITIES ---

def get_redfish_data(url, auth):
    try:
        resp = requests.get(url, auth=auth, verify=False, timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logging.error(f"Redfish error on {url}: {e}")
    return None

def deep_collect_server(ip):
    auth = (REDFISH_USER, REDFISH_PASS)
    base_url = f"https://{ip}/redfish/v1"
    
    data = {
        "ip": ip,
        "basic_info": {"hostname": None, "serial_number": None, "bios_version": None, "firmware_version": None},
        "processors": [], "memory": [], "ethernets": [], "disks": []
    }
    
    sys_url = f"{base_url}/Systems/1"
    sys_data = get_redfish_data(sys_url, auth)
    if sys_data:
        data["basic_info"]["serial_number"] = sys_data.get("SerialNumber")
        data["basic_info"]["bios_version"] = sys_data.get("BiosVersion")
    
    chassis_url = f"{base_url}/Chassis/1"
    chassis_data = get_redfish_data(chassis_url, auth)
    if chassis_data:
        loc_name = chassis_data.get("Location", {}).get("PostalAddress", {}).get("Name")
        if loc_name: data["basic_info"]["hostname"] = loc_name.strip()
    
    mgr_url = f"{base_url}/Managers/1"
    mgr_data = get_redfish_data(mgr_url, auth)
    if mgr_data: data["basic_info"]["firmware_version"] = mgr_data.get("FirmwareVersion")

    proc_coll = get_redfish_data(f"{sys_url}/Processors", auth)
    if proc_coll:
        for member in proc_coll.get("Members", []):
            p = get_redfish_data(f"https://{ip}{member['@odata.id']}", auth)
            if p and p.get("Status", {}).get("State") != "Absent":
                data["processors"].append({"model_name": p.get("Model"), "cores": p.get("TotalCores"), "logical_cores": p.get("TotalThreads"), "speed": p.get("MaxSpeedMHz")})

    mem_coll = get_redfish_data(f"{sys_url}/Memory", auth)
    if mem_coll:
        for member in mem_coll.get("Members", []):
            m = get_redfish_data(f"https://{ip}{member['@odata.id']}", auth)
            if m:
                if (m.get("CapacityMiB") or 0) > 0 and m.get("Status", {}).get("State") != "Absent":
                    data["memory"].append({"model_name": m.get("VendorID") or m.get("Manufacturer") or m.get("PartNumber"), "size": m.get("CapacityMiB"), "speed": m.get("OperatingSpeedMhz")})

    eth_coll = get_redfish_data(f"{sys_url}/EthernetInterfaces", auth)
    if eth_coll:
        for member in eth_coll.get("Members", []):
            e = get_redfish_data(f"https://{ip}{member['@odata.id']}", auth)
            if e and e.get("MACAddress") and e.get("Id") != "ToManager":
                data["ethernets"].append({"label": e.get("Id"), "mac": e.get("MACAddress"), "speed": SPEED_MAP.get(e.get("SpeedMbps", 0), 11), "model_name": e.get("Description") or "Ethernet Interface"})

    storage_coll = get_redfish_data(f"{sys_url}/Storage", auth)
    if storage_coll:
        for controller in storage_coll.get("Members", []):
            c_data = get_redfish_data(f"https://{ip}{controller['@odata.id']}", auth)
            if c_data:
                for drive in c_data.get("Drives", []):
                    d = get_redfish_data(f"https://{ip}{drive['@odata.id']}", auth)
                    if d and d.get("SerialNumber") and d.get("Status", {}).get("State") != "Absent":
                        slot = d.get("Id")
                        phys_loc = d.get("PhysicalLocation", {})
                        part_loc = phys_loc.get("PartLocation", {})
                        if part_loc.get("LocationOrdinalValue") is not None: slot = str(part_loc.get("LocationOrdinalValue"))
                        data["disks"].append({"model_name": d.get("Name") or d.get("Model"), "serial_number": d.get("SerialNumber"), "size": int(d.get("CapacityBytes", 0) / (1024**3)), "firmware_version": d.get("Revision"), "slot": slot})
    
    return data

# --- RALPH SYNC UTILITIES ---

def ralph_get_all(url, headers):
    """Fetch ALL results from a Ralph API endpoint, handling pagination."""
    results = []
    next_url = f"{url}&limit=200" if "?" in url else f"{url}?limit=200"
    while next_url:
        resp = requests.get(next_url, headers=headers, verify=False)
        if not resp.ok:
            break
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = data.get("next")
    return results

def sync_disks(asset_id, redfish_disks):
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    endpoint = f"{RALPH_API_BASE}/disks/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}", headers)
    
    current_sns = {d["serial_number"]: d for d in redfish_disks}
    processed_sns = set()

    # 1. Update or Create current ones
    for d in redfish_disks:
        sn = d["serial_number"]
        payload = {"base_object": asset_id, "model_name": d["model_name"], "serial_number": sn, "size": d["size"], "firmware_version": d["firmware_version"], "slot": d["slot"]}
        # Find FIRST existing disk with this SN
        match = next((e for e in existing if e["serial_number"] == sn), None)
        if match:
            requests.patch(f"{endpoint}{match['id']}/", headers=headers, json=payload, verify=False)
        else:
            requests.post(endpoint, headers=headers, json=payload, verify=False)
        processed_sns.add(sn)

    # 2. Delete ALL duplicates or obsolete ones
    # We must fetch again or use the original list and keep track of which ID we already used/updated
    # Re-fetch is safer to ensure we see the current state
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}", headers)
    already_synced_ids = set()
    
    # We want to keep only ONE entry per current SN, and delete everything else
    for disk in final_existing:
        sn = disk["serial_number"]
        if sn not in current_sns or sn in already_synced_ids:
            logging.info(f"Robust Pruning: Deleting disk ID {disk['id']} (SN: {sn})")
            requests.delete(f"{endpoint}{disk['id']}/", headers=headers, verify=False)
        else:
            already_synced_ids.add(sn)

def sync_ethernets(asset_id, redfish_eths):
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    endpoint = f"{RALPH_API_BASE}/ethernets/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}", headers)
    
    current_labels = {e["label"]: e for e in redfish_eths}
    processed_labels = set()

    for e in redfish_eths:
        label = e["label"]
        payload = {"base_object": asset_id, "label": label, "mac": e["mac"], "speed": e["speed"], "model_name": e["model_name"]}
        match = next((ex for ex in existing if ex["label"] == label), None)
        if match:
            requests.patch(f"{endpoint}{match['id']}/", headers=headers, json=payload, verify=False)
        else:
            requests.post(endpoint, headers=headers, json=payload, verify=False)
        processed_labels.add(label)

    # Prune duplicates/obsolete
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}", headers)
    already_synced_labels = set()
    for eth in final_existing:
        lbl = eth["label"]
        if lbl not in current_labels or lbl in already_synced_labels:
            logging.info(f"Robust Pruning: Deleting ethernet ID {eth['id']} (Label: {lbl})")
            requests.delete(f"{endpoint}{eth['id']}/", headers=headers, verify=False)
        else:
            already_synced_labels.add(lbl)

def sync_generic_components(asset_id, category, redfish_items):
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    endpoint = f"{RALPH_API_BASE}/{category}/"
    existing = ralph_get_all(f"{endpoint}?base_object={asset_id}", headers)
    
    # Generic sync: we just match by index for simplicity if no serial exists
    for i, item in enumerate(redfish_items):
        payload = item.copy()
        payload["base_object"] = asset_id
        if i < len(existing):
            requests.patch(f"{endpoint}{existing[i]['id']}/", headers=headers, json=payload, verify=False)
        else:
            requests.post(endpoint, headers=headers, json=payload, verify=False)
            
    # Prune extra
    final_existing = ralph_get_all(f"{endpoint}?base_object={asset_id}", headers)
    if len(final_existing) > len(redfish_items):
        for i in range(len(redfish_items), len(final_existing)):
            requests.delete(f"{endpoint}{final_existing[i]['id']}/", headers=headers, verify=False)

def update_management_info(asset_id, ip, hostname):
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    search_url = f"{RALPH_API_BASE}/ipaddresses/?ethernet__base_object={asset_id}&is_management=True"
    resp = requests.get(search_url, headers=headers, verify=False)
    if resp.ok and resp.json()["results"]:
        ip_obj = resp.json()["results"][0]
        requests.patch(f"{RALPH_API_BASE}/ipaddresses/{ip_obj['id']}/", headers=headers, json={"address": ip, "hostname": hostname}, verify=False)
    else:
        eth_url = f"{RALPH_API_BASE}/ethernets/?base_object={asset_id}"
        eth_resp = requests.get(eth_url, headers=headers, verify=False)
        if eth_resp.ok and eth_resp.json()["results"]:
            eth_id = eth_resp.json()["results"][0]["id"]
            requests.post(f"{RALPH_API_BASE}/ipaddresses/", headers=headers, json={"address": ip, "hostname": hostname, "is_management": True, "ethernet": eth_id}, verify=False)

def run_sync():
    logging.info("=== STARTING DEEP SERVER SYNC (REFINED V7 - PAGINATION FIX) ===")
    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    for ip in REDFISH_SERVERS:
        logging.info(f"Processing server {ip}...")
        raw = deep_collect_server(ip)
        sn = raw["basic_info"].get("serial_number")
        if not sn: continue
        asset = requests.get(f"{RALPH_API_BASE}/data-center-assets/?sn={sn}", headers=headers, verify=False).json()["results"]
        if not asset: continue
        asset_id = asset[0]["id"]
        hostname = raw["basic_info"].get("hostname")
        requests.patch(f"{RALPH_API_BASE}/data-center-assets/{asset_id}/", headers=headers, json={"hostname": hostname, "firmware_version": raw["basic_info"].get("firmware_version"), "bios_version": raw["basic_info"].get("bios_version"), "custom_fields": {"power_consumption": None, "device_temperature": None}}, verify=False)
        update_management_info(asset_id, ip, hostname)
        sync_generic_components(asset_id, "memory", raw["memory"])
        sync_generic_components(asset_id, "processors", raw["processors"])
        sync_ethernets(asset_id, raw["ethernets"])
        sync_disks(asset_id, raw["disks"])
    logging.info("=== SYNC COMPLETED ===")

if __name__ == "__main__":
    run_sync()
