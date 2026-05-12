import psycopg2
import json
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

def get_ralph_sot_data():
    conn = psycopg2.connect(
        host=os.getenv("SOT_DB_HOST", "192.168.101.73"),
        port=os.getenv("SOT_DB_PORT", "5432"),
        dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
        user=os.getenv("SOT_DB_USER", "sot_admin"),
        password=os.getenv("SOT_DB_PASS", "Inovasi@0918")
    )
    cur = conn.cursor()
    # Ralph structure might be different, usually has serial in raw_payload->'sn'
    cur.execute("SELECT hostname, raw_payload->'sn' FROM unified_assets WHERE source_system='Ralph'")
    rows = cur.fetchall()
    conn.close()
    return rows

ralph_data = get_ralph_sot_data()
print(f"SOT Data (Ralph): {len(ralph_data)} items")

with open('/home/infra/dcim_metrics_project/scratch/current_inventory.json', 'r') as f:
    inventory = json.load(f)

print("\nComparison with Ralph:")
matches = 0
missing = 0
for item in inventory:
    sn = item.get("serial_number")
    host = item.get("hostname")
    
    match = None
    for r_host, r_sn in ralph_data:
        if r_sn == sn:
            match = (r_host, r_sn)
            break
    
    if match:
        matches += 1
        # print(f"[MATCH] SN: {sn} | Poller Host: {host} | Ralph Host: {match[0]}")
    else:
        missing += 1
        print(f"[MISSING] SN: {sn} | Poller Host: {host} not in Ralph")

print(f"\nSummary: Matches: {matches}, Missing: {missing}")
