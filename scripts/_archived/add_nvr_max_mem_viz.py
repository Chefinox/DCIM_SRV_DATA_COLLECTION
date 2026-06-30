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

def create_metric_viz(viz_id, title, field, device_type):
    aggs = [{
        "id": "1",
        "enabled": True,
        "type": "avg",
        "schema": "metric",
        "params": {"field": field, "customLabel": title}
    }]
    
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
        "query": {"match_phrase": {"tag.device_type.keyword": device_type}}
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
    
    requests.post(
        f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
        headers=HEADERS, json=payload
    )

def fix_dashboard():
    dashboard_id = "dcim-monitoring"
    resp = requests.get(f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}", headers=HEADERS)
    if resp.status_code != 200:
        return
        
    dash = resp.json()
    attrs = dash["attributes"]
    refs = dash.get("references", [])
    panels = json.loads(attrs["panelsJSON"])
    
    # Check if max memory panel exists in dashboard
    if not any("dcim-mon-nvr-mem-max" in r["id"] for r in refs):
        idx = str(len(panels) + 1)
        # We will add it and then rearrange
        panels.append({
            "version": "8.8.0",
            "type": "visualization",
            "gridData": {"x": 0, "y": 0, "w": 10, "h": 5, "i": idx},
            "panelIndex": idx,
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": f"panel_{idx}"
        })
        refs.append({"name": f"panel_{idx}", "type": "visualization", "id": "dcim-mon-nvr-mem-max"})
    
    # Rearrange the 5 NVR metric panels
    # Find Y coordinate of NVR count
    target_y = -1
    for p in panels:
        ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
        if ref_id == "dcim-mon-nvr-count":
            target_y = p["gridData"]["y"]
            break
            
    if target_y != -1:
        # Resize and position the 5 panels
        # Panel IDs: count, cpu-avg, mem-avg, mem-max, mem-pct
        for p in panels:
            ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
            if ref_id == "dcim-mon-nvr-count":
                p["gridData"] = {"x": 0, "y": target_y, "w": 8, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nvr-cpu-avg":
                p["gridData"] = {"x": 8, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nvr-mem-avg":
                p["gridData"] = {"x": 18, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nvr-mem-max":
                p["gridData"] = {"x": 28, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nvr-mem-pct":
                p["gridData"] = {"x": 38, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
    
    attrs["panelsJSON"] = json.dumps(panels)
    
    requests.post(
        f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}?overwrite=true",
        headers=HEADERS, json={"attributes": attrs, "references": refs}
    )

if __name__ == "__main__":
    # 1. Revert Used Memory to single metric to avoid confusion
    create_metric_viz("dcim-mon-nvr-mem-avg", "Used Memory (MB)", "dcim_metrics.raw_fields_memoryUsage", "nvr")
    
    # 2. Create Max Memory visualization
    create_metric_viz("dcim-mon-nvr-mem-max", "Total Memory (MB)", "dcim_metrics.raw_fields_memoryTotal", "nvr")
    
    # 3. Apply dashboard layout
    fix_dashboard()
    print("✅ Successfully updated layout with separate panel for Total Memory")
