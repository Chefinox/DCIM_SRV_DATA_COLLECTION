# Standar DCIM Documentation

> Kumpulan dokumentasi standar DCIM Analytics Pipeline

---

## Daftar Dokumen

| # | Dokumen | Deskripsi |
|---|---------|-----------|
| 1 | [ai-team-access.md](ai-team-access.md) | Panduan akses untuk Tim AI |
| 2 | [ai-pipeline-architecture.md](ai-pipeline-architecture.md) | Arsitektur pipeline AI/ML |

---

## Quick Start - Akses Tim AI

### 1. Connect ke Database

```bash
psql -h 10.70.0.56 -p 5433 -U ai_team -d dcim_analytics
```

### 2. Query Data

```sql
-- Get latest metrics
SELECT * FROM metrics ORDER BY time DESC LIMIT 10;

-- Get hourly aggregates
SELECT * FROM metrics_hourly ORDER BY time DESC LIMIT 10;

-- Get daily aggregates
SELECT * FROM metrics_daily ORDER BY time DESC LIMIT 10;
```

### 3. Consume Kafka Topic

```python
from kafka import KafkaConsumer

consumer = KafkaConsumer(
    'dcim.analytics.metrics',
    bootstrap_servers='10.70.0.56:9092',
    group_id='ai-team-consumer',
    auto_offset_reset='earliest',
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)

for message in consumer:
    print(message.value)
```

---

## Arsitektur Overview

```
Sources → Telegraf/NiFi → Kafka → Stream Processor → TimescaleDB → Tim AI
                                              ↓
                                        Kafka Topics
                                        (dcim.analytics.*)
```

---

## Component Matrix

| Component | Host | Port | Purpose |
|-----------|------|------|---------|
| PostgreSQL (Main) | 10.70.0.56 | 5432 | dcim_sot |
| **TimescaleDB** | **10.70.0.56** | **5433** | **dcim_analytics** |
| Kafka | 10.70.0.56 | 9092 | Message broker |
| Schema Registry | 10.70.0.56 | 8081 | Avro schemas |
| Vault | 10.70.0.56 | 8200 | Secrets |
| NiFi | 10.70.0.56 | 8080 | Processing |

---

## Links

- [dcim-wiki](../dcim-wiki/) - Knowledge base referensi
- [Architecture Docs](../architecture/) - Dokumentasi arsitektur
- [Scripts](../scripts/) - Pipeline scripts
- [Configs](../configs/) - Konfigurasi

---

## Support

Untuk pertanyaan atau masalah:
- Check logs: `/home/infra/dcim_metrics_project/logs/`
- Contact: Infrastructure Team

---

> Last Updated: 2026-07-08