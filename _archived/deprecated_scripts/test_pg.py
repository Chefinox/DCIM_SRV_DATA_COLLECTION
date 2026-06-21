import psycopg2

try:
    conn = psycopg2.connect(host="localhost", dbname="dcim_sot", user="sot_admin", password="Inovasi@0918", port=5432)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM dcim_events WHERE measurement = 'server_redfish_util'")
    count = cur.fetchone()[0]
    print(f"Count of server_redfish_util in Postgres: {count}")
    
    cur.execute("SELECT event_time, hostname, metric_name, metric_value FROM dcim_events WHERE measurement = 'server_redfish_util' ORDER BY event_time DESC LIMIT 5")
    rows = cur.fetchall()
    for r in rows:
        print(r)
except Exception as e:
    print(f"Error: {e}")
