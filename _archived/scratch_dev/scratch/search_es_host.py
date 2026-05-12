import requests
import json
import os
from dotenv import load_dotenv
import urllib3
urllib3.disable_warnings()

load_dotenv('/home/infra/dcim_metrics_project/configs/.env')

ES_URL  = os.getenv("ES_URL", "https://10.70.0.56:9200")
ES_USER = os.getenv("ES_USER", "elastic")
ES_PASS = os.getenv("ES_PASS", "C+H+pFb*aIAqWcOo-X8q")

def search_es_by_hostname(hostname):
    query = {
        "size": 5,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "match": {"hostname": hostname}
        }
    }
    r = requests.post(
        f"{ES_URL}/telegraf-*/_search",
        auth=(ES_USER, ES_PASS),
        json=query,
        verify=False,
        timeout=5
    )
    return r.json()

res = search_es_by_hostname("UPS-APC-30K")
print(json.dumps(res, indent=2))
