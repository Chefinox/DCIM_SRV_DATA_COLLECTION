import psycopg2
import sys

try:
    conn = psycopg2.connect(
        host="192.168.101.73",
        port="5432",
        dbname="dcim_sot",
        user="sot_admin",
        password="sot_secure_password_123!"
    )
    cur = conn.cursor()
    # Check if any IPs or metadata like IPs are extracted mapped in raw_payload
    cur.execute("SELECT hostname, category, site, raw_payload->'primary_ip'->>'address' FROM unified_assets WHERE source_system='NetBox' AND raw_payload->'primary_ip' IS NOT NULL LIMIT 10;")
    rows = cur.fetchall()
    
    print("NetBox Devices with IP:")
    for row in rows:
        print(row)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
