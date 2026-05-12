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
    cur.execute("SELECT id, source_system, hostname, serial_number, category, site FROM unified_assets LIMIT 10;")
    rows = cur.fetchall()
    
    print(f"Ditemukan {len(rows)} baris:")
    for row in rows:
        print(row)
        
    conn.close()
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
