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

def create_bar_chart():
    viz_id = "dcim-mon-nas-bar"
    title = "Storage Capacity per NAS"
    
    aggs = [
        {
            "id": "1",
            "enabled": True,
            "type": "max",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_volumeTotalBytes", "customLabel": "Total Capacity"}
        },
        {
            "id": "2",
            "enabled": True,
            "type": "max",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_volumeUsedBytes", "customLabel": "Used Storage"}
        },
        {
            "id": "3",
            "enabled": True,
            "type": "terms",
            "schema": "segment",
            "params": {
                "field": "tag.hostname.keyword",
                "orderBy": "1",
                "order": "desc",
                "size": 10,
                "otherBucket": False,
                "missingBucket": False
            }
        }
    ]
    
    params = {
        "type": "histogram",
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
            "title": {"text": "Bytes"}
        }],
        "seriesParams": [
            {
                "show": True,
                "type": "histogram",
                "mode": "normal",
                "data": {"label": "Total Capacity", "id": "1"},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True,
                "showCircles": True
            },
            {
                "show": True,
                "type": "histogram",
                "mode": "normal",
                "data": {"label": "Used Storage", "id": "2"},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True,
                "showCircles": True
            }
        ],
        "addTooltip": True,
        "addLegend": True,
        "legendPosition": "right",
        "times": [],
        "addTimeMarker": False
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
        "query": {"match_phrase": {"tag.device_type.keyword": "nas"}}
    }]
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "histogram",
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
        print("✅ Created NAS Bar Chart")
    else:
        print("❌ Failed to create NAS Bar Chart:", resp.text)

def update_nas_table():
    viz_id = "dcim-mon-nas-list"
    resp = requests.get(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}", headers=HEADERS)
    if resp.status_code != 200:
        print("Failed to fetch table:", resp.text)
        return
        
    viz = resp.json()
    attrs = viz["attributes"]
    vis_state = json.loads(attrs["visState"])
    
    aggs = vis_state["aggs"]
    
    # Check if metrics already added
    if not any(a["id"] == "99" for a in aggs):
        aggs.append({
            "id": "99",
            "enabled": True,
            "type": "max",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_volumeTotalTB", "customLabel": "Total (TB)"}
        })
        aggs.append({
            "id": "100",
            "enabled": True,
            "type": "max",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_volumeUsedGB", "customLabel": "Used (GB)"}
        })
        aggs.append({
            "id": "101",
            "enabled": True,
            "type": "max",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_volumeUsagePct", "customLabel": "Used (%)"}
        })
        aggs.append({
            "id": "102",
            "enabled": True,
            "type": "max",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_volumeStatus", "customLabel": "Status (1=OK)"}
        })
        
        vis_state["aggs"] = aggs
        attrs["visState"] = json.dumps(vis_state)
        
        put_resp = requests.post(
            f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
            headers=HEADERS, json={"attributes": attrs, "references": viz["references"]}
        )
        if put_resp.status_code in (200, 201):
            print("✅ Updated NAS Devices Table")
        else:
            print("❌ Failed to update table:", put_resp.text)

def update_dashboard():
    dashboard_id = "dcim-monitoring"
    resp = requests.get(f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}", headers=HEADERS)
    if resp.status_code != 200:
        return
        
    dash = resp.json()
    attrs = dash["attributes"]
    refs = dash.get("references", [])
    panels = json.loads(attrs["panelsJSON"])
    
    # IDs to remove
    to_remove = ["dcim-mon-nas-vol-used", "dcim-mon-nas-vol-total", "dcim-mon-nas-vol-pct", "dcim-mon-nas-status"]
    
    # Filter out panels and references
    new_panels = []
    for p in panels:
        ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
        if ref_id not in to_remove:
            new_panels.append(p)
            
    # Remove references
    new_refs = [r for r in refs if r["id"] not in to_remove]
    
    # Add Bar Chart if not present
    if not any("dcim-mon-nas-bar" in r["id"] for r in new_refs):
        idx = str(len(new_panels) + 100)
        new_panels.append({
            "version": "8.8.0",
            "type": "visualization",
            "gridData": {"x": 0, "y": 0, "w": 36, "h": 5, "i": idx},
            "panelIndex": idx,
            "embeddableConfig": {"enhancements": {}},
            "panelRefName": f"panel_{idx}"
        })
        new_refs.append({"name": f"panel_{idx}", "type": "visualization", "id": "dcim-mon-nas-bar"})
    
    # Reposition
    target_y = -1
    for p in new_panels:
        ref_id = next((r["id"] for r in new_refs if r["name"] == p.get("panelRefName")), None)
        if ref_id == "dcim-mon-nas-count":
            target_y = p["gridData"]["y"]
            break
            
    if target_y != -1:
        for p in new_panels:
            ref_id = next((r["id"] for r in new_refs if r["name"] == p.get("panelRefName")), None)
            if ref_id == "dcim-mon-nas-count":
                p["gridData"] = {"x": 0, "y": target_y, "w": 12, "h": 8, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-bar":
                p["gridData"] = {"x": 12, "y": target_y, "w": 36, "h": 8, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-vol-time":
                p["gridData"] = {"x": 0, "y": target_y + 8, "w": 48, "h": 8, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-list":
                p["gridData"] = {"x": 0, "y": target_y + 16, "w": 48, "h": 10, "i": p["gridData"]["i"]}
                
    attrs["panelsJSON"] = json.dumps(new_panels)
    
    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}?overwrite=true",
        headers=HEADERS, json={"attributes": attrs, "references": new_refs}
    )
    if resp.status_code == 200:
        print("✅ Dashboard Layout Updated")
    else:
        print("❌ Failed to update dashboard:", resp.text)

if __name__ == "__main__":
    create_bar_chart()
    update_nas_table()
    update_dashboard()
