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
            "meta": {"alias": None, "disabled": False, "negate": False, "key": "log.level", "type": "phrase", "index": INDEX_PATTERN_ID},
            "query": {"match_phrase": {"log.level": level_filter}}
        })
    aggs = [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": title}}]
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title, "type": "metric",
                "params": {
                    "addTooltip": True, "addLegend": False, "type": "metric",
                    "metric": {
                        "percentageMode": False, "useRanges": False,
                        "colorSchema": "Green to Red", "metricColorMode": "None",
                        "colorsRange": [{"from": 0, "to": 10000}],
                        "labels": {"show": True}, "invertColors": False,
                        "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
                    }
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
        {"id": "2", "enabled": True, "type": "terms", "schema": "bucket", "params": {"field": "service.name", "size": 10, "order": "desc", "orderBy": "1", "customLabel": "Service"}},
        {"id": "3", "enabled": True, "type": "terms", "schema": "bucket", "params": {"field": "log.level", "size": 5, "order": "desc", "orderBy": "1", "customLabel": "Level"}}
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

def create_saved_search(search_id, title):
    payload = {
        "attributes": {
            "title": title,
            "description": "",
            "hits": 0,
            "columns": ["@timestamp", "log.level", "service.name", "message"],
            "sort": [["@timestamp", "desc"]],
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": [],
                    "index": INDEX_PATTERN_ID
                })
            }
        },
        "references": [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": INDEX_PATTERN_ID}]
    }
    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/search/{search_id}?overwrite=true", headers=HEADERS, json=payload, auth=AUTH)
    return resp.status_code in (200, 201)

if __name__ == "__main__":
    if not create_index_pattern():
        sys.exit(1)
    
    create_markdown_viz("dcim-log-header", "DCIM Logs Header", "# 📜 DCIM Centralized Logs\n**Monitor Python microservices via Filebeat JSON logging**")
    create_metric_viz("dcim-log-total", "Total Logs")
    create_metric_viz("dcim-log-error", "Total Errors", "ERROR")
    create_metric_viz("dcim-log-warn", "Total Warnings", "WARNING")
    create_table_viz("dcim-log-table", "Log Messages Summary")
    create_saved_search("dcim-raw-logs", "Raw Log Messages")
    
    panels = [
        {"id": "dcim-log-header", "x": 0, "y": 0, "w": 48, "h": 3, "type": "visualization"},
        {"id": "dcim-log-total", "x": 0, "y": 3, "w": 16, "h": 6, "type": "visualization"},
        {"id": "dcim-log-warn", "x": 16, "y": 3, "w": 16, "h": 6, "type": "visualization"},
        {"id": "dcim-log-error", "x": 32, "y": 3, "w": 16, "h": 6, "type": "visualization"},
        {"id": "dcim-log-table", "x": 0, "y": 9, "w": 48, "h": 10, "type": "visualization"},
        {"id": "dcim-raw-logs", "x": 0, "y": 19, "w": 48, "h": 15, "type": "search"}
    ]
    
    dashboard_panels = []
    references = []
    for i, p in enumerate(panels):
        dashboard_panels.append({
            "version": "8.9.2",
            "type": p.get("type", "visualization"),
            "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": str(i)},
            "panelIndex": str(i),
            "embeddableConfig": {},
            "panelRefName": f"panel_{i}"
        })
        references.append({
            "name": f"panel_{i}",
            "type": p.get("type", "visualization"),
            "id": p["id"]
        })
        
    dashboard_attrs = {
        "title": "DCIM Observability - Centralized Logs",
        "hits": 0,
        "description": "Monitor Python microservices via Filebeat JSON logging",
        "panelsJSON": json.dumps(dashboard_panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "version": 1,
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({
                "query": {"query": "", "language": "kuery"},
                "filter": [{
                    "meta": {
                        "alias": "Microservices Only",
                        "disabled": False,
                        "negate": False,
                        "key": "service.name",
                        "type": "exists",
                        "value": "exists",
                        "index": INDEX_PATTERN_ID
                    },
                    "exists": {"field": "service.name"}
                }]
            })
        }
    }
    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-log-dashboard?overwrite=true", headers=HEADERS, json={"attributes": dashboard_attrs, "references": references}, auth=AUTH)
    if resp.status_code in (200, 201):
        print(f"✅ Dashboard created! URL: {KIBANA_URL}/app/dashboards#/view/dcim-log-dashboard")
    else:
        print(f"❌ Failed: {resp.status_code}")
