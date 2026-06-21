import sys
sys.path.append('/home/infra/dcim_metrics_project/scripts')
from itop_sync_utils import DB_CONFIG
import psycopg2

print("Connecting to DB...")
try:
    conn = psycopg2.connect(**DB_CONFIG)
    print("Connected.")
    cur = conn.cursor()
    print("Executing query...")
    cur.execute("SELECT 1")
    print("Query done.")
except Exception as e:
    print(f"Error: {e}")
