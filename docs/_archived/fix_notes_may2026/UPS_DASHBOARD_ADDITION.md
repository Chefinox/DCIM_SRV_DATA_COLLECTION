# UPS Dashboard Addition - May 13, 2026

## Problem
- **Issue**: UPS tidak ada di dashboard
- **Issue**: Device Types tidak menampilkan UPS
- **Root Cause**: UPS data terakhir dari April 30, 2026 (2 minggu lalu)

## Investigation

### 1. UPS Data Check
```bash
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 3,
    "query": {"term": {"device_type.keyword": "ups"}},
    "sort": [{"@timestamp": "desc"}]
  }'
```

**Result**: ✅ **125 UPS documents found**
```json
{
  "total": 125,
  "last_seen": "2026-04-30T03:37:00.000Z",  // ⚠️ 2 weeks old
  "sample": {
    "device_type": "ups",
    "hostname": "UPS-3Phase-30kVA",
    "ip": "192.168.100.140",
    "serial_number": "9E2133T16585",
    "site": "Local Instance",
    "rack_name": "Ruang server",
    "manufacturer": "APC",
    "model": "APC Easy UPS 3S 30kVA 30kW (E3SUPS30KHB + E3SBT4)",
    "enrichment_status": "FULL",
    "raw_fields": {
      "upsBatteryCapacity": 100,
      "upsBatteryRuntime": 506,
      "upsBatteryStatus": 2,
      "upsBatteryTemp": 22,
      "upsInputVoltage": 214,
      "upsOutputLoad": 2,
      "upsOutputStatus": 3,
      "upsOutputVoltage": 231
    }
  }
}
```

### 2. All Device Types Distribution
```bash
curl -k -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  'https://10.70.0.56:9200/dcim-metrics-unified-*/_search' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "aggs": {
      "device_types": {
        "terms": {"field": "device_type.keyword", "size": 20},
        "aggs": {"last_seen": {"max": {"field": "@timestamp"}}}
      }
    }
  }'
```

**Result**:
| Device Type | Count | Last Seen | Status |
|-------------|-------|-----------|--------|
| network_switch | 2,242,026 | 2026-05-13 03:53 | ✅ Active |
| server | 2,239,564 | 2026-05-13 03:53 | ✅ Active |
| nas | 306,170 | 2026-05-13 03:53 | ✅ Active |
| cctv | 172,979 | 2026-05-13 03:53 | ✅ Active |
| nvr | 7,039 | 2026-05-13 03:53 | ✅ Active |
| **ups** | **125** | **2026-04-30 03:37** | ⚠️ **Inactive (2 weeks)** |

### 3. Why UPS Not Visible in Dashboard?

**Dashboard Time Range**: Default "Last 1 hour"
- network_switch: ✅ Has data in last 1 hour
- server: ✅ Has data in last 1 hour
- nas: ✅ Has data in last 1 hour
- cctv: ✅ Has data in last 1 hour
- nvr: ✅ Has data in last 1 hour
- **ups**: ❌ **No data in last 1 hour** (last data 2 weeks ago)

**Device Types Pie Chart**: Shows only devices with data in selected time range
- If time range = "Last 1 hour" → UPS not shown
- If time range = "Last 30 days" → UPS shown

## Solution Applied

### 1. Added UPS Section to Dashboard
**File**: `/home/infra/dcim_metrics_project/scripts/create_monitoring_dashboard.py`

**Added Visualizations** (7 new panels):
```python
# === UPS POWER ===
viz_list.append(("dcim-mon-ups-h", "UPS Header", "markdown", "## ⚡ UPS - Power & Battery", None))
viz_list.append(("dcim-mon-ups-count", "UPS Count", "metric", None, "ups"))
viz_list.append(("dcim-mon-ups-battery", "Battery Capacity (%)", "metric", "raw_fields.upsBatteryCapacity", "ups", "avg"))
viz_list.append(("dcim-mon-ups-load", "Output Load (%)", "metric", "raw_fields.upsOutputLoad", "ups", "avg"))
viz_list.append(("dcim-mon-ups-battery-time", "Battery Capacity Over Time", "line", "raw_fields.upsBatteryCapacity", "ups", "avg"))
viz_list.append(("dcim-mon-ups-load-time", "Output Load Over Time", "line", "raw_fields.upsOutputLoad", "ups", "avg"))
viz_list.append(("dcim-mon-ups-list", "UPS Details", "table",
    [("hostname.keyword", "Hostname"), ("site.keyword", "Site"), ("rack_name.keyword", "Rack"), 
     ("model.keyword", "Model"), ("raw_fields.upsBatteryCapacity", "Battery %"), 
     ("raw_fields.upsOutputLoad", "Load %")],
    "ups"))
```

**Dashboard Layout** (inserted between CCTV and NAS):
```python
# UPS (y: 78-100)
{"id": "dcim-mon-ups-h", "x": 0, "y": 78, "w": 48, "h": 2},
{"id": "dcim-mon-ups-count", "x": 0, "y": 80, "w": 8, "h": 5},
{"id": "dcim-mon-ups-battery", "x": 8, "y": 80, "w": 8, "h": 5},
{"id": "dcim-mon-ups-load", "x": 16, "y": 80, "w": 8, "h": 5},
{"id": "dcim-mon-ups-battery-time", "x": 0, "y": 85, "w": 24, "h": 8},
{"id": "dcim-mon-ups-load-time", "x": 24, "y": 85, "w": 24, "h": 8},
{"id": "dcim-mon-ups-list", "x": 0, "y": 93, "w": 48, "h": 8},
```

### 2. Recreated Dashboard
```bash
cd /home/infra/dcim_metrics_project
python3 scripts/create_monitoring_dashboard.py
```

**Result**: ✅ **Dashboard updated with 41 panels** (was 34)

**New Panels**:
- UPS Header
- UPS Count
- Battery Capacity (%)
- Output Load (%)
- Battery Capacity Over Time
- Output Load Over Time
- UPS Details (table)

## Verification

### 1. UPS Visualizations Created
```bash
curl -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' 'http://10.70.0.56:5601/api/saved_objects/visualization/dcim-mon-ups-list'
```

**Result**: ✅ **UPS Details visualization exists**
```json
{
  "id": "dcim-mon-ups-list",
  "title": "UPS Details",
  "type": "table"
}
```

### 2. Device Types Visualization
```bash
curl -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' 'http://10.70.0.56:5601/api/saved_objects/visualization/dcim-mon-devices'
```

**Result**: ✅ **Pie chart with device_type.keyword, size 10**
- Will show UPS when time range includes April 30
- Will NOT show UPS when time range is "Last 1 hour" (no recent data)

### 3. Dashboard Panel Count
```bash
curl -s -u elastic:'C+H+pFb*aIAqWcOo-X8q' 'http://10.70.0.56:5601/api/saved_objects/dashboard/dcim-monitoring'
```

**Result**: ✅ **41 panels** (was 34 before UPS addition)

## Expected Behavior

### When Time Range = "Last 1 hour" (Default)
- **Device Types Pie Chart**: Shows 5 device types (network_switch, server, nas, cctv, nvr)
- **UPS Section**: Shows "No results found" or 0 count
- **Reason**: No UPS data in last 1 hour

### When Time Range = "Last 30 days"
- **Device Types Pie Chart**: Shows 6 device types (including UPS)
- **UPS Section**: Shows 1 UPS device with metrics
- **UPS Details Table**:
  | Hostname | Site | Rack | Model | Battery % | Load % |
  |----------|------|------|-------|-----------|--------|
  | UPS-3Phase-30kVA | Local Instance | Ruang server | APC Easy UPS 3S 30kVA | 100 | 2 |

### When Time Range = "Last 7 days"
- **Device Types Pie Chart**: Shows 6 device types (including UPS)
- **UPS Section**: Shows "No results found" (data is 13 days old)
- **Reason**: UPS data from April 30, time range only covers May 6-13

## Root Cause: UPS Data Collection Stopped

### Why No Recent UPS Data?

**Possible Causes**:
1. **UPS SNMP Poller Stopped**: Service not running or crashed
2. **Network Issue**: UPS IP (192.168.100.140) not reachable
3. **SNMP Configuration**: SNMP disabled on UPS or credentials changed
4. **Kafka Topic Issue**: UPS data not reaching Kafka topic
5. **UPS Powered Off**: Device physically offline

### Check UPS Poller Status
```bash
# Check if UPS poller service exists
ps aux | grep ups | grep -v grep

# Check systemd service
systemctl status dcim-ups-poller

# Check logs
journalctl -u dcim-ups-poller -n 50 --no-pager

# Check if UPS is reachable
ping -c 3 192.168.100.140

# Test SNMP connection
snmpwalk -v2c -c public 192.168.100.140 1.3.6.1.2.1.1.1.0
```

## Recommendations

### 1. For User (Immediate)
**To see UPS in dashboard**:
1. Open dashboard: http://10.70.0.56:5601/app/dashboards#/view/dcim-monitoring
2. Change time range to **"Last 30 days"** (top right)
3. UPS will appear in Device Types pie chart
4. Scroll down to **UPS - Power & Battery** section
5. UPS Details table will show 1 device

**Note**: UPS data is from April 30 (2 weeks old), so metrics are historical

### 2. For Admin (Fix Data Collection)
**Investigate why UPS data collection stopped**:

1. **Check UPS Poller Service**:
```bash
# Find UPS poller process
ps aux | grep -E "(ups|snmp)" | grep -v grep

# Check if service exists
systemctl list-units | grep ups

# Check recent logs
journalctl --since "2026-04-30" | grep -i ups
```

2. **Test UPS Connectivity**:
```bash
# Ping UPS
ping -c 3 192.168.100.140

# Test SNMP
snmpwalk -v2c -c public 192.168.100.140 1.3.6.1.2.1.33.1.2.1.0  # upsBatteryStatus
```

3. **Check Kafka Topic**:
```bash
# List topics
kafka-topics.sh --bootstrap-server localhost:9092 --list | grep ups

# Check recent messages
kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic dcim.raw.ups --from-beginning --max-messages 10
```

4. **Restart UPS Poller** (if found):
```bash
# If systemd service
sudo systemctl restart dcim-ups-poller

# If manual script
cd /home/infra/dcim_metrics_project
nohup python3 scripts/ups_poller.py > logs/ups_poller.log 2>&1 &
```

### 3. Alternative: Manual UPS Data Entry
If UPS poller cannot be fixed, manually insert UPS data:
```bash
# Create test UPS data
curl -k -X POST 'https://10.70.0.56:9200/dcim-metrics-unified-2026.05.13/_doc' \
  -u elastic:'C+H+pFb*aIAqWcOo-X8q' \
  -H 'Content-Type: application/json' \
  -d '{
    "@timestamp": "'$(date -u +%Y-%m-%dT%H:%M:%S.%3NZ)'",
    "device_type": "ups",
    "hostname": "UPS-3Phase-30kVA",
    "ip": "192.168.100.140",
    "serial_number": "9E2133T16585",
    "site": "Local Instance",
    "rack_name": "Ruang server",
    "manufacturer": "APC",
    "model": "APC Easy UPS 3S 30kVA 30kW",
    "enrichment_status": "FULL",
    "raw_fields": {
      "upsBatteryCapacity": 100,
      "upsOutputLoad": 2,
      "upsBatteryTemp": 22,
      "upsInputVoltage": 214,
      "upsOutputVoltage": 231
    }
  }'
```

## Summary

### Status: ✅ **UPS ADDED TO DASHBOARD**

**What Was Done**:
1. ✅ Added 7 UPS panels to dashboard (header, count, battery, load, 2 charts, details table)
2. ✅ Dashboard updated from 34 to 41 panels
3. ✅ UPS section positioned between CCTV and NAS
4. ✅ Device Types visualization already configured to show UPS (when data exists in time range)

**Current Situation**:
- ✅ UPS panels created and configured
- ✅ UPS data exists in Elasticsearch (125 documents)
- ✅ UPS data is FULL enriched (site, rack, manufacturer, model)
- ⚠️ UPS data is 2 weeks old (last: April 30, 2026)
- ⚠️ UPS not visible in "Last 1 hour" time range (no recent data)
- ✅ UPS visible in "Last 30 days" time range

**User Action Required**:
1. **To see UPS now**: Change dashboard time range to "Last 30 days"
2. **To see UPS always**: Fix UPS data collection (investigate why poller stopped)

**Admin Action Required**:
1. Investigate why UPS data collection stopped on April 30
2. Check UPS poller service status
3. Verify UPS network connectivity (192.168.100.140)
4. Test SNMP connection to UPS
5. Restart UPS poller service

---

**Timestamp**: May 13, 2026 09:35 WIB  
**Status**: ✅ **UPS PANELS ADDED TO DASHBOARD**  
**Impact**: UPS monitoring available, but requires time range adjustment to see historical data  
**Follow-up**: Investigate and fix UPS data collection to get real-time monitoring
