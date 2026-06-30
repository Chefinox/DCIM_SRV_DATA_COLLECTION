# 📊 Kibana Dashboard DCIM - Comprehensive Monitoring

## 🎯 Overview

Dashboard Elasticsearch/Kibana yang **komprehensif** untuk monitoring seluruh infrastruktur DCIM, mencakup **6 kategori perangkat** dengan **40+ panels** dan **45+ unique metrics**.

## ✨ Highlights

- ✅ **Complete Coverage**: Network Switch, UPS, NAS, Server, CCTV/NVR, Inventory
- ✅ **Real-time Monitoring**: Auto-refresh 30 detik
- ✅ **Rich Visualizations**: Donut charts, line charts, bar charts, data tables
- ✅ **Color-coded Metrics**: Traffic light system (🟢🟡🔴)
- ✅ **Detailed Metrics**: 45+ metrics dari SNMP, Redfish, ISAPI
- ✅ **Easy Customization**: Modular panel creation

## 🚀 Quick Start

### Generate Dashboard

```bash
cd /home/infra/dcim_metrics_project
python3 scripts/create_kibana_dashboard.py
```

### Access Dashboard

**URL**: http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard

**Credentials**:
```
Username: elastic
Password: C+H+pFb*aIAqWcOo-X8q
```

## 📋 Dashboard Sections

### 1. Global Overview (4 panels)
- Total devices by type (donut chart)
- Enrichment status distribution
- Alert severity levels
- Devices by site

### 2. Network Switch (6 panels)
**Metrics**: Interface status, traffic (in/out), errors, CPU load
- Interface operational status
- Top interfaces by traffic
- Error monitoring over time
- CPU utilization trends
- Device status table

### 3. UPS (7 panels)
**Metrics**: Battery, voltage, load, runtime, temperature
- Battery capacity trends
- Output load monitoring
- Input/output voltage
- Runtime estimation with color coding
- Battery temperature
- Comprehensive status table

### 4. NAS Storage (5 panels)
**Metrics**: Disk health, temperature, CPU, memory
- Disk temperature per disk ID
- Disk status distribution
- CPU & memory utilization
- Detailed disk status table

### 5. Servers (6 panels)
**Metrics**: Temperature, power, health, state, fans
- Server temperature monitoring
- Power consumption tracking
- Health status distribution
- Server state overview
- Fan speed monitoring
- Health status table

### 6. CCTV/NVR (8 panels)
**Metrics**: Status, uptime, CPU, memory, bitrate, HDD, firmware
- Online/offline status
- Camera uptime tracking
- CPU & memory utilization
- Video bitrate monitoring
- NVR HDD status
- Firmware version tracking
- Comprehensive device table

### 7. Asset Inventory (4 panels)
**Metrics**: Site, rack, model, enrichment quality
- Device distribution by site
- Rack allocation
- Enrichment quality assessment
- Model distribution

## 📊 Metrics Coverage

| Category | Panels | Key Metrics |
|----------|--------|-------------|
| Global Overview | 4 | Device count, enrichment, severity, site |
| Network Switch | 6 | Interface, traffic, errors, CPU |
| UPS | 7 | Battery, voltage, load, runtime, temp |
| NAS Storage | 5 | Disk temp/status, CPU, memory |
| Servers | 6 | Temperature, power, health, fans |
| CCTV/NVR | 8 | Status, uptime, CPU, bitrate, HDD |
| Asset Inventory | 4 | Site, rack, model, enrichment |
| **TOTAL** | **40** | **45+ unique metrics** |

## 🎨 Visualization Types

- **Donut Charts** (11): Status distributions, categorical data
- **Line Charts** (14): Time series, trends, historical data
- **Bar Charts** (6): Comparisons, rankings, top N
- **Data Tables** (8): Detailed listings, drill-down data
- **Metric Panels** (1): Single value with color coding
- **Markdown** (7): Section headers, descriptions

## 🔧 Features

### Auto-Refresh
- **Interval**: 30 seconds (configurable)
- **Status**: Enabled by default
- **Benefit**: Real-time monitoring without manual refresh

### Time Range
- **Default**: Last 1 hour
- **Options**: 15m, 30m, 1h, 3h, 6h, 12h, 24h, 7d, 30d, custom
- **Adjustable**: Via time picker (top-right)

### Color Coding
- 🟢 **Green**: Normal/OK (> 80%)
- 🟡 **Yellow**: Warning (50-80%)
- 🔴 **Red**: Critical (< 50%)

### Filters
- **Global**: Device type, site, rack
- **Panel-specific**: Pre-configured per section
- **Custom**: Add via Kibana UI

## 📁 Files

```
dcim_metrics_project/
├── scripts/
│   └── create_kibana_dashboard.py          # Main generator script
├── docs/
│   ├── KIBANA_DASHBOARD_COMPREHENSIVE.md   # Full documentation
│   ├── KIBANA_DASHBOARD_QUICK_REF.md       # Quick reference guide
│   ├── KIBANA_DASHBOARD_LAYOUT.md          # Visual layout diagram
│   ├── KIBANA_DASHBOARD_SUMMARY.md         # Summary overview
│   └── KIBANA_DASHBOARD_README.md          # This file
└── configs/
    └── metric_mapping.yaml                 # Metric definitions
```

## 🔍 Detailed Metrics

### Network Switch (Mikrotik SNMP)
```
✓ ifOperStatus          Interface up/down status
✓ ifInOctets            Inbound traffic (bytes)
✓ ifOutOctets           Outbound traffic (bytes)
✓ ifInErrors            Inbound error count
✓ ifOutErrors           Outbound error count
✓ hrProcessorLoad       CPU utilization (%)
✓ hrStorageUsed         Memory usage
✓ ifDescr               Interface name
```

### UPS (SNMP)
```
✓ upsBatteryCapacity    Battery charge (%)
✓ upsOutputLoad         Output load (%)
✓ upsInputVoltage       Input voltage (V)
✓ upsOutputVoltage      Output voltage (V)
✓ upsBatteryRuntime     Runtime (seconds)
✓ upsBatteryTemp        Battery temp (°C)
✓ upsInputFrequency     Input frequency (Hz)
✓ upsOutputCurrent      Output current (A)
```

### NAS Storage (SNMP)
```
✓ disk_temp             Disk temperature (°C)
✓ disk_status           Disk health status
✓ system_temp           System temperature (°C)
✓ cpu_usage             CPU utilization (%)
✓ memory_usage          Memory utilization (%)
✓ volume_status         Volume health
✓ diskID                Disk identifier
```

### Servers (Redfish API)
```
✓ reading_celsius       Temperature (°C)
✓ power_input_watts     Power consumption (W)
✓ health                Health status
✓ state                 Server state
✓ fan_speed_rpm         Fan speed (RPM)
✓ memory_health         Memory health
✓ storage_health        Storage health
```

### CCTV/NVR (ISAPI)
```
✓ status_text           Online/offline status
✓ deviceUpTime          Uptime (seconds)
✓ cpuUtilization        CPU usage (%)
✓ memoryUsage           Memory usage (%)
✓ outputBitrate         Video bitrate (kbps)
✓ videoResolution       Video resolution
✓ capacity              HDD capacity (NVR)
✓ freeSpace             HDD free space (NVR)
✓ Status                HDD status (NVR)
✓ firmwareVersion       Firmware version
```

## 🎯 Use Cases

### 1. Real-time Monitoring
```
Time Range: Last 15-30 minutes
Auto-refresh: Enabled (30s)
Focus: Status panels (donut charts)
Goal: Monitor current infrastructure health
```

### 2. Troubleshooting
```
Time Range: Custom (incident window)
Auto-refresh: Disabled
Focus: Line charts & data tables
Filters: Specific device/site
Goal: Investigate issues and anomalies
```

### 3. Capacity Planning
```
Time Range: Last 7-30 days
Auto-refresh: Optional
Focus: Trend charts (CPU, memory, disk)
Goal: Forecast resource needs
```

### 4. Compliance & Audit
```
Time Range: Custom date range
Auto-refresh: Disabled
Focus: Data tables & inventory
Goal: Generate compliance reports
```

### 5. Performance Analysis
```
Time Range: Last 24 hours
Auto-refresh: Enabled
Focus: All metrics
Goal: Identify performance bottlenecks
```

## 🔧 Customization

### Add New Panel

1. Edit `scripts/create_kibana_dashboard.py`
2. Add in `create_all_visualizations()`:
```python
panels["my_panel"] = make_line_chart(
    "dcim-my-panel",
    "My Custom Metric",
    F("my_metric_field"),
    device_filter="my_device_type"
)
```
3. Add to `panel_layout`:
```python
{"id": "dcim-my-panel", "x": 0, "y": 200, "w": 24, "h": 8}
```
4. Regenerate dashboard

### Change Refresh Interval

Edit in `create_dashboard()`:
```python
"refreshInterval": {"pause": False, "value": 60000}  # 60 seconds
```

### Change Default Time Range

Edit in `create_dashboard()`:
```python
"timeFrom": "now-24h",  # Last 24 hours
"timeTo": "now"
```

### Add New Device Category

1. Add field mappings in `F()` function
2. Create section header (markdown panel)
3. Create visualizations with `device_filter="new_type"`
4. Add to dashboard layout

## 🔍 Troubleshooting

### Panel Shows "No Data"

**Check data exists**:
```bash
curl -u elastic:PASSWORD \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_count
```

**Check specific device type**:
```bash
curl -u elastic:PASSWORD \
  -H "Content-Type: application/json" \
  -d '{"query":{"match":{"tag.device_type":"network_switch"}}}' \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_search
```

### Dashboard Generation Fails

**Test Kibana connection**:
```bash
curl -u elastic:PASSWORD http://10.70.0.56:5601/api/status
```

**Verify credentials**:
```bash
curl -u elastic:PASSWORD http://10.70.0.56:9200/_cluster/health
```

### Panel Not Updating

1. Check auto-refresh toggle (top-right)
2. Adjust time range to recent period
3. Verify pipeline is running:
```bash
python3 scripts/check_cctv_status.py
```

## 📈 Performance Tips

1. **Limit time range** untuk dataset besar
2. **Use specific filters** untuk fokus pada subset
3. **Adjust refresh interval** sesuai kebutuhan
4. **Close unused panels** untuk improve rendering
5. **Use saved searches** untuk query kompleks

## 🔐 Security

- Credentials hardcoded untuk internal environment
- Untuk production: gunakan environment variables
- Enable Kibana audit logging
- Implement RBAC untuk access control
- Regular credential rotation

## 📚 Documentation

- **Comprehensive Guide**: `KIBANA_DASHBOARD_COMPREHENSIVE.md`
- **Quick Reference**: `KIBANA_DASHBOARD_QUICK_REF.md`
- **Layout Diagram**: `KIBANA_DASHBOARD_LAYOUT.md`
- **Summary**: `KIBANA_DASHBOARD_SUMMARY.md`

## 🎉 Summary

Dashboard Kibana DCIM yang komprehensif dengan:

✅ **40+ panels** covering semua kategori perangkat  
✅ **6 device categories** dengan detail metrik lengkap  
✅ **45+ unique metrics** dari SNMP, Redfish, ISAPI  
✅ **Auto-refresh 30s** untuk real-time monitoring  
✅ **Color-coded visualizations** untuk quick assessment  
✅ **Comprehensive documentation** untuk maintenance  

**Ready to deploy!** 🚀

---

**Version**: 2.0  
**Created**: 2026-05-12  
**Maintainer**: DCIM Infrastructure Team
