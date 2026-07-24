import sys
sys.path.append('/home/infra/dcim_metrics_project')
from src.utils.lineage import get_pool
pool = get_pool()
conn = pool.getconn()
cur = conn.cursor()
cur.execute("SELECT lineage_id, source_system, validation_status, ingested_at FROM event_lineage ORDER BY ingested_at DESC LIMIT 5;")
for row in cur.fetchall():
    print(row)
