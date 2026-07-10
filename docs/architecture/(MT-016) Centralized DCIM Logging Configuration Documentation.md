# (MT-016) Centralized DCIM Logging Configuration Documentation

# 1. System Configuration Overview

Dokumen ini menjelaskan konfigurasi teknis implementasi logging terpusat, mencakup modul logger Python, konfigurasi Filebeat, pengaturan Elasticsearch data streams, Telegraf self-monitoring, dan operasional Kibana.

***

# 2. Python Logger Module

File: `src/observability/logging/dcim_logger.py`

## 2.1 JSON Formatter

```python
import logging
import json
import sys
import traceback
from datetime import datetime, timezone

class DCIMJsonFormatter(logging.Formatter):
    def __init__(self, service_name="dcim-service"):
        super().__init__()
        self.service_name = service_name

    def format(self, record):
        log_entry = {
            "@timestamp": datetime.now(timezone.utc).isoformat(),
            "service": {"name": self.service_name},
            "log": {"level": record.levelname},
            "message": record.getMessage(),
        }
        
        standard_fields = ["event_type", "device_type", "hostname", "serial_number", "category", "severity"]
        for field in standard_fields:
            if hasattr(record, field):
                log_entry[field] = getattr(record, field)
                
        if record.exc_info:
            log_entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
            
        return json.dumps(log_entry)
```

## 2.2 Setup Function

```python
def setup_logger(service_name, log_file=None, level=logging.INFO):
    logger = logging.getLogger(service_name)
    logger.setLevel(level)
    
    if logger.hasHandlers():
        logger.handlers.clear()
        
    formatter = DCIMJsonFormatter(service_name)
    
    # stdout handler for journald
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)
    
    # optional file handler
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)
        except Exception as e:
            console_handler.setLevel(logging.WARNING)
            logger.warning(f"Failed to setup file handler for {log_file}: {e}")
            
    return logger
```

***

# 3. Filebeat Configuration

Filebeat diinstal langsung di host (`srv-rnd-dcim`).

File: `/etc/filebeat/filebeat.yml`

```yaml
filebeat.inputs:
# 1. Log files (JSON parsed)
- type: log
  enabled: true
  paths:
    - /home/infra/dcim_metrics_project/logs/*.log
  json.keys_under_root: true
  json.overwrite_keys: true
  json.add_error_key: true
  fields:
    log_source: "file"
    environment: "production"
  fields_under_root: true

# 2. Journald (Systemd services)
- type: journald
  id: dcim-services
  include_matches:
    - _SYSTEMD_UNIT=dcim-enrichment-api.service
    - _SYSTEMD_UNIT=dcim-sql-consumer.service
    - _SYSTEMD_UNIT=dcim-analytics-bridge.service
    - _SYSTEMD_UNIT=hikvision_poller_daemon.service

processors:
  - drop_fields:
      fields: ["host", "agent", "ecs"]

setup.ilm.enabled: true
setup.ilm.rollover_alias: "dcim-logs-app"
setup.ilm.pattern: "{now/d}-000001"

output.elasticsearch:
  hosts: ["https://10.70.0.56:9200"]
  username: "elastic"
  password: "${ES_PASSWORD}"
  ssl.verification_mode: "none"
  index: "dcim-logs-app-%{+yyyy.MM.dd}"
```

Service systemd:
```bash
sudo systemctl enable filebeat
sudo systemctl start filebeat
```

***

# 4. Elasticsearch Data Streams & ILM

Data di Elasticsearch diatur menggunakan **Index Lifecycle Management (ILM)** untuk retensi otomatis.

| Policy Name | Data Stream | Rollover | Delete Phase |
|-------------|-------------|----------|--------------|
| `dcim-logs-policy` | `dcim-logs-app-*` | 5GB / 1 day | 14 days |
| `dcim-metrics-policy` | `dcim-metrics-unified-*` | 10GB / 1 day | 7 days |
| `dcim-infra-policy` | `dcim-infra-metrics-*` | 5GB / 1 day | 7 days |
| `dcim-alerts-policy` | `dcim-alerts` | 1GB / 7 days | 30 days |

***

# 5. Infrastructure Self-Monitoring

Telegraf mengumpulkan metrik dari sistem inti dan mengirimnya ke ES.

File: `configs/telegraf/infra-monitoring.conf`

```toml
[agent]
  interval = "60s"
  round_interval = true
  metric_batch_size = 1000
  metric_buffer_limit = 10000
  collection_jitter = "0s"
  flush_interval = "10s"
  flush_jitter = "0s"
  precision = ""
  hostname = "srv-rnd-dcim"
  omit_hostname = false

# Output ke ES
[[outputs.elasticsearch]]
  urls = ["https://10.70.0.56:9200"]
  timeout = "5s"
  enable_sniffer = false
  health_check_interval = "10s"
  index_name = "dcim-infra-metrics-%Y.%m.%d"
  manage_template = false
  username = "elastic"
  password = "$ES_PASSWORD"
  insecure_skip_verify = true

# Input PostgreSQL
[[inputs.postgresql]]
  address = "postgres://sot_admin:Inovasi%400918@localhost/dcim_sot?sslmode=disable"
  databases = ["dcim_sot"]

# Input Elasticsearch cluster health
[[inputs.elasticsearch]]
  servers = ["https://10.70.0.56:9200"]
  username = "elastic"
  password = "$ES_PASSWORD"
  cluster_health = true
  cluster_stats = true
  insecure_skip_verify = true

# Input Redis (opsional, via port lokal)
[[inputs.redis]]
  servers = ["tcp://localhost:6379"]
```

***

# 6. Prometheus Exporters Stack

Selain Telegraf, tersedia stack Prometheus (di `docker-compose.yml` utama atau exporter-specific).

| Exporter | Image | Port |
|----------|-------|------|
| Elasticsearch | `prometheuscommunity/elasticsearch-exporter:latest` | `:9114` |
| PostgreSQL | `prometheuscommunity/postgres-exporter:latest` | `:9187` |
| Kafka | `danielqsj/kafka-exporter:latest` | `:9308` |
| Node | `prom/node-exporter:latest` | `:9100` |
| Prometheus | `prom/prometheus:v2.45.0` | `:9090` |
| Grafana | `grafana/grafana:10.0.3` | `:3000` |

***

# 7. Operational Commands

```bash
# === Filebeat ===
# Test config
sudo filebeat test config

# Test ES output
sudo filebeat test output

# View Filebeat logs
sudo journalctl -u filebeat -f

# === ES ILM (Kibana Dev Tools) ===
# Check ILM status
GET _ilm/status

# Check policy
GET _ilm/policy/dcim-logs-policy

# Check data stream stats
GET _data_stream/dcim-logs-app-*

# === Log Analysis ===
# View raw service log file
tail -f /home/infra/dcim_metrics_project/logs/normalizer.log | jq .

# View journald JSON output (using jq for formatting)
journalctl -u dcim-enrichment-api -f -o cat | jq .
```

***

# 8. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial configuration documentation |
