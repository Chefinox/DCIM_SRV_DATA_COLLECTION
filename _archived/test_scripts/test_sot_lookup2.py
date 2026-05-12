import psycopg2
import sys
import json

try:
    conn = psycopg2.connect(
        host="192.168.101.73",
        port="5432",
        dbname="dcim_sot",
        user="sot_admin",
        password="sot_secure_password_123!"
    )
    cur = conn.cursor()
    # Check what fields are in raw_payload to find IPs or rack info
    cur.execute("SELECT hostname, category, site, raw_payload->'rack'->>'name', raw_payload->'rack'->>'id' FROM unified_assets WHERE source_system='NetBox' AND raw_payload->'rack' IS NOT NULL LIMIT 10;")
    rows = cur.fetchall()
    
    print("NetBox Devices with Rack:")
    for row in rows:
        print(row)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
