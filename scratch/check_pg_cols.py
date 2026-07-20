import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.configs.database import get_db_config
import psycopg2

try:
    conn = psycopg2.connect(**get_db_config())
    cur = conn.cursor()
    cur.execute("SELECT table_name, column_name, data_type FROM information_schema.columns WHERE table_name IN ('metrics', 'dcim_events') AND column_name IN ('ci_id', 'asset_id')")
    rows = cur.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print(e)
