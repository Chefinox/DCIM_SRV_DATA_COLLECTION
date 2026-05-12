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
        
        print("=== 1. DATABASE CONNECTION OK ===")
        
        # Check old data (older than 7 days)
        cur.execute("SELECT COUNT(*) FROM dcim_events WHERE event_time < NOW() - INTERVAL '7 days';")
        old_rows_count = cur.fetchone()[0]
        print(f"\\n=== 2. OLD DATA (> 7 days) ===")
        print(f"Rows older than 7 days: {old_rows_count}")
        if old_rows_count > 0:
            cur.execute("SELECT device_type, COUNT(*) FROM dcim_events WHERE event_time < NOW() - INTERVAL '7 days' GROUP BY device_type;")
            for row in cur.fetchall():
                print(f"  - {row[0]}: {row[1]}")
        
        # Check newest data (Today, May 10th)
        cur.execute("SELECT COUNT(*) FROM dcim_events WHERE event_time >= CURRENT_DATE;")
        today_rows = cur.fetchone()[0]
        print(f"\\n=== 3. NEWEST DATA (Today) ===")
        print(f"Rows inserted today: {today_rows}")
        
        cur.execute("SELECT MAX(event_time) FROM dcim_events;")
        last_event = cur.fetchone()[0]
        print(f"Last event time in DB: {last_event}")
        
        # Validate data anomalies
        print(f"\\n=== 4. DATA VALIDATION / ANOMALIES ===")
        
        # Check missing or NO_IDENTIFIER serial_numbers
        cur.execute("SELECT device_type, COUNT(*) FROM dcim_events WHERE serial_number IN ('NO_IDENTIFIER', 'NO_SN', 'Unknown') OR serial_number IS NULL GROUP BY device_type;")
        anomalies_sn = cur.fetchall()
        print("Devices with NO_SN or NO_IDENTIFIER:")
        if not anomalies_sn:
            print("  - None")
        for row in anomalies_sn:
            print(f"  - {row[0]}: {row[1]} records")
            
        # Check un-enriched data
        cur.execute("SELECT enrichment_status, COUNT(*) FROM dcim_events GROUP BY enrichment_status;")
        enrichment_stats = cur.fetchall()
        print("\\nEnrichment Status Breakdown:")
        for row in enrichment_stats:
            print(f"  - {row[0]}: {row[1]} records")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
