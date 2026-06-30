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

def create_phases_viz():
    viz_id = "dcim-mon-ups-phases-time"
    title = "Output Load Per Phase Over Time"
    
    aggs = [
        {
            "id": "1",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_output_load_L1", "customLabel": "Load L1 (%)"}
        },
        {
            "id": "2",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_output_load_L2", "customLabel": "Load L2 (%)"}
        },
        {
            "id": "3",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": "dcim_metrics.raw_fields_output_load_L3", "customLabel": "Load L3 (%)"}
        },
        {
            "id": "4",
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
            "id": "5",
            "enabled": True,
            "type": "terms",
            "schema": "group",
            "params": {
                "field": "tag.hostname.keyword",
                "orderBy": "1",
                "order": "desc",
                "size": 5,
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
            "title": {"text": "Load (%)"}
        }],
        "seriesParams": [
            {
                "show": True,
                "type": "line",
                "mode": "normal",
                "data": {"label": "Load L1 (%)", "id": "1"},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True,
                "lineWidth": 2,
                "showCircles": True
            },
            {
                "show": True,
                "type": "line",
                "mode": "normal",
                "data": {"label": "Load L2 (%)", "id": "2"},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True,
                "lineWidth": 2,
                "showCircles": True
            },
            {
                "show": True,
                "type": "line",
                "mode": "normal",
                "data": {"label": "Load L3 (%)", "id": "3"},
                "valueAxis": "ValueAxis-1",
                "drawLinesBetweenPoints": True,
                "lineWidth": 2,
                "showCircles": True
            }
        ],
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
        "query": {"match_phrase": {"tag.device_type.keyword": "ups"}}
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
            "description": "Output Load Per Phase",
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
        return viz_id
    else:
        print(f"❌ Failed to create visualization: {resp.status_code}")
        print(resp.text)
        return None

def add_to_dashboard(viz_id):
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
    for ref in refs:
        if ref["id"] == viz_id:
            print("Visualization already in dashboard references.")
            return
            
    # Find the target Y coordinate (the UPS list panel)
    target_y = -1
    for p in panels:
        ref_name = p.get("panelRefName", "")
        # Find the viz id for this ref name
        ref_id = next((r["id"] for r in refs if r["name"] == ref_name), None)
        if ref_id == "dcim-mon-ups-list":
            target_y = p["gridData"]["y"]
            break
            
    if target_y == -1:
        # Fallback to appending at the end
        target_y = max((p["gridData"]["y"] + p["gridData"]["h"] for p in panels), default=0)
    else:
        # Shift everything at or below target_y down by 10 units
        for p in panels:
            if p["gridData"]["y"] >= target_y:
                p["gridData"]["y"] += 10
    
    # Create new panel at target_y
    new_panel_index = str(len(panels) + 1)
    new_panel_ref = f"panel_{new_panel_index}"
    
    new_panel = {
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": 0, "y": target_y, "w": 48, "h": 10, "i": new_panel_index},
        "panelIndex": new_panel_index,
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": new_panel_ref
    }
    
    panels.append(new_panel)
    refs.append({
        "name": new_panel_ref,
        "type": "visualization",
        "id": viz_id
    })
    
    attrs["panelsJSON"] = json.dumps(panels)
    
    update_payload = {
        "attributes": attrs,
        "references": refs
    }
    
    put_resp = requests.put(
        f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}",
        headers=HEADERS, json=update_payload
    )
    if put_resp.status_code == 200:
        print("✅ Added to dashboard!")
    else:
        print("❌ Failed to add to dashboard:", put_resp.text)

if __name__ == "__main__":
    vid = create_phases_viz()
    if vid:
        add_to_dashboard(vid)
