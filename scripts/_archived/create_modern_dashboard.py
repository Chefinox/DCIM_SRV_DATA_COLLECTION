#!/usr/bin/env python3
"""
Create Modern Kibana Dashboard using compatible visualization format
"""
import json
import sys
import requests

KIBANA_URL = "http://10.70.0.56:5601"
ES_URL = "https://10.70.0.56:9200"
INDEX_PATTERN_ID = "dcim-metrics-*"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}
AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def create_index_pattern():
    """Create or update index pattern"""
    print("📋 Creating index pattern...")
    payload = {
        "attributes": {
            "title": "dcim-metrics-unified-*",
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
    """Create markdown visualization"""
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "markdown",
                "params": {
                    "fontSize": 12,
                    "openLinksInNewTab": False,
                    "markdown": markdown_text
                },
                "aggs": []
            }),
            "uiStateJSON": "{}",
            "description": "",
            "version": 1,
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps({
                    "query": {"query": "", "language": "kuery"},
                    "filter": []
                })
            }
        }
    }
    
    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/visualization/{viz_id}?overwrite=true",
        headers=HEADERS, json=payload, auth=AUTH
    )
    return resp.status_code in (200, 201)

def create_metric_viz(viz_id, title, field=None, device_filter=None):
    """Create metric visualization"""
    filters = []
    if device_filter:
        filters.append({
            "meta": {
                "alias": None,
                "disabled": False,
                "negate": False,
                "key": "device_type.keyword",
                "type": "phrase",
                "index": INDEX_PATTERN_ID
            },
            "query": {"match_phrase": {"device_type.keyword": device_filter}}
        })
    
    aggs = []
    if field:
        aggs = [{
            "id": "1",
            "enabled": True,
            "type": "avg",
            "schema": "metric",
            "params": {"field": field, "customLabel": title}
        }]
    else:
        aggs = [{
            "id": "1",
            "enabled": True,
            "type": "count",
            "schema": "metric",
            "params": {"customLabel": title}
        }]
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "metric",
                "params": {
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
                        "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
                    }
                },
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
        headers=HEADERS, json=payload, auth=AUTH
    )
    return resp.status_code in (200, 201)

def create_data_table_viz(viz_id, title, columns, device_filter=None):
    """Create data table visualization"""
    filters = []
    if device_filter:
        filters.append({
            "meta": {
                "alias": None,
                "disabled": False,
                "negate": False,
                "key": "device_type.keyword",
                "type": "phrase",
                "index": INDEX_PATTERN_ID
            },
            "query": {"match_phrase": {"device_type.keyword": device_filter}}
        })
    
    aggs = [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}]
    for i, (field, label) in enumerate(columns, start=2):
        aggs.append({
            "id": str(i),
            "enabled": True,
            "type": "terms",
            "schema": "bucket",
            "params": {
                "field": field,
                "size": 20,
                "order": "desc",
                "orderBy": "1",
                "customLabel": label
            }
        })
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": "table",
                "params": {
                    "perPage": 10,
                    "showPartialRows": False,
                    "showMetricsAtAllLevels": False,
                    "showTotal": False,
                    "totalFunc": "sum",
                    "percentageCol": ""
                },
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
        headers=HEADERS, json=payload, auth=AUTH
    )
    return resp.status_code in (200, 201)

print("=" * 70)
print("DCIM MODERN DASHBOARD CREATOR")
print("=" * 70)

# Test connection
resp = requests.get(f"{KIBANA_URL}/api/status", headers=HEADERS, auth=AUTH)
if resp.status_code != 200:
    print(f"❌ Cannot connect to Kibana")
    sys.exit(1)
print("✅ Connected to Kibana\n")

# Create index pattern
if not create_index_pattern():
    sys.exit(1)

print("\n=== Creating Visualizations ===\n")

viz_count = 0

# Header
if create_markdown_viz("dcim-modern-header", "DCIM Dashboard", 
    "# 🖥️ DCIM Infrastructure Monitoring\n**Real-time metrics from all devices**"):
    print("  ✅ Header")
    viz_count += 1

# Global metrics
if create_metric_viz("dcim-modern-total", "Total Events"):
    print("  ✅ Total Events")
    viz_count += 1

if create_data_table_viz("dcim-modern-devices", "All Devices", 
    [("device_type.keyword", "Type"), ("hostname.keyword", "Hostname"), ("ip.keyword", "IP")]):
    print("  ✅ Device List")
    viz_count += 1

# Network
if create_markdown_viz("dcim-modern-net-h", "Network Section", "## 🔌 Network Switches"):
    print("  ✅ Network Header")
    viz_count += 1

if create_metric_viz("dcim-modern-net-count", "Network Devices", None, "network_switch"):
    print("  ✅ Network Count")
    viz_count += 1

if create_data_table_viz("dcim-modern-net-list", "Network Switch List",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP")], "network_switch"):
    print("  ✅ Network List")
    viz_count += 1

# Servers
if create_markdown_viz("dcim-modern-srv-h", "Server Section", "## 🖥️ Servers"):
    print("  ✅ Server Header")
    viz_count += 1

if create_metric_viz("dcim-modern-srv-count", "Server Count", None, "server"):
    print("  ✅ Server Count")
    viz_count += 1

if create_data_table_viz("dcim-modern-srv-list", "Server List",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP")], "server"):
    print("  ✅ Server List")
    viz_count += 1

# CCTV
if create_markdown_viz("dcim-modern-cctv-h", "CCTV Section", "## 📷 CCTV Cameras"):
    print("  ✅ CCTV Header")
    viz_count += 1

if create_metric_viz("dcim-modern-cctv-count", "Camera Count", None, "cctv"):
    print("  ✅ Camera Count")
    viz_count += 1

if create_data_table_viz("dcim-modern-cctv-list", "Camera List",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP")], "cctv"):
    print("  ✅ Camera List")
    viz_count += 1

print(f"\n✅ Created {viz_count} visualizations")

# Create dashboard
print("\n=== Creating Dashboard ===\n")

panels = [
    {"id": "dcim-modern-header", "x": 0, "y": 0, "w": 48, "h": 3},
    {"id": "dcim-modern-total", "x": 0, "y": 3, "w": 12, "h": 8},
    {"id": "dcim-modern-devices", "x": 12, "y": 3, "w": 36, "h": 8},
    
    {"id": "dcim-modern-net-h", "x": 0, "y": 11, "w": 48, "h": 2},
    {"id": "dcim-modern-net-count", "x": 0, "y": 13, "w": 12, "h": 6},
    {"id": "dcim-modern-net-list", "x": 12, "y": 13, "w": 36, "h": 6},
    
    {"id": "dcim-modern-srv-h", "x": 0, "y": 19, "w": 48, "h": 2},
    {"id": "dcim-modern-srv-count", "x": 0, "y": 21, "w": 12, "h": 6},
    {"id": "dcim-modern-srv-list", "x": 12, "y": 21, "w": 36, "h": 6},
    
    {"id": "dcim-modern-cctv-h", "x": 0, "y": 27, "w": 48, "h": 2},
    {"id": "dcim-modern-cctv-count", "x": 0, "y": 29, "w": 12, "h": 6},
    {"id": "dcim-modern-cctv-list", "x": 12, "y": 29, "w": 36, "h": 6},
]

dashboard_panels = []
references = []

for i, p in enumerate(panels):
    dashboard_panels.append({
        "version": "8.8.0",
        "type": "visualization",
        "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": str(i+1)},
        "panelIndex": str(i+1),
        "embeddableConfig": {"enhancements": {}},
        "panelRefName": f"panel_{i+1}"
    })
    references.append({
        "name": f"panel_{i+1}",
        "type": "visualization",
        "id": p["id"]
    })

dashboard_attrs = {
    "title": "DCIM Infrastructure - Modern Dashboard",
    "description": "Simple working dashboard with modern format",
    "panelsJSON": json.dumps(dashboard_panels),
    "optionsJSON": json.dumps({
        "useMargins": True,
        "syncColors": False,
        "hidePanelTitles": False
    }),
    "version": 1,
    "timeRestore": True,
    "timeTo": "now",
    "timeFrom": "now-1h",
    "refreshInterval": {
        "pause": False,
        "value": 30000
    },
    "kibanaSavedObjectMeta": {
        "searchSourceJSON": json.dumps({
            "query": {"query": "", "language": "kuery"},
            "filter": []
        })
    }
}

resp = requests.post(
    f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-modern-dashboard?overwrite=true",
    headers=HEADERS,
    json={"attributes": dashboard_attrs, "references": references},
    auth=AUTH
)

if resp.status_code in (200, 201):
    print("✅ Dashboard created!")
    print(f"\n📊 URL: {KIBANA_URL}/app/dashboards#/view/dcim-modern-dashboard")
    print(f"📊 Total panels: {len(panels)}")
else:
    print(f"❌ Failed: {resp.status_code}")
    print(resp.text[:500])

print("\n" + "=" * 70)
print("✅ COMPLETE")
print("=" * 70)
