# BASELINE RESMI PRE-UPGRADE KAFKA 4.1.x (CO-LOCATED TOPOLOGY)

**Tanggal Audit:** 2026-07-29
**Host Node 1:** `srv-rnd-dcim` (`10.70.0.56`)
**Topologi Cluster:** 3 Broker Co-located (`kafka1`, `kafka2`, `kafka3` di Node 1)
**KAFKA_CONTROLLER_QUORUM_VOTERS:** `1@kafka1:9093,2@kafka2:9093,3@kafka3:9093`

---

## 1. Backup Data Volume & Konfigurasi

### 1.1 Data Volume Backup Archives
- `kafka1`: `/home/infra/dcim_metrics_project/kafka/backups/kafka1_data-backup-20260729-1347.tar.gz` (Ukuran: **5.2 MB**)
- `kafka2`: `/home/infra/dcim_metrics_project/kafka/backups/kafka2_data-backup-20260729-1352.tar.gz` (Ukuran: **2.9 MB**)
- `kafka3`: `/home/infra/dcim_metrics_project/kafka/backups/kafka3_data-backup-20260729-1352.tar.gz` (Ukuran: **41 MB**)

### 1.2 Docker Compose Backup
- Backup path: `/home/infra/dcim_metrics_project/kafka/docker-compose-cluster.yml.bak-preupgrade41-20260729-1448`

---

## 2. Status Image Target
- **Target Tag Image:** `apache/kafka:4.1.2` (Dikonfirmasi dari Docker Hub)
- **Status Image:** Pulled & verified di Docker local store (`apache/kafka:4.1.2`).

---

## 3. Status Baseline Container & Systemd Service

### 3.1 Docker Containers (Pipeline Related)
| Container Name | Status | Port Mappings |
|---|---|---|
| `kafka1` | Up 8 days | 0.0.0.0:9092->9092/tcp, 0.0.0.0:9094->9094/tcp |
| `kafka2` | Up 6 hours | 9092/tcp, 0.0.0.0:9095-9096->9095-9096/tcp |
| `kafka3` | Up 21 minutes | 9092/tcp, 0.0.0.0:9097-9098->9097-9098/tcp |
| `dcim-nifi` | Up 2 days | - |
| `itop-web` | Up 23 hours (healthy) | 0.0.0.0:8080->80/tcp |
| `itop-db` | Up 10 days (healthy) | 0.0.0.0:3306->3306/tcp |
| `dcim_elasticsearch` | Up 5 days (healthy) | 0.0.0.0:9200->9200/tcp, 0.0.0.0:9300->9300/tcp |
| `dcim_sot_postgres` | Up 10 days | 0.0.0.0:5432->5432/tcp |
| `dcim-timescaledb` | Up 10 days (healthy) | 0.0.0.0:5433->5432/tcp |
| `dcim-redis-cache` | Up 10 days | 0.0.0.0:6379->6379/tcp |

### 3.2 Systemd DCIM Services
- `dcim-analytics-bridge.service` - `active (running)`
- `dcim-analytics-stream-processor.service` - `active (running)`
- `dcim-enrichment-api.service` - `active (running)`
- `dcim-es-consumer.service` - `active (running)`
- `dcim-itop-redis-sync.service` - `active (running)`
- `dcim-itop-unified.service` - `active (running)`
- `dcim-normalizer.service` - `active (running)`
- `dcim-siem-es-consumer.service` - `active (running)`
- `dcim-sql-consumer.service` - `active (running)`
- `dcim-threshold-alerter.service` - `active (running)`

---

## 4. Status LAG Seluruh 7 Consumer Group Produksi

| Consumer Group Name | Target Topic | Status Lag | Status Consumer |
|---|---|---|---|
| `nifi-enrichment-group` | `dcim.raw.*` | **0** | Active / Normal |
| `dcim_itop_group_v8` | `dcim.normalized.events` | **0** | Active / Normal |
| `dcim-postgres-consumer-v2` | `dcim.enriched.events` | **0** | Active / Normal |
| `dcim-siem-es-consumer-2` | `dcim.siem.alerts` | **0** | Active / Normal |
| `dcim-analytics-bridge` | `dcim.enriched.events` | **0** | Active / Normal |
| `dcim_python_normalizer_group` | `dcim.raw.*` | **0** | Active / Normal |
| `dcim-es-consumer` | `dcim.enriched.events` | **0** | Active / Normal |

---

## 5. Replikasi & Partisi Baseline
- `under-replicated-partitions`: **KOSONG (0)**
- `unavailable-partitions`: **KOSONG (0)**

---

## 6. Audit Logging Log4j
- **Mount Configuration:** Default image configuration (`no custom log4j mounts`).
- **Kesimpulan:** Tidak memerlukan konversi khusus Log4j2 pada upgrade ke Kafka 4.1.x.

---

## 7. Status Apache NiFi Java Runtime
- NiFi process: `/opt/java/openjdk/bin/java -Xmx1g -Xms1g ... org.apache.nifi.NiFi` (PID 71).
- Status flow: Running, tanpa backpressure kritis.
