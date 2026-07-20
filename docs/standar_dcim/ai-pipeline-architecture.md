# AI Pipeline Architecture - DCIM Analytics

> **Purpose:** Dokumentasi arsitektur pipeline AI/ML untuk DCIM
> **Created:** 2026-07-08
> **Updated:** 2026-07-20
> **Version:** 1.2
> **Status:** Production — 25 metrics, ~3,200 rows/5min

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
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌────────────────┐
│  Sources     │     │  Ingestion   │     │   Kafka (Raw)  │     │  Processing    │
├──────────────┤     ├──────────────┤     ├────────────────┤     ├────────────────┤
│ Server       │────▶│ NiFi         │────▶│ dcim.raw.*     │────▶│ Normalizer     │
│ (Redfish)*   │     │ ExecuteProcess│     │ (JSON)         │     │ (Python, Avro) │
│ CCTV/NVR     │     │ + Telegraf   │     │                │     │ Multi-Metric   │
│ NAS          │     │ (Python)     │     │                │     │ + Computed     │
│ UPS          │     │              │     │                │     │                │
│ Network      │     │              │     │                │     │                │
└──────────────┘     └──────────────┘     └────────────────┘     └────────────────┘
                                                                        │
                                                                        ▼
                                          ┌────────────────┐     ┌────────────────┐
                                          │ Kafka (Enrich) │     │ AI Integration │
                                          ├────────────────┤     ├────────────────┤
                                          │ dcim.enriched.*│────▶│ Analytics      │
                                          │ (Avro via SR)  │     │ Bridge (Python)│
                                          └────────────────┘     └────────────────┘
                                                                        │
                                                                        ▼
┌──────────────┐     ┌──────────────┐     ┌────────────────┐     ┌────────────────┐
│   Storage    │     │  TimescaleDB │     │  Analytics     │     │   Kafka (AI)   │
├──────────────┤     ├──────────────┤     ├────────────────┤     ├────────────────┤
│ PostgreSQL   │◀────│ metrics      │◀────│ Stream         │◀────│ dcim.          │
│ Elasticsearch│     │ hypertable   │     │ Processor      │     │ analytics.*    │
│ Redis        │     │ **(25 types)** │     │ (Python)       │     │ (JSON)         │
│              │     │ hourly agg   │     │                │     │                │
│              │     │ daily agg    │     │                │     │                │
└──────────────┘     └──────────────┘     └────────────────┘     └────────────────┘
```

---

## Components

### 1. Data Sources

| Source | Protocol | Metrics |
|--------|----------|---------|
| Server | Redfish*, IPMI | CPU, memory (fixed!), power_state, thermal |
| CCTV | Hikvision ISAPI | Status, CPU, memory, memory_pct |
| NAS | SNMP | Disk temp, system temp, volume usage/health |
| UPS | SNMP | Battery, voltage, current, frequency, load, **computed power** |
| Network | SNMP | Interface stats, CPU load, memory |

> \*Server CPU/memory metrics via Redfish OEM Lenovo XCC (Telegraf `inputs.exec` → `redfish_telemetry_poller.py`)

### 2. Ingestion Layer

| Component | Technology | Purpose |
|-----------|------------|---------|
| NiFi ExecuteProcess | Python scripts | Ingestion utama: Server, CCTV/NVR, NAS, UPS, Network |
| Telegraf | System metrics only | Self-monitoring server DCIM (CPU, disk, memory) |
| Kafka | 3-node cluster | Message broker (Port 9092 INTERNAL, 9094+SSL EXTERNAL) |

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
| Normalizer | **Python systemd service** | Transform raw → normalized format (Avro). Multi-metric: 1 raw message → N normalized events. Computed metrics (total_facility_power, it_equipment_power). |
| Enrichment | NiFi + Redis + FastAPI | Add CI/asset metadata from CMDB |
| Stream Processor | Python | Process Analytics Bridge output → TimescaleDB |

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
| `metrics` | Raw hypertable — **24 metric types, ~1,740 events/sec** |
| `metrics_hourly` | Hourly continuous aggregate |
| `metrics_daily` | Daily continuous aggregate |
| `anomaly_events` | Hasil deteksi anomali (Output) |
| `predictions` | Hasil prediksi kegagalan (Output) |
| `rca_reports` | Laporan Root Cause Analysis (Output) |
| `capacity_forecasts` | Hasil forecasting kapasitas (Output) |
| `energy_reports` | Laporan optimasi energi — **data `total_facility_power` & `it_equipment_power` now available** |
| `ml_models` | Registri model ML (Output) |
| `model_drift_tracking` | Monitoring drift model ML (Internal) |
| `audit_log` | Audit trail operasi analytics (Internal) |

### 5.1 Data Flow Analytics Result

```
TimescaleDB (metrics) ──▶ API Analytics (Block 7) ──▶ Tabel-Tabel Output (anomaly_events, dsb.)
                                                            │
                                                            ▼
                                                 Akses/Consume oleh Tim AI
```

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

| Metric | Target | Actual (2026-07-20) |
|--------|--------|----------------------|
| Throughput | 430+ metrics/sec | **~1,740 events/sec** (8,703/5min) |
| Metric Types | N/A | **24** distinct metric names |
| Device Types | 6 | 6 |
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

---

## Changelog

| Date | Version | Changes |
|------|---------|---------|
| 2026-07-20 | 1.2 | **Bug fix**: `memory_utilization` server metric now flowing. Field name mismatch fixed in metric_mapping.json (`memoryUsage`→`memory_usage`). Total metric types: 25. Note: server CPU/memory via Redfish OEM Lenovo XCC (Telegraf `inputs.exec`). |
| 2026-07-20 | 1.1 | Normalizer upgraded: resolve_metric→resolve_metrics (multi-metric output). Added secondary_metrics processing + computed power metrics. Metric types 5→24. Fixed architecture diagram (normalizer is Python systemd, not NiFi). |
| 2026-07-08 | 1.0 | Initial version |