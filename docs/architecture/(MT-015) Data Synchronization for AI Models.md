# (MT-015) Data Synchronization for AI Models

# 1. Overview

## Objective

Memastikan konsistensi data, keselarasan historis, dan kesiapan fitur untuk pelatihan dan inferensi AI/ML, mencakup:

* **AI Data Pipeline**: Bridge dari enriched events ke analytics topic (Avro → JSON) → TimescaleDB
* **Historical Data Archive**: Migrasi data ES ke PostgreSQL tabel `dcim_metrics_archive` (EAV format)
* **Materialized Views**: 6 view terlatih per device type (`v_train_server`, `v_train_ups`, dll.)
* **AI Data Interface**: Role PostgreSQL `dcim_ai_reader` (read-only, connection limit 10)
* **Data Quality**: Audit kelengkapan field harian, threshold 85%

## Prinsip Arsitektur

```
srv-rnd-dcim = PENYEDIA DATA (data provider), bukan host untuk menjalankan AI.
Tim AI mengakses data dari LUAR melalui PostgreSQL read-only role.
```

***

# 2. AI Data Pipeline Architecture

```
dcim.enriched.events (Avro)
        ↓
[Analytics Bridge] → Avro → JSON transformation
        ↓
dcim.analytics.metrics (JSON)
        ↓
[Stream Processor] → Kafka → TimescaleDB insert
        ↓
TimescaleDB (dcim_analytics:5433)
  └── metrics hypertable (time-series optimized)
```

***

# 3. Analytics Bridge

## 3.1 Fungsi

Membaca dari `dcim.enriched.events` (Avro), mendeserialisasi, lalu memproduksi ulang ke `dcim.analytics.metrics` (JSON) agar dapat dikonsumsi oleh stream processor yang menggunakan library `kafka-python` (tanpa Avro support native).

## 3.2 Detail Implementasi

| Item | Detail |
|------|--------|
| **Service** | `dcim-analytics-bridge.service` |
| **Script** | `scripts/dcim_analytics_bridge.py` |
| **Input** | `dcim.enriched.events` (Avro, via confluent-kafka AvroDeserializer) |
| **Output** | `dcim.analytics.metrics` (JSON) |
| **Consumer Group** | `dcim-analytics-bridge` |
| **Dependencies** | confluent-kafka, confluent-kafka[avro] |

## 3.3 Alur Proses

```python
1. Consume dari dcim.enriched.events (Avro deserialization via Schema Registry)
2. Tambahkan field komputasi (jika diperlukan)
3. Transform ke JSON dict
4. Produce ke dcim.analytics.metrics (JSON serialization)
```

***

# 4. Stream Processor

## 4.1 Fungsi

Membaca dari `dcim.analytics.metrics` (JSON) dan melakukan bulk insert ke TimescaleDB.

## 4.2 Detail Implementasi

| Item | Detail |
|------|--------|
| **Service** | `dcim-analytics-stream-processor.service` |
| **Script** | `scripts/analytics_stream_processor.py` |
| **Input** | `dcim.analytics.metrics` (JSON) |
| **Output** | TimescaleDB `metrics` hypertable |
| **Consumer Group** | `analytics-stream-processor` |
| **Dependencies** | kafka-python, psycopg2 |

## 4.3 TimescaleDB Schema

```sql
CREATE TABLE metrics (
    time        TIMESTAMPTZ NOT NULL,
    metric_name TEXT        NOT NULL,
    ci_id       TEXT,
    asset_id    TEXT,
    source      TEXT,
    value       DOUBLE PRECISION,
    unit        TEXT,
    tags        JSONB
);

SELECT create_hypertable('metrics', 'time');
```

**Fitur TimescaleDB:**
- **Hypertable**: Otomatis partition berdasarkan `time` (interval 7 hari)
- **Compression**: Otomatis compress chunk > 30 hari
- **Continuous aggregates**: Hourly/daily rollup untuk dashboard

***

# 5. AI Training Data Archive (L13)

## 5.1 Fungsi

Migrasi data historis dari Elasticsearch ke PostgreSQL tabel `dcim_metrics_archive` dalam format EAV (Entity-Attribute-Value) untuk akses AI/ML yang efisien.

## 5.2 Detail Implementasi

| Item | Detail |
|------|--------|
| **Service** | `dcim-metrics-archive.service` (oneshot) |
| **Timer** | `dcim-metrics-archive.timer` (daily 03:00 WIB) |
| **Script** | `scripts/es_to_pg_archive.py` |
| **Source** | Elasticsearch `dcim-metrics-unified-*` |
| **Target** | PostgreSQL `dcim_metrics_archive` (partisi bulanan) |
| **Mode** | Incremental (default) atau Backfill |

## 5.3 EAV Format

```sql
CREATE TABLE dcim_metrics_archive (
    event_time    TIMESTAMPTZ NOT NULL,
    device_type   TEXT NOT NULL,
    hostname      TEXT,
    serial_number TEXT,
    field_key     TEXT NOT NULL,
    field_value   DOUBLE PRECISION,
    field_value_txt TEXT,
    es_doc_id     TEXT
) PARTITION BY RANGE (event_time);
```

Contoh data:
```
| event_time | device_type | hostname | field_key | field_value |
|------------|-------------|----------|-----------|-------------|
| 2026-07-10 | server | SERVER-HCI-01 | cpuUtilization | 23.5 |
| 2026-07-10 | server | SERVER-HCI-01 | memoryUsage | 67.2 |
| 2026-07-10 | ups | UPS-SERVERROOM | battery_capacity | 95 |
```

***

# 6. Materialized Views

6 materialized views yang menyediakan data siap latih untuk AI/ML:

| View | Target Device | Source Table | Key Fields |
|------|--------------|-------------|------------|
| `v_train_server` | Server | `dcim_events` | cpu_util, mem_util, temp, power_watts |
| `v_train_ups` | UPS | `dcim_events` | battery_capacity, load, voltage, temp |
| `v_train_nas` | NAS | `dcim_events` | disk_temp, volume_usage, io_stats |
| `v_train_network` | Switch | `dcim_events` | cpu_load, if_status, traffic |
| `v_train_cctv` | CCTV | `dcim_events` | status_online, cpu_util, memory_pct |
| `v_train_nvr` | NVR | `dcim_events` | status_online, cpu_util, memory_pct |

**Refresh**: Otomatis setiap 1 jam via `REFRESH MATERIALIZED VIEW CONCURRENTLY`.

***

# 7. AI Data Interface (L17)

## 7.1 PostgreSQL Role

| Item | Detail |
|------|--------|
| **Role** | `dcim_ai_reader` |
| **Type** | LOGIN, read-only (least privilege) |
| **Connection Limit** | 10 koneksi paralel |
| **Host** | `10.70.0.56:5432` |
| **Database** | `dcim_sot` |
| **DDL** | `sql/ai_access_role.sql` |

## 7.2 Privileges

| Privilege | Target |
|-----------|--------|
| **SELECT** | `v_train_server`, `v_train_ups`, `v_train_nas`, `v_train_network`, `v_train_cctv`, `v_train_nvr`, `dcim_metrics_archive`, `dcim_failure_events`, `unified_assets`, `dcim_server_disks`, `dcim_server_ram`, `dcim_server_processors`, `dcim_server_nics` |
| **INSERT + UPDATE** | `dcim_server_anomalies` (wadah hasil skor AI) |
| **REVOKED** | INSERT/UPDATE/DELETE pada `dcim_events`, `dcim_metrics_archive`, `dcim_failure_events` |

## 7.3 Cara Pembuatan Role

```bash
psql -v ai_pw="'<PASSWORD>'" -f sql/ai_access_role.sql
```

***

# 8. Data Quality Assurance (L16)

## 8.1 Audit Script

| Item | Detail |
|------|--------|
| **Script** | `scripts/audit_data_quality.py` |
| **Timer** | `dcim-data-quality-check.timer` (daily 06:00 WIB) |
| **Log Output** | `logs/data_quality_YYYYMMDD.log` |

## 8.2 Quality Schema

File: `configs/data_quality_schema.yaml`

```yaml
server:
  - serial_number
  - model
  - raw_fields.cpuUtilization
  - raw_fields.memoryUsage
  - raw_fields.power_output_watts
  - raw_fields.system_temp

ups:
  - serial_number
  - model
  - raw_fields.output_load
  - raw_fields.battery_temp
  - raw_fields.battery_runtime_remain

network:
  - serial_number
  - model
  - raw_fields.cpu_load

nas:
  - serial_number
  - model
  - raw_fields.diskTemp
```

## 8.3 Threshold

Jika kelengkapan field per device_type < **85%** dalam 24 jam terakhir, maka status = `[WARNING]`.

***

# 9. AI Readiness Assessment

| Use Case | Data Tersedia | Kesiapan |
|----------|--------------|----------|
| Server Anomaly Detection | CPU util, mem util, temp, power (30s interval) | ✅ Ready |
| UPS Predictive Maintenance | Battery capacity/temp/runtime, load (60s) | ✅ Ready |
| NAS Disk Failure Prediction | Disk temp, status (120s) | ✅ Ready |
| Network Traffic Analysis | Interface stats, CPU load (60s) | ✅ Ready |
| CCTV Uptime Monitoring | Status online, CPU/mem usage (120s) | ✅ Ready |
| PUE Calculation | Server power + UPS input/output | ⚠️ Perlu integrasi PDU/cooling |
| Capacity Planning | Historical archive (3+ bulan) | ⚠️ Data masih terakumulasi |

***

# 10. Handover Notes

## Cara Menambahkan Materialized View Baru

1. Buat DDL `CREATE MATERIALIZED VIEW v_train_<device>` di database `dcim_sot`
2. Grant SELECT ke role `dcim_ai_reader`:
   ```sql
   GRANT SELECT ON v_train_<device> TO dcim_ai_reader;
   ```
3. Tambahkan refresh schedule ke cron/timer yang ada

## Export Data untuk ML Training

```bash
# Export data training dari materialized view
python3 scripts/export_training_data.py --device-type server --format csv --output data/train_server.csv
```

***

# 11. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial handover documentation |
