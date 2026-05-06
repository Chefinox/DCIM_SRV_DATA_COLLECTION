#!/usr/bin/env python3
"""
Create DCIM Infrastructure Monitoring Dashboard in Kibana.
Uses Kibana Saved Objects API to create all panels programmatically.
"""
import json
import sys
import requests

KIBANA_URL = "http://10.70.0.56:5601"
INDEX_PATTERN_ID = "dcim-enriched-main"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}

def F(field: str) -> str:
    """
    Translasi otomatis nama field dari prompt ke struktur ElasticSearch aktual.
    Karena field teks sekarang didaftarkan di tag_keys, mereka dipetakan ke tag.*
    """
    mapping = {
        "@timestamp": "@timestamp",
        "event_time": "@timestamp",
        "device_type": "tag.device_type",
        "hostname": "tag.hostname",
        "ip": "tag.ip",
        "serial_number": "tag.serial_number",
        "site": "tag.site",
        "rack_name": "tag.rack_name",
        "rack_position": "kafka_consumer.rack_position",
        "model": "tag.model",
        "enrichment_status": "tag.enrichment_status",
        "severity": "tag.severity",
        "metric_name": "tag.metric_name",
        "metric_value": "kafka_consumer.metric_value",
        
        # Network Switch
        "net_if_oper_status": "kafka_consumer.raw_fields_ifOperStatus",
        "net_if_in_octets": "kafka_consumer.raw_fields_ifInOctets",
        "net_if_out_octets": "kafka_consumer.raw_fields_ifOutOctets",
        "net_if_in_errors": "kafka_consumer.raw_fields_ifInErrors",
        "net_if_name": "kafka_consumer.raw_fields_ifDescr.keyword",
        
        # UPS
        "ups_battery_capacity": "kafka_consumer.raw_fields_upsBatteryCapacity",
        "ups_output_load": "kafka_consumer.raw_fields_upsOutputLoad",
        "ups_input_voltage": "kafka_consumer.raw_fields_upsInputVoltage",
        "ups_output_voltage": "kafka_consumer.raw_fields_upsOutputVoltage",
        "ups_battery_runtime_sec": "kafka_consumer.raw_fields_upsBatteryRuntime",
        
        # NAS
        "nas_disk_id": "kafka_consumer.raw_fields_diskID.keyword",
        "nas_disk_status": "kafka_consumer.raw_fields_disk_status",
        "nas_disk_temp": "kafka_consumer.raw_fields_disk_temp",
        "nas_system_temp": "kafka_consumer.raw_fields_system_temp",
        
        # Server
        "srv_reading_celsius": "kafka_consumer.raw_fields_reading_celsius",
        "srv_power_watts": "kafka_consumer.raw_fields_power_input_watts",
        "srv_health": "tag.health", # String field -> tag
        "srv_state": "tag.state",   # String field -> tag
        
        # CCTV / NVR
        "cctv_status_online": "kafka_consumer.metric_value",
        "cctv_status_text": "kafka_consumer.raw_fields_status_text.keyword"
    }
    return mapping.get(field, field)

def save_object(obj_type: str, obj_id: str, attributes: dict) -> str:
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
            "kibanaSavedObjectMeta": {
                "searchSourceJSON": json.dumps(searchSource)
            }
        }
        references = [{"name": "kibanaSavedObjectMeta.searchSourceJSON.index", "type": "index-pattern", "id": attributes.get("index", INDEX_PATTERN_ID)}]
        payload = {"attributes": final_attrs, "references": references}
    else:
        payload = {"attributes": attributes}

    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/{obj_type}/{obj_id}?overwrite=true",
        headers=HEADERS,
        json=payload,
        auth=("elastic", "C+H+pFb*aIAqWcOo-X8q")
    )
    if resp.status_code not in (200, 201):
        print(f"ERROR saving {obj_type}/{obj_id}: {resp.status_code} {resp.text[:200]}")
        return None
    print(f"  ✅ Saved {obj_type}: {obj_id}")
    return obj_id

def make_metric_panel(panel_id, title, field, agg="max", device_filter=None, color_ranges=None):
    filters = []
    if device_filter:
        filters.append({
            "meta": {"index": INDEX_PATTERN_ID, "key": F("device_type"), "negate": False},
            "query": {"match_phrase": {F("device_type"): device_filter}}
        })
    attrs = {
        "title": title,
        "type": "metric",
        "params": {
            "addTooltip": True, "addLegend": False, "type": "metric",
            "metric": {
                "percentageMode": False, "useRanges": color_ranges is not None,
                "colorSchema": "Traffic light", "metricColorMode": "Labels",
                "colorsRange": color_ranges or [{"from":0,"to":50,"color":"#D32F2F"}, {"from":50,"to":80,"color":"#F57F17"}, {"from":80,"to":100,"color":"#388E3C"}],
                "labels": {"show": True}, "invertColors": False,
                "style": {"bgFill": "#000", "bgColor": False, "labelColor": False, "subText": "", "fontSize": 60}
            }
        },
        "aggs": [{"id": "1", "enabled": True, "type": agg, "schema": "metric", "params": {"field": field, "customLabel": title}}],
        "filters": filters,
        "index": INDEX_PATTERN_ID
    }
    return save_object("visualization", panel_id, attrs)

def make_data_table(panel_id, title, columns, device_filter=None, size=20):
    filters = []
    if device_filter:
        if isinstance(device_filter, list):
            query = {"bool": {"should": [{"match_phrase": {F("device_type"): df}} for df in device_filter], "minimum_should_match": 1}}
            filters.append({"meta": {"index": INDEX_PATTERN_ID, "alias": "Device Filter"}, "query": query})
        else:
            filters.append({
                "meta": {"index": INDEX_PATTERN_ID, "key": F("device_type"), "negate": False},
                "query": {"match_phrase": {F("device_type"): device_filter}}
            })
    aggs = [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": "Count"}}]
    for i, (col_field, col_label) in enumerate(columns, start=2):
        aggs.append({
            "id": str(i), "enabled": True, "type": "terms", "schema": "bucket",
            "params": {"field": col_field, "size": size, "order": "desc", "orderBy": "1", "customLabel": col_label}
        })
    attrs = {
        "title": title, "type": "table",
        "params": {"perPage": 25, "showPartialRows": False, "showMetricsAtAllLevels": False, "showTotal": False, "totalFunc": "sum", "sort": {"columnIndex": None, "direction": None}},
        "aggs": aggs, "filters": filters, "index": INDEX_PATTERN_ID
    }
    return save_object("visualization", panel_id, attrs)

def make_donut_chart(panel_id, title, split_field, device_filter=None, size=10):
    filters = []
    if device_filter:
        if isinstance(device_filter, list):
            query = {"bool": {"should": [{"match_phrase": {F("device_type"): df}} for df in device_filter], "minimum_should_match": 1}}
            filters.append({"meta": {"index": INDEX_PATTERN_ID}, "query": query})
        else:
            filters.append({"meta": {"index": INDEX_PATTERN_ID, "key": F("device_type"), "negate": False}, "query": {"match_phrase": {F("device_type"): device_filter}}})
    attrs = {
        "title": title, "type": "pie",
        "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True, "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}},
        "aggs": [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": "Count"}}, {"id": "2", "enabled": True, "type": "terms", "schema": "segment", "params": {"field": split_field, "size": size, "order": "desc", "orderBy": "1", "customLabel": split_field}}],
        "filters": filters, "index": INDEX_PATTERN_ID
    }
    return save_object("visualization", panel_id, attrs)

def make_line_chart(panel_id, title, metric_field, split_field=None, device_filter=None, interval="auto"):
    filters = []
    if device_filter:
        filters.append({"meta": {"index": INDEX_PATTERN_ID, "key": F("device_type"), "negate": False}, "query": {"match_phrase": {F("device_type"): device_filter}}})
    aggs = [{"id": "1", "enabled": True, "type": "max", "schema": "metric", "params": {"field": metric_field, "customLabel": title}}, {"id": "2", "enabled": True, "type": "date_histogram", "schema": "segment", "params": {"field": "@timestamp", "interval": interval, "min_doc_count": 1, "extended_bounds": {}}}]
    if split_field:
        aggs.append({"id": "3", "enabled": True, "type": "terms", "schema": "group", "params": {"field": split_field, "size": 10, "order": "desc", "orderBy": "1"}})
    attrs = {
        "title": title, "type": "line",
        "params": {"type": "line", "grid": {"categoryLines": False}, "categoryAxes": [{"id": "CategoryAxis-1", "type": "category", "position": "bottom", "show": True, "style": {}, "scale": {"type": "linear"}, "labels": {"show": True, "filter": True, "truncate": 100}, "title": {}}], "valueAxes": [{"id": "ValueAxis-1", "name": "LeftAxis-1", "type": "value", "position": "left", "show": True, "style": {}, "scale": {"type": "linear", "mode": "normal"}, "labels": {"show": True, "rotate": 0, "filter": False, "truncate": 100}, "title": {"text": title}}], "seriesParams": [{"show": True, "type": "line", "mode": "normal", "data": {"label": title, "id": "1"}, "valueAxis": "ValueAxis-1", "drawLinesBetweenPoints": True, "showCircles": True, "interpolate": "linear"}], "addTooltip": True, "addLegend": True, "legendPosition": "right", "times": [], "addTimeMarker": False},
        "aggs": aggs, "filters": filters, "index": INDEX_PATTERN_ID
    }
    return save_object("visualization", panel_id, attrs)

def make_bar_chart(panel_id, title, metric_field, bucket_field, device_filter=None, horizontal=False, size=10):
    filters = []
    if device_filter:
        filters.append({"meta": {"index": INDEX_PATTERN_ID, "key": F("device_type"), "negate": False}, "query": {"match_phrase": {F("device_type"): device_filter}}})
    chart_type = "horizontal_bar" if horizontal else "histogram"
    attrs = {
        "title": title, "type": chart_type,
        "params": {"type": chart_type, "grid": {"categoryLines": False}, "addTooltip": True, "addLegend": True, "legendPosition": "right", "times": [], "addTimeMarker": False},
        "aggs": [{"id": "1", "enabled": True, "type": "max", "schema": "metric", "params": {"field": metric_field, "customLabel": title}}, {"id": "2", "enabled": True, "type": "terms", "schema": "segment", "params": {"field": bucket_field, "size": size, "order": "desc", "orderBy": "1"}}],
        "filters": filters, "index": INDEX_PATTERN_ID
    }
    return save_object("visualization", panel_id, attrs)

def make_markdown_panel(panel_id, title, markdown_text):
    return save_object("visualization", panel_id, {"title": title, "type": "markdown", "params": {"fontSize": 14, "openLinksInNewTab": False, "markdown": markdown_text}})

def create_all_visualizations():
    print("\n=== Creating Visualizations ===\n")
    panels = {}
    panels["header"] = make_markdown_panel("dcim-header", "Dashboard Header", "# 🖥️ DCIM Infrastructure Monitoring\n**Pipeline**: Unified Metric Stream → Elasticsearch\n| Auto-refresh: 30s | Index: dcim-metrics-unified-* |")
    panels["p1_device_count"] = save_object("visualization", "dcim-p1-device-count", {"title": "Total Devices by Type", "type": "pie", "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", "isDonut": True, "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}}, "aggs": [{"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": "Devices"}}, {"id": "2", "enabled": True, "type": "terms", "schema": "segment", "params": {"field": F("device_type"), "size": 10, "order": "desc", "orderBy": "1", "customLabel": "Device Type"}}], "index": INDEX_PATTERN_ID})
    panels["p2_enrichment"] = make_donut_chart("dcim-p2-enrichment", "Enrichment Status", F("enrichment_status"), size=5)
    panels["p3_last_ingest"] = save_object("visualization", "dcim-p3-last-ingest", {"title": "Pipeline Last Ingest", "type": "timelion", "params": {"expression": ".es(index='dcim-metrics-unified-*').label('Last Ingest')", "interval": "auto"}, "aggs": [], "index": INDEX_PATTERN_ID})
    panels["p4_severity"] = make_donut_chart("dcim-p4-severity", "Alert Severity", F("severity"), size=5)
    
    panels["net_header"] = make_markdown_panel("dcim-net-header", "Network Section Header", "## 🔌 Network Switch\nMikroTik SNMP metrics")
    panels["p5_if_status"] = make_donut_chart("dcim-p5-if-status", "Interface Status (Up/Down)", F("net_if_oper_status"), device_filter="network_switch")
    panels["p6_traffic"] = make_bar_chart("dcim-p6-traffic", "Top Interfaces by Inbound Traffic", F("net_if_in_octets"), F("net_if_name"), device_filter="network_switch", horizontal=True, size=15)
    panels["p7_errors"] = make_line_chart("dcim-p7-errors", "Interface Errors Over Time", F("net_if_in_errors"), split_field=F("hostname"), device_filter="network_switch")
    panels["p8_net_table"] = make_data_table("dcim-p8-net-table", "Network Device Status", [(F("hostname"), "Hostname"), (F("model"), "Model"), (F("site"), "Site"), (F("rack_name"), "Rack"), (F("enrichment_status"), "Enrich Status")], device_filter="network_switch")
    
    panels["ups_header"] = make_markdown_panel("dcim-ups-header", "UPS Section Header", "## ⚡ UPS\nPower & Battery metrics")
    panels["p9_battery"] = make_line_chart("dcim-p9-battery", "Battery Capacity (%)", F("ups_battery_capacity"), split_field=F("hostname"), device_filter="ups")
    panels["p10_load"] = make_line_chart("dcim-p10-load", "Output Load (%)", F("ups_output_load"), split_field=F("hostname"), device_filter="ups")
    panels["p11_voltage"] = make_line_chart("dcim-p11-voltage", "Input Voltage (V)", F("ups_input_voltage"), split_field=F("hostname"), device_filter="ups")
    panels["p12_runtime"] = make_metric_panel("dcim-p12-runtime", "Runtime Remaining", F("ups_battery_runtime_sec"), color_ranges=[{"from": 0, "to": 300, "color": "#D32F2F"}, {"from": 300, "to": 600, "color": "#F57F17"}, {"from": 600, "to": 99999, "color": "#388E3C"}])
    panels["p13_ups_table"] = make_data_table("dcim-p13-ups-table", "UPS Status Summary", [(F("hostname"), "UPS Name"), (F("ups_battery_capacity"), "Battery %"), (F("ups_output_load"), "Load %"), (F("ups_input_voltage"), "Input V"), (F("ups_output_voltage"), "Output V"), (F("site"), "Site")], device_filter="ups")
    
    panels["nas_header"] = make_markdown_panel("dcim-nas-header", "NAS Section Header", "## 💾 NAS Storage\nDisk health & temp")
    panels["p14_disk_temp"] = make_line_chart("dcim-p14-disk-temp", "Disk Temperature (°C)", F("nas_disk_temp"), split_field=F("nas_disk_id"), device_filter="nas")
    panels["p15_disk_status"] = make_donut_chart("dcim-p15-disk-status", "Disk Status", F("nas_disk_status"), device_filter="nas")
    panels["p16_nas_table"] = make_data_table("dcim-p16-nas-table", "NAS Disk Status Table", [(F("hostname"), "NAS Device"), (F("nas_disk_id"), "Disk ID"), (F("nas_disk_status"), "Status"), (F("nas_disk_temp"), "Temp °C"), (F("nas_system_temp"), "System Temp °C")], device_filter="nas")
    
    panels["srv_header"] = make_markdown_panel("dcim-srv-header", "Server Section Header", "## 🖥️ Servers\nRedfish metrics")
    panels["p17_srv_temp"] = make_line_chart("dcim-p17-srv-temp", "Server Temperature (°C)", F("srv_reading_celsius"), split_field=F("hostname"), device_filter="server")
    panels["p18_srv_power"] = make_bar_chart("dcim-p18-srv-power", "Server Power (W)", F("srv_power_watts"), F("hostname"), device_filter="server", horizontal=True)
    panels["p19_srv_table"] = make_data_table("dcim-p19-srv-table", "Server Health Status", [(F("hostname"), "Server"), (F("srv_health"), "Health"), (F("srv_state"), "State"), (F("srv_reading_celsius"), "Temp °C"), (F("srv_power_watts"), "Power W")], device_filter="server")
    
    panels["cctv_header"] = make_markdown_panel("dcim-cctv-header", "CCTV Section Header", "## 📷 CCTV & NVR\nSecurity feeds monitoring")
    panels["p20_cctv_status"] = make_donut_chart("dcim-p20-cctv-status", "CCTV/NVR Online Status", F("cctv_status_text"), device_filter=["cctv", "nvr"])
    panels["p21_cctv_table"] = make_data_table("dcim-p21-cctv-table", "Camera & NVR Detail", [(F("hostname"), "Device Name"), (F("ip"), "IP"), (F("cctv_status_text"), "Status"), (F("site"), "Site"), (F("rack_name"), "Location")], device_filter=["cctv", "nvr"])
    
    panels["inv_header"] = make_markdown_panel("dcim-inv-header", "Inventory Section Header", "## 📋 Asset Inventory\nData Quality")
    panels["p22_by_site"] = make_bar_chart("dcim-p22-by-site", "Devices by Site", F("device_type"), F("site"), horizontal=False)
    panels["p23_enrich_quality"] = make_data_table("dcim-p23-enrich-quality", "Enrichment Quality", [(F("device_type"), "Type"), (F("enrichment_status"), "Status"), (F("site"), "Site")])
    return panels

def create_dashboard(panels: dict):
    print("\n=== Creating Dashboard ===\n")
    # All X and W doubled from original (24 cols to 48 cols layout)
    panel_layout = [
        {"id": "dcim-header",          "x": 0,  "y": 0,   "w": 48, "h": 2},
        {"id": "dcim-p1-device-count", "x": 0,  "y": 2,   "w": 12, "h": 8},
        {"id": "dcim-p2-enrichment",   "x": 12, "y": 2,   "w": 12, "h": 8},
        {"id": "dcim-p3-last-ingest",  "x": 24, "y": 2,   "w": 12, "h": 8},
        {"id": "dcim-p4-severity",     "x": 36, "y": 2,   "w": 12, "h": 8},
        
        {"id": "dcim-net-header",      "x": 0,  "y": 10,  "w": 48, "h": 2},
        {"id": "dcim-p5-if-status",    "x": 0,  "y": 12,  "w": 16, "h": 10},
        {"id": "dcim-p6-traffic",      "x": 16, "y": 12,  "w": 32, "h": 10},
        {"id": "dcim-p7-errors",       "x": 0,  "y": 22,  "w": 24, "h": 8},
        {"id": "dcim-p8-net-table",    "x": 24, "y": 22,  "w": 24, "h": 8},
        
        {"id": "dcim-ups-header",      "x": 0,  "y": 30,  "w": 48, "h": 2},
        {"id": "dcim-p9-battery",      "x": 0,  "y": 32,  "w": 16, "h": 8},
        {"id": "dcim-p10-load",        "x": 16, "y": 32,  "w": 16, "h": 8},
        {"id": "dcim-p11-voltage",     "x": 32, "y": 32,  "w": 16, "h": 8},
        {"id": "dcim-p12-runtime",     "x": 0,  "y": 40,  "w": 16, "h": 6},
        {"id": "dcim-p13-ups-table",   "x": 16, "y": 40,  "w": 32, "h": 6},
        
        {"id": "dcim-nas-header",      "x": 0,  "y": 46,  "w": 48, "h": 2},
        {"id": "dcim-p14-disk-temp",   "x": 0,  "y": 48,  "w": 28, "h": 8},
        {"id": "dcim-p15-disk-status", "x": 28, "y": 48,  "w": 20, "h": 8},
        {"id": "dcim-p16-nas-table",   "x": 0,  "y": 56,  "w": 48, "h": 8},
        
        {"id": "dcim-srv-header",      "x": 0,  "y": 64,  "w": 48, "h": 2},
        {"id": "dcim-p17-srv-temp",    "x": 0,  "y": 66,  "w": 28, "h": 8},
        {"id": "dcim-p18-srv-power",   "x": 28, "y": 66,  "w": 20, "h": 8},
        {"id": "dcim-p19-srv-table",   "x": 0,  "y": 74,  "w": 48, "h": 8},
        
        {"id": "dcim-cctv-header",     "x": 0,  "y": 82,  "w": 48, "h": 2},
        {"id": "dcim-p20-cctv-status", "x": 0,  "y": 84,  "w": 16, "h": 8},
        {"id": "dcim-p21-cctv-table",  "x": 16, "y": 84,  "w": 32, "h": 8},
        
        {"id": "dcim-inv-header",      "x": 0,  "y": 92,  "w": 48, "h": 2},
        {"id": "dcim-p22-by-site",     "x": 0,  "y": 94,  "w": 28, "h": 8},
        {"id": "dcim-p23-enrich-quality","x": 28,"y": 94, "w": 20, "h": 8},
    ]

    dashboard_panels = []
    references = []
    for i, p in enumerate(panel_layout):
        dashboard_panels.append({"version": "8.0.0", "type": "visualization", "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": str(i + 1)}, "panelIndex": str(i + 1), "embeddableConfig": {}, "panelRefName": f"panel_{i + 1}"})
        references.append({"name": f"panel_{i + 1}", "type": "visualization", "id": p["id"]})

    dashboard_attrs = {"title": "DCIM Infrastructure — Operational Overview", "description": "Auto-refresh: 30s", "panelsJSON": json.dumps(dashboard_panels), "optionsJSON": json.dumps({"useMargins": True, "syncColors": True, "hidePanelTitles": False}), "timeRestore": True, "timeTo": "now", "timeFrom": "now-1h", "refreshInterval": {"pause": False, "value": 30000}, "kibanaSavedObjectMeta": {"searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})}}

    resp = requests.post(f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-main-dashboard?overwrite=true", headers=HEADERS, json={"attributes": dashboard_attrs, "references": references}, auth=("elastic", "C+H+pFb*aIAqWcOo-X8q"))
    if resp.status_code in (200, 201):
        print("✅ Dashboard created successfully!")
        print(f"   URL: {KIBANA_URL}/app/dashboards#/view/dcim-main-dashboard")
    else:
        print(f"❌ Dashboard creation failed: {resp.status_code}\n{resp.text[:500]}")

if __name__ == "__main__":
    resp = requests.get(f"{KIBANA_URL}/api/status", headers=HEADERS, auth=("elastic", "C+H+pFb*aIAqWcOo-X8q"))
    if resp.status_code != 200:
        print(f"❌ Cannot connect to Kibana: {resp.status_code}")
        sys.exit(1)
    
    # 1. Pastikan Index Pattern Ada
    requests.post(f"{KIBANA_URL}/api/saved_objects/index-pattern/dcim-enriched-main?overwrite=true", headers=HEADERS, json={"attributes": {"title": "dcim-metrics-unified-*", "timeFieldName": "@timestamp"}}, auth=("elastic", "C+H+pFb*aIAqWcOo-X8q"))
    
    panels = create_all_visualizations()
    create_dashboard(panels)
