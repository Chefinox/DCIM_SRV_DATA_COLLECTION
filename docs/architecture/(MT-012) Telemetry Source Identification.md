# (MT-012) Telemetry Source Identification

# 1. Overview

## Objective

Mengidentifikasi dan mendokumentasikan semua sumber data telemetri yang masuk ke platform DCIM, mencakup:

* Inventarisasi seluruh perangkat sumber data (BMS, EPMS, NMS, server, storage, security, cloud)
* Pemetaan protokol komunikasi per sumber (Redfish, SNMP, ISAPI HTTP)
* Pemetaan metode koleksi per sumber (NiFi ExecuteProcess, Telegraf, daemon standalone)
* Baseline format data, interval polling, dan health monitoring per sumber

## Scope

Dokumentasi ini mencakup semua perangkat yang **aktif terkoleksi** pada pipeline DCIM v4.4 di host `srv-rnd-dcim` (10.70.0.56). Total: **49 perangkat** dari **6 kategori**.

***

# 2. Telemetry Source Registry

## 2.1 Ringkasan Perangkat

| Kategori | Jumlah | Vendor | Protokol | Interval |
|----------|--------|--------|----------|----------|
| Server | 5 unit | Lenovo ThinkSystem | Redfish HTTPS | 60s (telemetry), 30s (CPU/mem util) |
| UPS | 1 unit | APC Smart-UPS 30K | SNMP v3 | 60s |
| NAS | 6 unit | Synology DS Series | SNMP v3 | 120s |
| Network Switch | 5 unit | MikroTik CCR/CRS | SNMP v2c | 60s |
| CCTV | 31 channel | Hikvision | ISAPI HTTP | 120s |
| NVR | 1 unit | Hikvision DS-7732 | ISAPI HTTP | 120s |
| **Total** | **49** | | | |

## 2.2 Inventaris Detail — Server

| Hostname | IP | Model | Protokol | Port | Endpoint BMC |
|----------|-------|-------|----------|------|-------------|
| server-HCI-01 | 10.50.0.2 | Lenovo ThinkSystem SR650 V3 | Redfish HTTPS | :443 | XCC (Lenovo XClarity Controller) |
| server-HCI-02 | 10.50.0.3 | Lenovo ThinkSystem SR650 V3 | Redfish HTTPS | :443 | XCC |
| server-HCI-03 | 10.50.0.4 | Lenovo ThinkSystem SR650 V3 | Redfish HTTPS | :443 | XCC |
| server-Render-01 | 10.50.0.5 | Lenovo ThinkSystem SR665 V3 | Redfish HTTPS | :443 | XCC |
| server-Render-02 | 10.50.0.6 | Lenovo ThinkSystem SR665 V3 | Redfish HTTPS | :443 | XCC |

**Redfish Endpoints yang Di-Poll:**

| Endpoint | Data | Interval |
|----------|------|----------|
| `/redfish/v1/Systems/1` | PowerState, Model, BIOS, SerialNumber | 60s |
| `/redfish/v1/Chassis/1/Thermal` | Temperatures (inlet, outlet, CPU) + Fan RPM | 60s |
| `/redfish/v1/Chassis/1/Power` | PSU watt output, PowerControl consumed watts | 60s |
| `/redfish/v1/Systems/1/Oem/Lenovo/Metrics/CPUSubsystemPerformance` | CPU utilization (%) — **Lenovo XCC OEM** | 30s |
| `/redfish/v1/Systems/1/Oem/Lenovo/Metrics/MemorySubsystemPerformance` | Memory utilization (%) — **Lenovo XCC OEM** | 30s |

> **Catatan:** Endpoint CPU/Memory Performance adalah OEM extension Lenovo XCC, **tidak tersedia** di Redfish standar DMTF.

## 2.3 Inventaris Detail — UPS

| Hostname | IP | Model | Protokol | Port | Credential |
|----------|-------|-------|----------|------|-----------|
| UPS-SERVERROOM-01 | 192.168.100.140 | APC Smart-UPS SRT 30K | SNMP v3 | :161 | User: hndept, Auth: SHA, Priv: AES |

**OID yang Di-Poll (30+ OIDs):**

| Kategori | OID Root | Data |
|----------|----------|------|
| PowerNet MIB (APC proprietary) | `.1.3.6.1.4.1.935.1.1.1.*` | Model, status, battery capacity/runtime/temp, input/output voltage/load |
| UPS MIB Standard | `.1.3.6.1.2.1.33.*` | Serial number, firmware, battery status/voltage/current, input/output frequency, per-phase voltage/current/load (L1, L2, L3) |
| System MIB | `.1.3.6.1.2.1.1.*` | sysName, sysLocation, sysDescr |

## 2.4 Inventaris Detail — NAS (Storage)

| Hostname | IP | Model | Protokol | Port | Credential |
|----------|-------|-------|----------|------|-----------|
| NAS-105 | 10.50.0.105 | Synology DS | SNMP v3 | :161 | User: hndept, Auth: SHA, AuthNoPriv |
| NAS-106 | 10.50.0.106 | Synology DS | SNMP v3 | :161 | Sama |
| NAS-107 | 10.50.0.107 | Synology DS | SNMP v3 | :161 | Sama |
| NAS-108 | 10.50.0.108 | Synology DS | SNMP v3 | :161 | Sama |
| NAS-109 | 10.50.0.109 | Synology DS | SNMP v3 | :161 | Sama |
| NAS-110 | 10.50.0.110 | Synology DS | SNMP v3 | :161 | Sama |

**OID yang Di-Poll:**

| Kategori | OID Root | Data |
|----------|----------|------|
| Synology System MIB | `.1.3.6.1.4.1.6574.1.*` | Model, serial number, DSM version, system status |
| Synology Disk MIB | `.1.3.6.1.4.1.6574.2.*` | Disk ID, model, type, temperature, status |
| Synology RAID MIB | `.1.3.6.1.4.1.6574.3.*` | RAID name, status |
| Host Resources MIB | `.1.3.6.1.2.1.25.2.*` | Storage usage (memory, volume size/used) |
| IF-MIB | `.1.3.6.1.2.1.31.1.1.*` | Network interface stats (rx/tx bytes) |

## 2.5 Inventaris Detail — Network Switch

| Hostname | IP | Model | Protokol | Port | Community |
|----------|-------|-------|----------|------|-----------|
| MikroTik-1 | 172.16.35.1 | MikroTik CCR/CRS | SNMP v2c | :161 | public |
| MikroTik-2 | 172.16.35.2 | MikroTik CCR/CRS | SNMP v2c | :161 | public |
| MikroTik-3 | 172.16.35.3 | MikroTik CCR/CRS | SNMP v2c | :161 | public |
| MikroTik-5 | 172.16.35.5 | MikroTik CCR/CRS | SNMP v2c | :161 | public |
| MikroTik-6 | 172.16.35.6 | MikroTik CCR/CRS | SNMP v2c | :161 | public |

**OID yang Di-Poll:**

| Kategori | OID Root | Data |
|----------|----------|------|
| System MIB | `.1.3.6.1.2.1.1` | sysName, sysDescr, sysUpTime |
| IF-MIB | `.1.3.6.1.2.1.2.2` | Interface status (ifOperStatus) |
| ifXTable | `.1.3.6.1.2.1.31.1.1` | Interface stats (rx/tx bytes, errors, speeds) |
| Host Resources | `.1.3.6.1.2.1.25.2` | Storage/memory usage |
| MikroTik Specific | `.1.3.6.1.4.1.14988.1.1.1` | CPU load, temperature |

## 2.6 Inventaris Detail — CCTV & NVR

| Kategori | IP Range | Jumlah | Model | Protokol | Port |
|----------|----------|--------|-------|----------|------|
| CCTV | 192.168.1.2 – 192.168.1.33 (skip .32) | 31 channel | Hikvision DS-2CD | ISAPI HTTP | :80 |
| NVR | 192.168.1.254 | 1 unit | Hikvision DS-7732 | ISAPI HTTP | :80 |

**ISAPI Endpoints yang Di-Poll:**

| Endpoint | Data |
|----------|------|
| `/ISAPI/System/deviceInfo` | Hostname, serial number, model, firmware |
| `/ISAPI/System/status` | CPU utilization, memory usage |
| `/ISAPI/System/Video/inputs/channels/status` | Channel status (online/offline) |

***

# 3. Protocol Capability Matrix

| Sumber | Redfish HTTPS | SNMP v3 | SNMP v2c | ISAPI HTTP | SSH | Modbus | MQTT |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Server Lenovo | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| UPS APC | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| NAS Synology | ❌ | ✅ | ❌ | ❌ | ❌ | ❌ | ❌ |
| Switch MikroTik | ❌ | ❌ | ✅ | ❌ | ✅ (cadangan) | ❌ | ❌ |
| CCTV Hikvision | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |
| NVR Hikvision | ❌ | ❌ | ❌ | ✅ | ❌ | ❌ | ❌ |

***

# 4. Collection Method Mapping

| Sumber | Metode Koleksi | Tool | Skrip/Config | Kafka Topic Output |
|--------|---------------|------|--------------|-------------------|
| Server (telemetry) | NiFi ExecuteProcess | Python | `scripts/redfish_poller.py` | `dcim.raw.hardware.server` |
| Server (CPU/Mem util) | NiFi ExecuteProcess | Python | `scripts/redfish_telemetry_poller.py` | `dcim.raw.hardware.server` |
| Server (inventory) | Cron daily 01:00 | Python | `scripts/server_inventory_collector.py` | `dcim.raw.hardware.server.inventory` |
| UPS | NiFi ExecuteProcess | Python + snmpwalk | `scripts/snmp_ups_poller.py` | `dcim.raw.power.ups` |
| NAS | NiFi ExecuteProcess | Python + snmpwalk | `scripts/nas_poller.py` | `dcim.raw.storage.nas` |
| Network | NiFi ExecuteProcess | Python + snmpwalk | `scripts/mikrotik_poller.py` | `dcim.raw.network.snmp` + `dcim.raw.network.interfaces` |
| CCTV & NVR | Systemd daemon | Python + ISAPI HTTP | `scripts/hikvision_poller_daemon.py` | `dcim.raw.device.isapi` |

**Alasan Pemilihan Metode:**

| Metode | Keunggulan | Digunakan Untuk |
|--------|-----------|----------------|
| NiFi ExecuteProcess | Scheduling terpusat, error handling terintegrasi, backpressure | Server, UPS, NAS, Network |
| Systemd daemon | Lifecycle management stabil, menghindari overhead startup Python berulang | CCTV (31 kamera = long poll cycle) |
| Cron job | One-shot harian, tidak perlu daemon | Server inventory deep scan |

***

# 5. Data Format per Source

Semua poller menghasilkan output dalam format **JSON Telegraf-compatible**:

```json
{
  "name": "<measurement_name>",
  "tags": {
    "hostname": "<device_hostname>",
    "device_type": "<server|ups|nas|network|cctv|nvr>",
    "serial_number": "<serial>",
    "ip": "<ip_address>",
    "model": "<model>",
    "manufacturer": "<vendor>"
  },
  "fields": {
    "<metric_key>": "<metric_value>",
    ...
  },
  "timestamp": <unix_epoch_seconds>
}
```

| Sumber | Measurement Name | Jumlah Fields Tipikal |
|--------|-----------------|----------------------|
| Server Redfish | `server_redfish` | 8–15 (temp, fan, power, health) |
| Server Util | `server_redfish_util` | 2 (cpuUtilization, memoryUsage) |
| Server Inventory | `server_inventory` | 20+ (komponen CPU, RAM, disk, NIC) |
| UPS | `ups_apc` | 30+ (voltage, current, load per fase, battery) |
| NAS | `dcim_nas` + `dcim_nas_volume` | 10–20 (disk temp, volume usage, net stats) |
| Network | `dcim_network` + `interface` | 15–30 (CPU, memory, interface stats) |
| CCTV/NVR | `cctv_metrics` | 5–8 (status, CPU, memory, network) |

***

# 6. Refresh Rate & Health Baseline

## 6.1 Interval Polling

| Sumber | Interval | Throughput Estimasi | Catatan |
|--------|----------|-------------------|---------|
| Server telemetry | 60s | ~5 msg/menit | 5 server × 1 poll/60s |
| Server CPU/Mem | 30s | ~10 msg/menit | 5 server × 1 poll/30s |
| Server inventory | Daily 01:00 | ~5 msg/hari | Deep scan Redfish |
| UPS | 60s | ~1 msg/menit | 1 UPS × 1 poll/60s |
| NAS | 120s | ~3 msg/2menit | 6 NAS × 1 poll/120s |
| Network | 60s | ~10 msg/menit | 5 switch × 2 topics/60s |
| CCTV + NVR | 120s | ~16 msg/2menit | 32 devices × 1 poll/120s |

## 6.2 Health Monitoring

Pipeline kesehatan sumber data dipantau melalui:

1. **Stale Device Detection** (`dcim-threshold-alerter.service`): Perangkat yang tidak mengirim data > 30 menit ditandai sebagai **Critical** alert di ES index `dcim-alerts`
2. **Pipeline Alive Check** (`dcim-telegram-alerter.service`): Jika tidak ada dokumen baru di ES > 2 jam, kirim notifikasi Telegram
3. **Data Quality Audit** (`audit_data_quality.py`): Validasi kelengkapan field per device_type, harian 06:00 WIB

***

# 7. Handover Notes

## Cara Menambah Sumber Data Baru

1. Buat poller script baru di `scripts/` mengikuti format JSON Telegraf-compatible
2. Tambahkan entry di `configs/metric_mapping.json`:
   - `topic_to_device_type`: mapping topik Kafka → device_type
   - `measurement_to_device_type`: mapping measurement name → device_type
3. Buat topik Kafka baru jika diperlukan (via Kafka UI di `:9000`)
4. Konfigurasikan NiFi ExecuteProcess atau systemd service baru
5. Tambahkan entry di `configs/data_quality_schema.yaml` untuk validasi
6. Update threshold alerter jika ada threshold spesifik untuk device type baru

## File Penting

| File | Fungsi |
|------|--------|
| `scripts/redfish_poller.py` | Poller server Lenovo via Redfish API |
| `scripts/redfish_telemetry_poller.py` | Poller CPU/Memory utilization via XCC OEM |
| `scripts/server_inventory_collector.py` | Deep scan inventory server (daily) |
| `scripts/snmp_ups_poller.py` | Poller UPS via SNMP v3 |
| `scripts/nas_poller.py` | Poller NAS Synology via SNMP v3 |
| `scripts/mikrotik_poller.py` | Poller MikroTik switch via SNMP v2c |
| `scripts/hikvision_poller_daemon.py` | Daemon poller CCTV/NVR via ISAPI |
| `configs/metric_mapping.json` | Mapping measurement → device_type + metric rules |
| `configs/data_quality_schema.yaml` | Required fields per device_type |

***

# 8. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial handover documentation |
