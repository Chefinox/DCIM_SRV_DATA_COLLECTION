import json
import base64
import requests

KIBANA_URL = "http://localhost:5601"
INDEX_PATTERN_ID = "dcim-metrics-*"
HEADERS = {
    "kbn-xsrf": "true",
    "Authorization": "Basic " + base64.b64encode(b"elastic:C+H+pFb*aIAqWcOo-X8q").decode('utf-8'),
    "Content-Type": "application/json"
}

def update_mem_viz():
    viz_id = "dcim-mon-nvr-mem-avg"
    title = "Avg Memory (MB)"
    
    aggs = [
        {
            "id": "1",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_memoryUsage", "customLabel": "Used Memory (MB)"}
        },
        {
            "id": "2",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_memoryTotal", "customLabel": "Total Memory (MB)"}
        }
    ]
    
    params = {
        "addTooltip": True,
        "addLegend": False,
        "type": "metric",
        "metric": {
            "percentageMode": False,
            "useRanges": False,
            "colorSchema": "Green to Red",
            "metricColorMode": "None",
            "colorsRange": [{"from": 0, "to": 10000}],
            "labels": {"show": True},
            "invertColors": False,
            "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 40}
        }
    }
    
    filters = [{
        "meta": {
            "alias": None,
            "disabled": False,
            "negate": False,
            "key": "tag.device_type.keyword",
            "type": "phrase",
            "index": INDEX_PATTERN_ID
        },
        "query": {"match_phrase": {"tag.device_type.keyword": "nvr"}}
    }]
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "metric",
                "params": params,
                "aggs": aggs
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": filters,
                    "index": INDEX_PATTERN_ID
                })
            }
        },
        "references": [
            {"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": INDEX_PATTERN_ID}
        ]
    }
    
    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
        headers=HEADERS, json=payload
    )
    
    if resp.status_code in (200, 201):
        print(f"✅ Updated visualization {viz_id}")
    else:
        print(f"❌ Failed to update {viz_id}: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    update_mem_viz()
