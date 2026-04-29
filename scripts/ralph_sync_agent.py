#!/usr/bin/env python3
import requests
import json
import os
import subprocess
from datetime import datetime
from dotenv import load_dotenv
import urllib3
urllib3.disable_warnings()

# Load Config
CONFIG_PATH = '/home/infra/dcim_metrics_project/configs/.env'
load_dotenv(CONFIG_PATH)

# Ralph Configuration
RALPH_API_URL = os.getenv("RALPH_API_URL", "http://192.168.101.73:8088/api/data-center-assets/")
RALPH_TOKEN   = os.getenv("RALPH_API_TOKEN", "")

# Elasticsearch Configuration
ES_URL  = os.getenv("ES_URL", "https://10.70.0.56:9200")
ES_USER = os.getenv("ES_USER", "elastic")
ES_PASS = os.getenv("ES_PASS", "C+H+pFb*aIAqWcOo-X8q")

# Path to Inventory Poller
INVENTORY_SCRIPT = '/home/infra/dcim_metrics_project/scripts/dcim_inventory_poller.py'


def get_current_inventory():
    """Execute the inventory poller and get JSON output."""
    try:
        result = subprocess.check_output(['python3', INVENTORY_SCRIPT], stderr=subprocess.DEVNULL)
        return json.loads(result)
    except Exception as e:
        print(f"Error reading inventory: {e}")
        return []


def get_latest_metrics_from_pg(serial_number):
    """
    Query PostgreSQL (V1 - dcim_events) for the latest telemetry for a given device.
    """
    import psycopg2
    from psycopg2.extras import RealDictCursor
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("PGDATABASE", "dcim_sot"),
            user=os.getenv("PGUSER", "sot_admin"),
            password=os.getenv("PGPASSWORD", "Inovasi@0918"),
            host=os.getenv("PGHOST", "192.168.101.73"),
            port=os.getenv("PGPORT", "5432")
        )
        # Use RealDictCursor to get column names as keys
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute("SELECT * FROM dcim_events WHERE serial_number = %s ORDER BY event_time DESC LIMIT 1;", (serial_number,))
        row = cur.fetchone()
        cur.close()
        conn.close()
        return row if row else {}
    except Exception as e:
        print(f"Error querying Postgres V1: {e}")
        return {}


def update_ralph_component(endpoint, asset_id, payload, headers):
    """Helper to update or create a Ralph component (Memory, Ethernet, etc.)"""
    # 1. Check if component already exists for this base_object
    search_url = f"http://192.168.101.73:8088/api/{endpoint}/?base_object={asset_id}"
    try:
        resp = requests.get(search_url, headers=headers, verify=False, timeout=5)
        if resp.ok:
            results = resp.json().get("results", [])
            if results:
                # Update existing
                comp_id = results[0]['id']
                requests.patch(f"http://192.168.101.73:8088/api/{endpoint}/{comp_id}/", 
                               headers=headers, json=payload, verify=False, timeout=5)
                return True
            else:
                # Create new
                payload["base_object"] = asset_id
                requests.post(f"http://192.168.101.73:8088/api/{endpoint}/", 
                              headers=headers, json=payload, verify=False, timeout=5)
                return True
    except:
        pass
    return False


def sync_to_ralph(devices):
    """Sync telemetry data to Ralph CMDB Native Fields."""
    if not RALPH_TOKEN:
        print("Error: RALPH_API_TOKEN is missing.")
        return

    headers = {"Authorization": f"Token {RALPH_TOKEN}", "Content-Type": "application/json"}
    print(f"--- Starting Ralph Deep Sync (V1) at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ---")

    for dev in devices:
        sn = dev.get("serial_number")
        hostname = dev.get("hostname", "Unknown")
        if not sn or sn == "Unknown" or len(sn) < 3: continue

        # 1. Search Asset in Ralph
        found_asset = None
        target_endpoint = None
        for endpoint in ["data-center-assets", "back-office-assets"]:
            search_url = f"http://192.168.101.73:8088/api/{endpoint}/?sn={sn}"
            try:
                resp = requests.get(search_url, headers=headers, verify=False, timeout=5)
                if resp.status_code == 200:
                    res = resp.json().get("results", [])
                    if res:
                        found_asset = res[0]
                        target_endpoint = endpoint
                        break
            except: continue

        if not found_asset: continue
        asset_id = found_asset.get("id")
        
        # 2. Get Data from Postgres V1
        v1_data = get_latest_metrics_from_pg(sn)
        
        # 3. Uniform Naming Logic
        clean_hostname = hostname.replace("FALAH01-", "").strip()
        
        # 4. Basic Info Payload
        payload = {
            "hostname": clean_hostname,
            "sn": sn,
            "remarks": f"Last Sync: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Source: V1 Postgres)"
        }
        
        # Native Fields Mapping
        firmware = v1_data.get("srv_firmware") or v1_data.get("ups_firmware") or dev.get("firmware_version")
        if firmware: payload["firmware_version"] = firmware
        
        # 5. Component Updates
        # A. Memory
        ram_mb = v1_data.get("srv_memory_total_mb")
        if ram_mb:
            update_ralph_component("memory", asset_id, {"size": int(ram_mb), "model_name": "System RAM"}, headers)
        
        # B. Ethernet / Network
        mac = v1_data.get("net_if_phys_address") or v1_data.get("ups_serial_snmp") # Some devices use SN as Mac label
        ip = v1_data.get("ip") or dev.get("ip_address")
        if mac or ip:
            eth_payload = {}
            if mac: eth_payload["mac"] = mac
            if ip: eth_payload["ipaddress"] = ip
            update_ralph_component("ethernets", asset_id, eth_payload, headers)

        # 6. Final Asset PATCH
        update_url = f"http://192.168.101.73:8088/api/{target_endpoint}/{asset_id}/"
        requests.patch(update_url, headers=headers, json=payload, verify=False, timeout=5)
        print(f"  [SUCCESS] {clean_hostname} Deep Synced.")

    print(f"--- Sync Completed. ---")


if __name__ == "__main__":
    inventory = get_current_inventory()
    if inventory:
        sync_to_ralph(inventory)
    else:
        print("No inventory data found to sync.")
