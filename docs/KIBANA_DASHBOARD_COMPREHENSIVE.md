# Dashboard Kibana DCIM - Komprehensif

## 📊 Overview

Dashboard ini mencakup **semua kategori perangkat DCIM** dengan detail metrik lengkap untuk setiap kategori. Dashboard dirancang dengan layout 48-kolom untuk visualisasi yang optimal.

## 🎯 Fitur Utama

- **Auto-refresh**: 30 detik
- **Time range**: Last 1 hour (dapat disesuaikan)
- **Total panels**: 40+ visualisasi
- **Device categories**: 6 kategori utama + inventory

## 📋 Struktur Dashboard

### 1. **Global Overview Section** (4 panels)

Memberikan gambaran umum infrastruktur:

| Panel | Tipe | Deskripsi |
|-------|------|-----------|
| Total Devices by Type | Donut Chart | Distribusi perangkat per kategori |
| Enrichment Status | Donut Chart | Status enrichment data (enriched/partial/failed) |
| Alert Severity Distribution | Donut Chart | Distribusi severity (info/warning/critical) |
| Devices by Site | Donut Chart | Distribusi perangkat per lokasi |

---

### 2. **Network Switch Section** (6 panels)

Monitoring switch Mikrotik via SNMP:

| Panel | Tipe | Metrik | Deskripsi |
|-------|------|--------|-----------|
| Interface Status | Donut Chart | `ifOperStatus` | Status interface (Up/Down) |
| Top Interfaces - Inbound | Bar Chart | `ifInOctets` | Traffic masuk tertinggi |
| Top Interfaces - Outbound | Bar Chart | `ifOutOctets` | Traffic keluar tertinggi |
| Interface Errors | Line Chart | `ifInErrors` | Error rate per interface |
| Switch CPU Load | Line Chart | `hrProcessorLoad` | CPU utilization per switch |
| Network Device Status | Data Table | Multiple | Hostname, model, site, rack, enrichment status |

**Metrik Detail:**
- Interface operational status
- Inbound/outbound octets
- Error counters (in/out)
- CPU load percentage
- Memory usage

---

### 3. **UPS Section** (7 panels)

Monitoring UPS (Uninterruptible Power Supply):

| Panel | Tipe | Metrik | Deskripsi |
|-------|------|--------|-----------|
| Battery Capacity | Line Chart | `upsBatteryCapacity` | Kapasitas baterai (%) |
| Output Load | Line Chart | `upsOutputLoad` | Beban output (%) |
| Input Voltage | Line Chart | `upsInputVoltage` | Tegangan input (V) |
| Output Voltage | Line Chart | `upsOutputVoltage` | Tegangan output (V) |
| Runtime Remaining | Metric | `upsBatteryRuntime` | Waktu backup tersisa (detik) |
| Battery Temperature | Line Chart | `upsBatteryTemp` | Suhu baterai (°C) |
| UPS Status Summary | Data Table | Multiple | Status lengkap semua UPS |

**Color Coding Runtime:**
- 🔴 Red: < 5 menit (critical)
- 🟡 Yellow: 5-10 menit (warning)
- 🟢 Green: > 10 menit (normal)

**Metrik Detail:**
- Battery capacity & temperature
- Input/output voltage & current
- Load percentage
- Runtime estimation
- Input frequency

---

### 4. **NAS Storage Section** (5 panels)

Monitoring NAS (Network Attached Storage):

| Panel | Tipe | Metrik | Deskripsi |
|-------|------|--------|-----------|
| Disk Temperature | Line Chart | `disk_temp` | Suhu disk per disk ID |
| Disk Status Distribution | Donut Chart | `disk_status` | Status kesehatan disk |
| NAS CPU Usage | Line Chart | `cpu_usage` | CPU utilization (%) |
| NAS Memory Usage | Line Chart | `memory_usage` | Memory utilization (%) |
| NAS Disk Status Table | Data Table | Multiple | Detail status semua disk |

**Metrik Detail:**
- Disk temperature & status
- System temperature
- CPU & memory usage
- Volume status
- Disk ID & health

---

### 5. **Server Section** (6 panels)

Monitoring server via Redfish API:

| Panel | Tipe | Metrik | Deskripsi |
|-------|------|--------|-----------|
| Server Temperature | Line Chart | `reading_celsius` | Suhu server (°C) |
| Server Power Consumption | Bar Chart | `power_input_watts` | Konsumsi daya (W) |
| Server Health Status | Donut Chart | `health` | Status kesehatan (OK/Warning/Critical) |
| Server State | Donut Chart | `state` | State server (Enabled/Disabled/StandbyOffline) |
| Server Fan Speed | Line Chart | `fan_speed_rpm` | Kecepatan fan (RPM) |
| Server Health Table | Data Table | Multiple | Detail status semua server |

**Metrik Detail:**
- Temperature sensors
- Power consumption
- Health status (overall, memory, storage)
- State (enabled/disabled/standby)
- Fan speed (RPM)

---

### 6. **CCTV & NVR Section** (8 panels)

Monitoring kamera CCTV dan NVR via ISAPI:

| Panel | Tipe | Metrik | Deskripsi |
|-------|------|--------|-----------|
| CCTV/NVR Online Status | Donut Chart | `status_text` | Status online/offline |
| Camera Uptime | Bar Chart | `deviceUpTime` | Uptime kamera (detik) |
| CPU Utilization | Line Chart | `cpuUtilization` | CPU usage (%) |
| Memory Usage | Line Chart | `memoryUsage` | Memory usage (%) |
| Camera Output Bitrate | Bar Chart | `outputBitrate` | Bitrate video (kbps) |
| NVR HDD Status | Donut Chart | `Status` | Status HDD NVR |
| Firmware Versions | Data Table | `firmwareVersion` | Versi firmware per device |
| Camera & NVR Detail | Data Table | Multiple | Detail lengkap semua kamera |

**Metrik Detail:**
- Online/offline status
- Device uptime
- CPU & memory utilization
- Video bitrate & resolution
- HDD capacity & free space
- Firmware version
- MAC address & serial number

---

### 7. **Asset Inventory Section** (4 panels)

Data quality dan distribusi aset:

| Panel | Tipe | Deskripsi |
|-------|------|-----------|
| Devices by Site | Bar Chart | Distribusi perangkat per site dan tipe |
| Devices by Rack | Data Table | Detail perangkat per rack |
| Enrichment Quality | Data Table | Kualitas enrichment per tipe device |
| Device Model Distribution | Data Table | Distribusi model perangkat |

---

## 🚀 Cara Menggunakan

### Generate Dashboard

```bash
cd /home/infra/dcim_metrics_project
python3 scripts/create_kibana_dashboard.py
```

### Akses Dashboard

```
URL: http://10.70.0.56:5601/app/dashboards#/view/dcim-main-dashboard
```

### Credentials

```
Username: elastic
Password: C+H+pFb*aIAqWcOo-X8q
```

---

## 🔧 Konfigurasi

### Field Mapping

Script menggunakan fungsi `F()` untuk mapping field dari nama logis ke path Elasticsearch aktual:

```python
# Contoh mapping
"device_type" → "tag.device_type"
"hostname" → "tag.hostname"
"ups_battery_capacity" → "kafka_consumer.raw_fields_upsBatteryCapacity"
"srv_reading_celsius" → "kafka_consumer.raw_fields_reading_celsius"
```

### Filter Device Type

Setiap section menggunakan filter `device_type`:
- `network_switch` - Switch Mikrotik
- `ups` - UPS devices
- `nas` - NAS storage
- `server` - Physical servers
- `cctv` - IP cameras
- `nvr` - Network Video Recorders

### Time Range & Refresh

- **Default time range**: Last 1 hour
- **Auto-refresh**: 30 seconds
- **Index pattern**: `dcim-metrics-unified-*`

---

## 📊 Visualisasi yang Tersedia

### Chart Types

1. **Donut Chart** - Distribusi kategorikal
2. **Line Chart** - Time series metrics
3. **Bar Chart** - Perbandingan nilai
4. **Metric Panel** - Single value dengan color coding
5. **Data Table** - Detail tabular
6. **Markdown** - Section headers

### Aggregations

- **Count** - Jumlah dokumen
- **Max** - Nilai maksimum
- **Terms** - Grouping by field
- **Date Histogram** - Time-based grouping

---

## 🎨 Customization

### Menambah Panel Baru

1. Buat fungsi helper di script:
```python
panels["new_panel"] = make_line_chart(
    "panel-id", 
    "Panel Title", 
    F("metric_field"),
    device_filter="device_type"
)
```

2. Tambahkan ke layout:
```python
{"id": "panel-id", "x": 0, "y": 100, "w": 24, "h": 8}
```

### Mengubah Color Ranges

```python
color_ranges=[
    {"from": 0, "to": 50, "color": "#D32F2F"},    # Red
    {"from": 50, "to": 80, "color": "#F57F17"},   # Yellow
    {"from": 80, "to": 100, "color": "#388E3C"}   # Green
]
```

### Menambah Device Category Baru

1. Tambahkan field mapping di fungsi `F()`
2. Buat section header (markdown panel)
3. Buat visualisasi dengan `device_filter="new_type"`
4. Tambahkan ke layout dashboard

---

## 🔍 Troubleshooting

### Panel Kosong

- Cek apakah data tersedia di Elasticsearch
- Verifikasi field mapping di fungsi `F()`
- Pastikan `device_type` filter sesuai

### Error saat Generate

```bash
# Cek koneksi Kibana
curl -u elastic:PASSWORD http://10.70.0.56:5601/api/status

# Cek index pattern
curl -u elastic:PASSWORD http://10.70.0.56:5601/api/saved_objects/index-pattern/dcim-enriched-main
```

### Data Tidak Update

- Verifikasi auto-refresh aktif (30s)
- Cek time range (default: last 1 hour)
- Pastikan pipeline ingestion berjalan

---

## 📈 Metrics Coverage

### Total Metrics Monitored

| Category | Metrics Count | Key Metrics |
|----------|---------------|-------------|
| Network Switch | 8+ | Interface status, traffic, errors, CPU |
| UPS | 8+ | Battery, voltage, load, runtime |
| NAS | 7+ | Disk temp/status, CPU, memory |
| Server | 7+ | Temperature, power, health, fans |
| CCTV/NVR | 10+ | Status, uptime, CPU, bitrate, HDD |
| Inventory | 5+ | Site, rack, model, enrichment |

**Total**: 45+ unique metrics across all categories

---

## 🔐 Security Notes

- Credentials hardcoded untuk environment internal
- Gunakan environment variables untuk production
- Implementasi RBAC untuk akses dashboard
- Enable audit logging di Kibana

---

## 📝 Changelog

### Version 2.0 (Current)
- ✅ Added comprehensive coverage untuk semua device types
- ✅ Expanded network metrics (CPU, memory, outbound traffic)
- ✅ Added UPS battery temperature & frequency
- ✅ Added NAS CPU & memory monitoring
- ✅ Added server fan speed & health details
- ✅ Expanded CCTV metrics (uptime, CPU, memory, bitrate, HDD)
- ✅ Added inventory section dengan rack & model distribution
- ✅ Total panels: 40+ (dari 23 sebelumnya)

### Version 1.0
- Initial dashboard dengan basic metrics
- 6 device categories
- 23 panels

---

## 🎯 Future Enhancements

1. **Environmental Sensors**
   - Temperature & humidity monitoring
   - Sensor status tracking

2. **PDU (Power Distribution Unit)**
   - Current & voltage per outlet
   - Power consumption tracking

3. **Alerting**
   - Threshold-based alerts
   - Anomaly detection

4. **Predictive Analytics**
   - Disk failure prediction
   - Battery replacement forecasting

5. **Custom Dashboards**
   - Per-site dashboards
   - Per-device-type focused views
   - Executive summary dashboard

---

## 📞 Support

Untuk pertanyaan atau issue:
- Check logs: `/home/infra/dcim_metrics_project/logs/`
- Review pipeline status: `CCTV_STATUS.md`
- Elasticsearch query console untuk debugging

---

**Generated by**: DCIM Dashboard Generator v2.0  
**Last Updated**: 2026-05-12  
**Maintainer**: DCIM Infrastructure Team
