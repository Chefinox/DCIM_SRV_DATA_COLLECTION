import psycopg2
import re

md_file_path = '/home/infra/dcim_metrics_project/docs/development/34-database-query-baseline-for-agents.md'

with open(md_file_path, 'r') as f:
    content = f.read()

sql_blocks = re.findall(r'```sql\n(.*?)\n```', content, re.DOTALL)

conn = psycopg2.connect(
    host="localhost",
    database="dcim_sot",
    user="sot_admin",
    password="Inovasi@0918"
)

for i, query in enumerate(sql_blocks):
    test_query = query.replace(':identifier', "'SRV-HCI-01'")
    test_query = test_query.replace(':hostname', "'SRV-HCI-01'")
    test_query = test_query.replace(':serial_number', "'J901GKXY'")
    test_query = test_query.replace(':table_name', "'dcim_events'")
    test_query = test_query.replace(':device_type', "'server'")
    test_query = test_query.replace(':measurement', "'server_redfish'")
    
    if not test_query.strip().upper().startswith("WITH") and not "LIMIT" in test_query.upper():
        if test_query.strip().upper().startswith("SELECT"):
             test_query += " LIMIT 10"
             
    try:
        cur = conn.cursor()
        cur.execute(test_query)
        rows = cur.fetchall()
        colnames = [desc[0] for desc in cur.description]
        
        if not rows:
            print(f"Query {i+1} Issues: ['No data returned.']")
        else:
            issues = []
            null_counts = {col: 0 for col in colnames}
            for row in rows:
                for idx, val in enumerate(row):
                    if val is None:
                        null_counts[colnames[idx]] += 1
            
            for col, count in null_counts.items():
                if count > 0:
                    issues.append(f"Column '{col}' has {count} NULL values.")
            
            if issues:
                print(f"Query {i+1} Issues: {issues} (Rows: {len(rows)})")
            else:
                print(f"Query {i+1} OK (Rows: {len(rows)})")
        cur.close()
    except Exception as e:
        print(f"Query {i+1} Runtime Error: {e}")
        conn.rollback()

conn.close()
