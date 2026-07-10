# (MT-015) Data Synchronization for AI Models Configuration Documentation

# 1. System Configuration Overview

Dokumen ini menjelaskan konfigurasi teknis seluruh komponen sinkronisasi data untuk AI/ML: TimescaleDB, analytics bridge, stream processor, archival pipeline, materialized views, dan AI access role.

***

# 2. TimescaleDB Configuration

File: `timescaledb/docker-compose.yml`

```yaml
version: '3.8'
services:
  timescaledb:
    image: timescale/timescaledb:latest-pg15
    container_name: dcim-timescaledb
    environment:
      POSTGRES_DB: dcim_analytics
      POSTGRES_USER: analytics_user
      POSTGRES_PASSWORD: ${TIMESCALE_DB_PASS:-changeme}
    ports:
      - "5433:5432"
    volumes:
      - timescaledb_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U analytics_user -d dcim_analytics"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  timescaledb_data:
```

Connection config:

| Parameter | Value |
|-----------|-------|
| Host | `localhost` |
| Port | `5433` |
| Database | `dcim_analytics` |
| User | `analytics_user` |
| Password | via env `TIMESCALE_DB_PASS` |

***

# 3. Analytics Bridge Configuration

## Systemd Service

File: `configs/systemd/dcim-analytics-bridge.service`

```ini
[Unit]
Description=DCIM Analytics Bridge Service
After=network.target kafka.service dcim-normalizer.service dcim-enrichment-api.service

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u /home/infra/dcim_metrics_project/scripts/dcim_analytics_bridge.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

## Kafka Configuration

```python
KAFKA_BOOTSTRAP_SERVERS = 'localhost:9094'
SCHEMA_REGISTRY_URL = 'http://localhost:8081'
SOURCE_TOPIC = 'dcim.enriched.events'
TARGET_TOPIC = 'dcim.analytics.metrics'

consumer_conf = {
    'bootstrap.servers': KAFKA_BOOTSTRAP_SERVERS,
    'group.id': 'dcim-analytics-bridge',
    'auto.offset.reset': 'latest',
    'enable.auto.commit': True,
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False
}
```

***

# 4. Stream Processor Configuration

## Systemd Service

File: `configs/systemd/dcim-analytics-stream-processor.service`

```ini
[Unit]
Description=DCIM Analytics Stream Processor (Kafka to TimescaleDB)
After=network.target dcim-analytics-bridge.service

[Service]
Type=simple
User=infra
Group=infra
WorkingDirectory=/home/infra/dcim_metrics_project
Environment="KAFKA_BOOTSTRAP_SERVERS=localhost:9094"
Environment="TIMESCALE_DB_HOST=localhost"
Environment="TIMESCALE_DB_PORT=5433"
Environment="TIMESCALE_DB_NAME=dcim_analytics"
Environment="TIMESCALE_DB_USER=analytics_user"
Environment="TIMESCALE_DB_PASS=changeme"
ExecStart=/usr/bin/python3 -u /home/infra/dcim_metrics_project/scripts/analytics_stream_processor.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
```

## Topics Configuration

```python
METRICS_TOPIC = 'dcim.analytics.metrics'
ANOMALIES_TOPIC = 'dcim.analytics.anomalies'
PREDICTIONS_TOPIC = 'dcim.analytics.predictions'
CONSUMER_GROUP = 'analytics-stream-processor'
```

***

# 5. ES-to-PG Archive Configuration

## Systemd Timer + Service

Timer file: `configs/systemd/dcim-metrics-archive.timer`

```ini
[Unit]
Description=DCIM Metrics Archive Timer

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
```

Service file: `configs/systemd/dcim-metrics-archive.service`

```ini
[Unit]
Description=DCIM Metrics Archive (ES to PG)

[Service]
Type=oneshot
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 scripts/es_to_pg_archive.py
```

## Script Configuration

File: `scripts/es_to_pg_archive.py`

```python
ES_URL = "https://10.70.0.56:9200"
INDEX = "dcim-metrics-unified-*"
AUTH = ('elastic', '<password>')

PG_PARAMS = {
    "host": "localhost",
    "user": "sot_admin",
    "password": "<password>",
    "dbname": "dcim_sot"
}
```

Mode operasi:
- **Incremental** (default): Arsipkan data 24 jam terakhir
- **Backfill**: `--mode backfill --start-date 2026-04-01 --end-date 2026-07-01`

***

# 6. AI Access Role SQL

File: `sql/ai_access_role.sql`

```sql
-- 1) Role login (idempoten)
SELECT 'CREATE ROLE dcim_ai_reader LOGIN'
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'dcim_ai_reader')
\gexec

ALTER ROLE dcim_ai_reader LOGIN PASSWORD :'ai_pw';
ALTER ROLE dcim_ai_reader NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
ALTER ROLE dcim_ai_reader CONNECTION LIMIT 10;

-- 2) Hak koneksi
GRANT CONNECT ON DATABASE dcim_sot TO dcim_ai_reader;
GRANT USAGE ON SCHEMA public TO dcim_ai_reader;

-- 3) READ-ONLY pada sumber data latih
GRANT SELECT ON
    v_train_server, v_train_ups, v_train_nas,
    v_train_network, v_train_cctv, v_train_nvr,
    dcim_metrics_archive, dcim_failure_events,
    unified_assets, dcim_server_disks, dcim_server_ram,
    dcim_server_processors, dcim_server_nics
  TO dcim_ai_reader;

-- 4) WRITE pada wadah hasil saja
GRANT SELECT, INSERT, UPDATE ON dcim_server_anomalies TO dcim_ai_reader;
GRANT USAGE, SELECT ON SEQUENCE dcim_server_anomalies_id_seq TO dcim_ai_reader;

-- 5) Jaring pengaman: REVOKE tulis ke tabel operasional
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON dcim_events FROM dcim_ai_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON dcim_metrics_archive FROM dcim_ai_reader;
REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON dcim_failure_events FROM dcim_ai_reader;
```

Cara deploy:

```bash
psql -v ai_pw="'<PASSWORD>'" -f sql/ai_access_role.sql
```

***

# 7. Data Quality Configuration

## Schema File

File: `configs/data_quality_schema.yaml`

```yaml
server:
  - serial_number
  - model
  - raw_fields.cpuUtilization
  - raw_fields.memoryUsage
  - raw_fields.power_output_watts
  - raw_fields.system_temp

ups:
  - serial_number
  - model
  - raw_fields.output_load
  - raw_fields.battery_temp
  - raw_fields.battery_runtime_remain

network:
  - serial_number
  - model
  - raw_fields.cpu_load

nas:
  - serial_number
  - model
  - raw_fields.diskTemp
```

## Timer + Service

Timer: `dcim-data-quality-check.timer` (daily 06:00 WIB)

Script: `scripts/audit_data_quality.py`

Output: `logs/data_quality_YYYYMMDD.log`

***

# 8. Operational Commands

```bash
# === TimescaleDB ===
# Connect to TimescaleDB
psql -h localhost -p 5433 -U analytics_user -d dcim_analytics

# Check hypertable info
SELECT * FROM timescaledb_information.hypertables;

# Check chunk info
SELECT * FROM timescaledb_information.chunks WHERE hypertable_name = 'metrics';

# === Analytics Services ===
# Restart analytics bridge
sudo systemctl restart dcim-analytics-bridge.service

# Restart stream processor
sudo systemctl restart dcim-analytics-stream-processor.service

# Check status
systemctl status dcim-analytics-bridge dcim-analytics-stream-processor

# === Archive ===
# Run archive manually
python3 scripts/es_to_pg_archive.py

# Run backfill
python3 scripts/es_to_pg_archive.py --mode backfill --start-date 2026-04-01

# Check archive data
psql -h localhost -U sot_admin -d dcim_sot -c "SELECT device_type, count(*) FROM dcim_metrics_archive GROUP BY device_type;"

# === Materialized Views ===
# Refresh materialized views
psql -h localhost -U sot_admin -d dcim_sot -c "REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_server;"

# === Data Quality ===
# Run audit manually
python3 scripts/audit_data_quality.py

# Check last audit log
cat logs/data_quality_$(date +%Y%m%d).log

# === AI Access ===
# Test AI reader access
psql -h 10.70.0.56 -U dcim_ai_reader -d dcim_sot -c "SELECT * FROM v_train_server LIMIT 5;"

# Export training data
python3 scripts/export_training_data.py --device-type server --format csv
```

***

# 9. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial configuration documentation |
