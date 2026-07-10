# (MT-016) Centralized DCIM Logging

# 1. Overview

## Objective

Menerapkan pencatatan terpusat untuk semua komponen, integrasi, dan peristiwa operasional DCIM, mencakup:

* **Unified JSON Structured Logging**: Semua service DCIM menggunakan format JSON terstruktur via `DCIMJsonFormatter`
* **Centralized Collection**: Filebeat mengumpulkan log dari file dan journald, mengirim ke Elasticsearch
* **Dashboard**: Kibana Log Dashboard untuk analisis real-time
* **Log Taxonomy**: 4 kategori log (Application, Pipeline, Security, Operational)
* **Infrastructure Self-Monitoring**: Telegraf memantau kesehatan ES, PG, Kafka via `dcim-infra-metrics-*`

## Arsitektur Logging

```
DCIM Services (11 systemd services)
  │  (JSON structured log → stdout/file)
  ↓
systemd journald ─────→ Filebeat ─────→ Elasticsearch
  │                                      ↓
Log files (/logs/*.log) → Filebeat ──→ dcim-logs-app-*
                                        ↓
                                      Kibana Dashboard
```

***

# 2. DCIM Logger Module

## 2.1 Implementasi

File: `src/observability/logging/dcim_logger.py`

Modul ini menyediakan **2 komponen utama**:

### DCIMJsonFormatter

Custom formatter yang menghasilkan log dalam format JSON terstruktur:

```json
{
  "@timestamp": "2026-07-10T10:30:00.000000+00:00",
  "service": {"name": "dcim-normalizer"},
  "log": {"level": "INFO"},
  "message": "Normalized 50 events in 120ms",
  "event_type": "batch_complete",
  "device_type": "server",
  "category": "PIPELINE",
  "severity": "P3"
}
```

### setup_logger() Function

```python
def setup_logger(service_name, log_file=None, level=logging.INFO):
    """
    Configure and return a standard logger for a DCIM service.
    - Always logs to stdout (journalctl / systemd compatible)
    - Optionally logs to file (dual-handler)
    """
```

## 2.2 Standard Log Fields

| Field | Type | Keterangan |
|-------|------|-----------|
| `@timestamp` | string | ISO 8601 UTC timestamp |
| `service.name` | string | Nama service (e.g., `dcim-normalizer`) |
| `log.level` | string | Level: DEBUG, INFO, WARNING, ERROR, CRITICAL |
| `message` | string | Pesan log |
| `event_type` | string (extra) | Tipe event (e.g., `sync_success`, `enrich_miss`) |
| `device_type` | string (extra) | Tipe perangkat (e.g., `server`, `ups`) |
| `hostname` | string (extra) | Hostname perangkat yang diproses |
| `serial_number` | string (extra) | Serial number perangkat |
| `category` | string (extra) | Kategori log (PIPELINE, OPERATIONAL, SECURITY) |
| `severity` | string (extra) | Severity level (P1, P2, P3, P4) |

## 2.3 Contoh Penggunaan di Service

```python
from src.observability.logging.dcim_logger import setup_logger

logger = setup_logger("dcim-normalizer", "/home/infra/dcim_metrics_project/logs/normalizer.log")

# Log biasa
logger.info("Processing batch")

# Log dengan structured fields
logger.info("Normalized event", extra={
    "event_type": "normalize_success",
    "device_type": "server",
    "hostname": "SERVER-HCI-01",
    "serial_number": "SN123456"
})

# Log error dengan exception traceback
try:
    process()
except Exception as e:
    logger.error("Failed to process", exc_info=True, extra={
        "event_type": "normalize_failure",
        "category": "PIPELINE",
        "severity": "P2"
    })
```

***

# 3. Service Adoption

Semua service berikut sudah menggunakan `DCIMJsonFormatter` via `setup_logger()`:

| Service | Log File | Category |
|---------|----------|----------|
| `dcim-normalizer` | `logs/normalizer.log` | PIPELINE |
| `dcim-enrichment-api` | stdout (journalctl) | PIPELINE |
| `dcim-es-consumer` | `logs/es_consumer.log` | PIPELINE |
| `dcim-sql-consumer` | stdout (journalctl) | PIPELINE |
| `dcim-itop-unified` | `logs/itop_unified.log` | PIPELINE |
| `dcim-itop-redis-sync` | `logs/itop_cache_sync.log` | OPERATIONAL |
| `dcim-threshold-alerter` | `logs/threshold_alerts.log` | ALERTING |
| `dcim-telegram-alerter` | `logs/dcim_telegram_alerter.log` | ALERTING |
| `dcim-dlq-consumer` | `logs/dlq_consumer.log` | PIPELINE |
| `dcim-analytics-bridge` | stdout (journalctl) | ANALYTICS |
| `hikvision_poller_daemon` | stdout (journalctl) | COLLECTION |

***

# 4. Filebeat Pipeline

## 4.1 Sumber Log

Filebeat mengumpulkan log dari 2 sumber:

1. **Log files** di `/home/infra/dcim_metrics_project/logs/*.log`
2. **Journald** (systemd journal) untuk service yang log ke stdout

## 4.2 Routing di Filebeat

Log di-route ke Elasticsearch berdasarkan tipe:

| Sumber | Index Target | Keterangan |
|--------|-------------|-----------|
| Service logs (JSON structured) | `dcim-logs-app-*` | Log aplikasi DCIM |
| NiFi logs | `dcim-logs-nifi-*` | Log NiFi container |
| System/security logs | `dcim-logs-system-*` | OS-level logs |

## 4.3 JSON Parsing

Filebeat dikonfigurasi untuk auto-parse JSON structured logs:

```yaml
filebeat.inputs:
  - type: log
    paths:
      - /home/infra/dcim_metrics_project/logs/*.log
    json.keys_under_root: true
    json.overwrite_keys: true
    json.add_error_key: true
```

***

# 5. Elasticsearch Data Streams

| Data Stream | Retensi | Keterangan |
|-------------|---------|-----------|
| `dcim-logs-app-*` | 14 hari | Log aplikasi DCIM |
| `dcim-metrics-unified-*` | 7 hari | Metrik telemetri (primary) |
| `dcim-infra-metrics-*` | 7 hari | Infra self-monitoring |
| `dcim-alerts` | 30 hari | Threshold & pipeline alerts |

***

# 6. Kibana Log Dashboard

Dashboard Kibana untuk analisis log termasuk:

1. **Log Volume Timeline**: Histogram per 5 menit, breakdown by `service.name`
2. **Error Rate**: Persentase log ERROR/CRITICAL per service
3. **Top Event Types**: Bar chart `event_type` distribution
4. **Device Activity Heatmap**: Grid `device_type` × `hostname`
5. **Enrichment Status**: Pie chart enrichment_status (FULL/PARTIAL/NOT_IN_CMDB)
6. **DLQ Events**: Timeline DLQ events per topic

***

# 7. Log Taxonomy

## 7.1 Kategori Log

| Kategori | Keterangan | Contoh Event Types |
|----------|-----------|-------------------|
| **PIPELINE** | Alur data dari ingestion ke persist | `normalize_success`, `enrich_miss`, `sql_insert`, `es_bulk` |
| **OPERATIONAL** | Operasi infrastruktur & maintenance | `cache_sync`, `partition_created`, `archive_complete` |
| **ALERTING** | Threshold & pipeline health alerts | `threshold_breach`, `stale_device`, `dlq_spike` |
| **SECURITY** | Autentikasi, akses, audit | `vault_auth`, `redis_lock`, `api_access` |

## 7.2 Severity Model

| Level | Keterangan | Response Time |
|-------|-----------|--------------|
| **P1** | Outage pipeline total | < 15 menit |
| **P2** | Degradasi signifikan (> 30% data loss) | < 1 jam |
| **P3** | Anomali minor (DLQ spike, cache miss tinggi) | < 4 jam |
| **P4** | Informational (scheduled maintenance, normal ops) | Next business day |

***

# 8. Infrastructure Self-Monitoring (L15)

Telegraf memantau kesehatan infrastruktur platform dan menulis ke ES:

File: `configs/telegraf/infra-monitoring.conf`

| Target | Plugin | Metrik |
|--------|--------|--------|
| Elasticsearch | `elasticsearch` | cluster health, node stats, index stats |
| PostgreSQL | `postgresql` | connections, queries, locks, dead tuples |
| Kafka | `jolokia` (via exporter) | broker stats, topic lag, partition status |
| Redis | `redis` | memory usage, hit ratio, connected clients |

Juga tersedia **Prometheus stack** (Grafana di `:3000`, Prometheus di `:9090`):

| Exporter | Container | Port |
|----------|-----------|------|
| `postgres_exporter` | dcim_postgres_exporter | :9187 |
| `elasticsearch_exporter` | dcim_elasticsearch_exporter | :9114 |
| `kafka_exporter` | dcim_kafka_exporter | :9308 |
| `node_exporter` | dcim_node_exporter | :9100 |

***

# 9. Handover Notes

## Log File Locations

```
/home/infra/dcim_metrics_project/logs/
├── normalizer.log
├── es_consumer.log
├── itop_unified.log
├── itop_cache_sync.log
├── threshold_alerts.log
├── dcim_telegram_alerter.log
├── dlq_consumer.log
├── telegram_alerter_state.json
├── data_quality_YYYYMMDD.log
└── partition_management_cron.log
```

## Cara Menambahkan Logging ke Service Baru

```python
import sys
sys.path.append("/home/infra/dcim_metrics_project")
from src.observability.logging.dcim_logger import setup_logger

logger = setup_logger("service-name", "/path/to/logfile.log")
logger.info("Service started", extra={"event_type": "startup", "category": "OPERATIONAL"})
```

***

# 10. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial handover documentation |
