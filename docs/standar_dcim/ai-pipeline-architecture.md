# AI Pipeline Architecture - DCIM Analytics

> **Purpose:** Dokumentasi arsitektur pipeline AI/ML untuk DCIM
> **Created:** 2026-07-08
> **Version:** 1.0
> **Status:** Production Ready

---

## Overview

Dokumen ini menjelaskan arsitektur pipeline AI/ML untuk Data Center Infrastructure Management (DCIM). Pipeline ini menyediakan:
- Data ingestion dari berbagai source (server, CCTV, NAS, UPS, network)
- Real-time processing dengan Kafka
- Time-series storage dengan TimescaleDB
- Akses untuk Tim AI/ML

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           DCIM AI Pipeline Architecture                       │
└─────────────────────────────────────────────────────────────────────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Sources    │     │  Ingestion   │     │   Kafka      │     │  Processing  │
├──────────────┤     ├──────────────┤     ├──────────────┤     ├──────────────┤
│ Server       │────▶│ NiFi         │────▶│ dcim.raw.*   │────▶│ NiFi         │
│ CCTV/NVR     │     │ ExecuteProcess│   │              │     │ Normalizer   │
│ NAS          │     │ (Python)     │     │              │     │              │
│ UPS          │     │              │     │              │     │              │
│ Network      │     │              │     │              │     │              │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
                                                                    │
                                                                    ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Storage    │     │  TimescaleDB │     │  Analytics   │     │    AI       │
├──────────────┤     ├──────────────┤     ├──────────────┤     ├──────────────┤
│ PostgreSQL   │◀────│ metrics      │◀────│ Stream       │◀────│ Kafka        │
│ Elasticsearch│     │ hypertable   │     │ Processor    │     │ Topics       │
│ Redis        │     │              │     │              │     │              │
│              │     │ hourly agg   │     │              │     │ dcim.        │
│              │     │ daily agg    │     │              │     │ analytics.*  │
└──────────────┘     └──────────────┘     └──────────────┘     └──────────────┘
```

---

## Components

### 1. Data Sources

| Source | Protocol | Metrics |
|--------|----------|---------|
| Server | Redfish, IPMI | CPU, memory, disk, network |
| CCTV | Hikvision ISAPI | Status, recording |
| NAS | SNMP | Storage, throughput |
| UPS | SNMP | Power, battery |
| Network | SNMP | Interface stats |

### 2. Ingestion Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| NiFi ExecuteProcess | Python scripts | Ingestion utama: Server, CCTV/NVR, NAS, UPS, Network |
| Telegraf | System metrics only | Self-monitoring server DCIM (CPU, disk, memory) |
| Kafka | 3-node cluster | Message broker |

### 2.1 NiFi ExecuteProcess Python Pollers

| Poller Script | Target Topic | Device Type | Protocol |
|---------------|--------------|-------------|----------|
| `redfish_poller.py` | `dcim.raw.hardware.server` | Server | Redfish |
| `cctv_poller.py` | `dcim.raw.device.isapi` | CCTV + NVR | Hikvision ISAPI |
| `nas_poller.py` | `dcim.raw.storage.nas` | NAS | SNMP |
| `snmp_ups_poller.py` | `dcim.raw.power.ups` | UPS | SNMP |
| `mikrotik_poller.py` | `dcim.raw.network.snmp` | Network (Mikrotik) | SNMP |

**Note:** Telegraf hanya berjalan untuk self-monitoring server DCIM (CPU, disk, memory), bukan untuk ingestion device. Semua device ingestion menggunakan NiFi ExecuteProcess dengan Python scripts.

### 3. Processing Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| Normalizer | NiFi | Transform to normalized format |
| Enrichment | NiFi + Redis | Add CI/asset metadata |
| Stream Processor | Python | Process for TimescaleDB |

### 4. Storage Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| PostgreSQL | 15.x | Primary database (dcim_sot) |
| TimescaleDB | 2.x | Time-series metrics (dcim_analytics) |
| Elasticsearch | 9.x | Log & metrics search |
| Redis | 7.x | Cache |

### 5. Analytics Layer

| Component | Description |
|-----------|-------------|
| `metrics` | Raw hypertable |
| `metrics_hourly` | Hourly continuous aggregate |
| `metrics_daily` | Daily continuous aggregate |

---

## Kafka Topics

### Analytics Topics

| Topic | Partitions | Retention | Purpose |
|-------|------------|-----------|---------|
| `dcim.analytics.metrics` | 6 | 7 days | Raw metrics untuk AI |
| `dcim.analytics.anomalies` | 3 | 30 days | Anomaly alerts |
| `dcim.analytics.predictions` | 3 | 30 days | Prediction results |

### Raw Topics

| Topic | Partitions | Retention |
|-------|------------|-----------|
| `dcim.raw.hardware.server` | 3 | 7 days |
| `dcim.raw.hardware.server.inventory` | 3 | 7 days |
| `dcim.raw.storage.nas` | 3 | 7 days |
| `dcim.raw.power.ups` | 3 | 7 days |
| `dcim.raw.network.snmp` | 3 | 7 days |
| `dcim.raw.network.interfaces` | 3 | 7 days |
| `dcim.raw.device.isapi` | 3 | 7 days |

### Processed Topics

| Topic | Partitions | Retention |
|-------|------------|-----------|
| `dcim.normalized.events` | 6 | 30 days |
| `dcim.enriched.events` | 6 | 90 days |

---

## TimescaleDB Schema

### Metrics Table (Hypertable)

```sql
CREATE TABLE metrics (
    time TIMESTAMPTZ NOT NULL,
    metric_name TEXT NOT NULL,
    ci_id UUID,
    asset_id UUID,
    source TEXT NOT NULL,
    value DOUBLE PRECISION NOT NULL,
    unit TEXT,
    tags JSONB DEFAULT '{}'
);

SELECT create_hypertable('metrics', 'time');
```

### Continuous Aggregates

```sql
-- Hourly aggregates
CREATE MATERIALIZED VIEW metrics_hourly WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 hour', time) AS time,
    metric_name,
    source,
    AVG(value) AS value_avg,
    MIN(value) AS value_min,
    MAX(value) AS value_max,
    COUNT(*) AS sample_count
FROM metrics
GROUP BY time_bucket('1 hour', time), metric_name, source;

-- Daily aggregates
CREATE MATERIALIZED VIEW metrics_daily WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS time,
    metric_name,
    source,
    AVG(value) AS value_avg,
    MIN(value) AS value_min,
    MAX(value) AS value_max,
    COUNT(*) AS sample_count
FROM metrics
GROUP BY time_bucket('1 day', time), metric_name, source;
```

---

## Data Policies

### Retention Policy

| Data Type | Retention | Storage |
|-----------|-----------|---------|
| Raw metrics | 90 days | TimescaleDB |
| Hourly aggregates | 2 years | TimescaleDB |
| Daily aggregates | 5 years | TimescaleDB |

### Compression Policy

| Data Age | Compression |
|----------|-------------|
| < 7 days | Uncompressed |
| > 7 days | Compressed (columnstore) |

---

## Performance

| Metric | Target | Actual |
|--------|--------|--------|
| Throughput | 430+ metrics/sec | ~500 metrics/sec |
| Latency | < 1s | < 500ms |
| Query performance | < 5s | < 2s |
| Availability | 99.9% | 99.9% |

---

## Security

### Network Segmentation

| VLAN | Subnet | Purpose |
|------|--------|---------|
| Management | 10.70.0.0/24 | Admin, monitoring |
| Data | 10.70.1.0/24 | DB, AI access |
| DMZ | 10.70.2.0/24 | External API |

### RBAC

| Role | Permissions |
|------|-------------|
| `ai_team` | SELECT on analytics tables |
| `analytics_read` | SELECT only |
| `analytics_write` | SELECT + INSERT |
| `analytics_admin` | ALL privileges |

---

## Monitoring

### Key Metrics

| Metric | Description |
|--------|-------------|
| `dcim.metrics.ingestion.rate` | Metrics per second |
| `dcim.kafka.lag` | Consumer lag |
| `dcim.timescale.size` | Database size |
| `dcim.pipeline.latency` | End-to-end latency |

### Dashboards

- Grafana: Pipeline monitoring
- Kibana: Log analysis
- Kafka UI: Topic monitoring

---

## Disaster Recovery

### Backup Strategy

| Data Type | Frequency | Retention |
|-----------|-----------|-----------|
| PostgreSQL | Daily | 30 days |
| TimescaleDB | Daily | 30 days |
| Kafka | Replica | 7 days |

### Recovery Point Objective (RPO)

- Database: 1 hour
- Kafka: 7 days (retention)

### Recovery Time Objective (RTO)

- Database: 4 hours
- Full system: 24 hours

---

## Dependencies

| Component | Version | Notes |
|-----------|---------|-------|
| PostgreSQL | 15.x | Main DB |
| TimescaleDB | 2.x | Time-series |
| Kafka | 3.7.0 | 3-node cluster |
| NiFi | 1.24.0 | Processing |
| Redis | 7.x | Cache |
| Elasticsearch | 9.x | Search |

---

## References

- [dcim-wiki: block7-analytics-ai-engine](../reference-designs/block7-analytics-ai-engine.md)
- [dcim-wiki: block2-data-ingestion-integration](../reference-designs/block2-data-ingestion-integration.md)
- [AI Team Access](ai-team-access.md)
- [TimescaleDB Documentation](https://docs.timescale.com/)