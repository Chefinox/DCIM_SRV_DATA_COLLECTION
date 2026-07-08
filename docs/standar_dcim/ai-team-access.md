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

### Dari Dalam (Internal)

| Parameter | Value |
|-----------|-------|
| Host | `10.70.0.56` |
| Port | `5433` |
| Protocol | PostgreSQL |

### Dari Luar (External)

Tim AI dari luar perlu:
1. **VPN** - Connect ke VPN internal
2. **Firewall** - Port 5433 perlu di-open untuk IP tertentu

---

## Database Credentials

### Primary Access (Read-Only)

| Parameter | Value |
|-----------|-------|
| Database | `dcim_analytics` |
| Username | `ai_team` |
| Password | `ai_team_access_pass` |

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

```sql
SELECT * FROM metrics ORDER BY time DESC LIMIT 10;
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
| Bootstrap Servers | `10.70.0.56:9092` |
| Protocol | PLAINTEXT |

### Example Consumer (Python)

```python
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'dcim.analytics.metrics',
    bootstrap_servers='10.70.0.56:9092',
    group_id='ai-team-consumer',
    auto_offset_reset='earliest',
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
    Telegraf/NiFi
        ↓
    Kafka (dcim.raw.*)
        ↓
    Normalization + Enrichment
        ↓
    Kafka (dcim.analytics.metrics) ← Tim AI bisa consume dari sini
        ↓
    Stream Processor (analytics_stream_processor.py)
        ↓
    TimescaleDB (metrics hypertable)
        ↓
    Continuous Aggregates (hourly, daily)
```

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
| `ai_team` | SELECT on metrics, metrics_hourly, metrics_daily |
| `analytics_read` | SELECT only |
| `analytics_write` | SELECT + INSERT |
| `analytics_admin` | ALL privileges |

### Best Practices

1. **Use read-only role** (`ai_team` or `analytics_read`) untuk training data
2. **Don't write directly to metrics table** - use Kafka for new data
3. **Use aggregates** for large queries - faster than raw data
4. **Limit query range** - use time filters to improve performance

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
# List topics
kafka-topics.sh --bootstrap-server 10.70.0.56:9092 --list

# Check topic details
kafka-topics.sh --bootstrap-server 10.70.0.56:9092 --topic dcim.analytics.metrics --describe
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