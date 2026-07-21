# Session Summary — DCIM Pipeline Recovery & Integration
## 2026-07-21 | srv-rnd-dcim (10.70.0.56)

> **Sesi dimulai dari**: Pipeline collapsed — ES hilang, consumer mati, Prometheus/Grafana incomplete  
> **Sesi berakhir**: ✅ Pipeline end-to-end restored, ES+Kibana deployed, Prometheus+Grafana siap external, Kafka broker fix, Network data flowing

---

## Timeline Perbaikan

### 1. Elasticsearch + Kibana — RECOVERED

| Problem | Root Cause | Fix |
|---------|------------|-----|
| ES `10.70.0.56:9200` tidak ada container | Terhapus oleh `docker system prune` (disebut di v4.5.1 changelog) | Deploy `elasticsearch/docker-compose.yml` — ES 9.3.1 + Kibana 9.3.1, single-node, no security |
| Tidak ada docker-compose di git history | ES sebelumnya dijalankan `docker run` langsung | Persistent compose file dibuat & di-commit |

**File**: `elasticsearch/docker-compose.yml`  
**Status**: ✅ ES 9.3.1 UP healthy, Kibana 9.3.1 UP

### 2. Pipeline Services — RESTARTED

| Service | Status | Catatan |
|---------|--------|---------|
| **Normalizer** | ✅ Running (3 instances) | Multi-metric v4.5, output ke `dcim.normalized.events` |
| **Enrichment API** | ✅ Running | Port 8000, Redis connected |
| **NiFi Enrichment** | ✅ Running | ConsumeKafka → LookupRecord → UpdateRecord → PublishKafka |
| **ES Consumer** | ✅ Running | `http://10.70.0.56:9200/_bulk` |
| **SQL Consumer → PG** | ✅ Running | 826K+ rows, batch committed tiap detik |
| **SIEM ES Consumer** | ✅ Running | Wazuh syslog → `dcim-siem-alerts-*` |

### 3. ES/SIEM Consumer SSL Fix

| Consumer | Sebelum | Sesudah |
|----------|---------|---------|
| `es_logger/executor.py` | `ES_URL = "https://..." + auth` | `ES_URL = "http://..."`, `ES_AUTH = None` |
| `siem_es_consumer/app.py` | `ES_URL = "https://..." + auth` | `ES_URL = "http://..."`, `ES_AUTH = None` |

### 4. Schema Registry — EnrichedEvent REGISTERED

| Subject | Status | ID |
|---------|--------|----|
| `dcim.normalized.events-value` | ✅ Existing | 1 |
| `dcim.enriched.events-value` | ✅ **Baru diregister** | 2 |

NiFi enrichment PublishKafka sebelumnya gagal karena subject `dcim.enriched.events-value` tidak ada di Schema Registry. Skema diambil dari `src/schemas/avro_schemas.py → ENRICHED_EVENT_SCHEMA` (28 fields).

### 5. Prometheus + Grafana — FULLY CONFIGURED (then stopped for external)

**Prometheus `prometheus.yml`** — 7 scrape targets:
| Job | Target |
|-----|--------|
| `prometheus` | `localhost:9090` |
| `node_exporter` | `10.70.0.56:9100` |
| `postgresql` | `10.70.0.56:9187` |
| `redis` | `10.70.0.56:9121` |
| `kafka` | `10.70.0.56:9308` |
| `elasticsearch` | `10.70.0.56:9114` |
| `grafana` | `dcim_grafana:3000` |

**Alert Rules** (`rules/dcim-alerts.yml`) — 12 rules:
- Critical: PostgreSQLDown, RedisDown, KafkaBrokerDown, ElasticsearchClusterRed, DiskSpaceCritical
- Warning: PostgreSQLTooManyConnections, RedisHighMemory, KafkaUnderReplicated, ElasticsearchClusterYellow, HighCPU, HighMemory, DiskSpaceLow

**Grafana Datasources** — 3 provisioned:
- Prometheus → `http://dcim_prometheus:9090`
- Elasticsearch → `http://10.70.0.56:9200`
- PostgreSQL → `10.70.0.56:5432 / dcim_sot`

**Lokal Prometheus + Grafana DIHENTIKAN** — karena integrasi ke external `10.70.0.25`. Semua 5 exporter tetap expose di host network:
```
http://10.70.0.56:9100/metrics → node_exporter
http://10.70.0.56:9187/metrics → postgres_exporter
http://10.70.0.56:9121/metrics → redis_exporter
http://10.70.0.56:9308/metrics → kafka_exporter
http://10.70.0.56:9114/metrics → elasticsearch_exporter
```

**File konfigurasi external**: `observability/prometheus/external-prometheus-10.70.0.25.yml`

### 6. Redis Exporter — FIXED

| Problem | Root Cause | Fix |
|---------|------------|-----|
| Container `dcim_redis_exporter` tidak ada | Gagal start — mount `/run/secrets/dcim/sot_db_pass` tidak ada | Hapus `REDIS_PASSWORD_FILE` + volume mount. Redis di host ini tidak pakai password |

### 7. Kafka Broker 2/3 — FIXED (ROOT CAUSE NiFi Ingestion Failure)

**Masalah**: Topic `dcim.raw.network.snmp` dan `dcim.raw.hardware.server` tidak menerima data, padahal NiFi MikroTik & Server processor group RUNNING.

**Root Cause berlapis**:

1. **advertised.listeners** broker 2/3 = `PLAINTEXT://localhost:9092` — menyebabkan inter-broker communication gagal
2. **Partition leader** untuk network & server topic di broker 2 — unreachable dari NiFi
3. **PublishKafka bootstrap** awalnya `127.0.0.1:9092,9095,9097` — multi-broker timeout

**Fix**:
- `kafka/docker-compose-cluster.yml`: advertised listeners diubah ke `PLAINTEXT://10.70.0.56:9092/9095/9097`
- NiFi `flow.json.gz`: PublishKafka bootstrap → `10.70.0.56:9092,10.70.0.56:9095,10.70.0.56:9097` (6 processors)
- Restart broker 2/3 → leader reassign otomatis ke broker 1
- Restart NiFi

### 8. ES Exporter — FIXED

| Sebelum | Sesudah |
|---------|---------|
| `--es.uri=https://10.70.0.56:9200` + SSL skip + basic auth | `--es.uri=http://10.70.0.56:9200` (no auth) |

`elasticsearch_cluster_health` metrics now flowing.

---

## Pipeline End-to-End Status (Final)

| Layer | Komponen | Status |
|-------|----------|--------|
| **L1** | Physical Infrastructure (Server, UPS, NAS, Network, CCTV) | ✅ Active |
| **L2** | NiFi Collection (7 process groups, ALL RUNNING) | ✅ Active |
| | Mikrotik SNMP Ingestion → `dcim.raw.network.snmp` | ✅ **FIXED** |
| | Server Redfish Ingestion → `dcim.raw.hardware.server` | ✅ **FIXED** |
| | UPS SNMP Ingestion → `dcim.raw.power.ups` | ✅ Active |
| | NAS Storage Ingestion → `dcim.raw.storage.nas` | ✅ Active |
| | Security System Ingestion → `dcim.raw.device.isapi` | ✅ Active |
| | Server Inventory Poller | ✅ Active |
| | Security SIEM Ingestion → `dcim.siem.alerts` | ✅ Active |
| **L3** | Kafka 3-node cluster (SSL/TLS) | ✅ Active (broker 2/3 advertised fix) |
| **L3** | Schema Registry | ✅ 2 subjects registered |
| **L4** | Normalizer (v4.5 Multi-Metric) | ✅ Running, ~378K offsets |
| **L5** | NiFi Enrichment | ✅ Running, ~157K offsets |
| **L6** | ES Consumer → `dcim-metrics-unified-*` | ✅ Running |
| **L6** | SQL Consumer → PostgreSQL `dcim_events` | ✅ Running, 826K+ rows |
| **L6** | SIEM ES Consumer → `dcim-siem-alerts-*` | ✅ Running, 2,115+ docs |
| **L7** | Elasticsearch 9.3.1 | ✅ UP |
| **L7** | Kibana 9.3.1 | ✅ UP |
| **L7** | PostgreSQL 15 | ✅ UP |
| **L8** | iTop CMDB | ✅ UP |
| **L8** | Ralph Asset Repository | ✅ UP |
| **L9** | Vault | ✅ UP |

---

## Elasticsearch Indices

| Index | Docs | Deskripsi |
|-------|------|-----------|
| `dcim-metrics-unified-2026.07.21` | 1,405+ | Metrics pipeline (NAS, UPS, CCTV, Server) |
| `dcim-siem-alerts-2026.07.21` | 2,115+ | Wazuh SIEM alerts |

---

## Disk Usage Analysis

| Komponen | Size | Rekomendasi |
|----------|------|-------------|
| `dcim_metrics_archive_y2026_m06` | 134 GB | 🔴 Safe to drop (90 day TimescaleDB retention is primary) |
| `dcim_metrics_archive_y2026_m05` | 73 GB | 🔴 Safe to drop |
| `dlq_records` | 8.5 GB | 🟡 Clean up |
| `event_lineage` + `dcim_lineage` | 1.8 GB | 🟡 Trim old records |
| `/home/infra/` | ~10 GB | 🟢 Normal (VS Code, Hermes, logs) |
| Docker images | ~30 GB | 🟢 Acceptable |

**Total disk**: 826GB / 969GB (86%) — **207GB dari metrics archive bulan Mei-Juni**. TimescaleDB 90-day policy sudah cukup untuk AI training.

---

## AI Training Retention (dcim-wiki Reference)

| Tier | Retention | Location |
|------|-----------|----------|
| TimescaleDB `metrics` hypertable | **90 hari** (auto-drop) | Block 7 |
| TimescaleDB compression | **7 hari** | Auto-compress |
| `dcim_events` PostgreSQL | **7 hari** (partisi harian) | `manage_partitions.py` |
| `dcim_metrics_archive` | **Tidak ada policy** | Akumulasi penyebab disk penuh |

---

## External Prometheus Integration (10.70.0.25)

| Exporter | Port | Endpoint |
|----------|------|----------|
| Node Exporter | 9100 | `http://10.70.0.56:9100/metrics` |
| PostgreSQL Exporter | 9187 | `http://10.70.0.56:9187/metrics` |
| Redis Exporter | 9121 | `http://10.70.0.56:9121/metrics` |
| Kafka Exporter | 9308 | `http://10.70.0.56:9308/metrics` |
| Elasticsearch Exporter | 9114 | `http://10.70.0.56:9114/metrics` |

Prometheus & Grafana lokal sudah dihentikan. File config siap: `observability/prometheus/external-prometheus-10.70.0.25.yml`

---

## Git Commits

```
1f9077e fix: Kafka broker advertised listeners to 10.70.0.56 (was localhost)
baa80ea fix: restore ES+Kibana, fix Kafka broker2/3, register EnrichedEvent schema, ES/SIEM HTTP fix, Prometheus+Grafana configs
```

---

## Pending Actions

| # | Action | Priority | Effort |
|---|--------|----------|--------|
| 1 | Drop/archive `dcim_metrics_archive_y2026_m05` (73GB) & `m06` (134GB) | P1 | Low |
| 2 | Add TimescaleDB retention policy (90d) | P1 | Low |
| 3 | Add PostgreSQL metrics archive retention policy | P2 | Low |
| 4 | Clean `dlq_records` (8.5GB) | P2 | Low |
| 5 | Restart Kafka cluster with fixed compose (persistent advertised listeners) | P2 | Medium |
| 6 | Integrate ke external Prometheus 10.70.0.25 | P2 | Low |
| 7 | Setup NOC dashboard di Grafana external | P3 | Medium |
| 8 | Add `manage_partitions.py` for `dcim_metrics_archive` | P3 | Low |
| 9 | Prometheus Alertmanager integration (currently no alert routing) | P3 | Medium |

---

## Running Containers (Final)

```
dcim_elasticsearch          Up (healthy)     :9200
dcim_kibana                 Up               :5601
dcim-nifi                   Up               host network
kafka1/kafka2/kafka3        Up               :9092-9098
schema-registry             Up               :8081
vault                       Up               :8200
dcim_sot_postgres           Up               :5432
dcim-timescaledb            Up               :5433
dcim-redis-cache            Up               :6379
dcim_node_exporter          Up               :9100
dcim_postgres_exporter      Up               :9187
dcim_redis_exporter         Up               :9121
dcim_kafka_exporter         Up               :9308
dcim_elasticsearch_exporter Up               :9114
itop-web + itop-db          Up               :8080
ralph_web + ralph_nginx     Up               :8082, :7712
```

---

*Generated: 2026-07-21 | Session: DCIM Pipeline Recovery & Prometheus/Grafana Integration*
