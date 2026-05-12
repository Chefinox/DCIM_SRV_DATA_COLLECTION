import psycopg2
import sys
from datetime import datetime, timedelta

def main():
    try:
        conn = psycopg2.connect(
            host="192.168.101.73",
            port="5432",
            dbname="dcim_sot",
            user="sot_admin",
            password="Inovasi@0918"
        )
        cur = conn.cursor()
        
        # Check overall table size
        cur.execute("SELECT pg_size_pretty(pg_total_relation_size('dcim_events'));")
        table_size = cur.fetchone()[0]
        print(f"Total size of dcim_events table: {table_size}")
        
        # Check database total size
        cur.execute("SELECT pg_size_pretty(pg_database_size('dcim_sot'));")
        db_size = cur.fetchone()[0]
        print(f"Total size of dcim_sot database: {db_size}")
        
        # Check old data
        cur.execute("SELECT COUNT(*) FROM dcim_events WHERE event_time < NOW() - INTERVAL '7 days';")
        old_rows_count = cur.fetchone()[0]
        
        cur.execute("SELECT COUNT(*) FROM dcim_events;")
        total_rows_count = cur.fetchone()[0]
        
        print(f"Total rows in dcim_events: {total_rows_count}")
        print(f"Rows older than 7 days: {old_rows_count}")
        
        if old_rows_count > 0:
            cur.execute("SELECT MIN(event_time), MAX(event_time) FROM dcim_events WHERE event_time < NOW() - INTERVAL '7 days';")
            min_time, max_time = cur.fetchone()
            print(f"Oldest record: {min_time}")
            print(f"Newest 'old' record: {max_time}")
            
            cur.execute("SELECT device_type, COUNT(*) FROM dcim_events WHERE event_time < NOW() - INTERVAL '7 days' GROUP BY device_type;")
            print("\nBreakdown of old records by device_type:")
            for row in cur.fetchall():
                print(f"- {row[0]}: {row[1]} records")
                
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
