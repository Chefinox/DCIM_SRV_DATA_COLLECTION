# DCIM Comprehensive Monitoring Dashboard

## 🔗 Access

**URL**: http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring

**Credentials**:
- Username: `elastic`
- Password: `C+H+pFb*aIAqWcOo-X8q`

---

## 📊 Dashboard Overview (34 Panels)

Dashboard ini menampilkan **beban kerja dan status real-time** dari semua perangkat infrastruktur.

### 1. Global Overview (4 panels)
- **Total Events** - Jumlah total event dalam 1 jam terakhir
- **Device Types** - Distribusi tipe perangkat (pie chart)
- **Severity Levels** - Level severity event
- **Enrichment Status** - Status enrichment data

---

### 2. 🔌 Network Switches (7 panels)

**Metrics Summary:**
- Switch Count
- **Avg CPU Load (%)** - Rata-rata beban CPU
- **Avg Memory (KB)** - Rata-rata penggunaan memory

**Time Series Charts:**
- **CPU Load Over Time** - Trend CPU load per switch
- **Memory Usage Over Time** - Trend memory usage per switch

**Details Table:**
- Hostname, IP, CPU %, Memory KB per switch

**Data Source**: Mikrotik SNMP (1.9M documents)

---

### 3. 🖥️ Servers (8 panels)

**Metrics Summary:**
- Server Count
- **Avg Temperature (°C)** - Rata-rata suhu server
- **Avg Power (W)** - Rata-rata konsumsi daya

**Time Series Charts:**
- **Temperature Over Time** - Trend suhu per server
- **Fan Speed Over Time** - Trend kecepatan fan (RPM)
- **Power Consumption Over Time** - Trend konsumsi daya

**Details Table:**
- Hostname, Model, Temperature °C, Power W per server

**Data Source**: Redfish API (1.9M documents)

---

### 4. 📷 CCTV Cameras (8 panels)

**Metrics Summary:**
- Camera Count
- **Avg CPU (%)** - Rata-rata CPU utilization
- **Avg Memory (%)** - Rata-rata memory usage

**Status:**
- **Camera Status** - Online/Offline distribution (pie chart)

**Time Series Charts:**
- **CPU Usage Over Time** - Trend CPU per camera
- **Memory Usage Over Time** - Trend memory per camera

**Details Table:**
- Hostname, IP, Status, CPU %, Memory % per camera

**Data Source**: Hikvision ISAPI (139K documents)

---

### 5. 💾 NAS Storage (4 panels)

- NAS Count
- **Storage Capacity per NAS** - Bar chart comparing Total vs Used capacity per device
- **Storage Usage Over Time (%)** - Line chart showing utilization trend
- **NAS Devices table** - Detailed table including Hostname, IP, Serial, Total (TB), Used (GB), Used (%), and Volume Status.

**Data Source**: SNMP (258K documents)

---

### 6. 📹 NVR Recorders (3 panels)

- NVR Count
- NVR Devices table (Hostname, IP, Serial)

**Data Source**: ISAPI (6K documents)

---

## 🎯 Key Features

### ✅ Real-time Monitoring
- **Auto-refresh**: 30 seconds
- **Time range**: Last 1 hour (adjustable)
- **Live metrics**: CPU, Memory, Temperature, Power

### ✅ Performance Metrics

| Device Type | Metrics Available |
|-------------|-------------------|
| **Network Switch** | CPU Load (%), Memory (KB) |
| **Server** | Temperature (°C), Fan Speed (RPM), Power (W) |
| **CCTV** | CPU (%), Memory (%), Status (Online/Offline) |
| **NAS** | Device count, Serial numbers |
| **NVR** | Device count, Serial numbers |

### ✅ Visualization Types
- **Metric panels** - Single value dengan average
- **Line charts** - Time series trends (top 10 devices)
- **Pie charts** - Distribution (status, types)
- **Data tables** - Detailed device information

---

## 📈 Use Cases

### 1. Monitor Beban Kerja
- Lihat **CPU Load** network switches untuk identifikasi bottleneck
- Monitor **Temperature** servers untuk deteksi overheating
- Track **Power Consumption** untuk optimasi energi

### 2. Deteksi Anomali
- **High CPU** pada switch → Possible network congestion
- **High Temperature** pada server → Cooling issue
- **Offline cameras** → Connectivity problem

### 3. Capacity Planning
- Trend **Memory Usage** untuk prediksi upgrade
- **Power Consumption** trend untuk budget planning
- Device count growth untuk infrastructure scaling

---

## 🔧 Customization

### Change Time Range
Default: Last 1 hour

Klik time picker di kanan atas:
- Last 15 minutes
- Last 1 hour
- Last 24 hours
- Last 7 days
- Custom range

### Change Refresh Interval
Default: 30 seconds

Klik refresh icon:
- 10 seconds
- 30 seconds
- 1 minute
- 5 minutes
- Pause

### Filter by Device
Tambahkan filter di search bar:
```
device_type.keyword: "network_switch"
hostname.keyword: "switch-core-01"
severity.keyword: "warning"
```

---

## 🚀 Regenerate Dashboard

```bash
cd /home/infra/dcim_metrics_project
python3 scripts/create_monitoring_dashboard.py
```

Output:
```
✅ Created 34/34 visualizations
✅ Dashboard created!
📊 URL: http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring
```

---

## 📋 Available Metrics per Device

### Network Switch (Mikrotik)
```
✅ raw_fields.cpu_load          # CPU load percentage
✅ raw_fields.memory_used_kb    # Memory usage in KB
✅ hostname.keyword              # Switch hostname
✅ ip.keyword                    # Switch IP address
```

### Server (Redfish)
```
✅ raw_fields.reading_celsius      # Temperature sensors
✅ raw_fields.reading_rpm          # Fan speed
✅ raw_fields.power_input_watts    # Power consumption
✅ raw_fields.model.keyword        # Server model
✅ raw_fields.firmware.keyword     # Firmware version
```

### CCTV Camera (Hikvision)
```
✅ raw_fields.cpuUtilization       # CPU usage %
✅ raw_fields.memoryUsage          # Memory usage %
✅ raw_fields.status_text.keyword  # Online/Offline
✅ raw_fields.status_online        # Boolean status
```

### NAS & NVR
```
✅ hostname.keyword
✅ ip.keyword
✅ serial_number.keyword
```

---

## ⚠️ Troubleshooting

### Panel Shows "No results found"

**Cause**: No data in selected time range

**Solution**:
1. Extend time range (e.g., Last 24 hours)
2. Check if data pipeline is running:
   ```bash
   python3 scripts/verify_dashboard_data.py
   ```

### Metrics Show Zero

**Cause**: Field not available for device type

**Solution**: Check available fields:
```bash
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{"size":1,"query":{"term":{"device_type.keyword":"network_switch"}}}' \
  | jq '.hits.hits[0]._source.raw_fields'
```

### Dashboard Slow to Load

**Cause**: Large time range or many devices

**Solution**:
1. Reduce time range to 1 hour
2. Add device filter to limit results
3. Reduce "size" in table visualizations

---

## 📞 Quick Commands

### Check Data Availability
```bash
# Count events per device type (last hour)
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "query": {"range": {"@timestamp": {"gte": "now-1h"}}},
    "aggs": {"types": {"terms": {"field": "device_type.keyword"}}}
  }' | jq '.aggregations.types.buckets'
```

### Verify Specific Metric
```bash
# Check if CPU load data exists
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "query": {
      "bool": {
        "must": [
          {"term": {"device_type.keyword": "network_switch"}},
          {"exists": {"field": "raw_fields.cpu_load"}}
        ]
      }
    }
  }' | jq '.hits.total.value'
```

---

## ✅ Verification Checklist

Setelah dashboard dibuat, verify:

- [ ] Dashboard URL accessible
- [ ] Global overview panels show data
- [ ] Network switch CPU/Memory charts display trends
- [ ] Server temperature/power charts show data
- [ ] CCTV status pie chart shows distribution
- [ ] All tables populated with devices
- [ ] Time series charts show multiple devices
- [ ] Auto-refresh working (30s)
- [ ] No "No results found" errors
- [ ] Metrics show realistic values

---

**Version**: 1.0 (Comprehensive Monitoring)  
**Created**: 2026-05-12  
**Status**: ✅ All 34 panels working  
**Total Visualizations**: 34  
**Data Coverage**: 4.2M documents  
**Refresh**: 30 seconds  
**Time Range**: Last 1 hour
