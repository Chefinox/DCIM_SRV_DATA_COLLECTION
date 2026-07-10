# (MT-013) Standardization of Telemetry Schema Configuration Documentation

# 1. System Configuration Overview

Dokumen ini menjelaskan konfigurasi teknis seluruh komponen yang terlibat dalam standarisasi skema telemetri: Avro schemas, Schema Registry, Normalizer service, Enrichment API, dan metric mapping.

Arsitektur standardisasi:

```
Raw JSON (multi-format per vendor)
        ↓
Normalizer (metric_mapping.json + Avro serialize)
        ↓
dcim.normalized.events (Avro NormalizedEvent)
        ↓
NiFi Enrichment (Redis + FastAPI)
        ↓
dcim.enriched.events (Avro EnrichedEvent)
```

***

# 2. Avro Schema Definitions

File: `src/schemas/avro_schemas.py`

## NormalizedEvent Schema

```python
NORMALIZED_EVENT_SCHEMA = """
{
  "type": "record",
  "name": "NormalizedEvent",
  "namespace": "dcim.events",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_time", "type": ["null", "string"], "default": null},
    {"name": "timestamp", "type": ["null", "long", "string", "double"], "default": null},
    {"name": "source_topic", "type": "string"},
    {"name": "measurement", "type": ["null", "string"], "default": null},
    {"name": "device_type", "type": "string"},
    {"name": "hostname", "type": "string"},
    {"name": "ip", "type": ["null", "string"], "default": null},
    {"name": "serial_number", "type": ["null", "string"], "default": null},
    {"name": "metric_name", "type": "string"},
    {"name": "metric_value", "type": ["null", "double", "int", "string"], "default": null},
    {"name": "metric_unit", "type": ["null", "string"], "default": null},
    {"name": "severity", "type": ["null", "string"], "default": null},
    {"name": "manufacturer", "type": ["null", "string"], "default": null},
    {"name": "model", "type": ["null", "string"], "default": null},
    {"name": "firmware", "type": ["null", "string"], "default": null},
    {"name": "raw_fields", "type": ["null", "string"], "default": null},
    {"name": "raw_tags", "type": ["null", "string"], "default": null}
  ]
}
"""
```

## EnrichedEvent Schema

```python
ENRICHED_EVENT_SCHEMA = """
{
  "type": "record",
  "name": "EnrichedEvent",
  "namespace": "dcim.events",
  "fields": [
    {"name": "event_id", "type": "string"},
    {"name": "event_time", "type": ["null", "string"], "default": null},
    {"name": "timestamp", "type": ["null", "long", "string", "double"], "default": null},
    {"name": "source_topic", "type": "string"},
    {"name": "measurement", "type": ["null", "string"], "default": null},
    {"name": "device_type", "type": "string"},
    {"name": "hostname", "type": "string"},
    {"name": "ip", "type": ["null", "string"], "default": null},
    {"name": "serial_number", "type": ["null", "string"], "default": null},
    {"name": "metric_name", "type": "string"},
    {"name": "metric_value", "type": ["null", "double", "int", "string"], "default": null},
    {"name": "metric_unit", "type": ["null", "string"], "default": null},
    {"name": "severity", "type": ["null", "string"], "default": null},
    {"name": "manufacturer", "type": ["null", "string"], "default": null},
    {"name": "model", "type": ["null", "string"], "default": null},
    {"name": "firmware", "type": ["null", "string"], "default": null},
    {"name": "raw_fields", "type": ["null", "string"], "default": null},
    {"name": "raw_tags", "type": ["null", "string"], "default": null},
    {"name": "site_id", "type": ["null", "string"], "default": null},
    {"name": "rack_id", "type": ["null", "string"], "default": null},
    {"name": "tenant", "type": ["null", "string"], "default": null},
    {"name": "status", "type": ["null", "string"], "default": null},
    {"name": "asset_tag", "type": ["null", "string"], "default": null},
    {"name": "owner", "type": ["null", "string"], "default": null},
    {"name": "department", "type": ["null", "string"], "default": null},
    {"name": "cmdb_sync_time", "type": ["null", "string"], "default": null}
  ]
}
"""
```

***

# 3. Metric Mapping Configuration

File: `configs/metric_mapping.json`

```json
{
  "topic_to_device_type": {
    "dcim.raw.network": "network_switch",
    "dcim.raw.power.ups": "ups",
    "dcim.raw.storage.nas": "nas",
    "dcim.raw.server": "server",
    "dcim.raw.cctv": "cctv",
    "dcim.raw.device.isapi": "cctv"
  },
  "measurement_to_device_type": {
    "interface": "network_switch",
    "ups_apc": "ups",
    "dcim_nas": "nas",
    "server_redfish": "server",
    "server_redfish_util": "server",
    "server_inventory": "server",
    "cctv_metrics": "cctv"
  },
  "dcim_nas": {
    "metric_name": "disk_temperature",
    "metric_field": "diskTemp",
    "metric_unit": "celsius",
    "severity_field": "diskStatus",
    "severity_map": {
      "1": "info",
      "2": "warning",
      "3": "critical"
    }
  },
  "ups_apc": {
    "metric_name": "battery_capacity",
    "metric_field": "battery_capacity",
    "metric_unit": "percent",
    "secondary_metrics": [
      {"field": "battery_temp", "name": "battery_temperature", "unit": "celsius"},
      {"field": "output_voltage", "name": "output_voltage", "unit": "volt"}
    ]
  },
  "interface": {
    "metric_name": "interface_status",
    "metric_field": "ifOperStatus",
    "metric_unit": "status_code"
  },
  "server_redfish_util": {
    "metric_name": "cpu_utilization",
    "metric_field": "cpuUtilization",
    "metric_unit": "percent",
    "secondary_metrics": [
      {"field": "memoryUsage", "name": "memory_utilization", "unit": "percent"}
    ]
  },
  "server_inventory": {
    "metric_name": "inventory_snapshot",
    "metric_field": null
  },
  "default": {
    "metric_name": "general_metric",
    "metric_field": null,
    "metric_unit": null
  }
}
```

***

# 4. Schema Registry Configuration

File: `schema-registry/docker-compose.yml`

```yaml
version: '3.8'
services:
  schema-registry:
    image: confluentinc/cp-schema-registry:7.6.0
    container_name: schema-registry
    ports:
      - "8081:8081"
    environment:
      SCHEMA_REGISTRY_HOST_NAME: schema-registry
      SCHEMA_REGISTRY_KAFKASTORE_BOOTSTRAP_SERVERS: "kafka1:29092,kafka2:29092,kafka3:29092"
      SCHEMA_REGISTRY_LISTENERS: "http://0.0.0.0:8081"
    networks:
      - kafka_default

networks:
  kafka_default:
    external: true
```

***

# 5. Normalizer Service Configuration

## Systemd Service

File: `configs/systemd/dcim-normalizer.service` (terdaftar di systemd)

```ini
[Unit]
Description=DCIM Normalizer Service (v3.4 Logic in Modular Structure)
After=network.target

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u src/skills/telemetry/normalizer/executor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Kafka Connection Configuration

Dari `src/skills/telemetry/normalizer/executor.py`:

```python
consumer_conf = {
    'bootstrap.servers': 'localhost:9094',
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False,
    'group.id': 'dcim-normalizer',
    'auto.offset.reset': 'earliest'
}

producer_conf = {
    'bootstrap.servers': 'localhost:9094',
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False
}

schema_registry_conf = {'url': 'http://localhost:8081'}
```

***

# 6. Enrichment API Configuration

## Systemd Service

```ini
[Unit]
Description=DCIM Enrichment API Service (v3.4 Logic in Modular Structure)
After=network.target

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u -m uvicorn src.skills.inventory.enrichment.executor:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Redis Connection

```python
redis_client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
```

## Cache Key Pattern

```
asset:sn:{serial_number_lowercase}    → Primary lookup
asset:{serial_number_lowercase}        → Legacy fallback
asset:ip:{ip_address_lowercase}        → SIEM IP-based fallback
```

TTL: 3600 seconds (1 jam), diperbarui oleh `itop_to_cache_sync.py` setiap 60 detik.

## iTop Redis Sync Service

File: `configs/systemd/dcim-itop-redis-sync.service`

```ini
[Unit]
Description=DCIM Redis Cache Sync — iTop to Redis (v4.0)
After=network.target docker.service

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 scripts/itop_to_cache_sync.py
Restart=always
RestartSec=10
StandardOutput=append:/home/infra/dcim_metrics_project/logs/itop_cache_sync.log
StandardError=append:/home/infra/dcim_metrics_project/logs/itop_cache_sync.log

[Install]
WantedBy=multi-user.target
```

***

# 7. Operational Commands

```bash
# Check Schema Registry schemas
curl http://localhost:8081/subjects

# Check specific schema versions
curl http://localhost:8081/subjects/NormalizedEvent/versions

# Restart normalizer
sudo systemctl restart dcim-normalizer.service

# Restart enrichment API
sudo systemctl restart dcim-enrichment-api.service

# Restart Redis cache sync
sudo systemctl restart dcim-itop-redis-sync.service

# Check enrichment API health
curl http://localhost:8000/docs

# Check unknown assets
curl http://localhost:8000/unknown-assets

# Check Redis cache entry
redis-cli -h localhost -p 6379 GET "asset:sn:<serial_number>"
```

***

# 8. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial configuration documentation |
