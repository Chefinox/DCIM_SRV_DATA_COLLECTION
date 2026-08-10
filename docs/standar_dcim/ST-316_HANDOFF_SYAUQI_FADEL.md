---
title: "ST-316 Handoff — Blocker Resolution for Syauqi & Fadel"
created: 2026-08-04
task: ST-316
status: waiting_on_dependencies
---

# ST-316 Handoff Notes

## Context

ST-316 (End-to-End Real-Time Anomaly Flow Validation) menguji alur:
```
Kafka (dcim.analytics.metrics)
  → TimescaleDB
    → Z-score anomaly detection
      → anomaly_events DB
        → Kafka (dcim.analytics.anomalies)
          → Workflow automation
```

Seluruh kode Block 7 sudah selesai dan lulus 28/28 contract tests + 135/136 full suite. Live E2E terblokir oleh 3 item di bawah.

---

## Untuk Syauqi (AI Team / DBA)

### 1. Jalankan Migration 003 — Lineage Columns

**File:** `implementation/dcim_ai_v2_rag/migrations/003_add_anomaly_lineage_and_idempotency.sql`

**Yang ditambahkan:**

| Kolom | Tipe | Fungsi |
|---|---|---|
| `correlation_id` | UUID | Traces metric → anomaly → workflow |
| `dedup_key` | TEXT (UNIQUE) | Mencegah duplicate incident dari replay |
| `event_state` | VARCHAR(20) | `anomaly` atau `recovery` |
| `source_event_id` | UUID | Event ID dari Kafka upstream |
| `test_run_id` | UUID | Links ke test run untuk cleanup |
| `scenario_id` | VARCHAR(100) | Test scenario identifier |

**Command:**
```bash
psql -h 10.70.0.56 -p 5433 -U analytics_user -d dcim_analytics \
  -f implementation/dcim_ai_v2_rag/migrations/003_add_anomaly_lineage_and_idempotency.sql
```

**Yang harus diverifikasi setelah migration:**
```sql
-- Pastikan kolom ada
SELECT column_name, data_type FROM information_schema.columns 
WHERE table_name = 'anomaly_events' 
AND column_name IN ('correlation_id', 'dedup_key', 'event_state');

-- Pastikan index terbuat
SELECT indexname FROM pg_indexes 
WHERE tablename = 'anomaly_events' AND indexname LIKE '%dedup%';

-- Pastikan ai_team bisa baca kolom baru
SET ROLE ai_team;
SELECT correlation_id, dedup_key, event_state FROM anomaly_events LIMIT 1;
```

### 2. Verifikasi Kafka SSL dari Host Block 7

**Masalah:** Dari host Block 7, koneksi Kafka SSL gagal:
```
SSL connection closed by server during handshake
```

**Yang perlu dicek:**

| Item | Nilai saat ini | Yang dicek |
|---|---|---|
| Bootstrap | `10.70.0.56:9094` | Port terbuka dari host Block 7? |
| Protocol | SSL | CA cert di `reference_docs/Syauqi/ca-cert.pem` masih valid? |
| Host Block 7 | `192.168.100.35` | Ada ACL/firewall yang block? |

**Kemungkinan penyebab:**
1. CA cert expired atau tidak match dengan broker cert
2. Broker butuh mTLS (client cert + key) bukan cuma CA
3. Firewall rule belum allow host `192.168.100.35` ke port `9094`

**Yang dibutuhkan:** Konfirmasi bahwa dari host `192.168.100.35` bisa:
```bash
# Test TCP connectivity
nc -vz 10.70.0.56 9094

# Test Kafka metadata (bisa pakai kafka-topics.sh atau python)
python3 -c "
from kafka import KafkaConsumer
import ssl
ctx = ssl.create_default_context(cafile='ca-cert.pem')
c = KafkaConsumer(bootstrap_servers='10.70.0.56:9094', security_protocol='SSL', ssl_context=ctx, api_version=(2,0,0))
print('Topics:', [t for t in c.topics() if 'dcim' in t])
c.close()
"
```

Kalau butuh client cert, tolong kirim path-nya atau letakkan di direktori yang bisa diakses Block 7.

### 3. Pastikan Topic Tersedia

Minimal dua topic harus ada dan accessible:
- `dcim.analytics.metrics` (input)
- `dcim.analytics.anomalies` (output)

```bash
kafka-topics.sh --bootstrap-server 10.70.0.56:9094 \
  --command-config client-ssl.properties --list | grep dcim
```

---

## Untuk Fadel (Infra / Workflow Automation)

### 1. Sediakan Workflow Test Endpoint

**Kebutuhan:** HTTP endpoint yang bisa menerima anomaly event dari Block 7 untuk validasi E2E.

**URL yang diharapkan:** `http://10.70.0.25:5678/webhook/dcim-anomaly` (atau sejenisnya)

**Status saat ini:** Port `5678` connection refused dari host Block 7.

### 2. Spesifikasi Test Route

| Requirement | Detail |
|---|---|
| Method | `POST` |
| Content-Type | `application/json` |
| Action | **HANYA log/receipt, JANGAN remediation** |
| Header yang dikirim | `X-Test-Mode: true`, `X-Idempotency-Key`, `X-Correlation-Id` |

**Payload contoh yang dikirim Block 7:**
```json
{
  "anomaly_id": "uuid",
  "correlation_id": "uuid",
  "event_state": "anomaly",
  "metric_name": "cpu_utilization",
  "severity": "high",
  "current_value": 95.0,
  "_test_mode": true,
  "_source": "dcim-analytics-st316"
}
```

### 3. Response Contract

Workflow endpoint harus mengembalikan response minimal:

```json
{
  "accepted": true,
  "test_mode": true,
  "correlation_id": "<sama dengan yang dikirim>",
  "event_id": "<event_id>",
  "received_at": "2026-08-04T10:00:00Z"
}
```

**Atau** response 200 apapun — Block 7 akan treat sebagai acknowledgment dasar.

### 4. Yang TIDAK BOLEH dilakukan test route

- ❌ Restart server/service
- ❌ Kill process
- ❌ Send notification ke user/WhatsApp/Telegram
- ❌ Create ticket production
- ❌ Execute script remediation
- ❌ Modify firewall/config

### 5. Health Check

Tambahkan endpoint health check:
```
GET http://10.70.0.25:5678/healthz → 200 OK
```

### 6. Test Mode Enforcement

Kalau n8n workflow punya production route yang sama, pastikan:
- Test route terpisah (workflow ID berbeda)
- Atau ada conditional: kalau header `X-Test-Mode: true`, skip action nodes

---

## Timeline

| Item | Owner | Urgency | Blocking |
|---|---|---|---|
| Migration 003 | Syauqi | High | Live E2E |
| Kafka SSL verify | Syauqi | High | Live E2E |
| Workflow endpoint | Fadel | High | Live E2E (partial) |

Setelah ketiga item di atas selesai, Block 7 bisa langsung jalankan:
```bash
WORKFLOW_TEST_URL=<url dari Fadel> \
WORKFLOW_TEST_MODE=true \
PYTHONPATH=. python scripts/run_st316_e2e.py --execute
```

---

## Kontak

Kalau ada pertanyaan soal schema, payload, atau integration pattern, tanya Fakhri / Block 7.
