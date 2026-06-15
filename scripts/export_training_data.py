#!/usr/bin/env python3
"""
Data Export Script for AI Training (ST-015-04)
Exports historical time-series data from PostgreSQL (v_train_* views) to CSV/JSONL for AI model training.
"""

import os
import csv
import json
import argparse
from datetime import datetime
import psycopg2
import psycopg2.extras

PG_PARAMS = {
    "host": "localhost",
    "user": "sot_admin",
    "password": "Inovasi@0918",
    "dbname": "dcim_sot"
}

VALID_DEVICES = ['server', 'ups', 'nas', 'network', 'cctv', 'nvr']

def export_data(device_type, date_from, date_to, out_format="csv"):
    if device_type not in VALID_DEVICES:
        print(f"Error: Unsupported device_type '{device_type}'. Valid options: {VALID_DEVICES}")
        return

    print(f"Exporting data for {device_type} from {date_from} to {date_to}...")
    
    query = f"""
        SELECT * FROM v_train_{device_type}
        WHERE ts >= %s AND ts <= %s
        ORDER BY ts ASC
    """
    
    start_ts = f"{date_from} 00:00:00+00"
    end_ts = f"{date_to} 23:59:59+00"

    os.makedirs("/home/infra/dcim_metrics_project/exports", exist_ok=True)
    out_file = f"/home/infra/dcim_metrics_project/exports/training_{date_from.replace('-','')}_{device_type}.{out_format}"
    
    records_written = 0
    
    try:
        conn = psycopg2.connect(**PG_PARAMS)
        # Using DictCursor to easily get column names
        with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
            cur.execute(query, (start_ts, end_ts))
            
            with open(out_file, "w", newline='') as f:
                writer = None
                
                # Fetch in batches
                while True:
                    rows = cur.fetchmany(5000)
                    if not rows:
                        break
                        
                    if records_written == 0 and out_format == "csv":
                        # Write header
                        headers = [desc[0] for desc in cur.description]
                        writer = csv.writer(f)
                        writer.writerow(headers)

                    for row in rows:
                        # Convert datetime to string for JSON serialization if needed
                        row_dict = dict(row)
                        if 'ts' in row_dict and isinstance(row_dict['ts'], datetime):
                            row_dict['ts'] = row_dict['ts'].isoformat()
                            
                        if out_format == "csv":
                            writer.writerow(list(row_dict.values()))
                        else:
                            f.write(json.dumps(row_dict) + "\n")
                            
                        records_written += 1
                        
    except Exception as e:
        print(f"PostgreSQL Error: {e}")
        return
    finally:
        if 'conn' in locals() and conn:
            conn.close()
            
    print(f"Export complete: {records_written} records written to {out_file}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export PostgreSQL AI Training Data")
    parser.add_argument("--device", required=True, help="Device type (server, ups, nas, network, cctv, nvr)")
    parser.add_argument("--start", required=True, help="Start date YYYY-MM-DD")
    parser.add_argument("--end", required=True, help="End date YYYY-MM-DD")
    parser.add_argument("--format", default="csv", choices=["csv", "jsonl"], help="Output format")
    
    args = parser.parse_args()
    export_data(args.device, args.start, args.end, args.format)
