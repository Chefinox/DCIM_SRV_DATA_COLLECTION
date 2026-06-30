import json

DATA_VIEW_ID = "2c1550f3-c9a5-410f-905c-43de003b1ca6"

def create_viz(viz_id, title, viz_type, params, aggs, filter_query=""):
    visState = {
        "title": title,
        "type": viz_type,
        "params": params,
        "aggs": aggs
    }
    
    return {
        "type": "visualization",
        "id": viz_id,
        "attributes": {
            "title": title,
            "visState": json.dumps(visState),
            "kibanaSavedObjectMeta": {
                "searchSource": {
                    "query": {"language": "kuery", "query": filter_query},
                    "filter": [],
                    "indexRefName": "kibanaSavedObjectMeta.searchSource.index"
                }
            }
        },
        "references": [
            {
                "name": "kibanaSavedObjectMeta.searchSource.index",
                "type": "data-view",
                "id": DATA_VIEW_ID
            }
        ]
    }

def create_metric(viz_id, title, field, agg_type="avg", filter_query=""):
    return create_viz(
        viz_id, title, "metric",
        {"addTooltip": True, "addLegend": False, "type": "metric", "metric": {"style": {"fontSize": 60}}},
        [{"id": "1", "enabled": True, "type": agg_type, "params": {"field": field} if field else {}, "schema": "metric"}],
        filter_query
    )

def create_line(viz_id, title, y_field, split_field=None, filter_query=""):
    aggs = [
        {"id": "1", "enabled": True, "type": "avg", "params": {"field": y_field}, "schema": "metric"},
        {"id": "2", "enabled": True, "type": "date_histogram", "params": {"field": "@timestamp", "calendar_interval": "auto"}, "schema": "segment"}
    ]
    if split_field:
        aggs.append({"id": "3", "enabled": True, "type": "terms", "params": {"field": split_field, "size": 5}, "schema": "group"})
    
    return create_viz(
        viz_id, title, "line",
        {"addLegend": True, "legendPosition": "right", "type": "line", "drawLinesBetweenPoints": True, "showCircles": True},
        aggs,
        filter_query
    )

def create_table(viz_id, title, split_field, metric_field=None, metric_agg="count", filter_query=""):
    aggs = [{"id": "1", "enabled": True, "type": metric_agg, "params": {"field": metric_field} if metric_field else {}, "schema": "metric"}]
    aggs.append({"id": "2", "enabled": True, "type": "terms", "params": {"field": split_field, "size": 20}, "schema": "bucket"})
    
    return create_viz(
        viz_id, title, "table",
        {"perPage": 10, "showPartialRows": False, "showMetricsAtAllLevels": False},
        aggs,
        filter_query
    )

visualizations = [
    # Global Summary
    create_metric("viz-alert-severity", "Alert Severity", "severity.keyword", "terms"),
    create_table("viz-devices-by-site", "Devices by Site", "site.keyword", filter_query="site : *"),
    
    # Network
    create_metric("viz-net-status", "Interface Status (Up/Down)", "raw_fields.if_oper_status", "avg", 'device_type: "network_switch"'),
    create_table("viz-net-traffic", "Top Interfaces by Traffic", "raw_tags.hostname.keyword", "raw_fields.if_in_octets", "sum", 'device_type: "network_switch"'),
    create_line("viz-net-errors", "Interface Errors Over Time", "raw_fields.if_in_errors", "raw_tags.hostname.keyword", 'device_type: "network_switch"'),
    
    # UPS
    create_metric("viz-ups-battery", "Battery Capacity (%)", "raw_fields.upsBatteryCapacity", "avg", 'device_type: "ups"'),
    create_metric("viz-ups-load", "Output Load (%)", "raw_fields.upsOutputLoad", "avg", 'device_type: "ups"'),
    create_metric("viz-ups-voltage", "Input Voltage (V)", "raw_fields.upsInputVoltage", "avg", 'device_type: "ups"'),
    create_metric("viz-ups-runtime", "Runtime Remaining", "raw_fields.upsEstimatedMinutesRemaining", "avg", 'device_type: "ups"'),
    create_table("viz-ups-summary", "UPS Status Summary", "hostname.keyword", filter_query='device_type: "ups"'),
    
    # NAS / Storage
    create_metric("viz-nas-temp", "Disk Temperature (°C)", "raw_fields.diskTemp", "avg", 'device_type: "nas"'),
    create_metric("viz-nas-status", "Disk Status", "raw_fields.diskStatus", "avg", 'device_type: "nas"'),
    create_table("viz-nas-table", "NAS Disk Status Table", "raw_tags.hostname.keyword", filter_query='device_type: "nas"'),
    
    # Server
    create_metric("viz-server-temp", "Server Temperature (°C)", "metric_value", "avg", 'device_type: "server" and measurement: "Temperature"'),
    create_metric("viz-server-power", "Server Power (W)", "metric_value", "avg", 'device_type: "server" and measurement: "Power"'),
    create_table("viz-server-health", "Server Health Status", "hostname.keyword", filter_query='device_type: "server"'),
    
    # CCTV / Security
    create_metric("viz-cctv-status", "CCTV/NVR Online Status", "metric_value", "avg", 'device_type: "cctv"'),
    create_table("viz-cctv-detail", "Camera & NVR Detail", "hostname.keyword", filter_query='device_type: "cctv" or device_type: "nvr"'),
]

# Create Dashboard
panels = []
x, y = 0, 0
for i, viz in enumerate(visualizations):
    panels.append({
        "version": "8.11.0",
        "type": "visualization",
        "gridData": {"x": x, "y": y, "w": 16, "h": 12},
        "panelIndex": f"panel_{i}",
        "panelRefName": f"ref_{i}"
    })
    x += 16
    if x >= 48:
        x = 0
        y += 12

dashboard = {
    "type": "dashboard",
    "id": "dcim-unified-ops-center-detailed",
    "attributes": {
        "title": "DCIM Unified Ops Center (Detailed)",
        "description": "Comprehensive monitoring for Server, UPS, NAS, Network, and Security.",
        "panelsJSON": json.dumps(panels),
        "optionsJSON": json.dumps({"useMargins": True, "hidePanelTitles": False}),
        "timeRestore": False,
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"language": "kuery", "query": ""}, "filter": []})
        }
    },
    "references": [{"name": f"ref_{i}", "type": "visualization", "id": viz["id"]} for i, viz in enumerate(visualizations)]
}

# Output to NDJSON
with open("/home/infra/dcim_metrics_project/phase2/dcim_detailed_dashboard.ndjson", "w") as f:
    for viz in visualizations:
        f.write(json.dumps(viz) + "\n")
    f.write(json.dumps(dashboard) + "\n")

print("Generated /home/infra/dcim_metrics_project/phase2/dcim_detailed_dashboard.ndjson")
