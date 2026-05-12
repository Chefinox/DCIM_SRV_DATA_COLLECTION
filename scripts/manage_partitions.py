import psycopg2
from datetime import datetime, timedelta
import logging

# Konfigurasi Log
logging.basicConfig(
    filename='/home/infra/dcim_metrics_project/logs/partition_management.log',
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.configs.database import get_db_config

DB_CONFIG = get_db_config()

RETENTION_DAYS = 7

def manage_partitions():
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()
    
    try:
        # 1. Buat partisi untuk hari ini, besok, dan lusa (antisipasi)
        now = datetime.now()
        for i in range(0, 3):
            start_date = (now + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = start_date + timedelta(days=1)
            
            table_name = f"dcim_events_y{start_date.year}_m{start_date.month:02d}_d{start_date.day:02d}"
            
            cur.execute(f"SELECT 1 FROM pg_tables WHERE tablename = '{table_name}';")
            if not cur.fetchone():
                logging.info(f"Creating new partition: {table_name}")
                sql = f"""
                CREATE TABLE IF NOT EXISTS {table_name} PARTITION OF dcim_events
                FOR VALUES FROM ('{start_date.isoformat()}') TO ('{end_date.isoformat()}');
                """
                cur.execute(sql)
        
        # 2. Hapus partisi yang sudah lewat dari 7 hari
        cutoff_date = (now - timedelta(days=RETENTION_DAYS)).replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Cari semua tabel yang merupakan partisi dari dcim_events
        cur.execute("""
            SELECT
                nmsp_child.nspname  AS child_schema,
                child.relname       AS child_table
            FROM pg_inherits
                JOIN pg_class parent            ON pg_inherits.inhparent = parent.oid
                JOIN pg_class child             ON pg_inherits.inhrelid  = child.oid
                JOIN pg_namespace nmsp_parent   ON nmsp_parent.oid       = parent.relnamespace
                JOIN pg_namespace nmsp_child    ON nmsp_child.oid        = child.relnamespace
            WHERE parent.relname = 'dcim_events';
        """)
        
        partitions = cur.fetchall()
        for schema, table in partitions:
            # Format nama: dcim_events_y2026_m04_d22
            try:
                parts = table.split('_')
                year = int(parts[2][1:]) # y2026 -> 2026
                month = int(parts[3][1:]) # m04 -> 4
                day = int(parts[4][1:]) # d22 -> 22
                
                table_date = datetime(year, month, day)
                if table_date < cutoff_date:
                    logging.info(f"Dropping old partition: {table}")
                    cur.execute(f"DROP TABLE {schema}.{table} CASCADE;")
            except (IndexError, ValueError):
                continue # Bukan tabel partisi yang kita kelola
                
        conn.commit()
        logging.info("Partition management completed successfully.")
    except Exception as e:
        conn.rollback()
        logging.error(f"Partition management failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    manage_partitions()
