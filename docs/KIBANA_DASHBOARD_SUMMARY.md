# DCIM Kibana Dashboard - Summary

> **Last Updated**: 2026-05-21  
> **Current Platform Version**: v3.5.5

## ✅ Apa yang Sudah Dibuat

### 1. **Script Dashboard Komprehensif**
**File**: `/home/infra/dcim_metrics_project/scripts/create_kibana_dashboard.py`

**Fitur**:
- ✅ Coverage lengkap untuk **6 kategori perangkat**
- ✅ **40+ panels** dengan visualisasi detail
- ✅ Auto-refresh 30 detik
- ✅ Field mapping otomatis via fungsi `F()`
- ✅ Support multiple device filters
- ✅ Color-coded metrics (traffic light system)
- ✅ Threshold + stale-device alerts via `dcim-alerts`

### 2. **Dokumentasi Lengkap**

#### A. Comprehensive Guide
**File**: `docs/KIBANA_DASHBOARD_COMPREHENSIVE.md`
- Penjelasan detail setiap section
- Daftar lengkap metrik per kategori
- Cara customization
- Troubleshooting guide
- Future enhancements

#### B. Quick Reference
**File**: `docs/KIBANA_DASHBOARD_QUICK_REF.md`
- Command cepat untuk generate dashboard
- Access credentials
- Key metrics per kategori
- Common operations
- Quick troubleshooting

#### C. Layout Visualization
**File**: `docs/KIBANA_DASHBOARD_LAYOUT.md`
- ASCII art layout dashboard
- Panel distribution chart
- Visualization types breakdown
- Grid structure explanation

---

## 📊 Dashboard Coverage

### Kategori Perangkat yang Tercakup

| # | Kategori | Panels | Key Metrics |
|---|----------|--------|-------------|
| 1 | **Global Overview** | 4 | Device count, enrichment, severity, site distribution |
| 2 | **Network Switch** | 6 | Interface status, traffic (in/out), errors, CPU load |
| 3 | **UPS** | 7 | Battery capacity/temp, voltage (in/out), load, runtime |
| 4 | **NAS Storage** | 5 | Disk temp/status, CPU, memory, volume status |
| 5 | **Servers** | 6 | Temperature, power, health, state, fan speed |
| 6 | **CCTV/NVR** | 8 | Online status, uptime, CPU, memory, bitrate, HDD, firmware |
| 7 | **Asset Inventory** | 4 | Site/rack distribution, enrichment quality, model dist |

**Total**: **40 panels** covering **45+ unique metrics**

---

## 🎯 Metrik Detail per Kategori

### 1. Network Switch (Mikrotik SNMP)
```
✓ ifOperStatus          - Interface up/down status
✓ ifInOctets            - Inbound traffic (bytes)
✓ ifOutOctets           - Outbound traffic (bytes)
✓ ifInErrors            - Inbound error count
✓ ifOutErrors           - Outbound error count
✓ hrProcessorLoad       - CPU utilization (%)
✓ hrStorageUsed         - Memory usage
✓ ifDescr               - Interface name/description
```

### 2. UPS (SNMP)
```
✓ upsBatteryCapacity    - Battery charge level (%)
✓ upsOutputLoad         - Output load (%)
✓ upsInputVoltage       - Input voltage (V)
✓ upsOutputVoltage      - Output voltage (V)
✓ upsBatteryRuntime     - Estimated runtime (seconds)
✓ upsBatteryTemp        - Battery temperature (°C)
✓ upsInputFrequency     - Input frequency (Hz)
✓ upsOutputCurrent      - Output current (A)
```

### 3. NAS Storage (SNMP)
```
✓ disk_temp             - Disk temperature (°C)
✓ disk_status           - Disk health status
✓ system_temp           - System temperature (°C)
✓ cpu_usage             - CPU utilization (%)
✓ memory_usage          - Memory utilization (%)
✓ volume_status         - Volume health status
✓ diskID                - Disk identifier
```

### 4. Servers (Redfish API)
```
✓ reading_celsius       - Temperature sensors (°C)
✓ power_input_watts     - Power consumption (W)
✓ health                - Overall health (OK/Warning/Critical)
✓ state                 - Server state (Enabled/Disabled/Standby)
✓ fan_speed_rpm         - Fan speed (RPM)
✓ memory_health         - Memory subsystem health
✓ storage_health        - Storage subsystem health
```

### 5. CCTV/NVR (ISAPI)
```
✓ status_text           - Online/offline status
✓ deviceUpTime          - Device uptime (seconds)
✓ cpuUtilization        - CPU usage (%)
✓ memoryUsage           - Memory usage (%)
✓ outputBitrate         - Video bitrate (kbps)
✓ videoResolutionWidth  - Video resolution width
✓ videoResolutionHeight - Video resolution height
✓ capacity              - HDD capacity (NVR)
✓ freeSpace             - HDD free space (NVR)
✓ Status                - HDD status (NVR)
✓ firmwareVersion       - Firmware version
```

### 6. Asset Inventory
```
✓ device_type           - Device category
✓ site                  - Physical site location
✓ rack_name             - Rack identifier
✓ model                 - Device model
✓ enrichment_status     - Data enrichment quality
```

---

## 🚀 Cara Menggunakan

### Generate Dashboard

```bash
cd /home/infra/dcim_metrics_project
python3 scripts/create_kibana_dashboard.py
```

**Output yang diharapkan**:
```
======================================================================
DCIM COMPREHENSIVE DASHBOARD GENERATOR
======================================================================
✅ Connected to Kibana: http://10.70.0.56:5601

📋 Creating/updating index pattern...
✅ Index pattern ready: dcim-metrics-unified-*

=== Creating Visualizations ===

  ✅ Saved visualization: dcim-header
  ✅ Saved visualization: dcim-p1-device-count
  ✅ Saved visualization: dcim-p2-enrichment
  ... (40+ panels)

=== Creating Dashboard ===

✅ Dashboard created successfully!
   URL: http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard

📊 Dashboard includes:
   - Global Overview (4 panels)
   - Network Switch (6 panels)
   - UPS (7 panels)
   - NAS Storage (5 panels)
   - Servers (6 panels)
   - CCTV/NVR (8 panels)
   - Asset Inventory (4 panels)
   Total: 40 panels

======================================================================
✅ DASHBOARD GENERATION COMPLETE
======================================================================
```

### Akses Dashboard

**URL**: http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard

**Credentials**:
- Username: `elastic`
- Password: `C+H+pFb*aIAqWcOo-X8q`

---

## 🎨 Fitur Dashboard

### Auto-Refresh
- **Interval**: 30 detik
- **Status**: Enabled by default
- **Customizable**: Ya, via dashboard settings

### Time Range
- **Default**: Last 1 hour
- **Adjustable**: Ya, via time picker
- **Options**: 15m, 30m, 1h, 3h, 6h, 12h, 24h, 7d, 30d, custom

### Filters
- **Global filters**: Device type, site, rack
- **Panel-specific filters**: Pre-configured per section
- **Custom filters**: Dapat ditambahkan via UI

### Color Coding
- 🟢 **Green**: Normal/OK (> 80%)
- 🟡 **Yellow**: Warning (50-80%)
- 🔴 **Red**: Critical (< 50%)

---

## 📁 File Structure

```
dcim_metrics_project/
├── scripts/
│   └── create_kibana_dashboard.py          # Main script
├── docs/
│   ├── KIBANA_DASHBOARD_COMPREHENSIVE.md   # Full documentation
│   ├── KIBANA_DASHBOARD_QUICK_REF.md       # Quick reference
│   ├── KIBANA_DASHBOARD_LAYOUT.md          # Visual layout
│   └── KIBANA_DASHBOARD_SUMMARY.md         # This file
└── configs/
    └── metric_mapping.yaml                 # Metric definitions
```

---

## 🔧 Customization

### Menambah Panel Baru

1. **Edit script**: `scripts/create_kibana_dashboard.py`
2. **Tambah di `create_all_visualizations()`**:
```python
panels["my_panel"] = make_line_chart(
    "dcim-my-panel",
    "My Custom Metric",
    F("my_metric_field"),
    device_filter="my_device_type"
)
```
3. **Tambah di `panel_layout`**:
```python
{"id": "dcim-my-panel", "x": 0, "y": 200, "w": 24, "h": 8}
```
4. **Regenerate dashboard**

### Mengubah Refresh Interval

Edit di `create_dashboard()`:
```python
"refreshInterval": {"pause": False, "value": 60000}  # 60 seconds
```

### Mengubah Time Range Default

Edit di `create_dashboard()`:
```python
"timeFrom": "now-24h",  # Last 24 hours
"timeTo": "now"
```

---

## 🔍 Troubleshooting

### Panel Kosong / No Data

**Penyebab**:
- Data belum ada di Elasticsearch
- Field mapping salah
- Device type filter tidak match

**Solusi**:
```bash
# Check data exists
curl -u elastic:PASSWORD \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_count

# Check specific device type
curl -u elastic:PASSWORD \
  -H "Content-Type: application/json" \
  -d '{"query":{"match":{"tag.device_type":"network_switch"}}}' \
  http://10.70.0.56:9200/dcim-metrics-unified-*/_search
```

### Dashboard Error saat Generate

**Penyebab**:
- Kibana tidak accessible
- Credentials salah
- Index pattern tidak ada

**Solusi**:
```bash
# Test Kibana connection
curl -u elastic:PASSWORD http://10.70.0.56:5601/api/status

# Verify credentials
curl -u elastic:PASSWORD http://10.70.0.56:9200/_cluster/health
```

### Panel Tidak Update

**Penyebab**:
- Auto-refresh disabled
- Time range terlalu lama
- Pipeline ingestion stopped

**Solusi**:
1. Check auto-refresh toggle (top-right)
2. Adjust time range ke "Last 15 minutes"
3. Verify pipeline: `check_cctv_status.py`

---

## 📈 Performance Tips

1. **Limit time range** untuk dataset besar
2. **Use specific filters** untuk fokus pada subset data
3. **Adjust refresh interval** sesuai kebutuhan (30s-5m)
4. **Close unused panels** untuk improve rendering
5. **Use saved searches** untuk query kompleks

---

## 🎯 Use Cases

### 1. Real-time Monitoring
- Auto-refresh enabled
- Time range: Last 15-30 minutes
- Focus: Status panels (donut charts)

### 2. Troubleshooting
- Disable auto-refresh
- Time range: Custom (incident window)
- Focus: Line charts & data tables
- Add filters: specific device/site

### 3. Capacity Planning
- Time range: Last 7-30 days
- Focus: Trend charts (CPU, memory, disk)
- Export data for analysis

### 4. Compliance & Audit
- Time range: Custom date range
- Focus: Data tables & inventory
- Export reports

### 5. Alerting Setup
- Identify threshold values
- Monitor severity distribution
- Set up Kibana alerts
- Review `dcim-alerts` for threshold and stale-device alerts

### 6. Commissioning / Decommissioning Monitoring
- New DC assets auto-register to Ralph via `scripts/ralph_cmdb_sync.py` when present in PostgreSQL but missing in Ralph.
- Stale devices trigger warning alert if no events arrive for 30 minutes.
- CCTV is excluded from DC asset auto-register; use Back Office registration script.

---

## 📊 Dashboard Statistics

```
Total Panels:           40+
Device Categories:      6
Unique Metrics:         45+
Visualization Types:    6
Grid Columns:           48
Auto-refresh:           30s
Default Time Range:     1h
Index Pattern:          dcim-metrics-unified-*
```

---

## 🔐 Security Notes

- Credentials hardcoded untuk internal environment
- Untuk production: gunakan environment variables
- Enable Kibana audit logging
- Implement RBAC untuk access control
- Regular credential rotation

---

## 📞 Support & Resources

### Documentation
- **Comprehensive**: `docs/KIBANA_DASHBOARD_COMPREHENSIVE.md`
- **Quick Ref**: `docs/KIBANA_DASHBOARD_QUICK_REF.md`
- **Layout**: `docs/KIBANA_DASHBOARD_LAYOUT.md`

### Logs
- **Pipeline logs**: `/home/infra/dcim_metrics_project/logs/`
- **Threshold/stale alerts**: `/home/infra/dcim_metrics_project/logs/threshold_alerts.log`
- **Telegraf file log**: `/var/log/telegraf/telegraf.log`
- **Kibana logs**: `/var/log/kibana/`
- **Elasticsearch logs**: `/var/log/elasticsearch/`

### Status Files
- **CCTV Status**: `CCTV_STATUS.md`
- **Pipeline Status**: `/memories/repo/pipeline-status.md`

---

## 🎉 Summary

Dashboard Kibana DCIM yang komprehensif telah dibuat dengan:

✅ **40+ panels** covering semua kategori perangkat  
✅ **6 device categories** dengan detail metrik lengkap  
✅ **45+ unique metrics** dari berbagai sumber (SNMP, Redfish, ISAPI)  
✅ **Auto-refresh 30s** untuk real-time monitoring  
✅ **Color-coded visualizations** untuk quick status assessment  
✅ **Alert index `dcim-alerts`** untuk threshold + stale-device alerting  
✅ **Comprehensive documentation** untuk maintenance & customization  

**Ready to use!** 🚀

---

**Version**: 2.1  
**Created**: 2026-05-12  
**Last Updated**: 2026-05-21  
**Maintainer**: DCIM Infrastructure Team
