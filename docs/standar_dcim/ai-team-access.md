# AI Team Access - DCIM Analytics Pipeline

> **Purpose:** Dokumentasi akses untuk Tim AI ke DCIM analytics pipeline
> **Created:** 2026-07-08
> **Updated:** 2026-07-20
> **Version:** 1.1
> **Status:** Production — 24 metric types, ~1,740 events/sec

---

## Overview

Dokumen ini menjelaskan cara akses Tim AI ke DCIM analytics pipeline untuk kebutuhan training AI/ML. Pipeline ini menyediakan:
- Real-time metrics dari seluruh device (server, CCTV, NAS, UPS, network) — **24 metric types, ~1,740 events/sec**
- **Energy metrics tersedia**: `total_facility_power`, `it_equipment_power` (dari UPS)
- Historical data dengan TimescaleDB
- Continuous aggregates (hourly, daily)
- Kafka topics untuk streaming

---

## Network Access

Karena Tim AI berada di dalam jaringan internal yang sama, Anda dapat langsung mengakses resource berikut dari mesin pengembangan (Jupyter Notebook / Server AI) Anda:

| Resource | Host | Port | Protocol | Keterangan |
|----------|------|------|----------|------------|
| TimescaleDB | `10.70.0.56` | `5433` | PostgreSQL | Untuk penarikan data historis. Pastikan `.env` API Anda menunjuk ke sini! |
| Kafka Broker | `10.70.0.56` | `9094` | SSL/TLS | Port 9092 hanya untuk internal. Koneksi eksternal wajib port 9094 + SSL |

---

## Database Credentials

### Primary Access (Read-Only)

| Parameter | Value |
|-----------|-------|
| Database | `dcim_analytics` |
| Username | `ai_team` |
| Password | `Inovasi@0918` |

### Alternative Roles

| Role | Permissions | Use Case |
|------|-------------|----------|
| `analytics_read` | SELECT only | General AI/ML queries |
| `analytics_write` | SELECT, INSERT | Write predictions |
| `analytics_admin` | ALL | Full access, model deployment |

---

## Database Schema

### Tables

#### `metrics` (Hypertable)

Main metrics table dengan TimescaleDB.

**Contoh Pengambilan Data dengan Python (Pandas):**
```python
import pandas as pd
import psycopg2

# Koneksi ke TimescaleDB
conn = psycopg2.connect(
    host="10.70.0.56",
    port="5433",
    dbname="dcim_analytics",
    user="ai_team",
    password="Inovasi@0918"
)

# Ambil data metrik UPS dalam 24 jam terakhir
query = """
    SELECT time, source, value, tags->>'device_type' as device_type
    FROM metrics 
    WHERE metric_name = 'battery_temperature' 
      AND time > NOW() - INTERVAL '24 hours'
    ORDER BY time ASC;
"""

df = pd.read_sql(query, conn)
print(df.head())
```

| Column | Type | Description |
|--------|------|-------------|
| time | TIMESTAMPTZ | Timestamp |
| metric_name | TEXT | Metric identifier |
| ci_id | UUID | Configuration Item ID |
| asset_id | UUID | Asset ID |
| source | TEXT | Source device type |
| value | DOUBLE | Metric value |
| unit | TEXT | Unit of measurement |
| tags | JSONB | Additional tags |

#### `metrics_hourly` (Continuous Aggregate)

Hourly aggregated metrics.

```sql
SELECT * FROM metrics_hourly ORDER BY time DESC LIMIT 10;
```

| Column | Type | Description |
|--------|------|-------------|
| time | TIMESTAMPTZ | Hour bucket |
| metric_name | TEXT | Metric identifier |
| source | TEXT | Source device type |
| value_avg | DOUBLE | Average value |
| value_min | DOUBLE | Minimum value |
| value_max | DOUBLE | Maximum value |
| sample_count | BIGINT | Number of samples |

#### `metrics_daily` (Continuous Aggregate)

Daily aggregated metrics.

```sql
SELECT * FROM metrics_daily ORDER BY time DESC LIMIT 10;
```

---

## Available Metrics Catalog

> **Diperbarui 2026-07-20** — 24 metric types dari 6 device types.

### UPS (8 metrics)
| Metric Name | Unit | Keterangan |
|-------------|------|------------|
| `battery_capacity` | percent | Kapasitas baterai saat ini |
| `battery_temperature` | celsius | Temperatur baterai |
| `battery_voltage` | volt | Tegangan baterai |
| `battery_current` | ampere | Arus baterai |
| `battery_runtime_remaining` | seconds | Estimasi runtime tersisa |
| `output_voltage` | volt | Tegangan output |
| `output_frequency` | hertz | Frekuensi output |
| `output_load` | percent | Beban output |
| `total_facility_power` | watts | **Computed**: total daya fasilitas |
| `it_equipment_power` | watts | **Computed**: estimasi daya IT equipment |

### CCTV / NVR (6 metrics)
| Metric Name | Unit | Keterangan |
|-------------|------|------------|
| `status_online` | status_code | 1=online, 0=offline |
| `cpu_utilization` | percent | Utilisasi CPU kamera |
| `memory_usage` | gigabytes | Memori terpakai |
| `memory_available` | gigabytes | Memori tersedia |
| `memory_usage_pct` | percent | Persentase memori terpakai |

### NAS (6 metrics)
| Metric Name | Unit | Keterangan |
|-------------|------|------------|
| `disk_temperature` | celsius | Temperatur disk |
| `system_temperature` | celsius | Temperatur sistem NAS |
| `volume_usage_pct` | percent | Persentase volume terpakai |
| `volume_used` | bytes | Volume terpakai |
| `volume_total` | bytes | Total volume |
| `volume_health` | status_code | Status kesehatan volume |

### Network / Switch (4 metrics)
| Metric Name | Unit | Keterangan |
|-------------|------|------------|
| `interface_status` | status_code | Status interface (1=up) |
| `cpu_load` | percent | CPU load switch |
| `memory_used` | kilobytes | Memori terpakai |
| `memory_total` | kilobytes | Total memori |

### Server (3 metrics)
| Metric Name | Unit | Keterangan |
|-------------|------|------------|
| `cpu_utilization` | percent | Utilisasi CPU server |
| `memory_utilization` | percent | Utilisasi memori server |
| `power_state` | status_code | Status power server |

> **Tip**: Gunakan query `SELECT DISTINCT metric_name, source FROM metrics WHERE time > NOW() - INTERVAL '1 hour' ORDER BY source, metric_name;` untuk melihat katalog metric terkini.

---

## Kafka Topics

### Available Topics

| Topic | Partitions | Retention | Purpose |
|-------|------------|-----------|---------|
| `dcim.analytics.metrics` | 6 | 7 days | Raw metrics untuk AI |
| `dcim.analytics.anomalies` | 3 | 30 days | Anomaly alerts |
| `dcim.analytics.predictions` | 3 | 30 days | Prediction results |

### Kafka Connection

| Parameter | Value |
|-----------|-------|
| Bootstrap Servers | `10.70.0.56:9094` |
| Protocol | SSL |
| CA Certificate | `ca-cert.pem` (Hubungi Tim Infra) |

### Example Consumer (Python)

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'dcim.analytics.metrics',
    bootstrap_servers='10.70.0.56:9094',
    group_id='ai-team-consumer',
    auto_offset_reset='earliest',
    security_protocol='SSL',
    ssl_cafile='ca-cert.pem',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    print(message.value)
```

---

## Data Flow

```
Source Devices (Server, CCTV, NAS, UPS, Network)
        ↓
    NiFi (Ingestion Pollers)
        ↓
    NiFi (Enrichment & Normalizer)
        ↓
    Kafka (dcim.enriched.events - Avro)
        ↓
    Analytics Bridge (Python)
        ↓
    Kafka (dcim.analytics.metrics - JSON) ← Tim AI bisa consume dari sini
        ↓
    Stream Processor (analytics_stream_processor.py)
        ↓
    TimescaleDB (metrics hypertable) ← Tim AI bisa query ke sini
        ↓
    Continuous Aggregates (hourly, daily)
```

---

## Data Polling Intervals & Recommended Query Windows

> [!IMPORTANT]
> Jangan memukul rata (hardcode) query window ke `INTERVAL '5 minutes'` untuk semua endpoint! Hal ini akan menyebabkan banyak data (seperti `inventory_snapshot`) tampak kosong (0 baris), padahal data tersebut memang di-poll dengan interval yang lebih lama sesuai prioritasnya.

Harap perhatikan **Polling Interval** aktual untuk tiap jenis metrik, dan sesuaikan **Query Window** Anda (di API yang di-deploy terpisah) sesuai dengan target SLA:

| Jenis Data / Metrik | Device / Tipe | Polling Interval Aktual | Rekomendasi Query Window | SLA Target |
|---|---|---|---|---|
| Server Health / Thermal | Server | 60 detik | `INTERVAL '5 minutes'` | P1 Critical |
| CPU & Memory Util | Server | 30 detik | `INTERVAL '5 minutes'` | P1 Critical |
| Power & Battery | UPS | 60 detik | `INTERVAL '5 minutes'` | P1 Critical |
| Network Interface | Switch / Router | 60 detik | `INTERVAL '5 minutes'` | P1 Critical |
| Storage & Disk Temp | NAS | 120 detik | `INTERVAL '5 minutes'` | P1 Critical |
| NAS Volume Usage | NAS | 120 detik | `INTERVAL '5 minutes'` | P2 High |
| CPU & Memory (Switch) | Switch / Router | 60 detik | `INTERVAL '5 minutes'` | P2 High |
| Energy (Power) | UPS | 60 detik | `INTERVAL '5 minutes'` | P1 Critical |
| Inventory Snapshot | Server | 24 jam (Pukul 01:00) | `INTERVAL '24 hours'` | P3 Medium (Capacity) |

> [!TIP]
> Jika Anda mengembangkan endpoint untuk *Capacity* atau laporan energi yang menggunakan data historis panjang, gunakan tabel Continuous Aggregates (`metrics_hourly` atau `metrics_daily`) dengan query window yang lebih lebar (mis. `INTERVAL '30 days'`).
> Untuk anomaly detection & RCA real-time, gunakan tabel `metrics` langsung dengan `INTERVAL '5 minutes'` — **energy metrics (`total_facility_power`, `it_equipment_power`) sekarang tersedia real-time setiap 60 detik.**

---

## Query Examples

### Get Latest Metrics

```sql
SELECT time, metric_name, source, value, unit
FROM metrics
WHERE time > NOW() - INTERVAL '1 hour'
ORDER BY time DESC;
```

### Get Hourly Aggregates

```sql
SELECT time, metric_name, source, value_avg, value_min, value_max
FROM metrics_hourly
WHERE time > NOW() - INTERVAL '7 days'
ORDER BY time DESC;
```

### Get Daily Aggregates

```sql
SELECT time, metric_name, source, value_avg
FROM metrics_daily
WHERE time > NOW() - INTERVAL '30 days'
ORDER BY time DESC;
```

### Get Specific Device Metrics

```sql
SELECT time, metric_name, value, unit
FROM metrics
WHERE source = 'server'
  AND metric_name = 'cpu_utilization'
  AND time > NOW() - INTERVAL '24 hours'
ORDER BY time DESC;
```

---

## Performance

| Metric | Target | Actual (2026-07-20) |
|--------|--------|----------------------|
| Throughput | 430+ metrics/sec | **~1,740 events/sec** |
| Latency | < 1s | < 500ms |
| Metric Types | 5 | **24** |
| Device Types | 6 | 6 |
| Retention | 90 days | 90 days |
| Compression | After 7 days | After 7 days |

---

## Security

### RBAC Roles

| Role | Permissions |
|------|-------------|
| `ai_team` | SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public |
| `analytics_read` | SELECT only |
| `analytics_write` | SELECT + INSERT |
| `analytics_admin` | ALL privileges |

### Best Practices

1. **Use read-only role** (`ai_team` or `analytics_read`) untuk training data
2. **Don't write directly to metrics table** - use Kafka for new data
3. **Use aggregates** for large queries - faster than raw data
4. **Limit query range** - use time filters to improve performance

---

## Deploy & Migration (Wajib Sebelum Deploy API)

Tabel-tabel hasil analytics (`anomaly_events`, `predictions`, dll.) **tidak terbuat secara otomatis**. Sebelum Anda mende-deploy API Analytics, pastikan Anda atau DBA telah menjalankan *script* migrasi SQL.

### Prosedur Migrasi
1. Migrasi harus dijalankan menggunakan user **`analytics_user`** (sebagai *schema owner*). User `ai_team` tidak memiliki hak *CREATE TABLE*.
2. Lokasi file migrasi (pada repo API Anda):
   - `001_create_timescaledb_schema.sql` (Sudah Dijalankan)
   - `002_create_analytics_tables.sql` (**Belum Dijalankan - Wajib Dijalankan**)

### Checklist Verifikasi Pra-Deploy
Jalankan pengecekan berikut. Pastikan *query* mengembalikan angka (bukan *error* tabel tidak ditemukan):
1. `SELECT COUNT(*) FROM anomaly_events;`
2. `SELECT COUNT(*) FROM predictions;`
3. `SELECT COUNT(*) FROM metrics;` (Harus > 0)

Jika *query* pertama/kedua gagal, API Anda akan mengembalikan array kosong atau *error*.

---

## Troubleshooting

### Connection Issues

```bash
# Test connection
psql -h 10.70.0.56 -p 5433 -U ai_team -d dcim_analytics
```

### Check Data Availability

```sql
-- Check row count
SELECT COUNT(*) FROM metrics WHERE time > NOW() - INTERVAL '24 hours';

-- Check by source
SELECT source, COUNT(*)
FROM metrics
WHERE time > NOW() - INTERVAL '1 hour'
GROUP BY source;
```

### Check Kafka Topics

```bash
# List topics (memerlukan file client-ssl.properties)
kafka-topics.sh --bootstrap-server 10.70.0.56:9094 --command-config client-ssl.properties --list

# Check topic details
kafka-topics.sh --bootstrap-server 10.70.0.56:9094 --command-config client-ssl.properties --topic dcim.analytics.metrics --describe
```

---

## Support

Untuk pertanyaan atau masalah:
1. Check logs: `/home/infra/dcim_metrics_project/logs/`
2. Contact: Infrastructure Team

---

## References

- [dcim-wiki: block7-analytics-ai-engine](../reference-designs/block7-analytics-ai-engine.md)
- [dcim-wiki: data-ingestion-architecture-comparison](../concepts/data-ingestion-architecture-comparison.md)
- [TimescaleDB Documentation](https://docs.timescale.com/)

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-07-20 | 1.1 | **Metric gap fixed**: metric types 5→24. Added energy metrics (`total_facility_power`, `it_equipment_power`). Added NAS volume, Network CPU/memory, UPS extended battery metrics. Added metric catalog section. Updated throughput & polling intervals. |
| 2026-07-08 | 1.0 | Initial version |