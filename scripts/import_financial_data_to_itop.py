#!/usr/bin/env python3
"""
Import Financial Data to iTop (ST-015-06)
Reads a CSV file (serialnumber, purchase_date, end_of_warranty, asset_number)
and updates the corresponding FunctionalCI records in iTop via REST API.
"""

import os
import csv
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

def read_secret(name, fallback=None):
    try:
        path = f"/run/secrets/dcim/{name.lower()}"
        if os.path.exists(path):
            with open(path) as f:
                return f.read().strip()
    except Exception:
        pass
    return os.getenv(name, fallback)

ITOP_URL = os.getenv("ITOP_API_URL", "http://localhost:8080/webservices/rest.php?version=1.3")
ITOP_USER = read_secret("ITOP_API_USER", "admin")
ITOP_PASS = read_secret("ITOP_API_PASS", "Inovasi@0918")

def update_itop_ci(serialnumber, data_fields):
    """Updates a CI in iTop based on its serialnumber."""
    # First, we need to find the CI class and ID
    search_payload = {
        "operation": "core/get",
        "class": "PhysicalDevice",
        "key": f"SELECT PhysicalDevice WHERE serialnumber = '{serialnumber}'",
        "output_fields": "id,class"
    }
    
    auth_data = {
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(search_payload)
    }
    
    try:
        r = requests.post(ITOP_URL, data=auth_data, timeout=10)
        res = r.json()
        objects = res.get("objects", {})
        
        if not objects:
            logging.warning(f"CI with SN {serialnumber} not found in iTop.")
            return False
            
        # Get the first match
        obj_key = list(objects.keys())[0]
        ci_class = objects[obj_key]["class"]
        ci_id = objects[obj_key]["key"]
        
        # Now update it
        update_payload = {
            "operation": "core/update",
            "class": ci_class,
            "key": ci_id,
            "output_fields": "id",
            "fields": data_fields
        }
        
        update_data = {
            "auth_user": ITOP_USER,
            "auth_pwd": ITOP_PASS,
            "json_data": json.dumps(update_payload)
        }
        
        r_update = requests.post(ITOP_URL, data=update_data, timeout=10)
        res_update = r_update.json()
        
        if res_update.get("code") == 0:
            logging.info(f"Successfully updated {ci_class} (SN: {serialnumber})")
            return True
        else:
            logging.error(f"Failed to update SN {serialnumber}: {res_update.get('message')}")
            return False
            
    except Exception as e:
        logging.error(f"Error processing SN {serialnumber}: {e}")
        return False

def run_import(csv_path):
    if not os.path.exists(csv_path):
        logging.error(f"CSV file not found: {csv_path}")
        return
        
    success_count = 0
    fail_count = 0
    
    with open(csv_path, newline='') as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            sn = row.get("serialnumber", "").strip()
            if not sn:
                continue
                
            fields_to_update = {}
            if row.get("purchase_date"):
                fields_to_update["purchase_date"] = row["purchase_date"].strip()
            if row.get("end_of_warranty"):
                fields_to_update["end_of_warranty"] = row["end_of_warranty"].strip()
            if row.get("asset_number"):
                fields_to_update["asset_number"] = row["asset_number"].strip()
                
            if fields_to_update:
                if update_itop_ci(sn, fields_to_update):
                    success_count += 1
                else:
                    fail_count += 1
                    
    logging.info(f"Import complete. Success: {success_count}, Failed: {fail_count}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default="/home/infra/dcim_metrics_project/docs/operations/asset-financial-data-template.csv", help="Path to CSV file")
    args = parser.parse_args()
    
    run_import(args.csv)
