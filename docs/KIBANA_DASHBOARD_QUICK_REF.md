# Quick Reference - Kibana Dashboard DCIM

## 🚀 Quick Start

```bash
# Generate dashboard
cd /home/infra/dcim_metrics_project
python3 scripts/create_kibana_dashboard.py

# Output:
# ✅ Connected to Kibana
# ✅ Index pattern ready
# ✅ Saved 40+ visualizations
# ✅ Dashboard created successfully
```

## 🔗 Access

**Dashboard URL**: http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard

**Credentials**:
- Username: `elastic`
- Password: `C+H+pFb*aIAqWcOo-X8q`

## 📊 Dashboard Sections

### 1. Global Overview (4 panels)
- Device count by type
- Enrichment status
- Severity distribution
- Site overview

### 2. Network Switch (6 panels)
- Interface status & traffic
- Error monitoring
- CPU load
- Device table

### 3. UPS (7 panels)
- Battery capacity & temp
- Voltage (in/out)
- Load & runtime
- Status table

### 4. NAS Storage (5 panels)
- Disk temperature & status
- CPU & memory usage
- Disk detail table

### 5. Servers (6 panels)
- Temperature & power
- Health & state
- Fan speed
- Server table

### 6. CCTV/NVR (8 panels)
- Online status
- Uptime & performance
- CPU, memory, bitrate
- HDD status
- Firmware versions
- Device table

### 7. Asset Inventory (4 panels)
- Site distribution
- Rack allocation
- Enrichment quality
- Model distribution

## 🎯 Key Metrics by Category

### Network Switch
```
- ifOperStatus (interface up/down)
- ifInOctets / ifOutOctets (traffic)
- ifInErrors / ifOutErrors (errors)
- hrProcessorLoad (CPU %)
- hrStorageUsed (memory)
```

### UPS
```
- upsBatteryCapacity (%)
- upsOutputLoad (%)
- upsInputVoltage / upsOutputVoltage (V)
- upsBatteryRuntime (seconds)
- upsBatteryTemp (°C)
```

### NAS
```
- disk_temp (°C)
- disk_status (health)
- cpu_usage (%)
- memory_usage (%)
- volume_status
```

### Server
```
- reading_celsius (°C)
- power_input_watts (W)
- health (OK/Warning/Critical)
- state (Enabled/Disabled)
- fan_speed_rpm
```

### CCTV/NVR
```
- status_text (online/offline)
- deviceUpTime (seconds)
- cpuUtilization (%)
- memoryUsage (%)
- outputBitrate (kbps)
- capacity / freeSpace (HDD)
```

## 🔧 Common Operations

### Regenerate Dashboard
```bash
python3 scripts/create_kibana_dashboard.py
```

### Check Kibana Status
```bash
curl -u elastic:C+H+pFb*aIAqWcOo-X8q \
  http://10.70.0.56:5601/api/status
```

### Verify Index Pattern
```bash
curl -u elastic:C+H+pFb*aIAqWcOo-X8q \
  http://10.70.0.56:5601/api/saved_objects/index-pattern/dcim-enriched-main
```

### Query Sample Data
```bash
curl -u elastic:C+H+pFb*aIAqWcOo-X8q \
  -H "Content-Type: application/json" \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_search?size=1
```

## 🎨 Customization Examples

### Add New Panel
```python
# In create_kibana_dashboard.py

# 1. Add to create_all_visualizations()
panels["my_panel"] = make_line_chart(
    "dcim-my-panel",
    "My Custom Metric",
    F("my_metric_field"),
    device_filter="my_device_type"
)

# 2. Add to panel_layout in create_dashboard()
{"id": "dcim-my-panel", "x": 0, "y": 200, "w": 24, "h": 8}
```

### Change Time Range
```python
# In dashboard_attrs
"timeFrom": "now-24h",  # Last 24 hours
"timeTo": "now"
```

### Change Refresh Interval
```python
# In dashboard_attrs
"refreshInterval": {"pause": False, "value": 60000}  # 60 seconds
```

## 🔍 Troubleshooting

### No Data in Panels
```bash
# Check if data exists
curl -u elastic:C+H+pFb*aIAqWcOo-X8q \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_count

# Check specific device type
curl -u elastic:C+H+pFb*aIAqWcOo-X8q \
  -H "Content-Type: application/json" \
  -d '{"query":{"match":{"tag.device_type":"network_switch"}}}' \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_search
```

### Panel Shows Error
- Verify field exists in index
- Check field mapping in `F()` function
- Ensure device_type filter is correct

### Dashboard Not Loading
- Clear browser cache
- Check Kibana logs: `/var/log/kibana/`
- Verify Elasticsearch is running

## 📈 Performance Tips

1. **Limit time range** untuk data besar
2. **Use filters** untuk fokus pada device tertentu
3. **Adjust refresh interval** sesuai kebutuhan
4. **Use saved searches** untuk query kompleks

## 🔐 Security

- Dashboard menggunakan basic auth
- Credentials di script untuk internal use
- Untuk production: gunakan environment variables
- Enable Kibana audit logging

## 📝 Quick Checks

### Verify All Components
```bash
# Elasticsearch
curl http://10.70.0.56:9200/_cluster/health

# Kibana
curl http://10.70.0.56:5601/api/status

# Index exists
curl http://10.70.0.56:9200/_cat/indices/dcim-metrics-unified-*

# Recent data
curl http://10.70.0.56:9200/dcim-metrics-unified-*/_search?size=1&sort=@timestamp:desc
```

## 📊 Dashboard Stats

- **Total Panels**: 40+
- **Device Categories**: 6
- **Metrics Tracked**: 45+
- **Auto-refresh**: 30 seconds
- **Default Time Range**: 1 hour
- **Grid Layout**: 48 columns

## 🎯 Use Cases

1. **Real-time Monitoring**: Auto-refresh untuk live view
2. **Troubleshooting**: Filter by device/site untuk investigasi
3. **Capacity Planning**: Historical trends untuk forecasting
4. **Compliance**: Audit trail via Elasticsearch
5. **Alerting**: Threshold monitoring untuk proactive response

## 📞 Support

**Documentation**: `/home/infra/dcim_metrics_project/docs/KIBANA_DASHBOARD_COMPREHENSIVE.md`

**Logs**: `/home/infra/dcim_metrics_project/logs/`

**Pipeline Status**: `CCTV_STATUS.md`

---

**Version**: 2.0  
**Last Updated**: 2026-05-12
