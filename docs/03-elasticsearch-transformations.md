# Data Transformation to Elasticsearch

## Overview

Raw metric data from physical devices goes through a series of transformations before it is stored in Elasticsearch.
This document explains each transformation step and shows a before/after comparison for each category.

---

## Transformation Pipeline

```
  Device Raw Output
        │
        ▼
  [Step 1] Protocol Decode
  (SNMP binary → integers/strings, Redfish JSON → dict, Hikvision XML → dict)
        │
        ▼
  [Step 2] Field Mapping
  (OID → human-readable name, e.g. ".1.3.6.1.4.1.318.1.1.1.2.2.1.0" → "battery_capacity")
        │
        ▼
  [Step 3] Flattening
  (Nested arrays/objects → flat key-value pairs)
        │
        ▼
  [Step 4] Metadata Tagging
  (Add @timestamp, category: "security system", device_type, ip)
        │
        ▼
  [Step 5] Elasticsearch Indexing
  (HTTP POST to https://10.70.0.56:9200/<index>/_doc)
```

---

## Common Metadata Fields Added to every Document

Regardless of source category, these fields are injected into **every** Elasticsearch document:

| Field | Source | Example Value | Description |
|---|---|---|---|
| `@timestamp` | Collector | `2026-04-10T07:30:01.219Z` | Time of collection (UTC, ISO 8601) |
| `category` | Poller Config | `security system`, `infrastructure` | High-level device grouping |
| `device_type` | Poller Config | `NVR`, `CCTV`, `UPS`, `switch` | Specific device role |
| `ip` | Host/Agent | `192.168.1.254` | Management IP of target |

---

## Category-by-Category Transformation

### 1. APC UPS (SNMP → Elasticsearch)

**Before** (raw SNMP integer from wire):
```
OID .1.3.6.1.4.1.318.1.1.1.2.2.1.0 = INTEGER: 100
```

**After** (stored in `telegraf-metrics-2026.04.10`):
```json
{
    "@timestamp": "2026-04-10T07:30:00.000Z",
    "category": "infrastructure",
    "device_type": "ups",
    "ups_apc": {
        "battery_capacity": 100,
        "battery_temp": 28,
        "battery_runtime_remain": 3600000,
        "input_voltage": 230,
        "output_voltage": 230,
        "output_load": 35,
        "status": 2,
        "model": "Smart-UPS 750"
    },
    "ip": "192.168.100.140"
}
```

---

### 2. Lenovo Servers (Redfish → Telegraf → Elasticsearch)

**Before** (Raw JSON response from `/redfish/v1/Chassis/1/Thermal`):
```json
{
    "Temperatures": [
        {
            "Name": "Inlet Temp",
            "ReadingCelsius": 24,
            "Status": { "State": "Enabled", "Health": "OK" }
        }
    ],
    "Fans": [
        {
            "FanName": "Fan 1",
            "Reading": 7800,
            "ReadingUnits": "RPM"
        }
    ]
}
```

**After** (stored in `telegraf-metrics-2026.04.13`):
```json
{
    "@timestamp": "2026-04-13T07:30:00Z",
    "category": "infrastructure",
    "device_type": "server",
    "host": "server-HCI-01",
    "ip": "10.50.0.2",
    "server_redfish": {
        "Inlet_Temp_Celsius": 24,
        "Fan_1_RPM": 7800,
        "Power_Consumption_Watts": 145
    }
}
```

---

### 3. Security System (XML → JSON → Elasticsearch)

**Before** (raw XML string from `/ISAPI/System/deviceInfo`):
```xml
<DeviceInfo>
    <model>DS-7716NI-Q4</model>
    <firmwareVersion>V4.62.210</firmwareVersion>
    <deviceUpTime>864000</deviceUpTime>
</DeviceInfo>
```

**After** (stored in `cctv-metrics-2026.04.10`):
```json
{
    "@timestamp": "2026-04-10T07:30:01.219Z",
    "category": "security system",
    "device_type": "NVR",
    "ip": "192.168.1.254",
    "status": "Online",
    "device_info": {
        "model": "DS-7716NI-Q4",
        "firmwareVersion": "V4.62.210"
    },
    "system_status": {
        "cpuUtilization": "12",
        "memoryUsage": "45"
    }
}
```

| Transformation Applied | Detail |
|---|---|
| XML → JSON | Python `xml.etree.ElementTree` parses XML tags into dict keys |
| Grouping | `device_info` and `system_status` keys nest related fields |
| Unified Category | Inject `category: "security system"` for unified dashboard filtering |

---

### 4. Mikrotik Switches (SNMP Table → Elasticsearch)

**Before** (SNMP table walk — one row per interface):
```
1.3.6.1.2.1.31.1.1.1.1.1  = STRING: "ether1"
1.3.6.1.2.1.31.1.1.1.6.1  = Counter64: 9823746123
1.3.6.1.2.1.31.1.1.1.10.1 = Counter64: 7264891034
```

**After** (one document per interface in `telegraf-metrics-2026.04.10`):
```json
{
    "@timestamp": "2026-04-09T01:16:07Z",
    "category": "infrastructure",
    "device_type": "switch",
    "ip": "172.16.35.3",
    "net_interface": {
        "if_name": "ether1",
        "if_speed": 1000000000,
        "if_in_octets": 9823746123,
        "if_out_octets": 7264891034
    }
}
```
