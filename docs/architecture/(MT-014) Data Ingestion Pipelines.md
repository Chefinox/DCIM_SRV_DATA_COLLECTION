# (MT-014) Data Ingestion Pipelines

# 1. Overview

## Objective

Membangun pipeline pengumpulan data end-to-end untuk telemetri data center secara real-time dan batch, mencakup:

* **Real-time streaming**: Polling perangkat setiap 30–120 detik via Redfish, SNMP, ISAPI
* **Batch processing**: Inventory deep scan harian, archival ES→PG harian
* **Message broker**: Apache Kafka 3-node cluster dengan SSL/TLS dan Avro serialization
* **Normalisasi**: Transformasi data multi-vendor ke Common Data Model (CDM)
* **Enrichment**: Penambahan metadata CMDB via Redis cache + FastAPI
* **Persist**: 3 consumer independen (PostgreSQL, Elasticsearch, iTop CMDB)
* **Error handling**: Dead Letter Queue (DLQ) dengan lineage tracking

## Arsitektur Pipeline v4.4

Pipeline berjalan di host `srv-rnd-dcim` (10.70.0.56) dengan arsitektur 7-layer:

```
L1  Physical Infrastructure (49 perangkat)
 ↓
L2  Collection (NiFi ExecuteProcess + Daemon)
 ↓
L3  Kafka Raw Topics (8 raw topics, SSL/TLS, RF=3)
 ↓
L4  Normalize (Avro via Schema Registry)
 ↓
L5  Enrich (NiFi + Redis + FastAPI)
 ↓
L6  Persist (3 consumers: SQL, ES, iTop)
 ↓
L7  Storage & Dashboard (PG 15, ES 9.x, Kibana)
```

***

# 2. Platform Infrastructure

## 2.1 Kafka Cluster (3-Node, SSL/TLS)

| Item | Detail |
|------|--------|
| **Image** | `apache/kafka:3.7.0` |
| **Compose** | `kafka/docker-compose-cluster.yml` |
| **Mode** | KRaft (tanpa ZooKeeper) |
| **Nodes** | kafka1 (9092/9094), kafka2 (9095/9096), kafka3 (9097/9098) |
| **SSL Certs** | `kafka/certs/` (JKS keystore & truststore, CA cert PEM) |
| **Replication Factor** | 3 |
| **Min ISR** | 2 |

Semua producer dan consumer terhubung via **SSL port 9094**:

```python
{
    'bootstrap.servers': 'localhost:9094',
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False
}
```

## 2.2 Schema Registry

| Item | Detail |
|------|--------|
| **Image** | `confluentinc/cp-schema-registry:7.6.0` |
| **Port** | `:8081` |
| **Schemas** | NormalizedEvent (Avro, 18 fields), EnrichedEvent (Avro, 26 fields) |

## 2.3 HashiCorp Vault

| Item | Detail |
|------|--------|
| **Image** | `hashicorp/vault:1.15` |
| **Port** | `:8200` |
| **Auth** | AppRole (`vault/config/role_id`, `vault/config/secret_id`) |
| **Secret Path** | `secret/dcim/*` (KV-v2) |
| **Client** | `src/utils/secrets.py` → `get_secret()` |

## 2.4 Apache NiFi

| Item | Detail |
|------|--------|
| **Image** | `dcim-nifi-custom:1.0` (custom dengan Python3 + snmp-mibs) |
| **Network** | `network_mode: host` |
| **Web UI** | `https://10.70.0.56:8443/nifi` |
| **Scripts Volume** | `/home/infra/dcim_metrics_project/scripts` → `/opt/nifi/nifi-current/scripts:ro` |

***

# 3. Collection Layer (L2)

Semua proses polling tersentralisasi menggunakan **Apache NiFi** via `ExecuteProcess` (kecuali CCTV yang menggunakan systemd daemon).

| Sumber | Metode | Script | Interval | Output Topic |
|--------|--------|--------|----------|-------------|
| Server Redfish | NiFi ExecuteProcess | `redfish_poller.py` | 60s | `dcim.raw.hardware.server` |
| Server CPU/Mem | NiFi ExecuteProcess | `redfish_telemetry_poller.py` | 30s | `dcim.raw.hardware.server` |
| Server Inventory | NiFi Cron | `server_inventory_collector.py` | Daily 01:00 | `dcim.raw.hardware.server.inventory` |
| UPS | NiFi ExecuteProcess | `snmp_ups_poller.py` | 60s | `dcim.raw.power.ups` |
| NAS | NiFi ExecuteProcess | `nas_poller.py` | 120s | `dcim.raw.storage.nas` |
| Network | NiFi ExecuteProcess | `mikrotik_poller.py` | 60s | `dcim.raw.network.snmp` / `.interfaces` |
| CCTV/NVR | Systemd daemon | `hikvision_poller_daemon.py` | 120s | `dcim.raw.device.isapi` |

***

# 4. Kafka Topics (L3)

| Kategori | Topik | Format | Replication |
|----------|-------|--------|-------------|
| **Raw** | `dcim.raw.hardware.server` | JSON | 3 |
| **Raw** | `dcim.raw.hardware.server.inventory` | JSON | 3 |
| **Raw** | `dcim.raw.power.ups` | JSON | 3 |
| **Raw** | `dcim.raw.storage.nas` | JSON | 3 |
| **Raw** | `dcim.raw.network.snmp` | JSON | 3 |
| **Raw** | `dcim.raw.network.interfaces` | JSON | 3 |
| **Raw** | `dcim.raw.device.isapi` | JSON | 3 |
| **Raw** | `dcim.raw.remote.ssh` (reserved) | JSON | 3 |
| **Normalized** | `dcim.normalized.events` | **Avro** | 3 |
| **Enriched** | `dcim.enriched.events` | **Avro** | 3 |
| **DLQ** | `dcim.dlq.parse-failure` | Raw bytes | 3 |
| **DLQ** | `dcim.dlq.enrichment-failure` | Raw bytes | 3 |
| **DLQ** | `dcim.dlq.delivery-failure` | Raw bytes | 3 |

***

# 5. Normalization Layer (L4)

| Item | Detail |
|------|--------|
| **Service** | `dcim-normalizer.service` |
| **Skrip** | `src/skills/telemetry/normalizer/executor.py` |
| **Input** | Semua `dcim.raw.*` (regex subscribe) |
| **Output** | `dcim.normalized.events` (Avro) |
| **Mapping** | `configs/metric_mapping.json` |

Alur: JSON parse → resolve device_type → resolve hostname → resolve serial → field computation → metric resolve → Avro serialize → produce → lineage track.

***

# 6. Enrichment Layer (L5)

| Item | Detail |
|------|--------|
| **Orchestrator** | Apache NiFi 1.24.0 |
| **API** | `dcim-enrichment-api.service` (FastAPI port `:8000`) |
| **Cache** | Redis 7 Alpine (`localhost:6379`) |
| **Cache Sync** | `dcim-itop-redis-sync.service` (60s loop) |
| **Input** | `dcim.normalized.events` (Avro) |
| **Output** | `dcim.enriched.events` (Avro) |

Alur NiFi: ConsumeKafkaRecord → LookupRecord (GET `/enrich/{sn}`) → PublishKafkaRecord.

Enrichment menambahkan 8 field metadata CMDB: `site_id`, `rack_id`, `tenant`, `status`, `asset_tag`, `owner`, `department`, `cmdb_sync_time`.

***

# 7. Persist Layer (L6)

Tiga consumer independen mengkonsumsi data enriched:

## 7.1 SQL Consumer → PostgreSQL

| Item | Detail |
|------|--------|
| **Service** | `dcim-sql-consumer.service` |
| **Skrip** | `src/skills/telemetry/event_logger/executor.py` |
| **Input** | `dcim.enriched.events` (Avro) |
| **Output** | PostgreSQL `dcim_events` + tabel relasional |
| **Consumer Group** | `dcim-postgres-consumer-v2` |
| **Fitur** | **Dual-layer enrichment** — NiFi upstream + local SQL enrichment via `unified_assets` cache (TTL 300s) |

Ketika `metric_name == 'inventory_snapshot'`, consumer melakukan **Clear and Replace** pada tabel komponen: `dcim_server_disks`, `dcim_server_ram`, `dcim_server_processors`, `dcim_server_nics`.

## 7.2 ES Consumer → Elasticsearch

| Item | Detail |
|------|--------|
| **Service** | `dcim-es-consumer.service` |
| **Skrip** | `src/skills/telemetry/es_logger/executor.py` |
| **Input** | `dcim.enriched.events` (Avro) |
| **Output** | Elasticsearch `dcim-metrics-unified-YYYY.MM.DD` |
| **Consumer Group** | `dcim-es-consumer` |
| **Batch** | 50 dokumen, flush 5 detik |

## 7.3 iTop Consumer → CMDB

| Item | Detail |
|------|--------|
| **Service** | `dcim-itop-unified.service` (v8) |
| **Skrip** | `scripts/dcim_itop_unified_consumer.py` |
| **Input** | `dcim.normalized.events` (Avro) |
| **Output** | iTop REST API (`localhost:8080`) |
| **Consumer Group** | `dcim_itop_group_v8` |
| **Fitur** | Redis Distributed Lock (TTL 30s), Smart Cache Invalidation, auto-create CI |

***

# 8. Dead Letter Queue (L10)

| Topik DLQ | Diisi Oleh | Jenis Error |
|-----------|-----------|-------------|
| `dcim.dlq.parse-failure` | Normalizer | JSON parse error, schema tidak dikenal |
| `dcim.dlq.enrichment-failure` | NiFi Enrichment | Enrichment API gagal respond |
| `dcim.dlq.delivery-failure` | SQL/iTop Consumer | Gagal simpan ke PostgreSQL/iTop |

**DLQ Consumer** (`dcim-dlq-consumer.service`): Mengkonsumsi semua 3 topik DLQ, log ke file, retry jika memungkinkan, dan track lineage dengan `status="dlq"`.

***

# 9. Pipeline Scheduling

## 9.1 Systemd Services (Daemon — Always Running)

| Service | Fungsi |
|---------|--------|
| `dcim-normalizer.service` | Normalisasi raw → Avro |
| `dcim-enrichment-api.service` | FastAPI enrichment (:8000) |
| `dcim-itop-redis-sync.service` | iTop → Redis cache (60s) |
| `dcim-sql-consumer.service` | Avro enriched → PostgreSQL |
| `dcim-es-consumer.service` | Avro enriched → Elasticsearch |
| `dcim-itop-unified.service` | Avro normalized → iTop CMDB |
| `dcim-cctv-poller.service` | CCTV/NVR daemon poller |
| `dcim-threshold-alerter.service` | Threshold & stale alerting |
| `dcim-dlq-consumer.service` | DLQ consumer + retry |
| `dcim-analytics-bridge.service` | Enriched → Analytics topic |
| `dcim-analytics-stream-processor.service` | Analytics → TimescaleDB |

## 9.2 Systemd Timers

| Timer | Jadwal | Fungsi |
|-------|--------|--------|
| `dcim-telegram-alerter.timer` | Setiap 5 menit | Pipeline health → Telegram |
| `dcim-itop-ralph-sync.timer` | Daily 02:00 WIB | iTop + PG → Ralph |
| `dcim-metrics-archive.timer` | Daily 03:00 WIB | ES → PG archival |
| `dcim-data-quality-check.timer` | Daily 06:00 WIB | Data quality audit |

## 9.3 Cron Jobs

| Waktu | Skrip | Fungsi |
|-------|-------|--------|
| `0 0 * * *` | `manage_partitions.py` | Manajemen partisi PostgreSQL |
| `0 * * * *` | `maintain_redis_cache.sh` | Redis cache maintenance |
| `*/5 * * * *` | `dcim_itop_inventory_sync.py` | Sinkronisasi komponen PG → iTop |

## 9.4 Docker Compose Stacks

| Stack | Compose File | Containers |
|-------|-------------|-----------|
| Kafka Cluster | `kafka/docker-compose-cluster.yml` | kafka1, kafka2, kafka3 |
| Schema Registry | `schema-registry/docker-compose.yml` | schema-registry |
| Vault | `vault/docker-compose.yml` | vault |
| NiFi + Redis + UI | `nifi/docker-compose.yml` | dcim-nifi, dcim-redis-cache, dcim-kafka-ui |
| PostgreSQL | (external) | dcim_sot_postgres |
| iTop | `itop/docker-compose.yml` | itop-web, itop-db |

***

# 10. Storage Layer (L7)

## PostgreSQL 15

| Item | Detail |
|------|--------|
| **Container** | `dcim_sot_postgres` |
| **Port** | `localhost:5432` |
| **Database** | `dcim_sot` |
| **Tabel utama** | `dcim_events` (partisi harian, retensi 7 hari), `unified_assets`, `dcim_server_*`, `event_lineage`, `dcim_metrics_archive` |

## Elasticsearch 9.x

| Item | Detail |
|------|--------|
| **Container** | `es01` |
| **Port** | `10.70.0.56:9200` (HTTPS) |
| **Index** | `dcim-metrics-unified-*`, `dcim-alerts`, `dcim-infra-metrics-*`, `dcim-logs-app-*` |

## Kibana

| Item | Detail |
|------|--------|
| **Container** | `kib01` |
| **Port** | `10.70.0.56:5601` |
| **Dashboard** | DCIM Monitoring, Alert Overview, Log Dashboard |

***

# 11. Handover Notes

## Quick Start — Restart Seluruh Pipeline

```bash
# 1. Start infrastructure
cd /home/infra/dcim_metrics_project
docker compose -f kafka/docker-compose-cluster.yml up -d
docker compose -f schema-registry/docker-compose.yml up -d
docker compose -f vault/docker-compose.yml up -d
docker compose -f nifi/docker-compose.yml up -d

# 2. Start all services
sudo systemctl start dcim-normalizer dcim-enrichment-api dcim-itop-redis-sync \
  dcim-sql-consumer dcim-es-consumer dcim-itop-unified dcim-cctv-poller \
  dcim-threshold-alerter dcim-dlq-consumer dcim-analytics-bridge \
  dcim-analytics-stream-processor

# 3. Start timers
sudo systemctl start dcim-telegram-alerter.timer dcim-data-quality-check.timer \
  dcim-metrics-archive.timer dcim-itop-ralph-sync.timer
```

## Troubleshooting

| Masalah | Penyebab | Solusi |
|---------|---------|-------|
| Data tidak masuk | NiFi processor stopped | Buka NiFi UI, start processor group |
| Avro decode error | Schema mismatch | Periksa Schema Registry: `curl http://localhost:8081/subjects` |
| DLQ penuh | Source data korup | Periksa `dcim-dlq-consumer.service` log |
| Enrichment kosong | Redis cache expired | Restart `dcim-itop-redis-sync.service` |
| iTop consumer error | Redis lock timeout | Restart `dcim-itop-unified.service` |

***

# 12. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial handover documentation |
