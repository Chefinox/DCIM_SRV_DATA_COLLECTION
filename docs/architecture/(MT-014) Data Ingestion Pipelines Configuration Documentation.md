# (MT-014) Data Ingestion Pipelines Configuration Documentation

# 1. System Configuration Overview

Dokumen ini menjelaskan konfigurasi teknis seluruh komponen pipeline data ingestion DCIM v4.4, termasuk Kafka cluster, Schema Registry, Vault, NiFi, semua consumer, dan systemd services.

***

# 2. Kafka Cluster Configuration

File: `kafka/docker-compose-cluster.yml`

3-node Kafka cluster dengan KRaft mode (tanpa ZooKeeper):

| Node | PLAINTEXT | SSL | Internal |
|------|-----------|-----|----------|
| kafka1 | 9092 | 9094 | 29092 |
| kafka2 | 9095 | 9096 | 29092 |
| kafka3 | 9097 | 9098 | 29092 |

Key settings per broker:

```yaml
environment:
  KAFKA_NODE_ID: 1  # (1, 2, 3 per broker)
  CLUSTER_ID: "dcim-kafka-cluster-001"
  KAFKA_PROCESS_ROLES: "broker,controller"
  KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 3
  KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 3
  KAFKA_DEFAULT_REPLICATION_FACTOR: 3
  KAFKA_MIN_INSYNC_REPLICAS: 2
```

SSL certificates:

```
kafka/certs/
├── ca-cert.pem          # CA certificate (digunakan semua client)
├── kafka1.keystore.jks  # Broker 1 keystore
├── kafka1.truststore.jks
├── kafka2.keystore.jks
├── kafka2.truststore.jks
├── kafka3.keystore.jks
├── kafka3.truststore.jks
```

***

# 3. Vault Configuration

File: `vault/docker-compose.yml`

```yaml
services:
  vault:
    image: hashicorp/vault:1.15
    container_name: vault
    ports:
      - "8200:8200"
    environment:
      VAULT_ADDR: "http://0.0.0.0:8200"
    volumes:
      - vault_data:/vault/file
    cap_add:
      - IPC_LOCK
```

AppRole credentials:

```
vault/config/role_id    # AppRole Role ID
vault/config/secret_id  # AppRole Secret ID
```

Secret paths:

| Path | Keys | Used By |
|------|------|---------|
| `secret/dcim/postgres` | `password` | SQL consumer, lineage tracker |
| `secret/dcim/redfish_pass` | `password` | Redfish pollers |
| `secret/dcim/ralph` | `token` | Ralph sync |

Fallback chain (dari `src/utils/secrets.py`):

```python
def get_secret(name, fallback_env=None):
    # 1. Try Vault AppRole
    # 2. Try Docker secret (/run/secrets/dcim/{name})
    # 3. Try environment variable
```

***

# 4. NiFi Configuration

File: `nifi/docker-compose.yml`

```yaml
services:
  nifi:
    build:
      context: .
      dockerfile: Dockerfile
    image: dcim-nifi-custom:1.0
    container_name: dcim-nifi
    network_mode: "host"
    environment:
      - NIFI_WEB_HTTPS_HOST=0.0.0.0
      - NIFI_WEB_HTTPS_PORT=8443
      - SINGLE_USER_CREDENTIALS_USERNAME=admin
      - SINGLE_USER_CREDENTIALS_PASSWORD_FILE=/run/secrets/nifi_password
      - NIFI_WEB_PROXY_HOST=10.70.0.56:8443
    volumes:
      - nifi_conf:/opt/nifi/nifi-current/conf
      - /etc/dcim/registry:/etc/dcim/registry:ro
      - /home/infra/dcim_metrics_project/scripts:/opt/nifi/nifi-current/scripts:ro
    mem_limit: 2g
```

Custom Docker image includes:
- Python3 + pip
- `snmp-mibs-downloader` (untuk SNMP polling dari NiFi)
- Scripts volume mounted read-only

***

# 5. Consumer Configurations

## 5.1 SQL Consumer

Service: `dcim-sql-consumer.service`

```ini
[Unit]
Description=DCIM SQL Consumer Service (v3.4 Logic in Modular Structure)
After=network.target

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u src/skills/telemetry/event_logger/executor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Key config:

| Parameter | Value |
|-----------|-------|
| Input topic | `dcim.enriched.events` |
| Consumer group | `dcim-postgres-consumer-v2` |
| Deserialization | Avro via Schema Registry |
| Local enrichment | `unified_assets` cache, TTL 300s |
| Target database | `dcim_sot` at `localhost:5432` |

## 5.2 ES Consumer

Service: `dcim-es-consumer.service`

```ini
[Unit]
Description=DCIM Elasticsearch Consumer
After=network.target

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u src/skills/telemetry/es_logger/executor.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Key config:

| Parameter | Value |
|-----------|-------|
| Input topic | `dcim.enriched.events` |
| Consumer group | `dcim-es-consumer` |
| ES endpoint | `https://10.70.0.56:9200` |
| Index pattern | `dcim-metrics-unified-YYYY.MM.DD` |
| Batch size | 50 documents |
| Flush timeout | 5 seconds |

## 5.3 iTop Consumer (v8)

Service: `dcim-itop-unified.service`

Key config:

| Parameter | Value |
|-----------|-------|
| Input topic | `dcim.normalized.events` |
| Consumer group | `dcim_itop_group_v8` |
| iTop API | `http://localhost:8080/webservices/rest.php` |
| Redis Lock | TTL 30s per hostname |
| Cache Invalidation | Auto-recreate CI if deleted, TTL 120s |

***

# 6. DLQ Consumer Configuration

Service: `dcim-dlq-consumer.service`

Script: `scripts/dcim_dlq_consumer.py`

```ini
[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u scripts/dcim_dlq_consumer.py
Restart=always
RestartSec=10
```

Subscribes to 3 DLQ topics:
- `dcim.dlq.parse-failure`
- `dcim.dlq.enrichment-failure`
- `dcim.dlq.delivery-failure`

***

# 7. Systemd Service Files

Semua service definitions tersimpan di `configs/systemd/`:

| File | Service |
|------|---------|
| `dcim-cctv-poller.service` | CCTV daemon poller (MemoryMax=512M, CPUQuota=50%) |
| `dcim-enrichment-api.service` | FastAPI enrichment (:8000) |
| `dcim-itop-redis-sync.service` | iTop → Redis cache sync |
| `dcim-analytics-bridge.service` | Enriched → Analytics topic |
| `dcim-analytics-stream-processor.service` | Kafka → TimescaleDB |
| `dcim-telegram-alerter.service` | Pipeline health Telegram alerts |
| `dcim-telegram-alerter.timer` | Timer: setiap 5 menit |
| `dcim-itop-ralph-sync.service` | iTop + PG → Ralph |
| `dcim-itop-ralph-sync.timer` | Timer: daily 02:00 WIB |
| `dcim-metrics-archive.service` | ES → PG archival (oneshot) |
| `dcim-metrics-archive.timer` | Timer: daily 03:00 WIB |
| `dcim-data-quality-check.service` | Data quality audit (oneshot) |
| `dcim-data-quality-check.timer` | Timer: daily 06:00 WIB |

***

# 8. Cron Configuration

```bash
# crontab -l (user: infra)
0 0 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/manage_partitions.py >> logs/partition_management_cron.log 2>&1
0 * * * * /home/infra/dcim_metrics_project/scripts/maintain_redis_cache.sh
*/5 * * * * python3 /home/infra/dcim_metrics_project/scripts/dcim_itop_inventory_sync.py
```

***

# 9. Operational Commands

```bash
# === Service Management ===
# Check all DCIM services
systemctl list-units --type=service --state=running | grep dcim

# Check all DCIM timers
systemctl list-timers | grep dcim

# Restart specific service
sudo systemctl restart dcim-normalizer.service

# View service logs
journalctl -u dcim-normalizer.service -f

# === Docker Management ===
# Check all containers
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"

# Restart Kafka cluster
cd /home/infra/dcim_metrics_project
docker compose -f kafka/docker-compose-cluster.yml restart

# === Kafka Management ===
# List all topics
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list

# Check topic details
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic dcim.normalized.events

# Check consumer group lag
docker exec kafka1 /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group dcim-normalizer

# === Kafka UI ===
# Web UI: http://10.70.0.56:9000

# === Schema Registry ===
# List schemas
curl http://localhost:8081/subjects

# === Vault ===
# Check vault status
docker exec vault vault status
```

***

# 10. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial configuration documentation |
