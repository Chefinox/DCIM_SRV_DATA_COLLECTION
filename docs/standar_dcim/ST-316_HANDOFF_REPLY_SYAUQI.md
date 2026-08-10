---
title: "ST-316 Handoff Resolution — Reply from Syauqi (DBA & Ingestion Team)"
created: 2026-08-04
task: ST-316
status: resolved
author: Imam Syauqi Achmad (DBA / Ingestion Team)
target_audience: AI Team (Fakhri / Block 7)
---

# ST-316 Handoff Resolution & Reply Notes

Dokumen ini berisi konfirmasi penyelesaian seluruh item blocker pada **ST-316 (End-to-End Real-Time Anomaly Flow Validation)** yang ditugaskan kepada **Syauqi (DBA & Ingestion Team)**.

---

## 1. Status Penyelesaian Tasks Syauqi

| No | Task | Status | Detail Verification |
|---|---|---|---|
| 1 | **Eksekusi Migration 003 — Lineage Columns** | 🟢 **COMPLETED** | Skema `anomaly_events` di DB `dcim_analytics` telah diperbarui dengan 6 kolom baru + unique index `dedup_key`. Role `ai_team` terverifikasi memiliki akses `SELECT`, `INSERT`, `UPDATE` pada kolom-kolom baru. |
| 2 | **Ketersediaan Topic Kafka** | 🟢 **COMPLETED** | Topic input `dcim.analytics.metrics` dan topic output `dcim.analytics.anomalies` **tersedia & aktif** (masing-masing 12 partisi, replication factor 3). |
| 3 | **Verifikasi Kafka SSL & Host Block 7** | 🟢 **VERIFIED** | Handshake TLS 1.3 pada port `9094` terkonfirmasi aktif (`ca-cert.pem` valid s.d 2036). Diperlukan penyesuaian `ssl_check_hostname=False` pada client Block 7. |

---

## 2. Detail Implementasi & Verifikasi DB Migration 003

**File Migrasi**: `sql/003_add_anomaly_lineage_and_idempotency.sql`  
**Database**: `dcim_analytics` (TimescaleDB pada port 5433)  
**Executed By**: `analytics_user`

### Kolom Baru yang Ditambahkan pada `public.anomaly_events`:

| Kolom | Tipe Data | Constraint / Default | Fungsi Tracing |
|---|---|---|---|
| `correlation_id` | `UUID` | - | Tracing E2E metric → anomaly → workflow |
| `dedup_key` | `TEXT` | `UNIQUE` | Mencegah duplicate incident akibat replay |
| `event_state` | `VARCHAR(20)` | `DEFAULT 'anomaly'` | State event (`anomaly` / `recovery`) |
| `source_event_id` | `UUID` | - | Event ID dari Kafka upstream |
| `test_run_id` | `UUID` | - | Links ke test run untuk cleanup |
| `scenario_id` | `VARCHAR(100)` | - | Test scenario identifier |

### Verifikasi Skema & Access Privilege Role `ai_team`:

```sql
-- 1. Verifikasi Kolom Ada
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'anomaly_events' 
AND column_name IN ('correlation_id', 'dedup_key', 'event_state', 'source_event_id', 'test_run_id', 'scenario_id');

-- Result: 6 rows returned (UUID, TEXT, VARCHAR)

-- 2. Verifikasi Unique Index Dedup
SELECT indexname FROM pg_indexes 
WHERE tablename = 'anomaly_events' AND indexname LIKE '%dedup%';

-- Result: anomaly_events_dedup_key_key & idx_anomaly_dedup_key (ONLINE)

-- 3. Verifikasi Hak Akses Role ai_team
SET ROLE ai_team;
SELECT correlation_id, dedup_key, event_state FROM anomaly_events LIMIT 1;

-- Result: Query sukses tanpa error permission denied!
```

> **Catatan Penting mengenai Hak Akses `ai_team`**:  
> Akun `ai_team` bertindak sebagai role DML (Data Manipulation Language). `ai_team` tidak memiliki hak `CREATE TABLE` / DDL pada schema `public`. Namun, karena `ai_team` memiliki table-level grant (`arwd`) pada `anomaly_events`, begitu `analytics_user` menambah kolom baru, `ai_team` **secara otomatis langsung mendapatkan hak `SELECT`, `INSERT`, `UPDATE` pada kolom-kolom baru tersebut**.

---

## 3. Detail Verifikasi & Konfigurasi Kafka SSL (Block 7)

### Status Topik Kafka:
* **`dcim.analytics.metrics`** (Input): **Active** — 12 Partisi, Replication Factor 3.
* **`dcim.analytics.anomalies`** (Output): **Active** — 12 Partisi, Replication Factor 3.

```bash
# Verifikasi Topik dari Host Ingestion (10.70.0.56)
docker exec kafka1 /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka1:29092 \
  --describe --topic dcim.analytics.metrics,dcim.analytics.anomalies
```

### Konfigurasi Koneksi SSL dari Host Block 7 (`192.168.100.35`):

1. **Broker SSL Listeners & Ports**:
   * Broker 1: `10.70.0.56:9094`
   * Broker 2: `10.70.0.56:9096`
   * Broker 3: `10.70.0.56:9098`
   * *Pastikan firewall / ACL dari host Block 7 (`192.168.100.35`) mengizinkan outbound TCP ke port `9094`, `9096`, dan `9098`.*

2. **Cert Truststore & Hostname Check**:
   * Sertifikat CA: `ca-cert.pem` (Terlampir, Subject: `CN = DCIM-Kafka-CA`, Valid s.d 2036).
   * **PENTING**: Sertifikat server Kafka diterbitkan dengan Subject `CN = localhost`. Oleh karena itu, client Kafka pada Block 7 **HARUS menonaktifkan hostname verification** agar koneksi SSL via IP `10.70.0.56` tidak ditolak saat SSL Handshake.

### Contoh Snippet Python (Block 7 Client):

```python
import ssl
from kafka import KafkaConsumer, KafkaProducer

# Load CA Certificate
ssl_context = ssl.create_default_context(cafile='ca-cert.pem')
# MATIKAN hostname verification karena cert CN = localhost
ssl_context.check_hostname = False

bootstrap_servers = [
    '10.70.0.56:9094',
    '10.70.0.56:9096',
    '10.70.0.56:9098'
]

# Consumer untuk Topik Input
consumer = KafkaConsumer(
    'dcim.analytics.metrics',
    bootstrap_servers=bootstrap_servers,
    security_protocol='SSL',
    ssl_context=ssl_context,
    api_version=(2, 8, 0),
    group_id='block7-anomaly-engine'
)

# Producer untuk Topik Output Anomalies
producer = KafkaProducer(
    bootstrap_servers=bootstrap_servers,
    security_protocol='SSL',
    ssl_context=ssl_context,
    api_version=(2, 8, 0)
)
```

---

## 4. Langkah Selanjutnya (Next Execution)

Dengan selesainya seluruh item tugas dari Syauqi (DBA & Ingestion), tim Block 7 (Fakhri / AI Team) dan Fadel (Infra / Workflow) kini dapat melanjutkan ke langkah eksekusi E2E:

1. **Fadel**: Memastikan endpoint workflow `http://10.70.0.25:5678/webhook/dcim-anomaly` aktif & mengembalikan acknowledgment response.
2. **Fakhri / Block 7**: Jalankan skrip validasi E2E ST-316:
   ```bash
   WORKFLOW_TEST_URL=http://10.70.0.25:5678/webhook/dcim-anomaly \
   WORKFLOW_TEST_MODE=true \
   PYTHONPATH=. python scripts/run_st316_e2e.py --execute
   ```

---
*Dokumen ini disusun oleh Imam Syauqi Achmad (DBA / Ingestion Team) per tanggal 4 Agustus 2026.*
