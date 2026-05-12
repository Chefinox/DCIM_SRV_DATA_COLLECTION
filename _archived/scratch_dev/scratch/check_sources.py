import psycopg2
import os
from dotenv import load_dotenv

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

def check_sources():
    conn = psycopg2.connect(
        host=os.getenv("SOT_DB_HOST", "192.168.101.73"),
        port=os.getenv("SOT_DB_PORT", "5432"),
        dbname=os.getenv("SOT_DB_NAME", "dcim_sot"),
        user=os.getenv("SOT_DB_USER", "sot_admin"),
        password=os.getenv("SOT_DB_PASS", "Inovasi@0918")
    )
    cur = conn.cursor()
    cur.execute("SELECT source_system, count(*) FROM unified_assets GROUP BY source_system")
    rows = cur.fetchall()
    conn.close()
    return rows

sources = check_sources()
print("Unified Assets Sources:")
for source, count in sources:
    print(f"  {source}: {count}")
