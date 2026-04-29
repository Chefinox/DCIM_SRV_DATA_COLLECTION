# 20. Contoh Data Aktual per Tahap Pipeline

**Versi Dokumen**: 1.0 | **Terakhir Diperbarui**: April 2026  
**Status**: Data diambil langsung dari sistem produksi (live sampling)

Dokumen ini menampilkan contoh data **aktual** yang mengalir di setiap tahap pipeline DCIM, mulai dari pengiriman Telegraf ke Kafka, proses normalisasi, pengayaan, hingga penyimpanan akhir di Elasticsearch dan PostgreSQL.

---

## Alur Data Ringkas

```
Perangkat Fisik
    ↓ (SNMP / Redfish / ISAPI)
Telegraf Producer
    ↓ JSON Mentah
[Kafka] dcim.raw.<kategori>
    ↓ Dikonsumsi
dcim-normalizer.service (Python)
    ↓ CDM JSON
[Kafka] dcim.normalized.events
    ↓ Dikonsumsi
Apache NiFi → Enrichment API → Redis
    ↓ CDM JSON + Metadata CMDB
[Kafka] dcim.enriched.events
    ↓ Dikonsumsi paralel
Elasticsearch (dcim-enriched-*)  ←→  PostgreSQL (device_metrics)
```

---

## 1. Network Switch (MikroTik)

### 🔵 Stage 1 — RAW (Telegraf → `dcim.raw.network.snmp`)

Data mentah dari Telegraf SNMP polling. Berisi tag Telegraf internal (`host` = nama server kolektor, bukan perangkat target) dan field OID langsung.

```json
{
  "name": "dcim_network_storage",
  "tags": {
    "host": "srv-rnd-dcim-consumer",
    "hostname": "FIT-Core-RTR",
    "ip": "172.16.35.1",
    "model": "RouterOS CCR2004-16G-2S+",
    "serial_number": "HC707RR1T60",
    "firmware": "7.16.2",
    "category": "infrastructure",
    "device_type": "mikrotik",
    "hrStorageIndex": "65536",
    "storageDescr": "main memory"
  },
  "fields": {
    "storageSize": 4194304,
    "storageUsed": 774016,
    "storage_type": "RAM"
  },
  "timestamp": 1777298880
}
```

> **Catatan**: Tag `host` berisi nama server Telegraf, bukan perangkat. `category: infrastructure` adalah tag lama yang tersisa — akan dibuang oleh normalizer.

---

### 🟡 Stage 2 — NORMALIZED (`dcim.normalized.events`)

Setelah diproses `dcim-normalizer.service`. Tag `host` dibuang, `hostname` dari perangkat dipetakan ke root, `event_time` ditambahkan, `device_type` diinferensi.

```json
{
  "event_id": "f23e7448-7f29-44c7-ab50-f15a13d3b61a",
  "event_time": "2026-04-28T03:37:13+00:00",
  "timestamp": 1777347433,
  "source_topic": "dcim.raw.network.snmp",
  "measurement": "dcim_network_storage",
  "device_type": "network_switch",
  "hostname": "FIT-Core-SW",
  "ip": "172.16.35.2",
  "serial_number": "HFH09B9A7A3",
  "metric_name": "general_metric",
  "metric_value": null,
  "metric_unit": null,
  "severity": "info",
  "raw_fields": {
    "storageSize": 131072,
    "storageUsed": 62144,
    "storage_type": "RAM"
  },
  "raw_tags": {
    "firmware": "7.16.2",
    "hostname": "FIT-Core-SW",
    "hrStorageIndex": "65536",
    "ip": "172.16.35.2",
    "model": "RouterOS CRS326-24S+2Q+",
    "serial_number": "HFH09B9A7A3",
    "storageDescr": "main memory"
  }
}
```

> **Yang berubah dari RAW**: `host` dihapus, `device_type` diubah dari `mikrotik` → `network_switch` (dari topic prefix), `event_id` dan `event_time` ditambahkan, semua field dipindah ke `raw_fields`.

---

### 🟢 Stage 3 — ENRICHED (`dcim.enriched.events`)

Setelah NiFi memanggil Enrichment API. Metadata CMDB (site, rack, manufacturer) disuntikkan ke dalam event.

```json
{
  "event_id": "05d275f5-d672-45ca-aac4-6277894d177f",
  "event_time": "2026-04-28T03:43:03+00:00",
  "timestamp": 1777347783,
  "source_topic": "dcim.raw.network.interfaces",
  "measurement": "interface",
  "device_type": "network_switch",
  "hostname": "FIT-DIST-SW-SERVER2",
  "ip": "172.16.35.6",
  "serial_number": "HEM08K3K7VW",
  "metric_name": "interface_status",
  "metric_value": 1,
  "metric_unit": "status_code",
  "severity": "info",
  "raw_fields": {
    "ifAdminStatus": 1,
    "ifDescr": "combo3",
    "ifInOctets": 1555239067,
    "ifOperStatus": 1,
    "ifOutOctets": 3766575171,
    "ifSpeed": 0,
    "if_name": "combo3",
    "if_oper_status": 1
  },
  "raw_tags": {
    "firmware": "7.15.1",
    "hostname": "FIT-DIST-SW-SERVER2",
    "ifIndex": "12",
    "ip": "172.16.35.6",
    "model": "RouterOS CRS312-4C+8XG",
    "serial_number": "HEM08K3K7VW"
  },
  "site": "Local Instance",
  "rack_name": "Rack Server 2",
  "rack_position": 40,
  "room_name": "FIT-HeadOffice Room",
  "manufacturer": "MikroTik",
  "model": "CRS312-4C+8XG-RM",
  "asset_status": "in use",
  "environment": "Production",
  "business_unit": "IT Infrastructure Departement",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:46.174284",
  "cached_at": "2026-04-28T03:25:10.968253"
}
```

---

### 🔵 Stage 4A — ELASTICSEARCH (`dcim-enriched-2026.04.28`)

Dokumen yang diindeks oleh Telegraf Consumer dari `dcim.enriched.events`.

```json
{
  "@timestamp": "2026-04-28T03:18:08Z",
  "measurement_name": "interface",
  "interface": {
    "ifAdminStatus": 1,
    "ifOperStatus": 1,
    "ifInOctets": 4125590499,
    "ifOutOctets": 33525854,
    "if_name": "sfp-sfpplus1",
    "if_oper_status": 1,
    "ifSpeed": 0,
    "ifMtu": 1500
  },
  "tag": {
    "device_type": "network_switch",
    "enrichment_status": "FULL",
    "hostname": "FIT-DIST-SW-SERVER1",
    "ip": "172.16.35.5",
    "manufacturer": "MikroTik",
    "metric_name": "interface_status",
    "rack_name": "Rack Server 2",
    "serial_number": "HF809EP9TTE",
    "severity": "info",
    "site": "Local Instance",
    "source_topic": "dcim.raw.network.interfaces"
  }
}
```

---

### 🟠 Stage 4B — POSTGRESQL (`device_metrics`)

Baris di tabel `device_metrics` yang diisi oleh `dcim-sql-consumer.service`.

```json
{
  "id": "100120",
  "collected_at": "2026-04-28 03:40:42+00:00",
  "hostname": "FIT-DIST-SW",
  "serial_number": "HFH09B9A7A3",
  "ip_address": "172.16.35.2",
  "device_type": "mikrotik",
  "category": "infrastructure",
  "manufacturer": "MikroTik",
  "model": "CRS326-24S+2Q+",
  "firmware_version": "7.16.2",
  "inventory_source": "snmp",
  "site": "FIT-Head-Office",
  "rack_name": "Rack Server 1",
  "status": "OK",
  "power_state": "On",
  "enrichment_status": "FULL",
  "metric_utilization": "54%",
  "metric_temperature": "3.9 C",
  "metric_power_watts": "N/A",
  "metric_health": "OK",
  "metric_status_detail": "CPU Load: 54%"
}
```

---

## 2. UPS (APC Smart-UPS)

### 🔵 Stage 1 — RAW (`dcim.raw.power.ups`)

```json
{
  "name": "ups_apc",
  "tags": {
    "host": "srv-rnd-dcim-consumer",
    "hostname": "UPS-FIT",
    "ip": "192.168.100.140",
    "model": "30KH",
    "serial_number": "9E2133T16585",
    "firmware": "V6.042/040",
    "device_type": "ups",
    "category": "infrastructure",
    "ci_id": "9E2133T16585",
    "enrichment_status": "PARTIAL",
    "site": "FIT-Head-Office",
    "rack_name": "Unknown",
    "location": "Server Room",
    "manufacturer": "APC",
    "inventory_source": "snmp"
  },
  "fields": {
    "battery_capacity": 100,
    "battery_temp": 0,
    "output_load": 0,
    "status": 2,
    "system_name": "UPS-FIT"
  },
  "timestamp": 1777298880
}
```

> **Catatan**: Data raw UPS ini masih mengandung sisa tag enrichment lama (`enrichment_status: PARTIAL`, `site`, `rack_name: Unknown`) yang diinjeksikan oleh pipeline lama. Tag ini diabaikan oleh normalizer dan akan ditimpa oleh enrichment baru.

---

### 🟡 Stage 2 — NORMALIZED (`dcim.normalized.events`)

```json
{
  "event_id": "d2a5e6fb-95a7-413f-8f72-af3d2ed6967f",
  "event_time": "2026-04-28T03:43:01+00:00",
  "timestamp": 1777347781,
  "source_topic": "dcim.raw.power.ups",
  "measurement": "ups_apc",
  "device_type": "ups",
  "hostname": "UPS-FIT",
  "ip": "192.168.100.140",
  "serial_number": "9E2133T16585",
  "metric_name": "battery_capacity",
  "metric_value": 100,
  "metric_unit": "percent",
  "severity": "info",
  "raw_fields": {
    "upsBatteryCapacity": 100,
    "upsBatteryRuntime": 506,
    "upsBatteryStatus": 2,
    "upsBatteryTemp": 23,
    "upsFirmware": "V6.042/040",
    "upsInputVoltage": 228,
    "upsModel": "30KH",
    "upsOutputFrequency": 499,
    "upsOutputLoad": 2,
    "upsOutputStatus": 3,
    "upsOutputVoltage": 231,
    "upsSecondsOnBattery": 0,
    "upsSerial": "9E2133T16585",
    "sysDescr": "UPS-FIT",
    "sysUpTime": 25299585
  },
  "raw_tags": {
    "device_type": "ups",
    "firmware": "V6.042/040",
    "hostname": "UPS-FIT",
    "ip": "192.168.100.140",
    "model": "30KH",
    "serial_number": "9E2133T16585"
  }
}
```

> **Yang berubah dari RAW**: `metric_name` dipetakan ke `battery_capacity` (dari `metric_mapping.json`), `metric_value: 100` diambil dari `upsBatteryCapacity`, tag legacy enrichment dibuang, `host` dihapus.

---

### 🟢 Stage 3 — ENRICHED (`dcim.enriched.events`)

```json
{
  "event_id": "d2a5e6fb-95a7-413f-8f72-af3d2ed6967f",
  "event_time": "2026-04-28T03:43:01+00:00",
  "timestamp": 1777347781,
  "source_topic": "dcim.raw.power.ups",
  "measurement": "ups_apc",
  "device_type": "ups",
  "hostname": "FALAH01-UPS-3Phase-30kVA",
  "ip": "192.168.100.140",
  "serial_number": "9E2133T16585",
  "metric_name": "battery_capacity",
  "metric_value": 100,
  "metric_unit": "percent",
  "severity": "info",
  "raw_fields": {
    "upsBatteryCapacity": 100,
    "upsBatteryRuntime": 506,
    "upsBatteryTemp": 23,
    "upsInputVoltage": 228,
    "upsOutputLoad": 2,
    "upsOutputVoltage": 231,
    "upsSecondsOnBattery": 0
  },
  "raw_tags": {
    "device_type": "ups",
    "firmware": "V6.042/040",
    "hostname": "UPS-FIT",
    "ip": "192.168.100.140",
    "model": "30KH",
    "serial_number": "9E2133T16585"
  },
  "site": "Local Instance",
  "rack_name": "Ruang server",
  "rack_position": 1,
  "room_name": "FIT-HeadOffice Room",
  "manufacturer": "APC",
  "model": "APC Easy UPS 3S 30kVA 30kW (E3SUPS30KHB + E3SBT4)",
  "asset_status": "in use",
  "environment": "Production",
  "business_unit": "Facility Management Department",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:54.712660",
  "cached_at": "2026-04-28T03:25:10.949598"
}
```

> **Yang bertambah dari NORMALIZED**: `site`, `rack_name`, `rack_position`, `room_name`, `manufacturer`, `model` (full name), `asset_status`, `environment`, `business_unit`, `enrichment_status: FULL`. `hostname` di root juga diperbarui menggunakan nama aset dari CMDB (`FALAH01-UPS-3Phase-30kVA`).

---

## 3. NAS (Synology)

### 🔵 Stage 1 — RAW (`dcim.raw.storage.nas`)

```json
{
  "name": "nas_snmp",
  "tags": {
    "host": "srv-rnd-dcim-consumer",
    "hostname": "NAS-FAT",
    "ip": "10.50.0.107",
    "model": "DS220+",
    "serial_number": "2230RLRHB9A4J",
    "firmware": "DSM 7.3-86009",
    "device_type": "nas",
    "category": "storage"
  },
  "fields": {
    "system_temp": 33
  },
  "timestamp": 1777300620
}
```

---

### 🟡 Stage 2 — NORMALIZED (`dcim.normalized.events`)

```json
{
  "event_id": "891fd1cf-ef5b-47c1-a0b9-de5d0614dac9",
  "event_time": "2026-04-28T03:43:00+00:00",
  "timestamp": 1777347780,
  "source_topic": "dcim.raw.storage.nas",
  "measurement": "dcim_nas",
  "device_type": "nas",
  "hostname": "NAS-CD02",
  "ip": "10.50.0.110",
  "serial_number": "2270SBRXKZY8V",
  "metric_name": "disk_temperature",
  "metric_value": 30,
  "metric_unit": "celsius",
  "severity": "info",
  "raw_fields": {
    "diskModel": "WD40EFPX-68C6CN0",
    "diskStatus": 1,
    "diskTemp": 30
  },
  "raw_tags": {
    "category": "storage",
    "device_type": "nas",
    "diskID": "Disk 3",
    "firmware": "DSM 7.2-72806",
    "hostname": "NAS-CD02",
    "ip": "10.50.0.110",
    "model": "DS920+",
    "serial_number": "2270SBRXKZY8V"
  }
}
```

> **Yang berubah**: `metric_name` → `disk_temperature`, `metric_value` → `30` (dari `diskTemp`), `metric_unit` → `celsius`.

---

### 🟢 Stage 3 — ENRICHED (`dcim.enriched.events`)

```json
{
  "event_id": "891fd1cf-ef5b-47c1-a0b9-de5d0614dac9",
  "event_time": "2026-04-28T03:43:00+00:00",
  "timestamp": 1777347780,
  "source_topic": "dcim.raw.storage.nas",
  "measurement": "dcim_nas",
  "device_type": "nas",
  "hostname": "NAS-CD02",
  "ip": "10.50.0.110",
  "serial_number": "2270SBRXKZY8V",
  "metric_name": "disk_temperature",
  "metric_value": 30,
  "metric_unit": "celsius",
  "severity": "info",
  "raw_fields": {
    "diskModel": "WD40EFPX-68C6CN0",
    "diskStatus": 1,
    "diskTemp": 30
  },
  "raw_tags": {
    "diskID": "Disk 3",
    "firmware": "DSM 7.2-72806",
    "hostname": "NAS-CD02",
    "ip": "10.50.0.110",
    "model": "DS920+",
    "serial_number": "2270SBRXKZY8V"
  },
  "site": "Local Instance",
  "rack_name": "Rack Server 2",
  "rack_position": 1,
  "room_name": "FIT-HeadOffice Room",
  "manufacturer": "Synology",
  "model": "DS220+",
  "asset_status": "in use",
  "environment": "Production",
  "business_unit": "IT Infrastructure Departement",
  "enrichment_status": "FULL",
  "enrichment_match_method": "serial_number",
  "enrichment_match_confidence": "high",
  "last_modified_cmdb": "2026-03-10T02:25:54.341710",
  "cached_at": "2026-04-28T03:25:10.949088"
}
```

---

## 4. CCTV (Hikvision)

### 🔵 Stage 1 — RAW (`dcim.raw.device.isapi`)

```json
{
  "name": "cctv_metrics",
  "tags": {
    "host": "srv-rnd-dcim-consumer",
    "hostname": "unknown",
    "ip": "192.168.1.5",
    "model": "unknown",
    "serial_number": "NO_SN"
  },
  "fields": {
    "status_online": 0,
    "status_text": "Offline"
  },
  "timestamp": 1777322580
}
```

> **Catatan**: Perangkat CCTV yang tidak dapat dijangkau via ISAPI muncul dengan `hostname: unknown` dan `serial_number: NO_SN`. Ini adalah perangkat offline.

---

### 🟡 Stage 2 — NORMALIZED

```json
{
  "event_id": "645a5cce-40e8-4442-8465-923e7a21f9e0",
  "event_time": "2026-04-27T20:43:00+00:00",
  "timestamp": 1777322580,
  "source_topic": "dcim.raw.device.isapi",
  "measurement": "cctv_metrics",
  "device_type": "cctv",
  "hostname": "unknown",
  "ip": "192.168.1.5",
  "serial_number": "NO_SN",
  "metric_name": "general_metric",
  "metric_value": null,
  "metric_unit": null,
  "severity": "info",
  "raw_fields": {
    "status_online": 0,
    "status_text": "Offline"
  },
  "raw_tags": {
    "hostname": "unknown",
    "ip": "192.168.1.5",
    "model": "unknown",
    "serial_number": "NO_SN"
  }
}
```

> **Yang berubah**: `device_type` diinferensi dari topik `dcim.raw.device.isapi` → `cctv`. `serial_number: NO_SN` dipertahankan karena memang tidak ada.

---

### 🟢 Stage 3 — ENRICHED

```json
{
  "event_id": "645a5cce-40e8-4442-8465-923e7a21f9e0",
  "event_time": "2026-04-27T20:43:00+00:00",
  "timestamp": 1777322580,
  "source_topic": "dcim.raw.device.isapi",
  "measurement": "cctv_metrics",
  "device_type": "cctv",
  "hostname": "unknown",
  "ip": "192.168.1.5",
  "serial_number": "NO_SN",
  "metric_name": "general_metric",
  "metric_value": null,
  "metric_unit": null,
  "severity": "info",
  "raw_fields": {
    "status_online": 0,
    "status_text": "Offline"
  },
  "site": "FIT-Head-Office",
  "rack_name": "Unknown",
  "manufacturer": "Epson",
  "model": "WorkForce WF-7710",
  "enrichment_status": "NO_IDENTIFIER",
  "enrichment_match_method": "hostname_fallback",
  "enrichment_match_confidence": "low"
}
```

> **Catatan**: `enrichment_status: NO_IDENTIFIER` karena `serial_number = NO_SN`. API Enrichment mencoba fallback via hostname tapi mendapat data salah (`Epson WorkForce`) — ini menunjukkan bahwa hostname `unknown` tidak bisa dijadikan kunci lookup yang andal.

---

## 5. Ringkasan Perubahan per Tahap

| Field | RAW | NORMALIZED | ENRICHED |
|:---|:---|:---|:---|
| `event_id` | ❌ | ✅ UUID v4 baru | ✅ Sama |
| `event_time` | ❌ | ✅ ISO-8601 UTC | ✅ Sama |
| `host` (Telegraf internal) | ✅ Ada | ❌ Dihapus | ❌ Tidak ada |
| `hostname` | Di dalam `tags` | ✅ Di root (device) | ✅ Di root (bisa diperbarui dari CMDB) |
| `device_type` | Bervariasi/tidak ada | ✅ Terstandar | ✅ Sama |
| `metric_name` | ❌ | ✅ Dari mapping JSON | ✅ Sama |
| `metric_value` | Di dalam `fields` | ✅ Di root | ✅ Sama |
| `site` | ❌ / Tidak akurat | ❌ | ✅ Dari CMDB |
| `rack_name` | ❌ / Tidak akurat | ❌ | ✅ Dari CMDB |
| `manufacturer` | ❌ | ❌ | ✅ Dari CMDB |
| `enrichment_status` | ❌ / Lama | ❌ | ✅ `FULL` / `NO_IDENTIFIER` |
| `raw_fields` | Tidak terstruktur | ✅ Objek terpisah | ✅ Sama |

---

## 6. Query untuk Validasi di pgAdmin

Hubungkan ke `192.168.101.73:5432` > Database `dcim_sot` > Jalankan query:

```sql
-- Lihat 10 data terbaru per device type
SELECT
    collected_at,
    hostname,
    device_type,
    serial_number,
    site,
    rack_name,
    enrichment_status,
    metric_utilization,
    metric_temperature,
    metric_health
FROM device_metrics
ORDER BY collected_at DESC
LIMIT 10;

-- Distribusi enrichment status
SELECT enrichment_status, device_type, COUNT(*) as jumlah
FROM device_metrics
GROUP BY enrichment_status, device_type
ORDER BY enrichment_status;

-- Perangkat yang tidak ter-enrich dengan baik
SELECT hostname, device_type, serial_number, enrichment_status, collected_at
FROM device_metrics
WHERE enrichment_status != 'FULL'
ORDER BY collected_at DESC;
```

---

**Referensi Implementasi**: `dcim_normalizer.py`, `enrichment_api.py`, `telegraf-consumer.conf`  
**Referensi Dokumen**: [13-telemetry-sources-identification.md](./13-telemetry-sources-identification.md), [14-standardization-telemetry-schema.md](./14-standardization-telemetry-schema.md), [19-kafka-pipeline-architecture.md](./19-kafka-pipeline-architecture.md)
