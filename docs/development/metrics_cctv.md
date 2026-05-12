# Metric Documentation: Security System (Hikvision)

**Category**: Security System
**Source**: 
- NVR: `192.168.1.254`
- Cameras: `192.168.1.2` through `192.168.1.33` (23 devices)
**Collector**: Python Poller (`hikvision_poller.py`)
**Index**: `cctv-metrics-YYYY.MM.DD`

## 1. NVR Metrics (Aggregated)

| Metric Field | Description | Path |
|---|---|---|
| `device_info.model` | NVR Model Number | /ISAPI/System/deviceInfo |
| `device_info.serialNumber` | NVR Serial Number | /ISAPI/System/deviceInfo |
| `system_status.cpuUtilization` | NVR CPU Usage | /ISAPI/System/status |
| `system_status.memoryUsage` | NVR Memory Usage | /ISAPI/System/status |
| `storage_status` | HDD Health Status (All disks) | /ISAPI/ContentMgmt/Storage/hdd |
| `channels.online_count` | Number of cameras online | /ISAPI/ContentMgmt/InputProxy/channels |

## 2. Direct Camera Metrics (Individual)

| Metric Field | Description | Path |
|---|---|---|
| `device_info.model` | Camera Model (e.g. DS-2CD1043G0E-I) | /ISAPI/System/deviceInfo |
| `device_info.firmwareVersion` | Firmware version | /ISAPI/System/deviceInfo |
| `network.ipAddress` | Camera IP | /ISAPI/System/Network/interfaces |
| `video.resolution` | Stream resolution (e.g. 1920x1080) | /ISAPI/Streaming/channels/101 |
| `video.bitrate` | Current bitrate | /ISAPI/Streaming/channels/101/status |
| `storage.sd_status` | SD Card Health (if present) | /ISAPI/ContentMgmt/Storage/hdd |

**Interval**: Every 1 minute via cron.
