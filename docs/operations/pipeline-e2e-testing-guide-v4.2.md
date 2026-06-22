# Panduan Pengujian End-to-End (E2E) Pipeline DCIM v4.2

> **Versi**: 4.2 · **Tanggal**: 2026-06-17
> **Menggantikan/melengkapi**: `pipeline-e2e-testing-guide.md` (v4.0 — tetap sebagai arsip)
> **Selaras**: `docs/architecture/v4.2-pipeline-architecture.md`
> **Tujuan**: Menguji aliran data ujung-ke-ujung dengan **3 skenario terverifikasi** — (1) jalur sukses, (2) data masuk **DLQ**, (3) data memicu **alert** — memakai data dummy maupun aktual.

---

## 0. Konteks & Prasyarat

### Jalur data (triple-write)
```
Perangkat → Telegraf → Kafka dcim.raw.* → Normalizer → dcim.normalized.events
   → NiFi Enrich → dcim.enriched.events → {Elasticsearch, PostgreSQL dcim_events, iTop}
```
Jalur kesalahan: parse gagal → `dcim.dlq.parse-failure`; enrich gagal → `dcim.dlq.enrichment-failure`;
tulis gagal → `dcim.dlq.delivery-failure`. Semua DLQ dikonsumsi `dcim-dlq-consumer.service` → tabel PG `dlq_records`.

### Endpoint & kredensial (host `srv-rnd-dcim` / 10.70.0.56)
| Komponen | Akses |
|---|---|
| Kafka | `localhost:9092` (CLI di dalam container `kafka-broker`: `/opt/kafka/bin/*.sh`) |
| Elasticsearch | `https://10.70.0.56:9200` — auth `elastic` (password tersimpan di secret store; saat ini juga ter-hardcode di `scripts/dcim_threshold_alerter.py`) |
| PostgreSQL | `docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot` |
| Kibana | `http://10.70.0.56:5601` |
| Kafka UI | container `dcim-kafka-ui` |

> **Catatan keamanan**: contoh di bawah memakai placeholder `$ES_AUTH`. Set sekali per sesi (ambil password dari secret store; bila perlu, nilainya juga ada di `scripts/dcim_threshold_alerter.py`):
> ```bash
> export ES_AUTH="elastic:<password>"
> ```

### Helper Kafka (agar perintah ringkas)
```bash
kt()  { docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 "$@"; }
kcon(){ docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 "$@"; }
kprod(){ docker exec -i kafka-broker /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 "$@"; }
```

### Cek kesehatan awal (semua harus `active (running)`)
```bash
systemctl is-active dcim-normalizer dcim-enrichment-api dcim-sql-consumer \
  telegraf-consumer dcim-itop-unified dcim-dlq-consumer dcim-threshold-alerter
kt --list | grep dcim   # pastikan topik raw/normalized/enriched/dlq ada
```

---

## SKENARIO 1 — Jalur Sukses (Happy Path)

**Tujuan**: membuktikan satu pesan mengalir utuh dari raw → normalized → enriched → ES + PostgreSQL.

### 1.1 Suntik data dummy
Generator bawaan mengirim payload server (`reading_celsius` 20–45, aman di bawah threshold):
```bash
python3 scripts/tests/dcim_test_payload_generator.py \
  --rate 1 --duration 5 --topic dcim.raw.hardware.server
```
> Mengirim 5 pesan host `TEST-SRV-001..005`, serial `TEST-SN-001..005`, `ip 10.200.0.x`.

### 1.2 Verifikasi per layer

**L3 — raw diterima Kafka:**
```bash
kcon --topic dcim.raw.hardware.server --max-messages 3 --timeout-ms 10000
```
*Harapan*: JSON mentah dengan `"serial_number": "TEST-SN-00x"`.

**L4 — normalisasi:**
```bash
journalctl -u dcim-normalizer.service -n 30 --no-pager | grep -i TEST-SN
kcon --topic dcim.normalized.events --max-messages 3 --timeout-ms 10000
```
*Harapan*: field rapi (CDM), `device_type=server`.

**L5 — enrichment (data dummy = tidak ada di CMDB):**
```bash
journalctl -u dcim-enrichment-api.service -n 30 --no-pager | grep -i TEST-SN
```
*Harapan*: `GET /enrich/TEST-SN-001` → `enrichment_status: NOT_IN_CMDB` (wajar untuk dummy; pesan **tetap lanjut**, bukan ke DLQ).

**L6/L7 — Elasticsearch:**
```bash
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/dcim-metrics-unified-*/_search" \
  -H 'Content-Type: application/json' \
  -d '{"size":3,"query":{"wildcard":{"tag.serial_number.keyword":"TEST-SN-*"}}}' \
  | python3 -c 'import sys,json;[print(h["_source"].get("tag",{}).get("serial_number")) for h in json.load(sys.stdin)["hits"]["hits"]]'
```

**L6/L7 — PostgreSQL `dcim_events`:**
```bash
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"SELECT event_time, hostname, serial_number, enrichment_status
 FROM dcim_events WHERE serial_number LIKE 'TEST-SN-%'
 AND event_time > now() - interval '15 min' ORDER BY event_time DESC LIMIT 5;"
```
*Harapan*: baris dummy muncul di ES **dan** PG → jalur sukses terbukti.

### 1.3 Uji dengan data AKTUAL (tanpa menyuntik apa pun)
Pipeline produksi terus mengalir tiap 120 detik. Verifikasi perangkat nyata:
```bash
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"SELECT device_type, count(*) AS events_5m, max(event_time) AS last
 FROM dcim_events WHERE event_time > now() - interval '5 min'
 GROUP BY device_type ORDER BY device_type;"
```
*Harapan*: semua device_type (server/ups/nas/network_switch/cctv/nvr) punya event segar (`last` < 3 menit).

### 1.4 Cleanup data dummy
```bash
# ES
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/dcim-metrics-unified-*/_delete_by_query" \
  -H 'Content-Type: application/json' \
  -d '{"query":{"wildcard":{"tag.hostname.keyword":"TEST-SRV-*"}}}'
# PostgreSQL
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"DELETE FROM dcim_events WHERE serial_number LIKE 'TEST-SN-%';"
```

---

## SKENARIO 2 — Data Masuk DLQ (Dead Letter Queue)

**Tujuan**: membuktikan pesan rusak/gagal **tidak hilang**, melainkan tertangkap di topik DLQ dan tercatat di `dlq_records`.

### 2.1 Cara termudah & paling deterministik: parse-failure
Normalizer melempar JSON korup ke `dcim.dlq.parse-failure`. Kirim payload **bukan JSON valid** ke topik raw:
```bash
printf 'this-is-not-valid-json-%s\n' "$(date +%s)" | kprod --topic dcim.raw.hardware.server
```

### 2.2 Verifikasi

**Topik DLQ menerima pesan:**
```bash
kcon --topic dcim.dlq.parse-failure --max-messages 2 --timeout-ms 15000
```
*Harapan*: payload korup tadi muncul (sering dibungkus metadata error/alasan).

**Log normalizer mencatat parse error:**
```bash
journalctl -u dcim-normalizer.service -n 30 --no-pager | grep -iE "dlq|parse|invalid|error"
```

**DLQ consumer menulis ke PostgreSQL:**
```bash
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"SELECT id, received_at, topic, failure_reason, left(original_payload::text,80) AS payload
 FROM dlq_records ORDER BY received_at DESC LIMIT 5;"
journalctl -u dcim-dlq-consumer.service -n 20 --no-pager
```
*Harapan*: ada baris baru di `dlq_records` dengan `topic = 'dcim.dlq.parse-failure'`.

### 2.3 Variasi (opsional)
- **enrichment-failure**: hentikan sementara Enrichment API (`sudo systemctl stop dcim-enrichment-api`), kirim 1 pesan valid, amati `dcim.dlq.enrichment-failure`, lalu **start lagi**. ⚠️ memengaruhi enrichment produksi — lakukan singkat di jam sepi.
- **delivery-failure**: simulasikan gagal tulis (mis. PG down) — **tidak disarankan** di produksi.

### 2.4 Cleanup
Pesan DLQ adalah catatan audit; biarkan saja, atau hapus baris uji:
```bash
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"DELETE FROM dlq_records WHERE original_payload::text LIKE '%this-is-not-valid-json%';"
```

---

## SKENARIO 3 — Data Memicu Alert

**Tujuan**: membuktikan `dcim-threshold-alerter.service` mendeteksi nilai melewati ambang dan menulis alert ke ES index `dcim-alerts` (tampil di Kibana).

### Ambang aktif (dari `scripts/dcim_threshold_alerter.py`)
| Alert | Field ES | Kondisi | Severity |
|---|---|---|---|
| Server temperature | `dcim_metrics.raw_fields_srv_reading_celsius` | > **75°C** | critical |
| UPS load | `dcim_metrics.raw_fields_output_load` | > **80%** | warning |
| NAS disk temp | (nas) | > **55°C** | warning |
| NVR memory | (nvr) | > **90%** | warning |
| Network switch CPU | `dcim_metrics.raw_fields_cpu_load` | > **85%** | warning |
| **Stale device** | `@timestamp` | tidak ada data > **30 menit** | warning |

Alerter membaca **Elasticsearch** (bukan Kafka), interval **120s**, lookback singkat. Maka untuk memicu alert, dokumen ber-suhu tinggi harus **ada di ES** dengan `@timestamp` baru.

### 3.1 Picu alert suhu (dummy, suntik langsung ke ES)
Generator bawaan tidak bisa >75°C, jadi kita tulis 1 dokumen panas langsung ke index harian:
```bash
IDX="dcim-metrics-unified-$(date +%Y.%m.%d)"
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/$IDX/_doc" \
  -H 'Content-Type: application/json' -d "{
    \"@timestamp\": \"$(date -u +%Y-%m-%dT%H:%M:%S.000Z)\",
    \"tag\": {\"hostname\":\"TEST-HOT-01\",\"serial_number\":\"TEST-HOT-01\",\"device_type\":\"server\"},
    \"dcim_metrics\": {\"raw_fields_srv_reading_celsius\": 95}
  }"
```

### 3.2 Verifikasi alert terbit
Tunggu ≤1 siklus (~2 menit), lalu:
```bash
# Log alerter
journalctl -u dcim-threshold-alerter.service -n 30 --no-pager | grep -iE "TEST-HOT|critical|temp"

# Index dcim-alerts
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/dcim-alerts/_search" \
  -H 'Content-Type: application/json' \
  -d '{"size":5,"sort":[{"@timestamp":"desc"}],"query":{"match":{"affected_hosts.hostname":"TEST-HOT-01"}}}' \
  | python3 -m json.tool | head -40
```
*Harapan*: muncul alert `server-temp-critical` severity `critical` untuk `TEST-HOT-01`.

**Visual (Kibana)**: buka `http://10.70.0.56:5601`, dashboard Alert Overview / Discover pada index `dcim-alerts`, filter `affected_hosts.hostname : "TEST-HOT-01"`.

### 3.3 Uji stale-device (opsional, pakai data aktual)
Stale alert muncul otomatis bila sebuah perangkat berhenti mengirim > 30 menit. Untuk mengamati tanpa mematikan perangkat nyata, cukup tinjau alert stale yang ada:
```bash
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/dcim-alerts/_search" \
  -H 'Content-Type: application/json' \
  -d '{"size":5,"sort":[{"@timestamp":"desc"}],"query":{"match":{"alert_type":"stale_device"}}}' \
  | python3 -m json.tool | head -40
```

### 3.4 Cleanup
```bash
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/dcim-metrics-unified-*/_delete_by_query" \
  -H 'Content-Type: application/json' \
  -d '{"query":{"term":{"tag.hostname.keyword":"TEST-HOT-01"}}}'
curl -s -k -u "$ES_AUTH" -X POST "https://10.70.0.56:9200/dcim-alerts/_delete_by_query" \
  -H 'Content-Type: application/json' \
  -d '{"query":{"match":{"affected_hosts.hostname":"TEST-HOT-01"}}}'
```

---

## Ringkasan Hasil yang Diharapkan

| Skenario | Pemicu | Bukti sukses |
|---|---|---|
| 1. Happy path | generator dummy / data aktual | baris di ES **dan** `dcim_events`; `enrichment_status` terisi |
| 2. DLQ | JSON korup ke topik raw | pesan di `dcim.dlq.parse-failure` + baris di `dlq_records` |
| 3. Alert | dokumen suhu 95°C di ES | alert `server-temp-critical` di index `dcim-alerts` + log alerter |

## Checklist pasca-uji
- [ ] Semua data `TEST-*` sudah dibersihkan dari ES & PostgreSQL.
- [ ] Service yang sempat dihentikan (jika Skenario 2.3) sudah `active` kembali.
- [ ] Baris uji di `dlq_records` / `dcim-alerts` sudah dihapus bila tidak diperlukan.
