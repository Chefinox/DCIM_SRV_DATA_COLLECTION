import requests
import json
import urllib3
urllib3.disable_warnings()
ES_URL = "https://10.70.0.56:9200"
ES_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")
query = {
    "size": 0,
    "query": {
        "bool": {
            "filter": [
                {"term": {"tag.enrichment_status.keyword": "NOT_IN_CMDB"}},
                {"range": {"@timestamp": {"gte": "2026-06-17T01:17:00Z", "lte": "2026-06-17T02:18:00Z"}}}
            ]
        }
    },
    "aggs": {
        "sns": {
            "terms": {"field": "tag.serial_number.keyword", "size": 100}
        }
    }
}
try:
    r = requests.post(f"{ES_URL}/dcim-metrics-unified-*/_search", json=query, auth=ES_AUTH, verify=False)
    print(json.dumps(r.json()["aggregations"]["sns"]["buckets"], indent=2))
except Exception as e:
    print(e)
