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
    
    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
        headers=HEADERS, json=payload
    )
    
    if resp.status_code in (200, 201):
        print(f"✅ Created visualization {viz_id}")
        return True
    else:
        print(f"❌ Failed to create {viz_id}: {resp.status_code}")
        print(resp.text)
        return False

def add_to_dashboard():
    dashboard_id = "dcim-monitoring"
    resp = requests.get(f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}", headers=HEADERS)
    if resp.status_code != 200:
        print("Failed to fetch dashboard")
        return
        
    dash = resp.json()
    attrs = dash["attributes"]
    refs = dash.get("references", [])
    
    panels = json.loads(attrs["panelsJSON"])
    
    # Check if already added
    if any("dcim-mon-nvr-cpu-avg" in r["id"] for r in refs):
        print("Already added to dashboard.")
        return
        
    # Find NVR Count panel Y (which is the start of NVR section below header)
    target_y = -1
    for p in panels:
        ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
        if ref_id == "dcim-mon-nvr-count":
            target_y = p["gridData"]["y"]
            break
            
    if target_y == -1:
        target_y = max((p["gridData"]["y"] + p["gridData"]["h"] for p in panels), default=0)
    
    # We will add 3 panels of width 8 next to NVR count. 
    # NVR Count is usually width 12. Let's make it width 8 and put these next to it.
    for p in panels:
        ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
        if ref_id == "dcim-mon-nvr-count":
            p["gridData"]["w"] = 12
            break
            
    idx1 = str(len(panels) + 1)
    idx2 = str(len(panels) + 2)
    idx3 = str(len(panels) + 3)
    
    panels.append({
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": 12, "y": target_y, "w": 12, "h": 5, "i": idx1},
        "panelIndex": idx1,
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": f"panel_{idx1}"
    })
    
    panels.append({
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": 24, "y": target_y, "w": 12, "h": 5, "i": idx2},
        "panelIndex": idx2,
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": f"panel_{idx2}"
    })
    
    panels.append({
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": 36, "y": target_y, "w": 12, "h": 5, "i": idx3},
        "panelIndex": idx3,
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": f"panel_{idx3}"
    })
    
    refs.append({"name": f"panel_{idx1}", "type": "visualization", "id": "dcim-mon-nvr-cpu-avg"})
    refs.append({"name": f"panel_{idx2}", "type": "visualization", "id": "dcim-mon-nvr-mem-avg"})
    refs.append({"name": f"panel_{idx3}", "type": "visualization", "id": "dcim-mon-nvr-mem-pct"})
    
    attrs["panelsJSON"] = json.dumps(panels)
    
    update_payload = {
        "attributes": attrs,
        "references": refs
    }
    
    put_resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}?overwrite=true",
        headers=HEADERS, json=update_payload
    )
    if put_resp.status_code == 200:
        print("✅ Added metrics to dashboard!")
    else:
        print("❌ Failed to add to dashboard:", put_resp.text)

if __name__ == "__main__":
    b1 = create_metric_viz("dcim-mon-nvr-cpu-avg", "Avg CPU (%)", "dcim_metrics.raw_fields_cpuUtilization", "nvr")
    b2 = create_metric_viz("dcim-mon-nvr-mem-avg", "Avg Memory (MB)", "dcim_metrics.raw_fields_memoryUsage", "nvr")
    b3 = create_metric_viz("dcim-mon-nvr-mem-pct", "Memory Used (%)", "dcim_metrics.raw_fields_memoryUsagePct", "nvr")
    if b1 and b2 and b3:
        add_to_dashboard()
