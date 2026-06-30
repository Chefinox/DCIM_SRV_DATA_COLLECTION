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
    
    # Visualizations to add
    new_vizes = [
        "dcim-mon-nas-vol-used", "dcim-mon-nas-vol-total", 
        "dcim-mon-nas-vol-pct", "dcim-mon-nas-status", 
        "dcim-mon-nas-vol-time"
    ]
    
    for viz_id in new_vizes:
        if not any(viz_id in r["id"] for r in refs):
            idx = str(len(panels) + 1)
            panels.append({
                "version": "8.8.0",
                "type": "visualization",
                "gridData": {"x": 0, "y": 0, "w": 10, "h": 5, "i": idx},
                "panelIndex": idx,
                "embeddableConfig": {"enhancements": {}},
                "panelRefName": f"panel_{idx}"
            })
            refs.append({"name": f"panel_{idx}", "type": "visualization", "id": viz_id})
    
    # Target Y
    target_y = -1
    for p in panels:
        ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
        if ref_id == "dcim-mon-nas-count":
            target_y = p["gridData"]["y"]
            break
            
    if target_y != -1:
        # Shift everything below target_y down by 8 units
        for p in panels:
            ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
            if ref_id not in ["dcim-mon-nas-count"] + new_vizes and p["gridData"]["y"] >= target_y:
                p["gridData"]["y"] += 8
                
        # Reposition NAS panels
        for p in panels:
            ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
            if ref_id == "dcim-mon-nas-count":
                p["gridData"] = {"x": 0, "y": target_y, "w": 8, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-vol-used":
                p["gridData"] = {"x": 8, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-vol-total":
                p["gridData"] = {"x": 18, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-vol-pct":
                p["gridData"] = {"x": 28, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-status":
                p["gridData"] = {"x": 38, "y": target_y, "w": 10, "h": 5, "i": p["gridData"]["i"]}
            elif ref_id == "dcim-mon-nas-vol-time":
                p["gridData"] = {"x": 0, "y": target_y + 5, "w": 48, "h": 8, "i": p["gridData"]["i"]}
                
        # Fix list table position (it might have been shifted down, but let's anchor it right below line chart)
        for p in panels:
            ref_id = next((r["id"] for r in refs if r["name"] == p.get("panelRefName")), None)
            if ref_id == "dcim-mon-nas-list":
                p["gridData"] = {"x": 0, "y": target_y + 13, "w": 48, "h": 8, "i": p["gridData"]["i"]}
    
    attrs["panelsJSON"] = json.dumps(panels)
    
    requests.post(
        f"{KIBANA_URL}/api/saved_objects/dashboard/{dashboard_id}?overwrite=true",
        headers=HEADERS, json={"attributes": attrs, "references": refs}
    )

if __name__ == "__main__":
    create_metric_viz("dcim-mon-nas-vol-used", "Used Storage (GB)", "dcim_metrics.raw_fields_volumeUsedGB", "nas")
    create_metric_viz("dcim-mon-nas-vol-total", "Total Capacity (TB)", "dcim_metrics.raw_fields_volumeTotalTB", "nas")
    create_metric_viz("dcim-mon-nas-vol-pct", "Storage Used (%)", "dcim_metrics.raw_fields_volumeUsagePct", "nas")
    create_metric_viz("dcim-mon-nas-status", "Volume Status (1=OK)", "dcim_metrics.raw_fields_volumeStatus", "nas")
    create_line_viz("dcim-mon-nas-vol-time", "Storage Usage Over Time (%)", "dcim_metrics.raw_fields_volumeUsagePct", "nas")
    
    fix_dashboard()
    print("✅ Successfully added 5 new visualizations for NAS Storage!")
