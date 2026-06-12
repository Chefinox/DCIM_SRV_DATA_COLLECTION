#!/usr/bin/env python3
"""
Data Export Script for AI Training (ST-015-04)
Exports historical time-series data from Elasticsearch to CSV/JSONL for AI model training.
"""

import os
import csv
import json
import argparse
import urllib3
import requests

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

ES_URL = "https://10.70.0.56:9200"
INDEX = "dcim-metrics-unified-*"
AUTH = ('elastic', 'C+H+pFb*aIAqWcOo-X8q')

def get_mapping_for_device(device_type):
    """Returns the mapping of logical feature names to ES field paths."""
    if device_type == "server":
        return {
            "timestamp": "@timestamp",
            "serial_number": "tag.serial_number",
            "model": "tag.model",
            "cpu_usage": "dcim_metrics.raw_fields_cpuUtilization",
            "ram_usage": "dcim_metrics.raw_fields_memoryUsage",
            "power_draw": "dcim_metrics.raw_fields_power_output_watts",
            "temperature": "dcim_metrics.raw_fields_system_temp"
        }
    elif device_type == "ups":
        return {
            "timestamp": "@timestamp",
            "serial_number": "tag.serial_number",
            "model": "tag.model",
            "output_load": "dcim_metrics.raw_fields_output_load",
            "battery_temp": "dcim_metrics.raw_fields_battery_temp",
            "battery_runtime": "dcim_metrics.raw_fields_battery_runtime_remain"
        }
    else:
        # Default fallback
        return {
            "timestamp": "@timestamp",
            "serial_number": "tag.serial_number"
        }

def resolve_field(doc, path):
    """Safely extracts a nested field from the document."""
    keys = path.split('.')
    val = doc
    try:
        for k in keys:
            val = val.get(k, {})
        return val if not isinstance(val, dict) else ""
    except Exception:
        return ""

def export_data(device_type, date_from, date_to, out_format="csv"):
    print(f"Exporting data for {device_type} from {date_from} to {date_to}...")
    
    mapping = get_mapping_for_device(device_type)
    headers = list(mapping.keys())
    
    query = {
        "size": 5000,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"tag.device_type.keyword": device_type}},
                    {"range": {
                        "@timestamp": {
                            "gte": f"{date_from}T00:00:00Z",
                            "lte": f"{date_to}T23:59:59Z"
                        }
                    }}
                ]
            }
        }
    }
    
    # Init scroll
    res = requests.post(f"{ES_URL}/{INDEX}/_search?scroll=1m", json=query, auth=AUTH, verify=False)
    data = res.json()
    
    if "error" in data:
        print(f"ES Error: {data['error']}")
        return
        
    scroll_id = data.get("_scroll_id")
    hits = data.get("hits", {}).get("hits", [])
    total = data.get("hits", {}).get("total", {}).get("value", 0)
    
    print(f"Found {total} records. Fetching...")
    
    os.makedirs("/home/infra/dcim_metrics_project/exports", exist_ok=True)
    out_file = f"/home/infra/dcim_metrics_project/exports/training_{date_from.replace('-','')}_{device_type}.{out_format}"
    
    records_written = 0
    
    with open(out_file, "w", newline='') as f:
        writer = None
        if out_format == "csv":
            writer = csv.writer(f)
            writer.writerow(headers)
            
        while hits:
            for hit in hits:
                source = hit["_source"]
                row_data = [resolve_field(source, mapping[h]) for h in headers]
                if out_format == "csv":
                    writer.writerow(row_data)
                else:
                    f.write(json.dumps(dict(zip(headers, row_data))) + "\n")
                records_written += 1
                
            # fetch next batch
            res = requests.post(f"{ES_URL}/_search/scroll", json={"scroll": "1m", "scroll_id": scroll_id}, auth=AUTH, verify=False)
            data = res.json()
            hits = data.get("hits", {}).get("hits", [])
            
    print(f"Export complete: {records_written} records written to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export ES Data for AI")
    parser.add_argument("--device", required=True, help="Device type (server, ups, etc)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--format", default="csv", choices=["csv", "jsonl"], help="Output format")
    
    args = parser.parse_args()
    export_data(args.device, args.start, args.end, args.format)
