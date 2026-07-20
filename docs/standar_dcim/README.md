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

> [!WARNING]
> Karena Tim AI melakukan deploy API di server eksternal (`192.168.100.35`), pastikan *environment variables* (`.env`) pada aplikasi Anda menunjuk ke Host `10.70.0.56`! Jika dibiarkan *default* (`localhost`), API Anda akan membaca database di server lokal yang kosong.

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

> [!IMPORTANT]
> Untuk akses dari luar jaringan internal docker (seperti dari server Tim AI), **wajib** menggunakan port `9094` dengan koneksi `SSL`. Penggunaan port `9092` hanya berlaku untuk internal lokal dan akan mengembalikan _localhost_.

```python
from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'dcim.analytics.metrics',
    bootstrap_servers='10.70.0.56:9094',
    group_id='ai-team-consumer',
    auto_offset_reset='earliest',
    security_protocol='SSL',
    ssl_cafile='ca-cert.pem', # Hubungi Tim Infra untuk mendapatkan CA Certificate
    value_deserializer=lambda m: json.loads(m.decode('utf-8'))
)
```

for message in consumer:
    print(message.value)
```

---

## Arsitektur Overview

```
Sources → NiFi (Pollers) → Kafka (Raw) → NiFi (Enrich) → Kafka (Avro) 
                                                              ↓
Tim AI ← TimescaleDB ← Stream Processor ← Kafka (JSON) ← Analytics Bridge
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