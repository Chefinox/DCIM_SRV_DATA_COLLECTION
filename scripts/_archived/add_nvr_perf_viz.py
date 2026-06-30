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

def create_line_viz(viz_id, title, field, device_type):
    aggs = [
        {
            "id": "1",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": field, "customLabel": title}
        },
        {
            "id": "2",
            "enabled": True,
            "type": "date_histogram",
            "schema": "segment",
            "params": {
                "field": "@timestamp",
                "timeRange": {"from": "now-1h", "to": "now"},
                "useNormalizedEsInterval": True,
                "scaleMetricValues": False,
                "interval": "auto",
                "drop_partials": False,
                "min_doc_count": 1,
                "extended_bounds": {}
            }
        },
        {
            "id": "3",
            "enabled": True,
            "type": "terms",
            "schema": "group",
            "params": {
                "field": "tag.hostname.keyword",
                "orderBy": "1",
                "order": "desc",
                "size": 10,
                "otherBucket": False,
                "otherBucketLabel": "Other",
                "missingBucket": False,
                "missingBucketLabel": "Missing"
            }
        }
    ]
    
    params = {
        "type": "line",
        "grid": {"categoryLines": False},
        "categoryAxes": [{
            "id": "CategoryAxis-1",
            "type": "category",
            "position": "bottom",
            "show": True,
            "style": {},
            "scale": {"type": "linear"},
            "labels": {"show": True, "filter": True, "truncate": 100},
            "title": {}
        }],
        "valueAxes": [{
            "id": "ValueAxis-1",
            "name": "LeftAxis-1",
            "type": "value",
            "position": "left",
            "show": True,
            "style": {},
            "scale": {"type": "linear", "mode": "normal"},
            "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100},
            "title": {"text": title}
        }],
        "seriesParams": [{
            "show": True,
            "type": "line",
            "mode": "normal",
            "data": {"label": title, "id": "1"},
            "valueAxis": "ValueAxis-1",
            "drawLinesBetweenPoints": True,
            "lineWidth": 2,
            "showCircles": True
        }],
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False,
        "thresholdLine": {"show": False, "value": 10, "width": 1, "style": "full", "color": "#E7664C"}
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
                "type": "line",
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
    if any("dcim-mon-nvr-cpu" in r["id"] for r in refs):
        print("Already added to dashboard.")
        return
        
    # Find NVR list panel Y
    target_y = -1
    for p in panels:
        ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
        if ref_id == "dcim-mon-nvr-list":
            target_y = p["gridData"]["y"]
            break
            
    if target_y == -1:
        target_y = max((p["gridData"]["y"] + p["gridData"]["h"] for p in panels), default=0)
    else:
        # Shift down by 8 units (height of line charts)
        for p in panels:
            if p["gridData"]["y"] >= target_y:
                p["gridData"]["y"] += 8
    
    cpu_index = str(len(panels) + 1)
    mem_index = str(len(panels) + 2)
    
    panels.append({
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": 0, "y": target_y, "w": 24, "h": 8, "i": cpu_index},
        "panelIndex": cpu_index,
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": f"panel_{cpu_index}"
    })
    
    panels.append({
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": 24, "y": target_y, "w": 24, "h": 8, "i": mem_index},
        "panelIndex": mem_index,
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": f"panel_{mem_index}"
    })
    
    refs.append({"name": f"panel_{cpu_index}", "type": "visualization", "id": "dcim-mon-nvr-cpu"})
    refs.append({"name": f"panel_{mem_index}", "type": "visualization", "id": "dcim-mon-nvr-mem"})
    
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
        print("✅ Added to dashboard!")
    else:
        print("❌ Failed to add to dashboard:", put_resp.text)

if __name__ == "__main__":
    cpu_ok = create_line_viz("dcim-mon-nvr-cpu", "NVR CPU Usage (%)", "dcim_metrics.raw_fields_cpuUtilization", "nvr")
    mem_ok = create_line_viz("dcim-mon-nvr-mem", "NVR Memory Usage (MB)", "dcim_metrics.raw_fields_memoryUsage", "nvr")
    if cpu_ok and mem_ok:
        add_to_dashboard()
