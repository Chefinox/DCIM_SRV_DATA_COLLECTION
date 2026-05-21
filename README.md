# DCIM Metrics Project

**Version**: v3.5.5 (Unified Pipeline + Auto-Commissioning/Stale Alerting)  
**Status**: ✅ Production Active  
**Last Updated**: 2026-05-21

## Project Overview

Unified DCIM telemetry and inventory management system using 4-layer decoupled architecture with Apache Kafka as the message broker backbone.

## Architecture

```
Device → Telegraf/Script → Kafka Raw → Normalizer → Kafka Normalized → 
NiFi Enrichment → Kafka Enriched → PostgreSQL/Elasticsearch → Ralph CMDB/Alerts
```

### Monitored Infrastructure
- **Servers**: 5 units (Lenovo ThinkSystem) - Redfish HTTPS
- **UPS**: 1 unit (APC Smart-UPS) - SNMP v3
- **NAS**: 6 units (Synology DS) - SNMP v3
- **Network**: 5 units (MikroTik) - SNMP v2c
- **CCTV/NVR**: 21 units (Hikvision) - ISAPI HTTP

**Total**: 38 devices monitored

## Directory Structure

```
dcim_metrics_project/
├── configs/                    # Configuration files
│   ├── telegraf/              # Telegraf input configs (*.conf)
│   ├── systemd/               # Systemd service files (*.service)
│   ├── docker/                # Docker compose files
│   ├── metric_mapping.json    # Normalization rules
│   └── metric_mapping.yaml    # Alternative format
│
├── scripts/                    # Production scripts
│   ├── dcim_normalizer.py              # Layer 2: Normalization
│   ├── dcim_sql_consumer.py            # Layer 4: PostgreSQL sink
│   ├── dcim_dlq_consumer.py            # Dead letter queue handler
│   ├── kafka_to_es_sync.py             # Kafka to Elasticsearch
│   ├── ralph_cmdb_sync.py              # Unified CMDB sync (all devices)
│   ├── server_inventory_to_pg.py       # Server inventory collector
│   ├── hikvision_poller.py             # CCTV/NVR data collector
│   └── [other production scripts]
│
├── src/                        # Modular architecture (v4.0 structure)
│   ├── tools/                 # Low-level drivers
│   ├── schemas/               # Data models
│   ├── skills/                # Business logic modules
│   ├── workflows/             # Orchestration
│   ├── agents/                # AI integration (future)
│   └── services/              # Microservices
│
├── docs/                       # Documentation
│   ├── architecture/          # Architecture & design docs
│   │   ├── 19-kafka-pipeline-architecture.md
│   │   ├── 24-versioning-change-management-standard.md
│   │   ├── 32-final-architecture-v3.4.md
│   │   ├── 35-pipeline-version-comparison.md
│   │   └── 36-complete-pipeline-diagram.md
│   ├── operations/            # Operational reports
│   ├── development/           # Development guides & metrics
│   └── raw_data/              # Raw device data samples
│
├── tests/                      # Test suite
│   ├── unit/                  # Unit tests
│   ├── integration/           # Integration tests
│   └── fixtures/              # Test fixtures
│
├── logs/                       # Application logs
├── kafka/                      # Kafka data directory
├── ai_agent/                   # AI agent project (future)
│
└── _archived/                  # Deprecated/legacy files
    ├── phase2_legacy/         # Old phase2 implementation
    ├── scratch_dev/           # Development scratch files
    ├── test_scripts/          # Old test scripts
    ├── deprecated_scripts/    # Superseded scripts
    ├── old_configs/           # Obsolete configs
    └── misc_files/            # Miscellaneous archived files
```

## Active Services

### Systemd Services
- `telegraf.service` - Data collection (120s interval)
- `dcim-normalizer.service` - Schema standardization
- `dcim-enrichment-api.service` - FastAPI enrichment endpoint
- `dcim-redis-sync.service` - CMDB cache sync (60s)
- `telegraf-consumer.service` - Elasticsearch sink
- `dcim-sql-consumer.service` - PostgreSQL sink
- `dcim-dlq-consumer.service` - Dead letter queue handler
- `dcim-kafka-es-sync.service` - Kafka to ES bridge
- `dcim-cctv-poller.service` - Hikvision ISAPI CCTV/NVR collector
- `dcim-threshold-alerter.service` - Threshold + stale-device alerting (120s interval)

### Docker Containers
- `kafka-broker` - Message broker (port 9092)
- `dcim-kafka-ui` - Kafka management UI
- `dcim-redis-cache` - Enrichment cache (port 6379)
- `dcim-nifi` - Enrichment orchestration (port 8443)

### Cron Jobs
- `01:00 WIB` - `server_inventory_to_pg.py` (collect server inventory)
- `02:00 WIB` - `ralph_cmdb_sync.py` (sync all devices to Ralph CMDB; auto-register missing DC assets)

## Data Flow

### Metrics Pipeline (Real-time)
```
Device → Telegraf → Kafka Raw → Normalizer → Kafka Normalized → 
NiFi Enrichment → Kafka Enriched → Elasticsearch/PostgreSQL → Kibana
```

### Inventory Pipeline (Daily)
```
Server Redfish → server_inventory_to_pg.py → PostgreSQL dcim_events
Device (NAS/Network/CCTV) → Telegraf → Kafka → ... → PostgreSQL dcim_events
PostgreSQL dcim_events → ralph_cmdb_sync.py → Ralph CMDB
```

### Commissioning / Decommissioning Automation (v3.5.5)
- New DC assets (`server`, `ups`, `nas`, `network_switch`, `nvr`) auto-register in Ralph when serial number appears in PostgreSQL but asset is missing in Ralph.
- CCTV remains a Back Office Asset flow; registration uses `scripts/register_cctv_to_ralph.py`.
- Stale-device detection runs in `dcim-threshold-alerter.service`; alert triggers when known device has no event for 30 minutes.
- Alerts are indexed to Elasticsearch index `dcim-alerts`.
- Kafka 3-second sampling warnings can be false positives because collectors run at 120s interval; prefer topic offsets + PostgreSQL/Elasticsearch counts.

## Key Technologies

- **Message Broker**: Apache Kafka
- **Orchestration**: Apache NiFi 1.24
- **Cache**: Redis 6.x
- **Time-series DB**: Elasticsearch 7.x
- **Relational DB**: PostgreSQL 14
- **CMDB**: Ralph (192.168.101.73:8088)
- **Visualization**: Kibana 7.x
- **Data Collection**: Telegraf, Python

## Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| v3.4.1 | 2026-05-12 | Unified pipeline restored, server_inventory_to_pg.py | **CURRENT** |
| v3.5.0 | 2026-05-07 | Hybrid: v3.4 logic + v4.0 structure | Active |
| v4.0.0 | 2026-05-06 | Modular agentic architecture | Superseded |
| v3.4.0 | 2026-05-04 | NAS & Network auto-update | Superseded |
| v3.3.0 | 2026-05-03 | Unified CMDB sync pipeline | Superseded |
| v3.0.0 | 2026-04-28 | Baseline: Unified Kafka Pipeline | Superseded |

## Quick Start

### Check System Status
```bash
# Check services
sudo systemctl status telegraf dcim-normalizer dcim-enrichment-api

# Check containers
docker ps | grep dcim

# Check logs
tail -f logs/dcim_normalizer.log
```

### Manual Sync
```bash
# Collect server inventory
python3 scripts/server_inventory_to_pg.py

# Sync to Ralph CMDB
python3 scripts/ralph_cmdb_sync.py
```

## Documentation

- **Architecture**: See `docs/architecture/36-complete-pipeline-diagram.md`
- **Versioning**: See `docs/architecture/24-versioning-change-management-standard.md`
- **Operations**: See `docs/operations/` for incident reports
- **Development**: See `docs/development/` for guides and metrics

## Compliance

- **FIT041**: Versioning & Change Management Standard
- **FIT157**: System Architecture Design (Kafka Backbone)

## Support

For issues or questions, refer to documentation in `docs/` directory or check logs in `logs/` directory.

---
**Last Updated**: 2026-05-12  
**Maintained By**: Infrastructure Team
