import psycopg2
import json
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

def get_sot_data():
    conn = psycopg2.connect(
        host=os.getenv("SOT_DB_HOST", "192.168.101.73"),
        port=os.getenv("SOT_DB_PORT", "5432"),
        dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
        user=os.getenv("SOT_DB_USER", "sot_admin"),
        password=os.getenv("SOT_DB_PASS", "Inovasi@0918")
    )
    cur = conn.cursor()
    cur.execute("SELECT hostname, raw_payload->'primary_ip'->>'address', raw_payload->'serial' FROM unified_assets WHERE source_system='NetBox'")
    rows = cur.fetchall()
    conn.close()
    return rows

sot_data = get_sot_data()
print("SOT Data (NetBox):")
for host, ip, sn in sot_data[:10]: # Print first 10
    print(f"  Host: {host}, IP: {ip}, SN: {sn}")

with open('/home/infra/dcim_metrics_project/scratch/current_inventory.json', 'r') as f:
    inventory = json.load(f)

print("\nComparison:")
for item in inventory[:10]:
    sn = item.get("serial_number")
    ip = item.get("ip_address")
    host = item.get("hostname")
    
    # Try to find in SOT
    match = None
    for s_host, s_ip, s_sn in sot_data:
        if s_sn == sn or (s_ip and s_ip.split('/')[0] == ip):
            match = (s_host, s_ip, s_sn)
            break
    
    if match:
        print(f"[MATCH] SN: {sn} | Poller Host: {host} | SOT Host: {match[0]}")
    else:
        print(f"[MISSING] SN: {sn} | Poller Host: {host} not in SOT")
