# (MT-013) Standardization of Telemetry Schema

# 1. Overview

## Objective

Menetapkan skema telemetri terpadu (Common Data Model / CDM) untuk semua metrik, log, peristiwa, dan jejak yang mengalir dalam pipeline DCIM, mencakup:

* Definisi skema Avro terstandardisasi: **NormalizedEvent** (18 fields) dan **EnrichedEvent** (26 fields)
* Implementasi **Confluent Schema Registry** untuk validasi skema di broker-level
* Pipeline normalisasi yang mengubah data mentah (multi-format) ke CDM tunggal
* Pipeline enrichment yang menambahkan metadata CMDB ke setiap event
* Mapping rule per device type dan measurement

***

# 2. Common Data Model (CDM)

Pipeline DCIM menggunakan dua skema Avro terdaftar di Confluent Schema Registry:

## 2.1 NormalizedEvent (18 Fields)

Skema ini digunakan di topik `dcim.normalized.events` — output dari Normalizer.

| # | Field | Type | Keterangan |
|---|-------|------|-----------|
| 1 | `event_id` | string | UUID unik per event |
| 2 | `event_time` | string (nullable) | ISO 8601 timestamp event |
| 3 | `timestamp` | long/string/double (nullable) | Unix epoch dari sumber |
| 4 | `source_topic` | string | Kafka topic asal (e.g., `dcim.raw.hardware.server`) |
| 5 | `measurement` | string (nullable) | Nama measurement Telegraf (e.g., `server_redfish`) |
| 6 | `device_type` | string | Tipe perangkat: `server`, `ups`, `nas`, `network_switch`, `cctv`, `nvr` |
| 7 | `hostname` | string | Nama host perangkat |
| 8 | `ip` | string (nullable) | Alamat IP perangkat |
| 9 | `serial_number` | string (nullable) | Serial number perangkat |
| 10 | `metric_name` | string | Nama metrik standar (e.g., `cpu_utilization`, `battery_capacity`) |
| 11 | `metric_value` | double/int/string (nullable) | Nilai metrik utama |
| 12 | `metric_unit` | string (nullable) | Satuan metrik (`celsius`, `percent`, `volt`, dll.) |
| 13 | `severity` | string (nullable) | Level severity: `info`, `warning`, `critical` |
| 14 | `manufacturer` | string (nullable) | Vendor perangkat (e.g., `Lenovo`, `APC`, `Hikvision`) |
| 15 | `model` | string (nullable) | Model perangkat |
| 16 | `firmware` | string (nullable) | Versi firmware |
| 17 | `raw_fields` | string (nullable) | JSON string berisi semua field mentah |
| 18 | `raw_tags` | string (nullable) | JSON string berisi semua tag mentah |

## 2.2 EnrichedEvent (26 Fields)

Skema ini digunakan di topik `dcim.enriched.events` — output dari Enrichment Layer.

Mencakup **seluruh 18 field NormalizedEvent** ditambah 8 field metadata CMDB:

| # | Field | Type | Keterangan |
|---|-------|------|-----------|
| 19 | `site_id` | string (nullable) | Lokasi site dari CMDB (iTop) |
| 20 | `rack_id` | string (nullable) | Rack assignment dari CMDB |
| 21 | `tenant` | string (nullable) | Tenant/penyewa |
| 22 | `status` | string (nullable) | Status aset di CMDB (production, stock, dll.) |
| 23 | `asset_tag` | string (nullable) | Tag aset |
| 24 | `owner` | string (nullable) | Pemilik aset |
| 25 | `department` | string (nullable) | Departemen pemilik |
| 26 | `cmdb_sync_time` | string (nullable) | Waktu terakhir sinkronisasi CMDB cache |

***

# 3. Schema Registry

## 3.1 Infrastruktur

| Item | Detail |
|------|--------|
| **Image** | `confluentinc/cp-schema-registry:7.6.0` |
| **Compose** | `schema-registry/docker-compose.yml` |
| **Port** | `:8081` |
| **Backend** | Kafka internal topics (via `kafka1:29092`, `kafka2:29092`, `kafka3:29092`) |

## 3.2 Skema Terdaftar

| Subject | Schema | Compatibility Mode |
|---------|--------|-------------------|
| `NormalizedEvent` | Avro record, 18 fields | BACKWARD (default) |
| `EnrichedEvent` | Avro record, 26 fields | BACKWARD (default) |

## 3.3 Keuntungan Adopsi Avro + Schema Registry

* **Validasi skema di broker-level** mencegah data korup masuk pipeline
* **Kompatibilitas evolusi skema** (forward/backward compatibility)
* **Ukuran payload lebih kecil** dibanding JSON (~30-40% lebih kecil)
* **Menghilangkan bug `invalid character '\x00'`** yang terjadi saat Telegraf consumer (JSON) membaca data Avro

***

# 4. Normalization Pipeline

## 4.1 Komponen

| Item | Detail |
|------|--------|
| **Service** | `dcim-normalizer.service` |
| **Skrip** | `src/skills/telemetry/normalizer/executor.py` |
| **Konfigurasi** | `configs/metric_mapping.json` |
| **Input** | Semua topik `dcim.raw.*` (regex subscribe `^dcim\\.raw\\..*`) |
| **Output** | `dcim.normalized.events` (Avro via Schema Registry) |

## 4.2 Alur Normalisasi

```
1. Consume dari semua topik dcim.raw.* (regex subscribe)
       ↓
2. Parse JSON (+ fallback JSON Lines untuk multi-line batch)
       ↓
3. Resolve device_type (3-level fallback):
   tags.device_type → topic_to_device_type map → measurement_to_device_type map
       ↓
4. Resolve hostname (5-level fallback):
   tags.hostname → fields.system_name → fields.sysName → tags.host (≠ srv-rnd-dcim) → "Unknown_Host"
       ↓
5. Resolve serial_number (4-level fallback):
   tags.serial_number → fields.serial_number → fields.upsSerial → XCC source tag parsing
       ↓
6. Field computation:
   - CCTV/NVR: memoryUsagePct dari memoryUsage + memoryAvailable
   - NAS: volumeUsagePct, volumeUsedGB, volumeTotalTB
   - UPS: max(L1, L2, L3) jika output_load = 0
       ↓
7. Resolve metric via metric_mapping.json
       ↓
8. Filter: skip jika metric_name = "general_metric" dan metric_value null
       ↓
9. Serialize Avro via Schema Registry → produce ke dcim.normalized.events
       ↓
10. Track lineage: track_lineage(event_id, "normalized", "success/dlq")
```

## 4.3 Metric Mapping Rules

Konfigurasi di `configs/metric_mapping.json`:

| Measurement | metric_name | metric_field | metric_unit |
|-------------|-------------|-------------|-------------|
| `server_redfish` | (default) | — | — |
| `server_redfish_util` | `cpu_utilization` | `cpuUtilization` | `percent` |
| `ups_apc` | `battery_capacity` | `battery_capacity` | `percent` |
| `dcim_nas` | `disk_temperature` | `diskTemp` | `celsius` |
| `interface` | `interface_status` | `ifOperStatus` | `status_code` |
| `cctv_metrics` | (default) | — | — |
| `server_inventory` | `inventory_snapshot` | — | — |

## 4.4 Device Type Resolution

**Topic-to-device_type mapping:**

| Topic Prefix | device_type |
|-------------|-------------|
| `dcim.raw.network` | `network_switch` |
| `dcim.raw.power.ups` | `ups` |
| `dcim.raw.storage.nas` | `nas` |
| `dcim.raw.server` | `server` |
| `dcim.raw.device.isapi` | `cctv` |

**Measurement-to-device_type mapping:**

| Measurement | device_type |
|-------------|-------------|
| `interface` | `network_switch` |
| `ups_apc` | `ups` |
| `dcim_nas` | `nas` |
| `server_redfish` / `server_redfish_util` | `server` |
| `cctv_metrics` | `cctv` |

***

# 5. Enrichment Schema

## 5.1 Komponen

| Item | Detail |
|------|--------|
| **Enrichment API** | `dcim-enrichment-api.service` → FastAPI di port `:8000` |
| **Skrip API** | `src/skills/inventory/enrichment/executor.py` |
| **Cache** | Redis 7 Alpine di `localhost:6379` |
| **Cache Sync** | `dcim-itop-redis-sync.service` → `scripts/itop_to_cache_sync.py` (60s) |
| **Cache Key** | `asset:sn:{serial_number}` (primary), `asset:{sn}` (legacy fallback) |
| **Cache TTL** | 3600s (1 jam) |

## 5.2 Enrichment Status

Setiap event yang melewati enrichment mendapat status berikut:

| Status | Kondisi | Aksi |
|--------|---------|------|
| `FULL` | Memiliki site/location + rack + brand/model/identity | Data lengkap |
| `PARTIAL` | Hanya sebagian field terisi | Data parsial, perlu update CMDB |
| `NOT_IN_CMDB` | Serial number tidak ditemukan di cache | Dicatat di Redis set `unknown_assets` |
| `NO_IDENTIFIER` | Serial number = placeholder (NO_SN, NO_IDENTIFIER) | Skip lookup, langsung return |

## 5.3 Alur Enrichment di NiFi

```
1. NiFi ConsumeKafkaRecord: dcim.normalized.events (Avro)
       ↓
2. NiFi LookupRecord: GET /enrich/{serial_number} → Enrichment API
       ↓
3. Enrichment API:
   - Lookup Redis: asset:sn:{sn} (primary) → asset:{sn} (fallback) → asset:ip:{ip} (SIEM)
   - Determine enrichment_status (FULL/PARTIAL/NOT_IN_CMDB/NO_IDENTIFIER)
   - Return metadata: site_id, rack_id, tenant, status, asset_tag, owner, department
       ↓
4. NiFi PublishKafkaRecord: dcim.enriched.events (Avro EnrichedEvent)
```

***

# 6. Kafka Topic-to-Schema Mapping

| Topik | Format | Schema | Sumber |
|-------|--------|--------|--------|
| `dcim.raw.hardware.server` | JSON | — (raw) | Redfish poller |
| `dcim.raw.hardware.server.inventory` | JSON | — (raw) | Inventory collector |
| `dcim.raw.power.ups` | JSON | — (raw) | SNMP UPS poller |
| `dcim.raw.storage.nas` | JSON | — (raw) | SNMP NAS poller |
| `dcim.raw.network.snmp` | JSON | — (raw) | SNMP MikroTik poller |
| `dcim.raw.network.interfaces` | JSON | — (raw) | SNMP MikroTik poller |
| `dcim.raw.device.isapi` | JSON | — (raw) | Hikvision daemon |
| `dcim.normalized.events` | **Avro** | NormalizedEvent (18 fields) | Normalizer |
| `dcim.enriched.events` | **Avro** | EnrichedEvent (26 fields) | NiFi Enrichment |
| `dcim.dlq.parse-failure` | Raw bytes | — | Normalizer (error) |
| `dcim.dlq.enrichment-failure` | Raw bytes | — | NiFi (error) |
| `dcim.dlq.delivery-failure` | Raw bytes | — | Consumers (error) |

***

# 7. PostgreSQL Storage Schema

Data enriched akhirnya disimpan di tabel `dcim_events` dengan **dedicated columns** per device type:

| Raw Field | PG Column | Type | Device Type |
|-----------|-----------|------|-------------|
| `battery_capacity` | `ups_battery_capacity` | int | UPS |
| `battery_runtime_remain` | `ups_battery_runtime` | int | UPS |
| `input_voltage` | `ups_input_voltage` | float | UPS |
| `output_load` | `ups_output_load` | int | UPS |
| `reading_celsius` | `srv_reading_celsius` | float | Server |
| `reading_rpm` | `srv_reading_rpm` | float | Server |
| `power_output_watts` | `srv_power_watts` | float | Server |
| `status_online` | `cctv_status_online` | int | CCTV |
| `diskStatus` | `nas_disk_status` | int | NAS |
| `ifOperStatus` | `net_if_oper_status` | int | Network |

***

# 8. Handover Notes

## Cara Menambahkan Metric Mapping Baru

1. Edit `configs/metric_mapping.json`
2. Tambahkan entry baru dengan format:
   ```json
   "measurement_name": {
     "metric_name": "nama_metrik_standar",
     "metric_field": "nama_field_di_raw",
     "metric_unit": "satuan"
   }
   ```
3. Restart normalizer: `sudo systemctl restart dcim-normalizer.service`

## Cara Evolusi Schema Avro

1. Edit `src/schemas/avro_schemas.py`
2. Tambahkan field baru dengan `"default": null` untuk backward compatibility
3. Restart service yang menggunakan schema tersebut
4. Schema Registry akan otomatis mendaftarkan versi baru

## File Penting

| File | Fungsi |
|------|--------|
| `src/schemas/avro_schemas.py` | Definisi Avro schema (NormalizedEvent + EnrichedEvent) |
| `configs/metric_mapping.json` | Mapping measurement → metric name/field/unit |
| `src/skills/telemetry/normalizer/executor.py` | Normalizer service executor |
| `src/skills/inventory/enrichment/executor.py` | Enrichment API (FastAPI) |
| `scripts/itop_to_cache_sync.py` | Cache sync iTop → Redis |

***

# 9. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial handover documentation |
