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

def check_es_for_sn(sn):
    query = {
        "size": 1,
        "sort": [{"@timestamp": {"order": "desc"}}],
        "query": {
            "bool": {
                "must": [{"term": {"serial_number.keyword": sn}}]
            }
        }
    }
    try:
        r = requests.post(
            f"{ES_URL}/telegraf-*/_search",
            auth=(ES_USER, ES_PASS),
            json=query,
            verify=False,
            timeout=5
        )
        return r.json()
    except Exception as e:
        return str(e)

sn = "9E2133T16585"
res = check_es_for_sn(sn)
print(json.dumps(res, indent=2))
