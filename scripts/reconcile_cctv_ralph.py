#!/usr/bin/env python3
"""
Reconcile CCTV Inventory in Ralph CMDB
1. Query NVR (192.168.1.254) for real serial numbers, models, and firmware versions of all 31 cameras.
2. Scan Ralph Back Office Assets, find and delete all placeholder assets (SN: CCTV-IP-*).
3. Register all missing cameras using their real serial numbers.
"""

import argparse
import urllib3
import requests
import xml.etree.ElementTree as ET
import re
import sys
import os
import time

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# --- CONFIG ---
RALPH_API_BASE = "http://192.168.100.115:8088/api"
RALPH_TOKEN = "1cd05b8d36e258399a52c59f1a4016addb2346a3"
RALPH_HEADERS = {
    "Authorization": f"Token {RALPH_TOKEN}",
    "Content-Type": "application/json"
}

NVR_IP = "192.168.1.254"
NVR_USER = "admin"
NVR_PASS = "qRvbi883=Zk[Q)@5"

CCTV_DEFAULT_MODEL = "DS-2CD1121-I"
REGION_ID = 1
WAREHOUSE_ID = 1
MANUFACTURER_HIKVISION_ID = 8

CCTV_TARGETS = {
    "192.168.1.2": "R. Content 2 View2",
    "192.168.1.3": "R. Content 2 View1",
    "192.168.1.4": "Koridor Mess Lt.2",
    "192.168.1.5": "R. Server",
    "192.168.1.6": "Gate In",
    "192.168.1.7": "R. Resepsionis",
    "192.168.1.8": "R. Meeting Lt.1",
    "192.168.1.9": "R. Lead Content",
    "192.168.1.10": "R. Content 4 Lt.2",
    "192.168.1.11": "Musholla",
    "192.168.1.12": "View Gudang & Toilet Lt.1",
    "192.168.1.13": "R. Infra",
    "192.168.1.14": "View FAT & CEO Lt.2",
    "192.168.1.15": "View Koridor Lt.2",
    "192.168.1.16": "Gate Out 2",
    "192.168.1.17": "R. SD 1 Lt.2",
    "192.168.1.18": "Pantry",
    "192.168.1.19": "Gate Out 1",
    "192.168.1.20": "Showroom 1",
    "192.168.1.21": "R. Project Lt.1",
    "192.168.1.22": "Showroom 2",
    "192.168.1.23": "R. Procurement",
    "192.168.1.24": "Break Room",
    "192.168.1.25": "Gudang Lt.2",
    "192.168.1.26": "R. Project Lt.2",
    "192.168.1.27": "R.BD",
    "192.168.1.28": "R.SD 2 Lt.2",
    "192.168.1.29": "R.Content 1 Lt.2",
    "192.168.1.30": "R. HRD",
    "192.168.1.31": "View Tangga",
    "192.168.1.33": "R. Security",
}


def parse_isapi_xml(xml_string):
    """Recursively converts ISAPI XML responses to Python dictionaries."""
    if not xml_string:
        return {}
    try:
        clean_xml = re.sub(r'\sxmlns="[^"]+"', '', xml_string)
        root = ET.fromstring(clean_xml)
        return _xml_to_dict(root)
    except Exception as e:
        print(f"XML Parse error: {e}")
        return {}


def _xml_to_dict(node):
    data = {}
    for child in node:
        tag = child.tag.split('}')[-1]
        if len(child) > 0:
            child_data = _xml_to_dict(child)
        else:
            child_data = child.text.strip() if child.text else ""
        
        if tag in data:
            if not isinstance(data[tag], list):
                data[tag] = [data[tag]]
            data[tag].append(child_data)
        else:
            data[tag] = child_data
    return data


def discover_nvr_channels():
    """Query NVR to get a mapping of {camera_ip: {serial_number, model, firmware, hostname}}."""
    print(f"Connecting to NVR at {NVR_IP}...")
    url = f"http://{NVR_IP}/ISAPI/ContentMgmt/InputProxy/channels"
    
    try:
        r = requests.get(url, auth=requests.auth.HTTPDigestAuth(NVR_USER, NVR_PASS), timeout=15)
        if not r.ok:
            print(f"NVR query failed: HTTP {r.status_code}")
            return {}
        
        mapping = {}
        parsed = parse_isapi_xml(r.text)
        channels = parsed.get("InputProxyChannel", [])
        if isinstance(channels, dict):
            channels = [channels]
            
        for ch in channels:
            desc = ch.get("sourceInputPortDescriptor") or {}
            ip = desc.get("ipAddress")
            sn = desc.get("serialNumber")
            model = desc.get("model")
            fw = desc.get("firmwareVersion")
            name = ch.get("name")
            if ip and sn:
                # Remove build text from firmware
                if fw and "build" in fw:
                    fw = fw.split("build")[0].strip()
                mapping[ip] = {
                    "serial_number": sn,
                    "model": model or CCTV_DEFAULT_MODEL,
                    "firmware": fw,
                    "hostname": name
                }
        print(f"Discovered {len(mapping)} channels from NVR")
        return mapping
    except Exception as e:
        print(f"Error querying NVR: {e}")
        return {}


def ralph_get_all(endpoint):
    """Fetch all pages from Ralph API."""
    results = []
    if endpoint.startswith("http"):
        next_url = endpoint
    else:
        separator = "&" if "?" in endpoint else "?"
        base = RALPH_API_BASE.rstrip('/')
        clean_endpoint = endpoint.strip('/')
        next_url = f"{base}/{clean_endpoint}{separator}limit=200"
        
    while next_url:
        resp = requests.get(next_url, headers=RALPH_HEADERS, verify=False)
        if not resp.ok:
            print(f"Ralph GET failed: {next_url} -> {resp.status_code} {resp.text[:200]}")
            break
        data = resp.json()
        results.extend(data.get("results", []))
        next_url = data.get("next")
    return results


def ensure_category_cctv():
    """Ensure category CCTV exists, return its ID."""
    cats = ralph_get_all("categories")
    for c in cats:
        if c.get("name", "").upper() == "CCTV":
            return c["id"]

    # Create new
    payload = {"name": "CCTV"}
    r = requests.post(f"{RALPH_API_BASE}/categories/", headers=RALPH_HEADERS, json=payload, verify=False)
    if r.ok:
        cat_id = r.json()["id"]
        print(f"Category CCTV created (id={cat_id})")
        return cat_id
    else:
        print(f"Failed to create category CCTV: {r.status_code} {r.text[:200]}")
        return None


def ensure_model(model_name, category_id):
    """Ensure assetmodel exists, return its ID."""
    models = ralph_get_all(f"assetmodels")
    for m in models:
        if m.get("name") == model_name:
            return m["id"]

    # Create new
    payload = {
        "name": model_name,
        "manufacturer": MANUFACTURER_HIKVISION_ID,
        "category": category_id,
        "type": "back office"
    }
    r = requests.post(f"{RALPH_API_BASE}/assetmodels/", headers=RALPH_HEADERS, json=payload, verify=False)
    if r.ok:
        model_id = r.json()["id"]
        print(f"Model '{model_name}' created (id={model_id})")
        return model_id
    else:
        print(f"Failed to create model '{model_name}': {r.status_code} {r.text[:200]}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Reconcile Ralph CCTV back office assets using NVR real serial numbers")
    parser.add_argument("--apply", action="store_true", help="Apply deletions and registrations")
    args = parser.parse_args()

    mode = "APPLY" if args.apply else "DRY-RUN"
    print("=" * 80)
    print(f"CCTV CMDB RECONCILER & CLEANUP ({mode})")
    print("=" * 80)

    # 1. Discover actual info from NVR
    nvr_mapping = discover_nvr_channels()
    if not nvr_mapping:
        print("Error: Could not retrieve NVR channel mapping. Aborting.")
        return

    # 2. Get existing Back Office assets in Ralph
    print("Fetching existing Back Office assets from Ralph...")
    all_assets = ralph_get_all("back-office-assets")
    print(f"Found {len(all_assets)} Back Office assets total")

    # 3. Find placeholders to delete
    placeholders_to_delete = []
    active_real_assets = {}

    for asset in all_assets:
        sn = asset.get("sn") or ""
        # Check if placeholder format
        if sn.startswith("CCTV-IP-"):
            placeholders_to_delete.append(asset)
        elif sn.startswith("DS-2CD") or sn.startswith("DS-77"):
            # Check if this matches one of our target CCTV IPs (from remarks or management IP)
            remarks = asset.get("remarks") or ""
            # Extract IP from remarks like "IP: 192.168.1.19"
            ip_match = re.search(r"192\.168\.1\.\d+", remarks)
            if ip_match:
                active_real_assets[ip_match.group(0)] = asset

    print(f"Identified {len(placeholders_to_delete)} placeholder assets to delete:")
    for p in placeholders_to_delete:
        print(f"  - ID: {p['id']}, Hostname: {p['hostname']}, SN: {p['sn']}")

    # 4. Perform Deletions
    if placeholders_to_delete:
        if args.apply:
            print("\nDeleting placeholder assets...")
            for p in placeholders_to_delete:
                url = f"{RALPH_API_BASE}/back-office-assets/{p['id']}/"
                r = requests.delete(url, headers=RALPH_HEADERS, verify=False)
                if r.ok:
                    print(f"  ✅ Deleted ID {p['id']} ({p['hostname']})")
                else:
                    print(f"  ❌ Failed to delete ID {p['id']}: {r.status_code}")
                time.sleep(0.5)
        else:
            print(f"\n[DRY-RUN] Would delete {len(placeholders_to_delete)} placeholder assets.")

    # 5. Ensure CCTV category and models exist
    category_id = None
    if args.apply:
        category_id = ensure_category_cctv()
        if not category_id:
            print("Error: Could not ensure CCTV category. Aborting.")
            return

    # 6. Reconcile 31 target cameras
    print("\nReconciling 31 target CCTV cameras...")
    registered_count = 0
    skipped_count = 0
    failed_count = 0

    # Ensure model mapping exists in dry-run
    model_id_cache = {}

    for ip, location in sorted(CCTV_TARGETS.items(), key=lambda item: [int(x) for x in item[0].split('.')]):
        # Get info from NVR
        cam_info = nvr_mapping.get(ip)
        if not cam_info:
            print(f"  ⚠️  No NVR mapping found for IP {ip} ({location}). Skipping.")
            failed_count += 1
            continue

        sn = cam_info["serial_number"]
        model = cam_info["model"]
        fw = cam_info["firmware"]
        hostname = f"CCTV-{location.replace(' ', '-')}"

        # Check if already registered under real SN in Ralph
        # Search by SN
        existing = ralph_get_all(f"back-office-assets/?sn={sn}")
        if existing:
            print(f"  ⏭️  Skip (already registered): {ip} -> SN: {sn} ({location})")
            skipped_count += 1
            continue

        if args.apply:
            # Ensure model exists
            model_id = model_id_cache.get(model)
            if not model_id:
                model_id = ensure_model(model, category_id)
                if model_id:
                    model_id_cache[model] = model_id
                else:
                    print(f"  ❌ Failed to ensure model {model} for IP {ip}. Skipping.")
                    failed_count += 1
                    continue

            # Register
            payload = {
                "sn": sn,
                "model": model_id,
                "region": REGION_ID,
                "warehouse": WAREHOUSE_ID,
                "property_of": 1,  # Facility Management
                "status": "in use",
                "hostname": hostname,
                "remarks": f"IP: {ip} | Location: {location} | Auto-registered using real SN from NVR",
            }
            if fw:
                payload["remarks"] += f" | FW: {fw}"

            r = requests.post(f"{RALPH_API_BASE}/back-office-assets/", headers=RALPH_HEADERS, json=payload, verify=False)
            if r.ok:
                asset_id = r.json().get("id")
                print(f"  ✅ Registered: {hostname} (SN: {sn}) -> ID: {asset_id}")
                registered_count += 1
            else:
                print(f"  ❌ Failed to register {hostname} (SN: {sn}): {r.status_code} {r.text[:200]}")
                failed_count += 1
            time.sleep(1)
        else:
            print(f"  📝 Dry-run register: {ip} -> {hostname} | SN: {sn} | model: {model} | Location: {location}")
            registered_count += 1

    print("\n" + "=" * 80)
    print("Reconciliation Summary")
    print("=" * 80)
    print(f"  Deleted placeholders: {len(placeholders_to_delete) if args.apply else 0}")
    print(f"  Registered/Would register: {registered_count}")
    print(f"  Skipped (already exists): {skipped_count}")
    print(f"  Failed: {failed_count}")
    print(f"  Total processed: {registered_count + skipped_count + failed_count}")
    print("=" * 80)


if __name__ == "__main__":
    main()
