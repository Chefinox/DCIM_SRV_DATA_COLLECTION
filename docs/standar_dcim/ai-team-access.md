# AI Team Access - DCIM Analytics Pipeline

> **Purpose:** Dokumentasi akses untuk Tim AI ke DCIM analytics pipeline
> **Created:** 2026-07-08
> **Version:** 1.0
> **Status:** Production Ready

---

## Overview

Dokumen ini menjelaskan cara akses Tim AI ke DCIM analytics pipeline untuk kebutuhan training AI/ML. Pipeline ini menyediakan:
- Real-time metrics dari seluruh device (server, CCTV, NAS, UPS, network)
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
    WHERE metric_name = 'battery_temp' 
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
| Inventory Snapshot | Server | 24 jam (Pukul 01:00) | `INTERVAL '24 hours'` | P3 Medium (Capacity) |
| Energy (PUE) | Keseluruhan | Agregasi Harian | `INTERVAL '24 hours'` | P3 Medium (Energy) |

> [!TIP]
> Jika Anda mengembangkan endpoint untuk prediksi *Capacity* atau laporan energi yang mentolerir data harian, sangat disarankan menggunakan tabel Continuous Aggregates (`metrics_hourly` atau `metrics_daily`) dengan query window yang lebih lebar (mis. `INTERVAL '24 hours'`).

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

| Metric | Target |
|--------|--------|
| Throughput | 430+ metrics/sec |
| Latency | < 1s |
| Retention | 90 days |
| Compression | After 7 days |

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