# (MT-017) Identification of Critical Logs and Events Configuration Documentation

# 1. System Configuration Overview

Dokumen ini menjelaskan konfigurasi teknis untuk sistem alerting, tracking, dan penanganan error pada pipeline DCIM. Komponen yang didokumentasikan meliputi threshold alerter, Telegram alerter, event lineage tracking, dan DLQ consumer.

***

# 2. Threshold Alerter Configuration

File: `scripts/dcim_threshold_alerter.py`

## 2.1 Threshold Rules

Threshold didefinisikan dalam dictionary Python:

```python
THRESHOLDS = [
    {
        "id": "server-temp-critical",
        "description": "Server Temperature >75°C",
        "device_type": "server",
        "field": "dcim_metrics.raw_fields_srv_reading_celsius",
        "comparator": "gt",
        "threshold": 75,
        "severity": "critical",
        "agg": "max"
    },
    {
        "id": "ups-battery-low",
        "description": "UPS Battery <50%",
        "device_type": "ups",
        "field": "dcim_metrics.raw_fields_battery_capacity",
        "comparator": "lt",
        "threshold": 50,
        "severity": "warning",
        "agg": "min"
    },
    # ... rule lain untuk UPS load, NAS temp, NVR memory, Switch CPU ...
]
```

## 2.2 Systemd Service

File: `configs/systemd/dcim-threshold-alerter.service`

```ini
[Unit]
Description=DCIM Threshold Alerter Service
After=network.target

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u scripts/dcim_threshold_alerter.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Alert disimpan di Elasticsearch pada index `dcim-alerts` (dengan field `alert_id`, `severity`, `description`, `device`, `value`).

***

# 3. Telegram Alerter Configuration

File: `scripts/dcim_telegram_alerter.py`

## 3.1 Bot Settings

```python
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8320149476:AAFy2G5ma1YQnQeIC-PBuwFH1xxiKO38JF4")
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "-5266403936")
TELEGRAM_API       = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
```

## 3.2 State & Cooldown

State file menyimpan status alert terakhir untuk mencegah spam (cooldown 60 menit per tipe alert):
`STATE_FILE = "/home/infra/dcim_metrics_project/logs/telegram_alerter_state.json"`

## 3.3 Systemd Timer

Dijalankan setiap 5 menit via systemd timer.

Timer file: `configs/systemd/dcim-telegram-alerter.timer`
```ini
[Unit]
Description=Timer for DCIM Telegram Alerter

[Timer]
OnCalendar=*:0/5
Persistent=true

[Install]
WantedBy=timers.target
```

Service file: `configs/systemd/dcim-telegram-alerter.service`
```ini
[Unit]
Description=DCIM Telegram Alerter

[Service]
Type=oneshot
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 scripts/dcim_telegram_alerter.py
```

***

# 4. DLQ Consumer Configuration

File: `scripts/dcim_dlq_consumer.py`

## 4.1 Kafka Subscription

Consumer ini subscribe ke 3 topik error:

```python
DLQ_TOPICS = [
    "dcim.dlq.parse-failure",
    "dcim.dlq.enrichment-failure",
    "dcim.dlq.delivery-failure"
]

consumer_conf = {
    'bootstrap.servers': 'localhost:9094',
    'group.id': 'dcim-dlq-consumer',
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False,
    'auto.offset.reset': 'earliest'
}
```

## 4.2 Systemd Service

File: `configs/systemd/dcim-dlq-consumer.service`

```ini
[Unit]
Description=DCIM Dead Letter Queue (DLQ) Consumer
After=network.target kafka.service

[Service]
Type=simple
User=infra
WorkingDirectory=/home/infra/dcim_metrics_project
ExecStart=/usr/bin/python3 -u scripts/dcim_dlq_consumer.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Output log DLQ dicatat ke: `/home/infra/dcim_metrics_project/logs/dlq_consumer.log`

***

# 5. Event Lineage Tracker Configuration

Tracker ini mencatat setiap perpindahan state data ke tabel PostgreSQL.

## 5.1 Database Schema (DDL)

File: `sql/create_lineage_table.sql`

```sql
CREATE TABLE IF NOT EXISTS event_lineage (
    lineage_id UUID PRIMARY KEY,
    event_id TEXT NOT NULL,
    source_system VARCHAR(100),
    
    ingested_at TIMESTAMPTZ,
    
    validation_status VARCHAR(20),
    validated_at TIMESTAMPTZ,
    validation_error TEXT,
    
    enrichment_status VARCHAR(20),
    enriched_at TIMESTAMPTZ,
    enrichment_error TEXT,
    
    routing_status VARCHAR(20),
    routed_at TIMESTAMPTZ,
    target_store VARCHAR(50),
    target_id VARCHAR(100),
    
    processing_ms_total INTEGER
);
```

## 5.2 LineageTracker Class

File: `src/utils/lineage.py`

Koneksi menggunakan psycopg2 connection pool (thread-safe):

```python
_pool = pool.ThreadedConnectionPool(
    1, 20,
    host="10.70.0.56",
    database="dcim_sot",
    user="sot_admin",
    password=db_pass
)
```

Method yang digunakan oleh komponen pipeline:
- `tracker.create_lineage(event_id, source_system)` → Dipanggil oleh Normalizer
- `tracker.update_validation(event_id, status)` → Dipanggil oleh Normalizer (sukses/dlq)
- `tracker.update_enrichment(event_id, status)` → Dipanggil oleh SQL Consumer setelah terima enriched event
- `tracker.update_routing(event_id, target)` → Dipanggil oleh Consumer (PG/ES/iTop) setelah sukses insert

***

# 6. Operational Commands

```bash
# === Threshold Alerter ===
# Restart service
sudo systemctl restart dcim-threshold-alerter.service

# View alerts in Elasticsearch
curl -u elastic:C+H+pFb*aIAqWcOo-X8q -k https://10.70.0.56:9200/dcim-alerts/_search?pretty

# === Telegram Alerter ===
# Run alerter manually
python3 scripts/dcim_telegram_alerter.py

# Check cooldown state
cat logs/telegram_alerter_state.json

# === DLQ Consumer ===
# View DLQ logs
tail -f logs/dlq_consumer.log | jq .

# === Event Lineage ===
# Check lineage count in PG
psql -h localhost -U sot_admin -d dcim_sot -c "SELECT validation_status, count(*) FROM event_lineage GROUP BY validation_status;"
```

***

# 7. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial configuration documentation |
