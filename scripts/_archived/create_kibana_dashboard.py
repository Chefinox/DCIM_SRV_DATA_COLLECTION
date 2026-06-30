#!/usr/bin/env python3
"""
Create DCIM Infrastructure Monitoring Dashboard in Kibana.
Comprehensive dashboard covering ALL device categories with detailed metrics.
Uses Kibana Saved Objects API to create all panels programmatically.
"""
import json
import sys
import requests

KIBANA_URL = "http://10.70.0.56:5601"
INDEX_PATTERN_ID = "dcim-enriched-main"
HEADERS = {"kbn-xsrf": "true", "Content-Type": "application/json"}
ELASTIC_AUTH = ("elastic", "C+H+pFb*aIAqWcOo-X8q")

def F(field: str) -> str:
    """
    Translasi otomatis nama field dari prompt ke struktur ElasticSearch aktual.
    Data structure: flat fields at root level
    """
    mapping = {
        "@timestamp": "@timestamp",
        "event_time": "event_time",
        "device_type": "device_type",
        "hostname": "hostname",
        "ip": "ip",
        "serial_number": "serial_number",
        "site": "site",
        "rack_name": "rack_name",
        "rack_position": "rack_position",
        "model": "model",
        "enrichment_status": "enrichment_status",
        "severity": "severity",
        "metric_name": "metric_name",
        "metric_value": "metric_value",
        
        # Network Switch (Mikrotik) - from raw_fields
        "net_if_oper_status": "raw_fields.ifOperStatus",
        "net_if_in_octets": "raw_fields.ifInOctets",
        "net_if_out_octets": "raw_fields.ifOutOctets",
        "net_if_in_errors": "raw_fields.ifInErrors",
        "net_if_out_errors": "raw_fields.ifOutErrors",
        "net_if_name": "raw_fields.ifDescr.keyword",
        "net_cpu_load": "metric_value",
        "net_memory_used": "raw_fields.memory_used",
        
        # UPS - from raw_fields
        "ups_battery_capacity": "metric_value",
        "ups_output_load": "raw_fields.output_load",
        "ups_input_voltage": "raw_fields.input_voltage",
        "ups_output_voltage": "raw_fields.output_voltage",
        "ups_battery_runtime_sec": "raw_fields.battery_runtime_sec",
        "ups_battery_temp": "raw_fields.battery_temperature",
        "ups_input_frequency": "raw_fields.input_frequency",
        "ups_output_current": "raw_fields.output_current",
        
        # NAS - from raw_fields
        "nas_disk_id": "raw_fields.diskID.keyword",
        "nas_disk_status": "raw_fields.diskStatus",
        "nas_disk_temp": "raw_fields.diskTemp",
        "nas_system_temp": "raw_fields.systemTemp",
        "nas_cpu_usage": "raw_fields.cpuUsage",
        "nas_memory_usage": "raw_fields.memoryUsage",
        "nas_volume_status": "raw_fields.volumeStatus",
        
        # Server (Redfish) - from raw_fields
        "srv_reading_celsius": "raw_fields.reading_celsius",
        "srv_power_watts": "raw_fields.power_input_watts",
        "srv_health": "raw_fields.health.keyword",
        "srv_state": "raw_fields.state.keyword",
        "srv_fan_speed": "raw_fields.reading_rpm",
        "srv_memory_health": "raw_fields.memory_health.keyword",
        "srv_storage_health": "raw_fields.storage_health.keyword",
        
        # CCTV / NVR - from raw_fields
        "cctv_status_online": "metric_value",
        "cctv_status_text": "raw_fields.status_text.keyword",
        "cctv_uptime": "raw_fields.deviceUpTime",
        "cctv_cpu_util": "raw_fields.cpuUtilization",
        "cctv_memory_usage": "raw_fields.memoryUsage",
        "cctv_firmware": "raw_fields.firmwareVersion.keyword",
        "cctv_bitrate": "raw_fields.outputBitrate",
        "cctv_resolution_width": "raw_fields.videoResolutionWidth",
        "cctv_hdd_capacity": "raw_fields.capacity",
        "cctv_hdd_free": "raw_fields.freeSpace",
        "cctv_hdd_status": "raw_fields.Status.keyword",
        
        # Environmental Sensors
        "env_temperature": "raw_fields.temperature",
        "env_humidity": "raw_fields.humidity",
        "env_sensor_status": "raw_fields.sensor_status.keyword",
        
        # PDU
        "pdu_current": "raw_fields.current_ampere",
        "pdu_voltage": "raw_fields.voltage",
        "pdu_power": "raw_fields.power_watts",
        "pdu_outlet_status": "raw_fields.outlet_status",
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
        auth=ELASTIC_AUTH
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
    """Create comprehensive visualizations for ALL device categories"""
    print("\n=== Creating Visualizations ===\n")
    panels = {}
    
    # ========== GLOBAL OVERVIEW ==========
    panels["header"] = make_markdown_panel("dcim-header", "Dashboard Header", 
        "# 🖥️ DCIM Infrastructure Monitoring\n**Pipeline**: Unified Metric Stream → Elasticsearch\n| Auto-refresh: 30s | Index: dcim-metrics-unified-* |")
    
    panels["p1_device_count"] = save_object("visualization", "dcim-p1-device-count", {
        "title": "Total Devices by Type", "type": "pie",
        "params": {"type": "pie", "addTooltip": True, "addLegend": True, "legendPosition": "right", 
                   "isDonut": True, "labels": {"show": True, "values": True, "last_level": True, "truncate": 100}},
        "aggs": [
            {"id": "1", "enabled": True, "type": "count", "schema": "metric", "params": {"customLabel": "Devices"}},
            {"id": "2", "enabled": True, "type": "terms", "schema": "segment", 
             "params": {"field": F("device_type"), "size": 15, "order": "desc", "orderBy": "1", "customLabel": "Device Type"}}
        ],
        "index": INDEX_PATTERN_ID
    })
    
    panels["p2_enrichment"] = make_donut_chart("dcim-p2-enrichment", "Enrichment Status", F("enrichment_status"), size=5)
    panels["p3_severity"] = make_donut_chart("dcim-p3-severity", "Alert Severity Distribution", F("severity"), size=5)
    panels["p4_site_overview"] = make_donut_chart("dcim-p4-site-overview", "Devices by Site", F("site"), size=10)
    
    # Pipeline health metric - total events in last hour
    panels["p5_pipeline_health"] = make_metric_panel("dcim-p5-pipeline-health", "Events Last Hour", 
                                                      F("@timestamp"), agg="count",
                                                      color_ranges=[{"from": 0, "to": 100, "color": "#D32F2F"}, 
                                                                   {"from": 100, "to": 1000, "color": "#F57F17"}, 
                                                                   {"from": 1000, "to": 999999, "color": "#388E3C"}])
    
    # ========== NETWORK SWITCH SECTION ==========
    panels["net_header"] = make_markdown_panel("dcim-net-header", "Network Section Header", 
        "## 🔌 Network Switch (Mikrotik)\nSNMP metrics: interfaces, traffic, CPU, memory")
    
    panels["p5_if_status"] = make_donut_chart("dcim-p5-if-status", "Interface Status (Up/Down)", 
                                               F("net_if_oper_status"), device_filter="network_switch")
    panels["p6_traffic_in"] = make_bar_chart("dcim-p6-traffic-in", "Top Interfaces by Inbound Traffic (Octets)", 
                                              F("net_if_in_octets"), F("net_if_name"), 
                                              device_filter="network_switch", horizontal=True, size=15)
    panels["p7_traffic_out"] = make_bar_chart("dcim-p7-traffic-out", "Top Interfaces by Outbound Traffic (Octets)", 
                                               F("net_if_out_octets"), F("net_if_name"), 
                                               device_filter="network_switch", horizontal=True, size=15)
    panels["p8_errors"] = make_line_chart("dcim-p8-errors", "Interface Errors Over Time", 
                                          F("net_if_in_errors"), split_field=F("hostname"), 
                                          device_filter="network_switch")
    panels["p9_cpu_load"] = make_line_chart("dcim-p9-cpu-load", "Switch CPU Load (%)", 
                                            F("net_cpu_load"), split_field=F("hostname"), 
                                            device_filter="network_switch")
    panels["p10_net_table"] = make_data_table("dcim-p10-net-table", "Network Device Status", 
        [(F("hostname"), "Hostname"), (F("model"), "Model"), (F("site"), "Site"), 
         (F("rack_name"), "Rack"), (F("enrichment_status"), "Enrich Status")], 
        device_filter="network_switch")
    
    # ========== UPS SECTION ==========
    panels["ups_header"] = make_markdown_panel("dcim-ups-header", "UPS Section Header", 
        "## ⚡ UPS (Uninterruptible Power Supply)\nBattery, load, voltage, runtime monitoring")
    
    panels["p11_battery"] = make_line_chart("dcim-p11-battery", "Battery Capacity (%)", 
                                            F("ups_battery_capacity"), split_field=F("hostname"), 
                                            device_filter="ups")
    panels["p12_load"] = make_line_chart("dcim-p12-load", "Output Load (%)", 
                                         F("ups_output_load"), split_field=F("hostname"), 
                                         device_filter="ups")
    panels["p13_voltage_in"] = make_line_chart("dcim-p13-voltage-in", "Input Voltage (V)", 
                                               F("ups_input_voltage"), split_field=F("hostname"), 
                                               device_filter="ups")
    panels["p14_voltage_out"] = make_line_chart("dcim-p14-voltage-out", "Output Voltage (V)", 
                                                F("ups_output_voltage"), split_field=F("hostname"), 
                                                device_filter="ups")
    panels["p15_runtime"] = make_metric_panel("dcim-p15-runtime", "Runtime Remaining (sec)", 
                                              F("ups_battery_runtime_sec"), device_filter="ups",
                                              color_ranges=[{"from": 0, "to": 300, "color": "#D32F2F"}, 
                                                           {"from": 300, "to": 600, "color": "#F57F17"}, 
                                                           {"from": 600, "to": 99999, "color": "#388E3C"}])
    panels["p16_battery_temp"] = make_line_chart("dcim-p16-battery-temp", "Battery Temperature (°C)", 
                                                 F("ups_battery_temp"), split_field=F("hostname"), 
                                                 device_filter="ups")
    panels["p17_ups_table"] = make_data_table("dcim-p17-ups-table", "UPS Status Summary", 
        [(F("hostname"), "UPS Name"), (F("ups_battery_capacity"), "Battery %"), 
         (F("ups_output_load"), "Load %"), (F("ups_input_voltage"), "Input V"), 
         (F("ups_output_voltage"), "Output V"), (F("site"), "Site")], 
        device_filter="ups")
    
    # ========== NAS SECTION ==========
    panels["nas_header"] = make_markdown_panel("dcim-nas-header", "NAS Section Header", 
        "## 💾 NAS Storage\nDisk health, temperature, CPU, memory, volume status")
    
    panels["p18_disk_temp"] = make_line_chart("dcim-p18-disk-temp", "Disk Temperature (°C)", 
                                              F("nas_disk_temp"), split_field=F("nas_disk_id"), 
                                              device_filter="nas")
    panels["p19_disk_status"] = make_donut_chart("dcim-p19-disk-status", "Disk Status Distribution", 
                                                  F("nas_disk_status"), device_filter="nas")
    panels["p20_nas_cpu"] = make_line_chart("dcim-p20-nas-cpu", "NAS CPU Usage (%)", 
                                            F("nas_cpu_usage"), split_field=F("hostname"), 
                                            device_filter="nas")
    panels["p21_nas_memory"] = make_line_chart("dcim-p21-nas-memory", "NAS Memory Usage (%)", 
                                               F("nas_memory_usage"), split_field=F("hostname"), 
                                               device_filter="nas")
    panels["p22_nas_table"] = make_data_table("dcim-p22-nas-table", "NAS Disk Status Table", 
        [(F("hostname"), "NAS Device"), (F("nas_disk_id"), "Disk ID"), 
         (F("nas_disk_status"), "Status"), (F("nas_disk_temp"), "Temp °C"), 
         (F("nas_system_temp"), "System Temp °C")], 
        device_filter="nas")
    
    # ========== SERVER SECTION ==========
    panels["srv_header"] = make_markdown_panel("dcim-srv-header", "Server Section Header", 
        "## 🖥️ Servers (Redfish API)\nTemperature, power, health, fan speed, memory, storage")
    
    panels["p23_srv_temp"] = make_line_chart("dcim-p23-srv-temp", "Server Temperature (°C)", 
                                             F("srv_reading_celsius"), split_field=F("hostname"), 
                                             device_filter="server")
    panels["p24_srv_power"] = make_bar_chart("dcim-p24-srv-power", "Server Power Consumption (W)", 
                                             F("srv_power_watts"), F("hostname"), 
                                             device_filter="server", horizontal=True)
    panels["p25_srv_health"] = make_donut_chart("dcim-p25-srv-health", "Server Health Status", 
                                                F("srv_health"), device_filter="server")
    panels["p26_srv_state"] = make_donut_chart("dcim-p26-srv-state", "Server State", 
                                               F("srv_state"), device_filter="server")
    panels["p27_srv_fan"] = make_line_chart("dcim-p27-srv-fan", "Server Fan Speed (RPM)", 
                                            F("srv_fan_speed"), split_field=F("hostname"), 
                                            device_filter="server")
    panels["p28_srv_table"] = make_data_table("dcim-p28-srv-table", "Server Health Status", 
        [(F("hostname"), "Server"), (F("srv_health"), "Health"), (F("srv_state"), "State"), 
         (F("srv_reading_celsius"), "Temp °C"), (F("srv_power_watts"), "Power W")], 
        device_filter="server")
    
    # ========== CCTV & NVR SECTION ==========
    panels["cctv_header"] = make_markdown_panel("dcim-cctv-header", "CCTV Section Header", 
        "## 📷 CCTV & NVR (Security Cameras)\nOnline status, uptime, CPU, memory, HDD, bitrate, firmware")
    
    panels["p29_cctv_status"] = make_donut_chart("dcim-p29-cctv-status", "CCTV/NVR Online Status", 
                                                 F("cctv_status_text"), device_filter=["cctv", "nvr"])
    panels["p30_cctv_uptime"] = make_bar_chart("dcim-p30-cctv-uptime", "Camera Uptime (seconds)", 
                                               F("cctv_uptime"), F("hostname"), 
                                               device_filter="cctv", horizontal=True, size=20)
    panels["p31_cctv_cpu"] = make_line_chart("dcim-p31-cctv-cpu", "CCTV/NVR CPU Utilization (%)", 
                                             F("cctv_cpu_util"), split_field=F("hostname"), 
                                             device_filter=["cctv", "nvr"])
    panels["p32_cctv_memory"] = make_line_chart("dcim-p32-cctv-memory", "CCTV/NVR Memory Usage (%)", 
                                                F("cctv_memory_usage"), split_field=F("hostname"), 
                                                device_filter=["cctv", "nvr"])
    panels["p33_cctv_bitrate"] = make_bar_chart("dcim-p33-cctv-bitrate", "Camera Output Bitrate (kbps)", 
                                                F("cctv_bitrate"), F("hostname"), 
                                                device_filter="cctv", horizontal=True, size=20)
    panels["p34_cctv_hdd"] = make_donut_chart("dcim-p34-cctv-hdd", "NVR HDD Status", 
                                              F("cctv_hdd_status"), device_filter="nvr")
    panels["p35_cctv_firmware"] = make_data_table("dcim-p35-cctv-firmware", "CCTV/NVR Firmware Versions", 
        [(F("hostname"), "Device"), (F("model"), "Model"), (F("cctv_firmware"), "Firmware"), 
         (F("site"), "Site")], 
        device_filter=["cctv", "nvr"], size=30)
    panels["p36_cctv_table"] = make_data_table("dcim-p36-cctv-table", "Camera & NVR Detail", 
        [(F("hostname"), "Device Name"), (F("ip"), "IP"), (F("cctv_status_text"), "Status"), 
         (F("site"), "Site"), (F("rack_name"), "Location")], 
        device_filter=["cctv", "nvr"])
    
    # ========== ASSET INVENTORY SECTION ==========
    panels["inv_header"] = make_markdown_panel("dcim-inv-header", "Inventory Section Header", 
        "## 📋 Asset Inventory & Data Quality\nDevice distribution, enrichment quality, site breakdown")
    
    panels["p37_by_site"] = make_bar_chart("dcim-p37-by-site", "Devices by Site", 
                                           F("device_type"), F("site"), horizontal=False)
    panels["p38_by_rack"] = make_data_table("dcim-p38-by-rack", "Devices by Rack", 
        [(F("site"), "Site"), (F("rack_name"), "Rack"), (F("device_type"), "Type")], size=30)
    panels["p39_enrich_quality"] = make_data_table("dcim-p39-enrich-quality", "Enrichment Quality", 
        [(F("device_type"), "Type"), (F("enrichment_status"), "Status"), (F("site"), "Site")])
    panels["p40_model_dist"] = make_data_table("dcim-p40-model-dist", "Device Model Distribution", 
        [(F("device_type"), "Type"), (F("model"), "Model")], size=50)
    
    return panels

def create_dashboard(panels: dict):
    """Create comprehensive dashboard with all device categories"""
    print("\n=== Creating Dashboard ===\n")
    
    # Layout using 48-column grid (doubled from standard 24)
    panel_layout = [
        # Global Overview Section
        {"id": "dcim-header",          "x": 0,  "y": 0,   "w": 48, "h": 2},
        {"id": "dcim-p1-device-count", "x": 0,  "y": 2,   "w": 12, "h": 10},
        {"id": "dcim-p2-enrichment",   "x": 12, "y": 2,   "w": 12, "h": 10},
        {"id": "dcim-p3-severity",     "x": 24, "y": 2,   "w": 12, "h": 10},
        {"id": "dcim-p4-site-overview","x": 36, "y": 2,   "w": 12, "h": 10},
        {"id": "dcim-p5-pipeline-health","x": 0,"y": 12,  "w": 12, "h": 6},
        {"id": "dcim-p5-pipeline-health","x": 0,"y": 12,  "w": 12, "h": 6},
        
        # Network Switch Section
        {"id": "dcim-net-header",      "x": 0,  "y": 18,  "w": 48, "h": 2},
        {"id": "dcim-p5-if-status",    "x": 0,  "y": 20,  "w": 12, "h": 10},
        {"id": "dcim-p6-traffic-in",   "x": 12, "y": 20,  "w": 18, "h": 10},
        {"id": "dcim-p7-traffic-out",  "x": 30, "y": 20,  "w": 18, "h": 10},
        {"id": "dcim-p8-errors",       "x": 0,  "y": 30,  "w": 24, "h": 8},
        {"id": "dcim-p9-cpu-load",     "x": 24, "y": 30,  "w": 24, "h": 8},
        {"id": "dcim-p10-net-table",   "x": 0,  "y": 38,  "w": 48, "h": 8},
        {"id": "dcim-p10-net-table",   "x": 0,  "y": 38,  "w": 48, "h": 8},
        
        # UPS Section
        {"id": "dcim-ups-header",      "x": 0,  "y": 46,  "w": 48, "h": 2},
        {"id": "dcim-p11-battery",     "x": 0,  "y": 48,  "w": 16, "h": 8},
        {"id": "dcim-p12-load",        "x": 16, "y": 48,  "w": 16, "h": 8},
        {"id": "dcim-p13-voltage-in",  "x": 32, "y": 48,  "w": 16, "h": 8},
        {"id": "dcim-p14-voltage-out", "x": 0,  "y": 56,  "w": 16, "h": 8},
        {"id": "dcim-p15-runtime",     "x": 16, "y": 56,  "w": 16, "h": 8},
        {"id": "dcim-p16-battery-temp","x": 32, "y": 56,  "w": 16, "h": 8},
        {"id": "dcim-p17-ups-table",   "x": 0,  "y": 64,  "w": 48, "h": 8},
        {"id": "dcim-p17-ups-table",   "x": 0,  "y": 64,  "w": 48, "h": 8},
        
        # NAS Section
        {"id": "dcim-nas-header",      "x": 0,  "y": 72,  "w": 48, "h": 2},
        {"id": "dcim-p18-disk-temp",   "x": 0,  "y": 74,  "w": 24, "h": 8},
        {"id": "dcim-p19-disk-status", "x": 24, "y": 74,  "w": 12, "h": 8},
        {"id": "dcim-p20-nas-cpu",     "x": 36, "y": 74,  "w": 12, "h": 8},
        {"id": "dcim-p21-nas-memory",  "x": 0,  "y": 82,  "w": 24, "h": 8},
        {"id": "dcim-p22-nas-table",   "x": 24, "y": 82,  "w": 24, "h": 8},
        
        # Server Section
        {"id": "dcim-srv-header",      "x": 0,  "y": 90,  "w": 48, "h": 2},
        {"id": "dcim-p23-srv-temp",    "x": 0,  "y": 92,  "w": 24, "h": 8},
        {"id": "dcim-p24-srv-power",   "x": 24, "y": 92,  "w": 24, "h": 8},
        {"id": "dcim-p25-srv-health",  "x": 0,  "y": 100, "w": 12, "h": 8},
        {"id": "dcim-p26-srv-state",   "x": 12, "y": 100, "w": 12, "h": 8},
        {"id": "dcim-p27-srv-fan",     "x": 24, "y": 100, "w": 24, "h": 8},
        {"id": "dcim-p28-srv-table",   "x": 0,  "y": 108, "w": 48, "h": 8},
        {"id": "dcim-p28-srv-table",   "x": 0,  "y": 108, "w": 48, "h": 8},
        
        # CCTV & NVR Section
        {"id": "dcim-cctv-header",     "x": 0,  "y": 116, "w": 48, "h": 2},
        {"id": "dcim-p29-cctv-status", "x": 0,  "y": 118, "w": 12, "h": 10},
        {"id": "dcim-p30-cctv-uptime", "x": 12, "y": 118, "w": 18, "h": 10},
        {"id": "dcim-p31-cctv-cpu",    "x": 30, "y": 118, "w": 18, "h": 10},
        {"id": "dcim-p32-cctv-memory", "x": 0,  "y": 128, "w": 24, "h": 8},
        {"id": "dcim-p33-cctv-bitrate","x": 24, "y": 128, "w": 24, "h": 8},
        {"id": "dcim-p34-cctv-hdd",    "x": 0,  "y": 136, "w": 12, "h": 8},
        {"id": "dcim-p35-cctv-firmware","x": 12,"y": 136, "w": 36, "h": 8},
        {"id": "dcim-p36-cctv-table",  "x": 0,  "y": 144, "w": 48, "h": 8},
        
        # Asset Inventory Section
        {"id": "dcim-inv-header",      "x": 0,  "y": 152, "w": 48, "h": 2},
        {"id": "dcim-p37-by-site",     "x": 0,  "y": 154, "w": 24, "h": 10},
        {"id": "dcim-p38-by-rack",     "x": 24, "y": 154, "w": 24, "h": 10},
        {"id": "dcim-p39-enrich-quality","x": 0,"y": 164, "w": 24, "h": 8},
        {"id": "dcim-p40-model-dist",  "x": 24, "y": 164, "w": 24, "h": 8},
    ]

    dashboard_panels = []
    references = []
    for i, p in enumerate(panel_layout):
        dashboard_panels.append({
            "version": "8.0.0",
            "type": "visualization",
            "gridData": {"x": p["x"], "y": p["y"], "w": p["w"], "h": p["h"], "i": str(i + 1)},
            "panelIndex": str(i + 1),
            "embeddableConfig": {},
            "panelRefName": f"panel_{i + 1}"
        })
        references.append({"name": f"panel_{i + 1}", "type": "visualization", "id": p["id"]})

    dashboard_attrs = {
        "title": "DCIM Infrastructure — Complete Operational Overview",
        "description": "Comprehensive monitoring: Network, UPS, NAS, Server, CCTV/NVR, Inventory | Auto-refresh: 30s",
        "panelsJSON": json.dumps(dashboard_panels),
        "optionsJSON": json.dumps({"useMargins": True, "syncColors": True, "hidePanelTitles": False}),
        "timeRestore": True,
        "timeTo": "now",
        "timeFrom": "now-1h",
        "refreshInterval": {"pause": False, "value": 30000},
        "kibanaSavedObjectMeta": {
            "searchSourceJSON": json.dumps({"query": {"query": "", "language": "kuery"}, "filter": []})
        }
    }

    resp = requests.post(
        f"{KIBANA_URL}/api/saved_objects/dashboard/dcim-main-dashboard?overwrite=true",
        headers=HEADERS,
        json={"attributes": dashboard_attrs, "references": references},
        auth=ELASTIC_AUTH
    )
    
    if resp.status_code in (200, 201):
        print("✅ Dashboard created successfully!")
        print(f"   URL: {KIBANA_URL}/app/dashboards#/view/dcim-main-dashboard")
        print(f"\n📊 Dashboard includes:")
        print("   - Global Overview (5 panels)")
        print("   - Network Switch (6 panels)")
        print("   - UPS (7 panels)")
        print("   - NAS Storage (5 panels)")
        print("   - Servers (6 panels)")
        print("   - CCTV/NVR (8 panels)")
        print("   - Asset Inventory (4 panels)")
        print(f"   Total: {len(panel_layout)} panels")
    else:
        print(f"❌ Dashboard creation failed: {resp.status_code}\n{resp.text[:500]}")

if __name__ == "__main__":
    print("=" * 70)
    print("DCIM COMPREHENSIVE DASHBOARD GENERATOR")
    print("=" * 70)
    
    # Check Kibana connectivity
    resp = requests.get(f"{KIBANA_URL}/api/status", headers=HEADERS, auth=ELASTIC_AUTH)
    if resp.status_code != 200:
        print(f"❌ Cannot connect to Kibana: {resp.status_code}")
        sys.exit(1)
    
    print(f"✅ Connected to Kibana: {KIBANA_URL}")
    
    # Ensure Index Pattern exists
    print("\n📋 Creating/updating index pattern...")
    requests.post(
        f"{KIBANA_URL}/api/saved_objects/index-pattern/dcim-enriched-main?overwrite=true",
        headers=HEADERS,
        json={"attributes": {"title": "dcim-metrics-unified-*", "timeFieldName": "@timestamp"}},
        auth=ELASTIC_AUTH
    )
    print("✅ Index pattern ready: dcim-metrics-unified-*")
    
    # Create all visualizations
    panels = create_all_visualizations()
    
    # Create dashboard
    create_dashboard(panels)
    
    print("\n" + "=" * 70)
    print("✅ DASHBOARD GENERATION COMPLETE")
    print("=" * 70)
