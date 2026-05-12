import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

def search_sn_everywhere(sn):
    conn = psycopg2.connect(
        host=os.getenv("SOT_DB_HOST", "192.168.101.73"),
        port=os.getenv("SOT_DB_PORT", "5432"),
        dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
        user=os.getenv("SOT_DB_USER", "sot_admin"),
        password=os.getenv("SOT_DB_PASS", "Inovasi@0918")
    )
    cur = conn.cursor()
    cur.execute("SELECT source_system, hostname, raw_payload FROM unified_assets WHERE raw_payload::text LIKE %s", (f'%{sn}%',))
    rows = cur.fetchall()
    conn.close()
    return rows

sn = "9E2133T16585"
results = search_sn_everywhere(sn)
print(f"Results for SN {sn}:")
for source, host, payload in results:
    print(f"  Source: {source}, Host: {host}")
