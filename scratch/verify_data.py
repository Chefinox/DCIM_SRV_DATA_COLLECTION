import psycopg2
import requests
import warnings
from requests.packages.urllib3.exceptions import InsecureRequestWarning
warnings.simplefilter('ignore',InsecureRequestWarning)

# Postgres
print("=== Postgres (dcim_events) ===")
try:
    conn = psycopg2.connect(
        host="127.0.0.1",
        database="dcim_sot",
        user="sot_admin",
        password="Inovasi@0918"
    )
    cur = conn.cursor()
    cur.execute("SELECT device_type, count(*), max(inserted_at) FROM dcim_events GROUP BY device_type;")
    rows = cur.fetchall()
    print("Postgres dcim_events Counts by Device Type:")
    for row in rows:
        print(f" - {row[0]}: {row[1]} (latest: {row[2]})")
    conn.close()
except Exception as e:
    print(f"PG error: {e}")

# Elasticsearch
print("\n=== Elasticsearch ===")
try:
    query = {
        "size": 0,
        "query": {
            "range": {
                "@timestamp": {
                    "gte": "now-2h"
                }
            }
        },
        "aggs": {
            "device_types": {
                "terms": { "field": "device_type.keyword" },
                "aggs": {
                    "latest": {
                        "max": { "field": "@timestamp" }
                    }
                }
            }
        }
    }
    res2 = requests.get('https://127.0.0.1:9200/dcim-metrics-*/_search', auth=('elastic', 'C+H+pFb*aIAqWcOo-X8q'), json=query, verify=False)
    buckets = res2.json().get('aggregations', {}).get('device_types', {}).get('buckets', [])
    print("New ES docs in last 2 hours:")
    for b in buckets:
        print(f" - {b['key']}: {b['doc_count']} (latest: {b['latest']['value_as_string']})")
except Exception as e:
    print(f"ES error: {e}")
