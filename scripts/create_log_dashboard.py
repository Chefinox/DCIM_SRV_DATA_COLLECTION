#!/usr/bin/env python3
"""
Create Kibana Dashboard for DCIM Logs
"""
import json
import sys
import requests

KIBANA_URL = "http://10.70.0.56:5601"
ES_URL = "https://10.70.0.56:9200"
INDEX_PATTERN_ID = "dcim-logs-*"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}
AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def create_index_pattern():
    print("📋 Creating index pattern dcim-logs-* ...")
    payload = {
        "attributes": {
            "title": "dcim-logs-*",
            "timeFieldName": "@timestamp"
        }
    }
    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}?overwrite=true",
        headers=HEADERS, json=payload, auth=AUTH
    )
    if resp.status_code in (200, 201):
        print(f"✅ Index pattern created: {INDEX_PATTERN_ID}")
        return True
    else:
        print(f"❌ Failed: {resp.status_code} - {resp.text[:200]}")
        return False

def create_markdown_viz(viz_id, title, markdown_text):
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "markdown",
                "params": {"fontSize": 12, "openLinksInNewTab": False, "markdown": markdown_text},
                "aggs": []
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
            }
        }
    }
    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true", headers=HEADERS, json=payload, auth=AUTH)
    return resp.status_code in (200, 201)

def create_metric_viz(viz_id, title, level_filter=None):
    filters = []
    if level_filter:
        filters.append({
            "meta": {"alias": None, "disabled": False, "negate": False, "key": "level", "type": "phrase", "index": INDEX_PATTERN_ID},
            "query": {"match_phrase": {"level": level_filter}}
        })
    aggs = [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": title}}]
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title, "type": "metric",
                "params": {
                    "addTooltip": True, "addLegend": False, "type": "metric",
                    "metric": {"percentageMode": False, "useRanges": False, "labels": {"show": True}, "style": {"fontSize": 60}}
                },
                "aggs": aggs
            }),
            "uiStateJSON": "{}",
            "description": "", "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": filters, "index": INDEX_PATTERN_ID})
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": INDEX_PATTERN_ID}]
    }
    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true", headers=HEADERS, json=payload, auth=AUTH)
    return resp.status_code in (200, 201)

def create_table_viz(viz_id, title, query_str=""):
    filters = []
    aggs = [
        {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket", "params": {"field": "service.keyword", "size": 10, "order": "desc", "orderBy": "1", "customLabel": "Service"}},
        {"id": "3", "enabled": True, "type": "terms", "schema": "bucket", "params": {"field": "level.keyword", "size": 5, "order": "desc", "orderBy": "1", "customLabel": "Level"}},
        {"id": "4", "enabled": True, "type": "terms", "schema": "bucket", "params": {"field": "message.keyword", "size": 20, "order": "desc", "orderBy": "1", "customLabel": "Message"}}
    ]
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title, "type": "table",
                "params": {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False},
                "aggs": aggs
            }),
            "uiStateJSON": "{}",
            "description": "", "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({"query": {"query": query_str, "language": "kuery"}, "filter": filters, "index": INDEX_PATTERN_ID})
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": INDEX_PATTERN_ID}]
    }
    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true", headers=HEADERS, json=payload, auth=AUTH)
    return resp.status_code in (200, 201)

if __name__ == "__main__":
    if not create_index_pattern():
        sys.exit(1)
    
    create_markdown_viz("dcim-log-header", "DCIM Logs Header", "# 📜 DCIM Centralized Logs\n**Monitor Python microservices via Filebeat JSON logging**")
    create_metric_viz("dcim-log-total", "Total Logs")
    create_metric_viz("dcim-log-error", "Total Errors", "ERROR")
    create_metric_viz("dcim-log-warn", "Total Warnings", "WARN")
    create_table_viz("dcim-log-table", "Log Messages Summary")
    
    panels = [
        {"id": "dcim-log-header", "x": 0, "y": 0, "w": 48, "h": 3},
        {"id": "dcim-log-total", "x": 0, "y": 3, "w": 16, "h": 6},
        {"id": "dcim-log-warn", "x": 16, "y": 3, "w": 16, "h": 6},
        {"id": "dcim-log-error", "x": 32, "y": 3, "w": 16, "h": 6},
        {"id": "dcim-log-table", "x": 0, "y": 9, "w": 48, "h": 15},
    ]
    
    dashboard_panels = []
    references = []
    for i, p in enumerate(panels):
        dashboard_panels.append({
            "version": "8.8.0", "type": "visualization",
            "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": str(i+1)},
            "panelIndex": str(i+1), "embeddableConfig": {"enhancements": {}}, "panelRefName": f"panel_{i+1}"
        })
        references.append({"name": f"panel_{i+1}", "type": "visualization", "id": p["id"]})
        
    dashboard_attrs = {
        "title": "DCIM Observability - Centralized Logs",
        "description": "Dashboard for JSON structured logs",
        "panelsJSON": json.dumps(dashboard_panels),
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": False, "hidePanelTitles": False}),
        "version": 1, "timeRestore": True, "timeTo": "now", "timeFrom": "now-24h",
        "refreshInterval": {"pause": False, "value": 10000},
        "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})}
    }
    
    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-log-dashboard?overwrite=true", headers=HEADERS, json={"attributes": dashboard_attrs, "references": references}, auth=AUTH)
    if resp.status_code in (200, 201):
        print(f"✅ Dashboard created! URL: {KIBANA_URL}/app/dashboards#/view/dcim-log-dashboard")
    else:
        print(f"❌ Failed: {resp.status_code}")
