#!/usr/bin/env python3
"""
Create SIMPLE WORKING Kibana Dashboard - Only fields that exist in data
"""
import json
import sys
import requests

KIBANA_URL = "http://10.70.0.56:5601"
INDEX_PATTERN_ID = "dcim-working"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}
ELASTIC_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def save_object(obj_type, obj_id, attributes):
    """Save Kibana object"""
    if obj_type == "visualization":
        visState = {
            "title": attributes.get("title", ""),
            "type": attributes.get("type", "metric"),
            "params": attributes.get("params", {}),
            "aggs": attributes.get("aggs", [])
        }
        searchSource = {
            "query": {"query": "", "language": "kuery"},
            "filter": attributes.get("filters", []),
            "indexRefName": "kibanaSavedObjectMeta.searchSourceJSON.index"
        }
        final_attrs = {
            "title": attributes.get("title", ""),
            "visState": json.dumps(visState),
            "uiStateJSON": "{}",
            "description": "",
            "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps(searchSource)}
        }
        references = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": INDEX_PATTERN_ID}]
        payload = {"attributes": final_attrs, "references": references}
    else:
        payload = {"attributes": attributes}

    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true",
        headers=HEADERS, json=payload, auth=ELASTIC_AUTH
    )
    if resp.status_code in (200, 201):
        print(f"  ✅ {obj_id}")
        return True
    else:
        print(f"  ❌ {obj_id}: {resp.status_code}")
        print(f"     Error: {resp.text[:500]}")
        return False

def make_donut(panel_id, title, field, device_filter=None):
    """Create donut chart"""
    filters = []
    if device_filter:
        filters.append({
            "meta": {"index": INDEX_PATTERN_ID, "key": "device_type.keyword"},
            "query": {"match_phrase": {"device_type.keyword": device_filter}}
        })
    
    success = save_object("visualization", panel_id, {
        "title": title, "type": "pie",
        "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", 
                   "isDonut": True, "labels": {"show": True, "values": True}},
        "aggs": [
            {"id": "1", "type": "count", "schema": "metric", "params": {}},
            {"id": "2", "type": "terms", "schema": "segment", 
             "params": {"field": field, "size": 10, "order": "desc", "orderBy": "1"}}
        ],
        "filters": filters
    })
    return panel_id if success else None

def make_line(panel_id, title, field, device_filter=None):
    """Create line chart"""
    filters = []
    if device_filter:
        filters.append({
            "meta": {"index": INDEX_PATTERN_ID, "key": "device_type.keyword"},
            "query": {"match_phrase": {"device_type.keyword": device_filter}}
        })
    
    success = save_object("visualization", panel_id, {
        "title": title, "type": "line",
        "params": {"type": "line", "addTooltip": True, "addLegend": True, "legendPosition": "right"},
        "aggs": [
            {"id": "1", "type": "avg", "schema": "metric", "params": {"field": field}},
            {"id": "2", "type": "date_histogram", "schema": "segment", 
             "params": {"field": "@timestamp", "interval": "auto"}},
            {"id": "3", "type": "terms", "schema": "group", 
             "params": {"field": "hostname.keyword", "size": 5, "order": "desc", "orderBy": "1"}}
        ],
        "filters": filters
    })
    return panel_id if success else None

def make_table(panel_id, title, columns, device_filter=None):
    """Create data table"""
    filters = []
    if device_filter:
        filters.append({
            "meta": {"index": INDEX_PATTERN_ID, "key": "device_type.keyword"},
            "query": {"match_phrase": {"device_type.keyword": device_filter}}
        })
    
    aggs = [{"id": "1", "type": "count", "schema": "metric", "params": {}}]
    for i, (field, label) in enumerate(columns, start=2):
        aggs.append({
            "id": str(i), "type": "terms", "schema": "bucket",
            "params": {"field": field, "size": 20, "order": "desc", "orderBy": "1"}
        })
    
    success = save_object("visualization", panel_id, {
        "title": title, "type": "table",
        "params": {"perPage": 10, "showPartialRows": False, "showTotal": False},
        "aggs": aggs, "filters": filters
    })
    return panel_id if success else None

def make_metric(panel_id, title):
    """Create metric panel"""
    success = save_object("visualization", panel_id, {
        "title": title, "type": "metric",
        "params": {"addTooltip": True, "addLegend": False, "type": "metric",
                   "metric": {"style": {"fontSize": 60}}},
        "aggs": [{"id": "1", "type": "count", "schema": "metric", "params": {}}],
        "filters": []
    })
    return panel_id if success else None

def make_markdown(panel_id, title, text):
    """Create markdown panel"""
    success = save_object("visualization", panel_id, {
        "title": title, "type": "markdown",
        "params": {"fontSize": 12, "markdown": text}
    })
    return panel_id if success else None

print("=" * 70)
print("DCIM SIMPLE WORKING DASHBOARD")
print("=" * 70)

# Test connection
resp = requests.get(f"{KIBANA_URL}/api/status", headers=HEADERS, auth=ELASTIC_AUTH)
if resp.status_code != 200:
    print(f"❌ Cannot connect to Kibana")
    sys.exit(1)

print(f"✅ Connected to Kibana\n")

# Create index pattern
print("📋 Creating index pattern...")
requests.post(
    f"{KIBANA_URL}/api/saved_objects/index-pattern/{INDEX_PATTERN_ID}?overwrite=true",
    headers=HEADERS,
    json={"attributes": {"title": "dcim-metrics-unified-*", "timeFieldName": "@timestamp"}},
    auth=ELASTIC_AUTH
)
print("✅ Index pattern ready\n")

print("=== Creating Visualizations ===\n")

panels = {}

# Header
panels["header"] = make_markdown("dcim-header", "Header", 
    "# 🖥️ DCIM Monitoring Dashboard\n**Real-time metrics from all infrastructure devices**")

# Global Overview
panels["p1"] = make_donut("dcim-p1", "Devices by Type", "device_type.keyword")
panels["p2"] = make_donut("dcim-p2", "Enrichment Status", "enrichment_status.keyword")
panels["p3"] = make_donut("dcim-p3", "Severity Levels", "severity.keyword")
panels["p4"] = make_metric("dcim-p4", "Total Events (1h)")

# Network Switch
panels["net_h"] = make_markdown("dcim-net-h", "Network Header", "## 🔌 Network Switches")
panels["p5"] = make_line("dcim-p5", "Switch CPU Load", "raw_fields.cpu_load", "network_switch")
panels["p6"] = make_line("dcim-p6", "Switch Memory (KB)", "raw_fields.memory_used_kb", "network_switch")
panels["p7"] = make_table("dcim-p7", "Network Devices", 
    [("hostname.keyword", "Hostname"), ("device_type.keyword", "Type")], "network_switch")

# Servers
panels["srv_h"] = make_markdown("dcim-srv-h", "Server Header", "## 🖥️ Servers")
panels["p8"] = make_line("dcim-p8", "Server Temperature (°C)", "raw_fields.reading_celsius", "server")
panels["p9"] = make_line("dcim-p9", "Server Fan Speed (RPM)", "raw_fields.reading_rpm", "server")
panels["p10"] = make_line("dcim-p10", "Server Power (W)", "raw_fields.power_input_watts", "server")
panels["p11"] = make_table("dcim-p11", "Server List",
    [("hostname.keyword", "Hostname"), ("raw_fields.model.keyword", "Model")], "server")

# CCTV
panels["cctv_h"] = make_markdown("dcim-cctv-h", "CCTV Header", "## 📷 CCTV Cameras")
panels["p12"] = make_donut("dcim-p12", "Camera Status", "raw_fields.status_text.keyword", "cctv")
panels["p13"] = make_line("dcim-p13", "Camera CPU (%)", "raw_fields.cpuUtilization", "cctv")
panels["p14"] = make_line("dcim-p14", "Camera Memory (%)", "raw_fields.memoryUsage", "cctv")
panels["p15"] = make_table("dcim-p15", "Camera List",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP")], "cctv")

# NAS
panels["nas_h"] = make_markdown("dcim-nas-h", "NAS Header", "## 💾 NAS Storage")
panels["p16"] = make_table("dcim-p16", "NAS Devices",
    [("hostname.keyword", "Hostname"), ("device_type.keyword", "Type")], "nas")

# NVR
panels["nvr_h"] = make_markdown("dcim-nvr-h", "NVR Header", "## 📹 NVR Recorders")
panels["p17"] = make_table("dcim-p17", "NVR Devices",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP")], "nvr")

print("\n=== Creating Dashboard ===\n")

# Layout - simple 2-column grid (24 columns total)
layout = [
    {"id": "dcim-header", "x": 0, "y": 0, "w": 24, "h": 2},
    
    # Global
    {"id": "dcim-p1", "x": 0, "y": 2, "w": 6, "h": 8},
    {"id": "dcim-p2", "x": 6, "y": 2, "w": 6, "h": 8},
    {"id": "dcim-p3", "x": 12, "y": 2, "w": 6, "h": 8},
    {"id": "dcim-p4", "x": 18, "y": 2, "w": 6, "h": 8},
    
    # Network
    {"id": "dcim-net-h", "x": 0, "y": 10, "w": 24, "h": 1},
    {"id": "dcim-p5", "x": 0, "y": 11, "w": 12, "h": 6},
    {"id": "dcim-p6", "x": 12, "y": 11, "w": 12, "h": 6},
    {"id": "dcim-p7", "x": 0, "y": 17, "w": 24, "h": 6},
    
    # Server
    {"id": "dcim-srv-h", "x": 0, "y": 23, "w": 24, "h": 1},
    {"id": "dcim-p8", "x": 0, "y": 24, "w": 8, "h": 6},
    {"id": "dcim-p9", "x": 8, "y": 24, "w": 8, "h": 6},
    {"id": "dcim-p10", "x": 16, "y": 24, "w": 8, "h": 6},
    {"id": "dcim-p11", "x": 0, "y": 30, "w": 24, "h": 6},
    
    # CCTV
    {"id": "dcim-cctv-h", "x": 0, "y": 36, "w": 24, "h": 1},
    {"id": "dcim-p12", "x": 0, "y": 37, "w": 8, "h": 6},
    {"id": "dcim-p13", "x": 8, "y": 37, "w": 8, "h": 6},
    {"id": "dcim-p14", "x": 16, "y": 37, "w": 8, "h": 6},
    {"id": "dcim-p15", "x": 0, "y": 43, "w": 24, "h": 6},
    
    # NAS
    {"id": "dcim-nas-h", "x": 0, "y": 49, "w": 24, "h": 1},
    {"id": "dcim-p16", "x": 0, "y": 50, "w": 24, "h": 6},
    
    # NVR
    {"id": "dcim-nvr-h", "x": 0, "y": 56, "w": 24, "h": 1},
    {"id": "dcim-p17", "x": 0, "y": 57, "w": 24, "h": 6},
]

dashboard_panels = []
references = []
for i, p in enumerate(layout):
    dashboard_panels.append({
        "version": "8.0.0", "type": "visualization",
        "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": str(i+1)},
        "panelIndex": str(i+1), "panelRefName": f"panel_{i+1}"
    })
    references.append({"name": f"panel_{i+1}", "type": "visualization", "id": p["id"]})

dashboard_attrs = {
    "title": "DCIM Infrastructure - Working Dashboard",
    "description": "Simple working dashboard with only available fields",
    "panelsJSON": json.dumps(dashboard_panels),
    "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
    "timeRestore": True, "timeTo": "now", "timeFrom": "now-1h",
    "refreshInterval": {"pause": False, "value": 30000},
    "kibanaSavedObjectMeta": {
        "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
    }
}

resp = requests.post(
    f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-working-dashboard?overwrite=true",
    headers=HEADERS,
    json={"attributes": dashboard_attrs, "references": references},
    auth=ELASTIC_AUTH
)

if resp.status_code in (200, 201):
    print("✅ Dashboard created!")
    print(f"\n📊 URL: {KIBANA_URL}/app/dashboards#/view/dcim-working-dashboard")
    print(f"📊 Total panels: {len(layout)}")
else:
    print(f"❌ Failed: {resp.status_code}")

print("\n" + "=" * 70)
print("✅ COMPLETE")
print("=" * 70)
