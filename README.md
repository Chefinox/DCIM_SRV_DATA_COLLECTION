# DCIM Metrics Project

**Version**: v4.8.0 (Virtualization Ingestion, ITSM Mock Readiness, Pipeline Remediation, Load Test Verified)  
**Status**: ✅ Production Active  
**Last Updated**: 2026-08-28


## Project Overview

Unified DCIM telemetry and inventory management system using multi-layer decoupled architecture with Apache Kafka as the message broker backbone. All 6 device types use **NiFi ExecuteProcess** for uniform data ingestion.

## Architecture

```mermaid
flowchart LR
    Device[DCIM Devices] --> NiFi[Apache NiFi]
    NiFi --> KRaw[Kafka Raw]
    VM[Proxmox Mock API :8085] --> KRaw
    KRaw --> Norm[dcim-normalizer]
    Norm -- Avro --> KNorm[Kafka Normalized]
    
    KNorm --> Enrich[NiFi Enrichment + FastAPI]
    Enrich -- Avro --> KEnriched[Kafka Enriched]
    
    KEnriched --> ES[(Elasticsearch 9.3.1)]
    KEnriched --> PG[(PostgreSQL 15)]
    KEnriched --> TSDB[(TimescaleDB)]
    
    PG -.-> iTop[(iTop CMDB)]
    iTop -.-> Ralph[(Ralph)]
    
    KEnriched --> Bridge[Analytics Bridge]
    Bridge --> TSDB
    
    ES --> Kibana[Kibana]
    ES --> Alert[Alerting]
    Alert --> TG[Telegram]
    
    KEnriched -.-> ITSM[ITSM Mock API :8083]
```

### Monitored Infrastructure
- **Servers**: 5 units (Lenovo ThinkSystem) - Redfish HTTPS
- **UPS**: 1 unit (APC Smart-UPS) - SNMP v3
- **NAS**: 6 units (Synology DS) - SNMP v3
- **Network**: 5 units (MikroTik) - SNMP v2c
- **CCTV/NVR**: 32 units (Hikvision: 31 Cameras + 1 NVR) - ISAPI HTTP
- **Virtualization**: 3 VMs (Proxmox Mock Fixture Adapter) - REST API

**Total**: 52 devices monitored (49 physical + 3 virtual mock)

## Directory Structure

```
dcim_metrics_project/
├── configs/                    # Configuration files
│   ├── telegraf/               # Telegraf input configs (legacy, disabled)
│   ├── systemd/                # Systemd services and timers
│   ├── docker/                 # Docker compose files
│   ├── secrets/                # Secret configuration files
│   └── metric_mapping.json     # Normalization rules (25 metric types)
│
├── docs/                       # Documentation
│   ├── architecture/           # Architecture & design docs (v4.7, v4.8)
│   │   └── _archived/         # Superseded architecture docs (v4.6 and older)
│   ├── handoff/                # Handover reports
│   │   └── _archived/         # Completed prompt-agent specs
│   ├── operations/             # Operational/incident reports
│   │   └── _archived/         # Superseded operation docs
│   ├── standar_dcim/           # Compliance, SOP, and AI team guides
│   │   └── _archived/         # Superseded implementation plans & prompts
│   ├── development/            # Development guides & metrics
│   ├── changes/                # Change management reports
│   ├── incidents/              # Post-mortem incident reports
│   └── Task Tracker/          # Task tracker TSV files (active versions)
│
├── elasticsearch/              # Elasticsearch docker-compose
├── exporters/                  # Prometheus exporters docker-compose
├── itop/                       # iTop CMDB integration & auto-registration
├── kafka/                      # Kafka 3-node cluster docker-compose & certs
├── nifi/                       # Apache NiFi flows & templates
├── observability/              # Prometheus + Grafana configuration
├── schema-registry/            # Confluent Avro schemas
├── vault/                      # HashiCorp Vault secrets policies
├── timescaledb/                # TimescaleDB continuous aggregates schemas
│
├── scripts/                    # Active utility scripts, pollers, consumers
│   ├── redfish_poller.py       # Server Redfish data collector
│   ├── snmp_ups_poller.py      # UPS SNMP data collector
│   ├── nas_poller.py           # NAS SNMP data collector
│   ├── mikrotik_poller.py      # Network SNMP data collector
│   ├── cctv_poller.py          # CCTV/NVR ISAPI data collector
│   ├── virtualization_poller.py         # Virtualization Kafka poller (Port 8085)
│   ├── virtualization_poller_nifi.py    # Virtualization NiFi poller (Port 8085)
│   ├── trigger_itsm_ticket.py           # ITSM ServiceNow/Jira ticket trigger
│   ├── dcim_itop_unified_consumer.py    # iTop CMDB auto-registration (v8)
│   ├── dcim_telegram_alerter.py         # Alert notification service
│   ├── dcim_threshold_alerter.py        # Threshold & stale device alerter
│   └── _archived/              # Legacy/superseded scripts & backup files
│
├── src/                        # Modular Architecture Core
│   ├── configs/                # Configuration loader (Vault integration)
│   ├── schemas/                # Pydantic & Avro data models
│   ├── connectors/             # External system adapters
│   │   ├── virtualization/     # Proxmox Fixture Adapter (Port 8085)
│   │   └── itsm/               # ITSM ServiceNow/Jira Mock API (Port 8083)
│   ├── skills/                 # Core processing logic
│   │   ├── telemetry/          # Normalizer, ES/SQL consumers, SIEM
│   │   ├── inventory/          # Enrichment API, Redfish scanner
│   │   ├── cmdb/               # Asset enricher
│   │   └── security/           # Hikvision poller
│   ├── utils/                  # Lineage tracking, secrets, Kafka producers
│   ├── observability/          # Logging & metrics
│   └── tools/                  # Integration tools
│
├── tests/                      # Test suites
│   └── load_testing/           # Locust load test scripts
│
├── sql/                        # SQL schemas & migrations
├── _archived/                  # Legacy/superseded code & old files
├── logs/                       # Application & service logs
├── rollback_snapshots/         # Rollback snapshots (used/ subfolder)
└── ai_agent/                   # AI integration & analytics models
```

## Active Services

### NiFi Process Groups (Data Ingestion)
| Process Group | Poller | Schedule | Topic |
|---|---|---|---|
| Server Redfish Ingestion | `redfish_poller.py` | 60s | `dcim.raw.hardware.server` |
| UPS SNMP Ingestion | `snmp_ups_poller.py` | 60s | `dcim.raw.power.ups` |
| NAS Storage Ingestion | `nas_poller.py` | 60s | `dcim.raw.storage.nas` |
| Mikrotik SNMP Ingestion | `mikrotik_poller.py` | 60s | `dcim.raw.network.snmp` |
| Security System Ingestion | `cctv_poller.py` | 120s | `dcim.raw.device.isapi` |
| Server Inventory Poller | `server_inventory_collector.py` | 1 day | `dcim.raw.hardware.server.inventory` |
| Security SIEM Ingestion | ListenSyslog (Wazuh) | event-driven | `dcim.siem.alerts` |

### Systemd Services (Pipeline)
- `dcim-normalizer.service` - Schema standardization & multi-metric normalization (Avro output, 25 metric types)
- `dcim-enrichment-api.service` - FastAPI enrichment endpoint (:8000)
- `dcim-itop-redis-sync.service` - CMDB cache sync (60s)
- `dcim-es-consumer.service` - Elasticsearch sink (Python Avro)
- `dcim-sql-consumer.service` - PostgreSQL sink & local SQL enrichment (Python Avro)
- `dcim-itop-unified.service` - iTop CMDB automated registration v8 (Python Avro)
- `dcim-siem-es-consumer.service` - SIEM alerts consumer
- `dcim-dlq-consumer.service` - Dead letter queue handler & lineage tracking
- `dcim-threshold-alerter.service` - Threshold + stale-device alerting (120s interval)
- `dcim-proxmox-mock-api.service` - Proxmox Virtualization Fixture Adapter (:8085)
- `dcim-itsm-mock-api.service` - ITSM ServiceNow/Jira Fixture Adapter (:8083)

### Systemd Services (AI Analytics)
- `dcim-analytics-bridge.service` - Analytics Bridge (Kafka Avro → JSON)
- `dcim-analytics-stream-processor.service` - Analytics Stream Processor → TimescaleDB

### Systemd Timers & Cron Jobs
- `dcim-virtualization-poller.timer` - Virtualization poller every 1 minute
- `dcim-itop-ralph-sync.timer` - Daily sync to Ralph CMDB (02:00 WIB)
- `dcim-telegram-alerter.timer` - Telegram alerter every 5 minutes
- `dcim-data-quality-check.timer` - Daily pipeline data quality check (06:00 WIB)
- `0 0 * * *` - Partition management for PostgreSQL `dcim_events`
- `0 * * * *` - Redis cache maintenance
- `*/5 * * * *` - PG → iTop inventory sync

### Docker Containers (25+ active)

| Stack | Containers |
|---|---|
| **Kafka Cluster** | `kafka1`, `kafka2`, `kafka3` (4.1.2, KRaft, SSL, Named Volumes) |
| **Schema Registry** | `schema-registry` (Confluent 7.6.0, Port 8081) |
| **Vault** | `vault` (HashiCorp 1.15) |
| **NiFi** | `dcim-nifi` (custom Python3 image) |
| **Redis** | `dcim-redis-cache` (7-alpine) |
| **Elasticsearch + Kibana** | `dcim_elasticsearch`, `dcim_kibana` (9.3.1) |
| **PostgreSQL** | `dcim_sot_postgres` (15-alpine) |
| **TimescaleDB** | `dcim-timescaledb` (PG 15) |
| **iTop** | `itop-web` (3.2.3), `itop-db` (MariaDB 10.11), `itop-cloudbeaver` |
| **Ralph** | `ralph_web`, `ralph_nginx`, `ralph_inkpy`, `docker-db-1`, `docker-redis-1` |
| **Prometheus Exporters** | `dcim_node_exporter`, `dcim_postgres_exporter`, `dcim_redis_exporter`, `dcim_kafka_exporter`, `dcim_elasticsearch_exporter` |
| **Observability** | Prometheus + Grafana (external `10.70.0.25`) |
| **PgAdmin** | `dcim_pgadmin` |
| **Kafka UI** | `dcim-kafka-ui` (Kafbat UI) |
| **Telegraf** | `dcim-telegraf-consumer` |

## Data Flow

### Metrics Pipeline (Real-time)
```
Device → NiFi ExecuteProcess → Kafka Raw (JSON) → Normalizer (Multi-Metric) →
Kafka Normalized (Avro) → NiFi Enrichment → Kafka Enriched (Avro) →
Elasticsearch 9.3.1 / PostgreSQL 15 → Kibana
```

### AI Analytics Pipeline
```
Kafka Enriched (Avro) → dcim-analytics-bridge → Kafka Analytics (JSON) →
dcim-analytics-stream-processor → TimescaleDB (hypertable, 25 metric types)
```

### Inventory Pipeline (Hybrid)
```
1. Real-time CMDB:
Kafka (dcim.normalized.events) → dcim-itop-unified.service → iTop CMDB (Auto-create CI)

2. Batch Asset Sync (Daily):
Server Redfish → NiFi ExecuteProcess → Kafka Raw Inventory → Normalizer → ... → PostgreSQL
PostgreSQL / iTop → itop_to_ralph_sync.py → Ralph Asset Repository
```

### Commissioning / Decommissioning Automation
- New DC assets auto-register in iTop CMDB via the unified consumer when a serial number appears in Kafka.
- Stale-device detection runs in `dcim-threshold-alerter.service`; alert triggers when a known device has no event for 30 minutes.
- Alerts are indexed to Elasticsearch index `dcim-alerts`.

## Key Technologies

- **Message Broker**: Apache Kafka 4.1.2 (3-node cluster, SSL/TLS, Schema Registry, external `10.70.0.56:9094`)
- **Orchestration & Polling**: Apache NiFi 1.24 (custom Python3 image, 7 process groups)
- **Cache**: Redis 7
- **Time-series DB (Analytics)**: TimescaleDB (PostgreSQL 15, port 5433)
- **Search & Telemetry**: Elasticsearch 9.3.1
- **Relational DB**: PostgreSQL 15
- **Secrets Management**: HashiCorp Vault 1.15 (AppRole auth, per-connector isolation)
- **CMDB (Primary)**: iTop 3.2.3 (10.70.0.56:8080)
- **Asset Repository**: Ralph (10.70.0.56:8082)
- **Visualization**: Kibana 9.3.1
- **Monitoring**: Prometheus + Grafana + 5 Exporters (Node, PG, Redis, Kafka, ES)
- **Data Collection**: NiFi ExecuteProcess (Python pollers)
- **Load Testing**: Locust (219+ req/s, 0% error rate verified)

## Version History

| Version | Date | Changes | Status |
|---------|------|---------|--------|
| v4.8.0 | 2026-08-28 | Virtualization Ingestion (Port 8085), ITSM Mock Readiness (Port 8083), Normalizer DLQ Reject Fix, Load Test Verified (219 req/s), Repository Cleanup & Archival | **CURRENT** |
| v4.7.0 | 2026-08-11 | Validation Engine (Range, Regex, Duplicate, Freshness), DLQ 3-Topic + 4-Stage Lineage, Impact Scoring, Data Quality Scorecard, Fixture-Replay Connectors | Superseded |
| v4.6.2 | 2026-08-04 | Kafka 4.1.2 upgrade, log dirs persistence fix, iTop consumer lag remediation (0 lag), MariaDB/Postgres index optimization | Superseded |
| v4.6.1 | 2026-07-27 | 12-partition topic alignment across all Kafka topics, Kafbat UI compose restoration | Superseded |
| v4.6.0 | 2026-07-24 | Circuit Breaker Pattern, Data Classification Matrix, Prometheus CB exporter | Superseded |
| v4.5.2 | 2026-07-24 | Kafka broker listener fix, ES 9.3.1 restore, Prometheus exporters active, project cleanup | Superseded |
| v4.5.1 | 2026-07-21 | CCTV NiFi migration, credential hardening, systemd bridge removal | Superseded |
| v4.5.0 | 2026-07-20 | Multi-metric normalizer (25 types), computed energy metrics, Ralph asset_id | Superseded |
| v4.4.0 | 2026-07-10 | Full NiFi Cutover, SIEM Consumer, AI Pipeline (TimescaleDB) | Superseded |
| v4.3.0 | 2026-07-01 | Kafka 3-Node SSL Cluster, Schema Registry (Avro), HashiCorp Vault Integration | Superseded |

## Quick Start

### Check System Status
```bash
# Check core pipeline services
sudo systemctl status dcim-normalizer dcim-enrichment-api dcim-sql-consumer dcim-es-consumer dcim-itop-unified

# Check mock fixture services
sudo systemctl status dcim-proxmox-mock-api dcim-itsm-mock-api dcim-virtualization-poller.timer

# Check infrastructure containers
docker ps --format "table {{.Names}}\t{{.Status}}" | grep -E "dcim|kafka|schema|vault|itop|ralph"

# Check NiFi process groups
curl -sk https://localhost:8443/nifi-api/process-groups/root/process-groups | python3 -m json.tool

# Check active service logs via journalctl
sudo journalctl -u dcim-normalizer -f
```

## Documentation

- **Architecture**: See `docs/architecture/v4.8-pipeline-architecture.md`
- **Comparison**: See `docs/architecture/v4.8-pipeline-architecture-komparasi.md`
- **Gap Analysis**: See `docs/architecture/v4.7-gap-analysis-aktual-vs-wiki.md`
- **Implementation Plan**: See `docs/architecture/v4.7-implementation-plan-data-ingestion-gaps.md`
- **Versioning**: See `docs/architecture/24-versioning-change-management-standard.md`
- **Operations**: See `docs/operations/` for incident reports
- **AI Team**: See `docs/standar_dcim/` for AI access guides
- **Development**: See `docs/development/` for guides and metrics
