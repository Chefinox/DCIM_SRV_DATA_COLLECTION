# (MT-017) Identification of Critical Logs and Events

# 1. Overview

## Objective

Mengklasifikasikan log dan peristiwa yang penting untuk peringatan, kepatuhan, forensik, dan analitik AI, mencakup:

* **Threshold Alerting**: Peringatan jika metrik perangkat melewati batas aman (e.g. Suhu > 75°C)
* **Pipeline Health Alerting**: Notifikasi Telegram jika pipeline mati atau error rate tinggi
* **Event Lineage Tracking**: Melacak perjalanan data (ingested → validated → enriched → routed)
* **Dead Letter Queue (DLQ)**: Mengamankan pesan error untuk analisis forensik
* **Priority & Severity Model**: Pemodelan tingkat keparahan insiden (S1-S4) dan prioritas data (P1-P4)

***

# 2. Threshold Alerting (L9.1)

## 2.1 Fungsi

Mendeteksi anomali pada metrik hardware secara real-time dengan melakukan query ke Elasticsearch. Alert disimpan kembali ke ES di index `dcim-alerts` untuk divisualisasikan di Kibana.

## 2.2 Threshold Rules

Terdapat 6 rules aktif + 1 stale detection:

| ID Rule | Deskripsi | Perangkat | Kondisi | Severity |
|---------|-----------|-----------|---------|----------|
| `server-temp-critical` | Server Temp > 75°C | Server | `srv_reading_celsius > 75` | Critical |
| `ups-battery-low` | UPS Battery < 50% | UPS | `battery_capacity < 50` | Warning |
| `ups-load-high` | UPS Load > 80% | UPS | `output_load > 80` | Warning |
| `nas-disk-temp-high`| NAS Disk Temp > 55°C | NAS | `diskTemp > 55` | Warning |
| `nvr-memory-high` | NVR Memory > 90% | NVR | `memoryUsagePct > 90` | Warning |
| `network-cpu-high` | Switch CPU > 85% | Network | `cpu_load > 85` | Warning |
| `stale-device` | Tidak ada data > 30m | (Semua) | Count(30m) == 0 | Critical |

***

# 3. Pipeline Health Alerting (L9.2)

## 3.1 Fungsi

Mengawasi kesehatan pipeline DCIM itu sendiri dan mengirim notifikasi darurat via **Telegram** ke tim infra. Dirancang sebagai skrip mandiri untuk menghindari ketergantungan pada Kibana Actions (yang butuh lisensi Elastic Gold).

## 3.2 Health Checks

| Check | Kondisi Trigger | Implikasi |
|-------|-----------------|-----------|
| **Pipeline Mati** | `doc_count == 0` di ES dalam 2 jam terakhir | Ingestion stop / ES mati |
| **Enrichment Failure** | > 100 `NOT_IN_CMDB` dalam 1 jam | CMDB out-of-sync / cache mati |
| **CMDB Drift** | `hostname != name` di enriched events | Data CMDB tidak cocok dengan realita |
| **DLQ Spike** | Topik DLQ menerima > 50 error / 30 menit | Schema berubah / DB target mati |
| **Data Quality Drop** | Valid docs < 85% dari total (daily audit) | Format log polling berubah |

*Cooldown period: 60 menit antar alert yang sama untuk mencegah spam.*

***

# 4. Dead Letter Queue (DLQ) Classification

Pesan yang gagal diproses diarahkan ke 3 topik Kafka terpisah berdasarkan jenis kegagalannya:

| Topik DLQ | Penyebab | Klasifikasi Forensik | Tindakan |
|-----------|----------|----------------------|----------|
| `dcim.dlq.parse-failure` | JSON parse error, unknown schema di Normalizer | Bug di poller script, format vendor berubah | Review poller script, fix schema |
| `dcim.dlq.enrichment-failure`| API timeout, Redis down saat NiFi HTTP Lookup | Kegagalan infrastruktur internal | Auto-retry saat API UP |
| `dcim.dlq.delivery-failure` | iTop REST error, PostgreSQL connection refused | Database target bermasalah | Alert DBA, auto-retry consumer |

***

# 5. Event Lineage Tracking (L14)

## 5.1 Fungsi

Melacak siklus hidup setiap pesan (event) dari saat diterima hingga disimpan. Berguna untuk audit kepatuhan, troubleshooting data loss, dan mengukur processing latency.

## 5.2 Tabel `event_lineage` (PostgreSQL)

| Kolom | Keterangan |
|-------|------------|
| `lineage_id` | UUID unik |
| `event_id` | ID event dari payload |
| `source_system` | Topik asal (e.g. `dcim.raw.server`) |
| `ingested_at` | Waktu event diterima pipeline |
| `validation_status` | Status normalisasi (`success`, `dlq`) |
| `enrichment_status` | Status CMDB lookup (`FULL`, `PARTIAL`, dll) |
| `routing_status` | Status persisten (`routed`) |
| `target_store` | Tujuan simpan (`postgres`, `elasticsearch`, `itop`) |
| `processing_ms_total`| Total waktu pemrosesan (latency) |

***

# 6. Priority & Severity Model

## 6.1 Data Priority (P1-P4)

Klasifikasi prioritas aliran data:

| Level | Kategori Data | Toleransi Delay |
|-------|--------------|-----------------|
| **P1** | UPS power, Server temp, Switch CPU | < 1 menit |
| **P2** | NAS disk status, CCTV online status | < 5 menit |
| **P3** | Inventory changes, CMDB sync | < 24 jam |
| **P4** | Log aplikasi (DEBUG/INFO) | Best effort |

## 6.2 Incident Severity (S1-S4)

Klasifikasi keparahan jika alert terpicu:

| Level | Contoh Alert | SLA Respon |
|-------|--------------|------------|
| **S1 (Critical)** | Pipeline Mati, Server Temp > 75°C, UPS Mati | 15 menit |
| **S2 (High)** | DLQ Spike, Switch CPU > 85%, UPS Battery Low | 1 jam |
| **S3 (Medium)** | Enrichment Failure > 100, Stale Device (NAS) | 4 jam |
| **S4 (Low)** | CMDB Drift, Log Warning | 24 jam |

***

# 7. Handover Notes

## Telegram Bot

- Bot Name: `DCIM_Alert_Bot`
- Token: (Tersimpan di environment variables)
- Chat ID: `-5266403936` (Grup Tim Infra)

## Menambah Alert Rule Baru

1. Buka `scripts/dcim_threshold_alerter.py`
2. Tambahkan dict baru di array `THRESHOLDS`:
   ```python
   {
       "id": "nama-rule",
       "description": "Deskripsi",
       "device_type": "tipe_device",
       "field": "kolom_di_es",
       "comparator": "gt/lt/eq",
       "threshold": nilai_angka,
       "severity": "warning/critical",
       "agg": "max/min"
   }
   ```
3. Restart service: `sudo systemctl restart dcim-threshold-alerter.service`

***

# 8. Version History

| Date | Version | Author | Notes |
|------|---------|--------|-------|
| 10/07/2026 | 1.0 | Imam Syauqi Achmad | Initial handover documentation |
