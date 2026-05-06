import psycopg2
from datetime import datetime

def run_audit():
    try:
        conn = psycopg2.connect(
            host="192.168.101.73",
            user="sot_admin",
            password="Inovasi@0918",
            database="dcim_sot"
        )
        cur = conn.cursor()
        
        query = """
        SELECT 
            device_type,
            COUNT(*) as total_rows,
            COUNT(site) as site_filled,
            COUNT(rack_name) as rack_filled,
            COUNT(enrichment_status) as enrich_status_filled,
            COUNT(metric_value) as metric_val_filled,
            COUNT(srv_reading_celsius) as srv_temp_filled,
            COUNT(srv_power_watts) as srv_power_filled,
            COUNT(ups_battery_capacity) as ups_cap_filled,
            COUNT(ups_battery_runtime) as ups_run_filled
        FROM dcim_events
        WHERE event_time > NOW() - INTERVAL '1 hour'
        GROUP BY device_type;
        """
        
        cur.execute(query)
        rows = cur.fetchall()
        
        print("=== DCIM PIPELINE AUDIT REPORT (Last 1 Hour) ===")
        print(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        print("-" * 60)
        print(f"{'Device Type':<15} | {'Total':<8} | {'Site%':<6} | {'Metric%':<7} | {'Specific Metrics'}")
        print("-" * 60)
        
        for r in rows:
            dtype = r[0] or "unknown"
            total = r[1]
            site_pct = (r[2]/total*100) if total > 0 else 0
            metric_pct = (r[5]/total*100) if total > 0 else 0
            
            spec = ""
            if dtype == 'server':
                spec = f"Temp:{r[6]}, Power:{r[7]}"
            elif dtype == 'ups':
                spec = f"Cap:{r[8]}, Run:{r[9]}"
            elif dtype == 'nas':
                spec = f"Rows:{total}"
            
            print(f"{dtype:<15} | {total:<8} | {site_pct:>5.1f}% | {metric_pct:>6.1f}% | {spec}")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    run_audit()
