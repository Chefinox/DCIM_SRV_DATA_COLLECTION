import psycopg2
from datetime import datetime, timedelta

DB_CONFIG = {
    "host": "192.168.101.73",
    "database": "dcim_sot",
    "user": "sot_admin",
    "password": "Inovasi@0918"
}

def get_columns(cur):
    cur.execute("""
        SELECT column_name, data_type, character_maximum_length, is_nullable
        FROM information_schema.columns
        WHERE table_name = 'dcim_events'
        ORDER BY ordinal_position;
    """)
    return cur.fetchall()

def create_partitioned_table(cur):
    columns = get_columns(cur)
    col_defs = []
    for col in columns:
        name, dtype, length, nullable = col
        if dtype == 'character varying' and length:
            dtype = f"character varying({length})"
        elif dtype == 'numeric':
            dtype = "numeric" # Simplified
        
        null_str = " NOT NULL" if nullable == 'NO' or name == 'event_time' else ""
        col_defs.append(f"{name} {dtype}{null_str}")
    
    sql = f"""
    CREATE TABLE dcim_events_p (
        {', '.join(col_defs)},
        PRIMARY KEY (event_id, event_time)
    ) PARTITION BY RANGE (event_time);
    """
    print("Creating parent table dcim_events_p...")
    cur.execute("DROP TABLE IF EXISTS dcim_events_p CASCADE;")
    cur.execute(sql)

def create_partitions(cur):
    # Create partitions for last 7 days + next 3 days
    now = datetime.now()
    for i in range(-7, 4):
        start_date = (now + timedelta(days=i)).replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)
        
        table_name = f"dcim_events_y{start_date.year}_m{start_date.month:02d}_d{start_date.day:02d}"
        sql = f"""
        CREATE TABLE {table_name} PARTITION OF dcim_events_p
        FOR VALUES FROM ('{start_date.isoformat()}') TO ('{end_date.isoformat()}');
        """
        print(f"Creating partition {table_name}...")
        cur.execute(f"DROP TABLE IF EXISTS {table_name} CASCADE;")
        cur.execute(sql)

def migrate_data(cur):
    print("Migrating data from dcim_events to dcim_events_p (This may take a while)...")
    cur.execute("INSERT INTO dcim_events_p SELECT * FROM dcim_events ON CONFLICT DO NOTHING;")

def create_indexes(cur):
    print("Creating indexes on dcim_events_p...")
    cur.execute("CREATE INDEX idx_dcim_p_event_time ON dcim_events_p (event_time DESC);")
    cur.execute("CREATE INDEX idx_dcim_p_hostname ON dcim_events_p (hostname);")
    cur.execute("CREATE INDEX idx_dcim_p_device_type ON dcim_events_p (device_type);")
    cur.execute("CREATE INDEX idx_dcim_p_site ON dcim_events_p (site);")

def swap_tables(cur):
    print("Swapping tables...")
    # Rename original constraint to avoid conflict
    cur.execute("ALTER TABLE dcim_events RENAME CONSTRAINT dcim_events_pkey TO dcim_events_old_pkey;")
    cur.execute("ALTER TABLE dcim_events RENAME TO dcim_events_old;")
    cur.execute("ALTER TABLE dcim_events_p RENAME TO dcim_events;")
    # Also rename the pkey constraint of the new table to keep it standard
    cur.execute("ALTER TABLE dcim_events RENAME CONSTRAINT dcim_events_p_pkey TO dcim_events_pkey;")

def main():
    conn = psycopg2.connect(**DB_CONFIG)
    conn.autocommit = False
    cur = conn.cursor()
    try:
        create_partitioned_table(cur)
        create_partitions(cur)
        migrate_data(cur)
        create_indexes(cur)
        swap_tables(cur)
        conn.commit()
        print("Migration to Partitioning completed successfully!")
    except Exception as e:
        conn.rollback()
        print(f"Migration failed: {e}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
