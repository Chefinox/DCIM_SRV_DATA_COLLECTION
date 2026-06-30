#!/usr/bin/env python3
"""
Create Comprehensive DCIM Monitoring Dashboard with Performance Metrics
"""
import json
import sys
import requests

KIBANA_URL = "http://10.70.0.56:5601"
INDEX_PATTERN_ID = "dcim-metrics-*"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}
AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def create_viz(viz_id, title, viz_type, field=None, device_filter=None, agg_type="avg"):
    """Create visualization with proper format"""
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
    
    # Build aggregations based on viz type
    if viz_type == "metric":
        if field:
            aggs = [{
                "id": "1",
                "enabled": True,
                "type": agg_type,
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
    
    elif viz_type == "line":
        aggs = [
            {
                "id": "1",
                "enabled": True,
                "type": agg_type,
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
                    "field": "hostname.keyword",
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
    
    elif viz_type == "pie":
        aggs = [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}},
            {
                "id": "2",
                "enabled": True,
                "type": "terms",
                "schema": "segment",
                "params": {
                    "field": field,
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
            "type": "pie",
            "addTooltip": True,
            "addLegend": True,
            "legendPosition": "right",
            "isDonut": True,
            "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}
        }
    
    elif viz_type == "table":
        aggs = [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {}}]
        if field:
            # For tables, field is a list of (field_name, label) tuples
            for i, (fname, label) in enumerate(field, start=2):
                aggs.append({
                    "id": str(i),
                    "enabled": True,
                    "type": "terms",
                    "schema": "bucket",
                    "params": {
                        "field": fname,
                        "orderBy": "1",
                        "order": "desc",
                        "size": 20,
                        "otherBucket": False,
                        "otherBucketLabel": "Other",
                        "missingBucket": False,
                        "missingBucketLabel": "Missing",
                        "customLabel": label
                    }
                })
        params = {
            "perPage": 10,
            "showPartialRows": False,
            "showMetricsAtAllLevels": False,
            "showTotal": False,
            "totalFunc": "sum",
            "percentageCol": ""
        }
    
    elif viz_type == "markdown":
        aggs = []
        params = {
            "fontSize": 12,
            "openLinksInNewTab": False,
            "markdown": field  # field contains markdown text
        }
    
    payload = {
        "attributes": {
            "title": title,
            "visState": json.dumps({
                "title": title,
                "type": viz_type,
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
        headers=HEADERS, json=payload, auth=AUTH
    )
    
    if resp.status_code in (200, 201):
        print(f"  ✅ {title}")
        return True
    else:
        print(f"  ❌ {title}: {resp.status_code}")
        return False

print("=" * 70)
print("DCIM COMPREHENSIVE MONITORING DASHBOARD")
print("=" * 70)

# Test connection
resp = requests.get(f"{KIBANA_URL}/api/status", headers=HEADERS, auth=AUTH)
if resp.status_code != 200:
    print(f"❌ Cannot connect to Kibana")
    sys.exit(1)
print("✅ Connected to Kibana\n")

print("=== Creating Visualizations ===\n")

viz_list = []

# Header
viz_list.append(("dcim-mon-header", "DCIM Monitoring", "markdown", 
    "# 🖥️ DCIM Infrastructure Monitoring\n**Real-time performance metrics and device status**", None))

# Global Overview
viz_list.append(("dcim-mon-total", "Total Events", "metric", None, None))
viz_list.append(("dcim-mon-devices", "Device Types", "pie", "device_type.keyword", None))
viz_list.append(("dcim-mon-severity", "Severity Levels", "pie", "severity.keyword", None))
viz_list.append(("dcim-mon-enrichment", "Enrichment Status", "pie", "enrichment_status.keyword", None))

# === NETWORK SWITCHES ===
viz_list.append(("dcim-mon-net-h", "Network Header", "markdown", "## 🔌 Network Switches - Performance", None))
viz_list.append(("dcim-mon-net-count", "Switch Count", "metric", None, "network_switch"))
viz_list.append(("dcim-mon-net-cpu-avg", "Avg CPU Load (%)", "metric", "metric_value", "network_switch", "avg"))
viz_list.append(("dcim-mon-net-mem-avg", "Avg Memory (KB)", "metric", "raw_fields.memory_used", "network_switch", "avg"))
viz_list.append(("dcim-mon-net-cpu", "CPU Load Over Time", "line", "metric_value", "network_switch", "avg"))
viz_list.append(("dcim-mon-net-mem", "Memory Usage Over Time", "line", "raw_fields.memory_used", "network_switch", "avg"))
viz_list.append(("dcim-mon-net-list", "Switch Details", "table", 
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP"), ("metric_value", "CPU %"), ("raw_fields.memory_used", "Memory KB")], 
    "network_switch"))

# === SERVERS ===
viz_list.append(("dcim-mon-srv-h", "Server Header", "markdown", "## 🖥️ Servers - Performance & Health", None))
viz_list.append(("dcim-mon-srv-count", "Server Count", "metric", None, "server"))
viz_list.append(("dcim-mon-srv-temp-avg", "Avg Temperature (°C)", "metric", "raw_fields.reading_celsius", "server", "avg"))
viz_list.append(("dcim-mon-srv-power-avg", "Avg Power (W)", "metric", "raw_fields.power_input_watts", "server", "avg"))
viz_list.append(("dcim-mon-srv-temp", "Temperature Over Time", "line", "raw_fields.reading_celsius", "server", "avg"))
viz_list.append(("dcim-mon-srv-fan", "Fan Speed Over Time", "line", "raw_fields.reading_rpm", "server", "avg"))
viz_list.append(("dcim-mon-srv-power", "Power Consumption Over Time", "line", "raw_fields.power_input_watts", "server", "avg"))
viz_list.append(("dcim-mon-srv-list", "Server Details", "table",
    [("hostname.keyword", "Hostname"), ("site.keyword", "Site"), ("rack_name.keyword", "Rack"), ("model.keyword", "Model"), ("manufacturer.keyword", "Manufacturer")],
    "server"))

# === CCTV CAMERAS ===
viz_list.append(("dcim-mon-cctv-h", "CCTV Header", "markdown", "## 📷 CCTV Cameras - Status & Performance", None))
viz_list.append(("dcim-mon-cctv-count", "Camera Count", "metric", None, "cctv"))
viz_list.append(("dcim-mon-cctv-cpu-avg", "Avg CPU (%)", "metric", "raw_fields.cpuUtilization", "cctv", "avg"))
viz_list.append(("dcim-mon-cctv-mem-avg", "Avg Memory (%)", "metric", "raw_fields.memoryUsage", "cctv", "avg"))
viz_list.append(("dcim-mon-cctv-status", "Camera Status", "pie", "raw_fields.status_text.keyword", "cctv"))
viz_list.append(("dcim-mon-cctv-cpu", "CPU Usage Over Time", "line", "raw_fields.cpuUtilization", "cctv", "avg"))
viz_list.append(("dcim-mon-cctv-mem", "Memory Usage Over Time", "line", "raw_fields.memoryUsage", "cctv", "avg"))
viz_list.append(("dcim-mon-cctv-list", "Camera Details", "table",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP"), ("raw_fields.status_text.keyword", "Status"), ("raw_fields.cpuUtilization", "CPU %"), ("raw_fields.memoryUsage", "Mem %")],
    "cctv"))

# === UPS POWER ===
viz_list.append(("dcim-mon-ups-h", "UPS Header", "markdown", "## ⚡ UPS - Power & Battery", None))
viz_list.append(("dcim-mon-ups-count", "UPS Count", "metric", None, "ups"))
viz_list.append(("dcim-mon-ups-battery", "Battery Capacity (%)", "metric", "metric_value", "ups", "avg"))
viz_list.append(("dcim-mon-ups-load", "Output Load (%)", "metric", "raw_fields.output_load", "ups", "avg"))
viz_list.append(("dcim-mon-ups-battery-time", "Battery Capacity Over Time", "line", "metric_value", "ups", "avg"))
viz_list.append(("dcim-mon-ups-load-time", "Output Load Over Time", "line", "raw_fields.output_load", "ups", "avg"))
viz_list.append(("dcim-mon-ups-list", "UPS Details", "table",
    [("hostname.keyword", "Hostname"), ("site.keyword", "Site"), ("rack_name.keyword", "Rack"), ("model.keyword", "Model"), ("metric_value", "Battery %"), ("raw_fields.output_load", "Load %")],
    "ups"))

# === NAS STORAGE ===
viz_list.append(("dcim-mon-nas-h", "NAS Header", "markdown", "## 💾 NAS Storage", None))
viz_list.append(("dcim-mon-nas-count", "NAS Count", "metric", None, "nas"))
viz_list.append(("dcim-mon-nas-list", "NAS Devices", "table",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP"), ("serial_number.keyword", "Serial")],
    "nas"))

# === NVR RECORDERS ===
viz_list.append(("dcim-mon-nvr-h", "NVR Header", "markdown", "## 📹 NVR Recorders", None))
viz_list.append(("dcim-mon-nvr-count", "NVR Count", "metric", None, "nvr"))
viz_list.append(("dcim-mon-nvr-list", "NVR Devices", "table",
    [("hostname.keyword", "Hostname"), ("ip.keyword", "IP"), ("serial_number.keyword", "Serial")],
    "nvr"))

# Create all visualizations
success_count = 0
for viz_data in viz_list:
    if len(viz_data) == 5:
        viz_id, title, viz_type, field, device_filter = viz_data
        agg_type = "avg"
    else:
        viz_id, title, viz_type, field, device_filter, agg_type = viz_data
    
    if create_viz(viz_id, title, viz_type, field, device_filter, agg_type):
        success_count += 1

print(f"\n✅ Created {success_count}/{len(viz_list)} visualizations")

# Create dashboard
print("\n=== Creating Dashboard ===\n")

panels = [
    # Header
    {"id": "dcim-mon-header", "x": 0, "y": 0, "w": 48, "h": 3},
    
    # Global Overview
    {"id": "dcim-mon-total", "x": 0, "y": 3, "w": 12, "h": 6},
    {"id": "dcim-mon-devices", "x": 12, "y": 3, "w": 12, "h": 6},
    {"id": "dcim-mon-severity", "x": 24, "y": 3, "w": 12, "h": 6},
    {"id": "dcim-mon-enrichment", "x": 36, "y": 3, "w": 12, "h": 6},
    
    # Network Switches
    {"id": "dcim-mon-net-h", "x": 0, "y": 9, "w": 48, "h": 2},
    {"id": "dcim-mon-net-count", "x": 0, "y": 11, "w": 8, "h": 5},
    {"id": "dcim-mon-net-cpu-avg", "x": 8, "y": 11, "w": 8, "h": 5},
    {"id": "dcim-mon-net-mem-avg", "x": 16, "y": 11, "w": 8, "h": 5},
    {"id": "dcim-mon-net-cpu", "x": 0, "y": 16, "w": 24, "h": 8},
    {"id": "dcim-mon-net-mem", "x": 24, "y": 16, "w": 24, "h": 8},
    {"id": "dcim-mon-net-list", "x": 0, "y": 24, "w": 48, "h": 8},
    
    # Servers
    {"id": "dcim-mon-srv-h", "x": 0, "y": 32, "w": 48, "h": 2},
    {"id": "dcim-mon-srv-count", "x": 0, "y": 34, "w": 8, "h": 5},
    {"id": "dcim-mon-srv-temp-avg", "x": 8, "y": 34, "w": 8, "h": 5},
    {"id": "dcim-mon-srv-power-avg", "x": 16, "y": 34, "w": 8, "h": 5},
    {"id": "dcim-mon-srv-temp", "x": 0, "y": 39, "w": 16, "h": 8},
    {"id": "dcim-mon-srv-fan", "x": 16, "y": 39, "w": 16, "h": 8},
    {"id": "dcim-mon-srv-power", "x": 32, "y": 39, "w": 16, "h": 8},
    {"id": "dcim-mon-srv-list", "x": 0, "y": 47, "w": 48, "h": 8},
    
    # CCTV
    {"id": "dcim-mon-cctv-h", "x": 0, "y": 55, "w": 48, "h": 2},
    {"id": "dcim-mon-cctv-count", "x": 0, "y": 57, "w": 8, "h": 5},
    {"id": "dcim-mon-cctv-cpu-avg", "x": 8, "y": 57, "w": 8, "h": 5},
    {"id": "dcim-mon-cctv-mem-avg", "x": 16, "y": 57, "w": 8, "h": 5},
    {"id": "dcim-mon-cctv-status", "x": 24, "y": 57, "w": 12, "h": 10},
    {"id": "dcim-mon-cctv-cpu", "x": 0, "y": 62, "w": 24, "h": 8},
    {"id": "dcim-mon-cctv-mem", "x": 24, "y": 67, "w": 24, "h": 8},
    {"id": "dcim-mon-cctv-list", "x": 0, "y": 70, "w": 48, "h": 8},
    
    # UPS
    {"id": "dcim-mon-ups-h", "x": 0, "y": 78, "w": 48, "h": 2},
    {"id": "dcim-mon-ups-count", "x": 0, "y": 80, "w": 8, "h": 5},
    {"id": "dcim-mon-ups-battery", "x": 8, "y": 80, "w": 8, "h": 5},
    {"id": "dcim-mon-ups-load", "x": 16, "y": 80, "w": 8, "h": 5},
    {"id": "dcim-mon-ups-battery-time", "x": 0, "y": 85, "w": 24, "h": 8},
    {"id": "dcim-mon-ups-load-time", "x": 24, "y": 85, "w": 24, "h": 8},
    {"id": "dcim-mon-ups-list", "x": 0, "y": 93, "w": 48, "h": 8},
    
    # NAS
    {"id": "dcim-mon-nas-h", "x": 0, "y": 101, "w": 48, "h": 2},
    {"id": "dcim-mon-nas-count", "x": 0, "y": 103, "w": 12, "h": 5},
    {"id": "dcim-mon-nas-list", "x": 0, "y": 108, "w": 48, "h": 6},
    
    # NVR
    {"id": "dcim-mon-nvr-h", "x": 0, "y": 114, "w": 48, "h": 2},
    {"id": "dcim-mon-nvr-count", "x": 0, "y": 116, "w": 12, "h": 5},
    {"id": "dcim-mon-nvr-list", "x": 0, "y": 121, "w": 48, "h": 6},
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
    "title": "DCIM Infrastructure - Comprehensive Monitoring",
    "description": "Complete monitoring dashboard with performance metrics, CPU, memory, temperature, power, and device status",
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
    f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-monitoring?overwrite=true",
    headers=HEADERS,
    json={"attributes": dashboard_attrs, "references": references},
    auth=AUTH
)

if resp.status_code in (200, 201):
    print("✅ Dashboard created!")
    print(f"\n📊 URL: {KIBANA_URL}/app/dashboards#/view/dcim-monitoring")
    print(f"📊 Total panels: {len(panels)}")
    print("\n📈 Metrics included:")
    print("   • Network: CPU load, Memory usage")
    print("   • Servers: Temperature, Fan speed, Power consumption")
    print("   • CCTV: CPU usage, Memory usage, Status")
    print("   • UPS: Battery capacity, Output load, Power status")
    print("   • All devices: Count, Status, Details table")
else:
    print(f"❌ Failed: {resp.status_code}")
    print(resp.text[:500])

print("\n" + "=" * 70)
print("✅ COMPLETE")
print("=" * 70)
