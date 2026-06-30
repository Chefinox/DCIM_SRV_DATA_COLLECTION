import psycopg2
import re
import os

md_file_path = '/home/infra/dcim_metrics_project/docs/development/34-database-query-baseline-for-agents.md'

with open(md_file_path, 'r') as f:
    content = f.read()

# find all sql blocks
sql_blocks = re.findall(r'```sql\n(.*?)\n```', content, re.DOTALL)

conn = psycopg2.connect(
    host="localhost",
    database="dcim_sot",
    user="sot_admin",
    password="Inovasi@0918"
)

for i, query in enumerate(sql_blocks):
    print(f"\n--- Testing query {i+1} ---")
    
    # Replace parameters if any, just to test syntax
    test_query = query.replace(':identifier', "'123'")
    test_query = test_query.replace(':hostname', "'123'")
    test_query = test_query.replace(':serial_number', "'123'")
    test_query = test_query.replace(':table_name', "'dcim_events'")
    test_query = test_query.replace(':device_type', "'server'")
    test_query = test_query.replace(':measurement', "'server_redfish'")
    
    try:
        cur = conn.cursor()
        cur.execute(f"EXPLAIN {test_query}")
        cur.fetchall()
        print("Syntax: OK")
        cur.close()
    except Exception as e:
        print(f"Syntax: ERROR - {e}")
        conn.rollback()

conn.close()
