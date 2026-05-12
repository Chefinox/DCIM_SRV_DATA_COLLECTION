# Raw Data from Devices

## Overview

This document shows the **exact raw payloads** that each device returns when queried by a collector. This is the data before any transformation or field-mapping is applied.

---

## 1. APC UPS — SNMPv3 Raw Response

**Queried by:** Telegraf `inputs.snmp`
**Endpoint:** `192.168.100.140:161`
**Protocol:** SNMPv3, Auth: SHA, Privacy: AES

When Telegraf polls a single OID (e.g. `battery_capacity`), the SNMPv3 decrypted response looks like:

```
SNMP Response PDU
  Version:      3
  Community:    (not used in v3, replaced by user context)
  User:         hndept
  Request-ID:   1234567
  Error-Status: noError (0)
  Variable Bindings:
    OID   = .1.3.6.1.4.1.318.1.1.1.2.2.1.0
    Type  = INTEGER
    Value = 100
```

Telegraf sends **one GET request per configured OID** per interval. A full poll cycle for our UPS config returns 8 individual integer/string values.

| OID Queried | Raw Type | Example Value |
|---|---|---|
| `.1.3.6.1.4.1.318.1.1.1.1.1.1.0` | STRING | `"Smart-UPS 750"` |
| `.1.3.6.1.4.1.318.1.1.1.4.1.1.0` | INTEGER | `2` (= OnLine) |
| `.1.3.6.1.4.1.318.1.1.1.2.2.1.0` | INTEGER | `100` (= 100%) |
| `.1.3.6.1.4.1.318.1.1.1.2.2.3.0` | TIMETICKS | `6000` (= 60 min) |
| `.1.3.6.1.4.1.318.1.1.1.2.2.2.0` | INTEGER | `28` (= 28°C) |
| `.1.3.6.1.4.1.318.1.1.1.3.2.1.0` | INTEGER | `230` (= 230V) |
| `.1.3.6.1.4.1.318.1.1.1.4.2.1.0` | INTEGER | `230` (= 230V) |
| `.1.3.6.1.4.1.318.1.1.1.4.2.3.0` | INTEGER | `35` (= 35% load) |

---

## 2. Lenovo Servers — Redfish JSON Response

**Queried by:** Telegraf `inputs.redfish`
**Endpoint:** `https://10.50.0.x/redfish/v1/`
**Protocol:** HTTPS Basic Auth

The Telegraf Redfish plugin fetches raw JSON from multiple BMC endpoints. A typical response from `/redfish/v1/Chassis/1/Thermal` looks like:

```json
{
    "@odata.type": "#Thermal.v1_4_0.Thermal",
    "Temperatures": [
        {
            "Name": "Ambient Temp",
            "ReadingCelsius": 24,
            "Status": { "State": "Enabled", "Health": "OK" }
        },
        {
            "Name": "CPU 1 Temp",
            "ReadingCelsius": 48,
            "Status": { "State": "Enabled", "Health": "OK" }
        }
    ],
    "Fans": [
        {
            "FanName": "Fan 1 Front Tach",
            "Reading": 7790,
            "ReadingUnits": "RPM",
            "Status": { "State": "Enabled", "Health": "OK" }
        }
    ]
}
```

---

## 3. Security System — Hikvision ISAPI (XML)

**Queried by:** Python script `hikvision_poller.py`
**Targets:** 
- NVR: `192.168.1.254`
- CCTV: `192.168.1.x` (23 cameras)
**Protocol:** HTTP, Digest Auth

The NVR and Cameras return all responses in **XML format** using the Hikvision namespace schema.

### 3.1 Device Info (/ISAPI/System/deviceInfo)

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DeviceInfo version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
    <deviceName>Hikvision NVR</deviceName>
    <deviceID>f0e5b1c0-3d2a-11ee-be56-0242ac120002</deviceID>
    <deviceDescription>Network Video Recorder</deviceDescription>
    <deviceLocation>Server Room</deviceLocation>
    <model>DS-7716NI-Q4</model>
    <serialNumber>DS-7716NI-Q420200101BBWR123456789WCVU</serialNumber>
    <macAddress>8c:e7:48:ab:cd:ef</macAddress>
    <firmwareVersion>V4.62.210</firmwareVersion>
    <firmwareReleasedDate>2022-11-15</firmwareReleasedDate>
    <encoderVersion>V7.3</encoderVersion>
</DeviceInfo>
```

System status endpoint (`/ISAPI/System/status`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<DeviceStatus version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
    <currentDeviceTime>2026-04-10T12:00:00+07:00</currentDeviceTime>
    <deviceUpTime>864000</deviceUpTime>
    <CPUList>
        <CPU>
            <cpuDescription>Main processor</cpuDescription>
            <cpuUtilization>12</cpuUtilization>
        </CPU>
    </CPUList>
    <MemoryList>
        <Memory>
            <memoryDescription>DDR RAM</memoryDescription>
            <memoryUsage>45</memoryUsage>
            <memoryAvailable>8192</memoryAvailable>
        </Memory>
    </MemoryList>
</DeviceStatus>
```

### 3.4 Camera Channel Status (/ISAPI/Streaming/channels)

Individual cameras provide streaming metadata including resolution and bitrate:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<StreamingChannelList version="2.0" xmlns="http://www.hikvision.com/ver20/XMLSchema">
    <StreamingChannel>
        <id>101</id>
        <channelName>Main Stream</channelName>
        <enabled>true</enabled>
        <Video>
            <videoCodecType>H.265</videoCodecType>
            <videoResolutionWidth>2560</videoResolutionWidth>
            <videoResolutionHeight>1440</videoResolutionHeight>
            <vbrUpperCap>4096</vbrUpperCap>
        </Video>
    </StreamingChannel>
</StreamingChannelList>
```

> **Note:** Hikvision exclusively uses XML. The Python poller parses this into a unified JSON schema before sending to the `cctv-metrics-*` index in Elasticsearch.

---

## 4. Mikrotik Switches — SNMPv2c Raw Response

**Queried by:** Telegraf `inputs.snmp`
**Endpoint:** `172.16.35.1-6:161`
**Protocol:** SNMPv2c, community: `public`

For interface traffic tables, Telegraf requests the entire `ifXTable` (OID `1.3.6.1.2.1.31.1.1`) and receives one row per interface:

```
SNMP Response PDU — GetNext (table walk)
  Variable Bindings:
    1.3.6.1.2.1.31.1.1.1.1.1  = STRING: "ether1"        (ifName)
    1.3.6.1.2.1.31.1.1.1.15.1 = Gauge32: 1000000000      (ifHighSpeed bps)
    1.3.6.1.2.1.31.1.1.1.6.1  = Counter64: 9823746123    (ifHCInOctets)
    1.3.6.1.2.1.31.1.1.1.10.1 = Counter64: 7264891034    (ifHCOutOctets)
    1.3.6.1.2.1.2.2.1.14.1    = Counter32: 0             (ifInErrors)
    1.3.6.1.2.1.2.2.1.20.1    = Counter32: 0             (ifOutErrors)
```

One response block is returned **per physical interface** per device (e.g. ether1…ether48 for a 48-port switch).
