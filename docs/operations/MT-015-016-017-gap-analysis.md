# Analisis Gap Implementasi — MT-015, MT-016, MT-017

> **Tanggal Review**: 2026-06-12  
> **Reviewer**: Antigravity AI (berdasarkan audit sistem aktual)  
> **Status Keseluruhan**: In Progress  
> **Server**: `10.70.0.56` (srv-rnd-dcim)

---

## Ringkasan Eksekutif

| Task | Judul | % Selesai (Estimasi) | Status |
|---|---|---|---|
| MT-015 | Data Synchronization for AI Models | ~60% | 🟡 In Progress |
| MT-016 | Centralized DCIM Logging | ~45% | 🟡 In Progress |
| MT-017 | Identification of Critical Logs & Events | ~30% | 🔴 Mayoritas Belum |

---

## MT-015 — Data Synchronization for AI Models

**Tujuan**: Pastikan konsistensi data, keselarasan historis, dan kesiapan fitur untuk pelatihan dan inferensi AI/ML.

### ✅ Yang Sudah Berjalan

| Komponen | Bukti Aktual |
|---|---|
| Pipeline Kafka real-time (dcim.raw.* → dcim.normalized.events → dcim.enriched.events) | Service aktif dan terverifikasi |
| Enrichment API (/enrich/{sn}) mengembalikan data CMDB lengkap | J901GKXY mendapat enrichment_status: FULL |
| Redis Cache sinkronisasi dari iTop via dcim-itop-redis-sync.service | Service aktif, key asset:sn:* terisi |
| Script export training data (export_training_data.py) | File ada di scripts/ |
| Script audit kualitas data (audit_data_quality.py) + timer harian | Timer dcim-data-quality-check.timer aktif |
| Baseline PUE sudah dihitung | logs/pue_baseline_20260611.json ada |
| Dokumentasi AI schema & panduan akses data | File ada di docs/development/ |

### ❌ Gap yang Masih Ada

#### GAP-015-01 — Enrichment Belum Menjangkau Semua Device Type
> **Dampak**: Data dcim.enriched.events untuk NAS, Network Switch, UPS masih parsial

- **Masalah**: Telegraf measurement table (interface di nas-snmp.conf) tidak meneruskan serial_number ke Kafka karena inherit_tags yang tidak lengkap.
- **Bukti**: Event NAS-SD01 menunjukkan `serial_number: "NO_IDENTIFIER"` dan `enrichment_status: "NO_IDENTIFIER"`.
- **Status**: Diperbaiki 2026-06-12 untuk NAS. Perlu verifikasi untuk Network Switch dan UPS.
- **Tindakan**: Cek semua file Telegraf .conf yang menggunakan [[inputs.snmp.table]] sudah memiliki inherit_tags lengkap.

#### GAP-015-02 — Script audit_data_quality.py Menghasilkan 0% Completeness
> **Dampak**: Laporan kualitas data harian tidak akurat → tidak bisa dipakai sebagai acuan AI readiness

- **Masalah**: Log audit (data_quality_20260611.log) menunjukkan `Total: 0 | Valid: 0 | Completeness: 0.00%` untuk semua device, meski data ES ada (38.4 juta dokumen).
- **Penyebab**: Query ES menggunakan nama field yang tidak cocok dengan mapping aktual.
- **Tindakan**: Debug dan perbaiki query di scripts/audit_data_quality.py.

#### GAP-015-03 — Field brand, location, rack Kosong di Data Historis ES (0%)
> **Dampak**: Model AI yang dilatih data historis tidak punya konteks lokasi/merk perangkat

- **Masalah**: Audit ES 2026-06-11 menunjukkan brand, location, rack = 0% di semua device type.
- **Penyebab**: Field enrichment baru diterapkan via NiFi (setelah v4.0). Data historis lama tidak punya field ini.
- **Tindakan**: Untuk data baru sudah teratasi (NiFi UpdateRecord+LookupRecord). Untuk data historis, tim AI harus pivot via serial_number ke Enrichment API. Dokumentasikan batasan ini.

#### GAP-015-04 — Kedalaman Data Historis Belum Cukup (< 30 hari)
> **Dampak**: UC-AI-1 (Predictive Failure) dan UC-AI-2 (Capacity Optimization) belum bisa dijalankan

- **Masalah**: Semua device hanya punya ~21.7 hari data. Requirement minimum = 30 hari.
- **Target**: 30 hari penuh tercapai ~2026-06-20 jika pipeline berjalan tanpa gangguan.
- **Tindakan**: Pantau pipeline dan pastikan tidak ada service yang mati.

#### GAP-015-05 — Atribut Finansial Aset Belum Terisi
> **Dampak**: UC-CMDB-3 (Asset Lifecycle) tidak bisa menghasilkan laporan akurat

- **Masalah**: purchase_date, warranty_end_date, acquisition_cost di iTop dan Ralph masih kosong.
- **Tindakan**: Koordinasi dengan procurement/finance → isi template → jalankan import_financial_data_to_itop.py.

#### GAP-015-06 — Tidak Ada Deteksi CMDB Drift Otomatis
> **Dampak**: Perbedaan hostname (fisik) vs name (CMDB) tidak terdeteksi proaktif

- **Masalah**: Desain data sudah benar (kedua field tersedia di Kafka), tapi belum ada Kibana Alert yang membandingkannya.
- **Tindakan**: Buat Kibana Alert Rule: hostname != name → notifikasi.

---

## MT-016 — Centralized DCIM Logging

**Tujuan**: Terapkan pencatatan terpusat untuk semua komponen, integrasi, dan peristiwa operasional DCIM.

### ✅ Yang Sudah Berjalan

| Komponen | Bukti Aktual |
|---|---|
| Filebeat aktif, membaca logs Python dan Docker container | filebeat.service = active (running) |
| Logrotate aktif untuk beberapa service | File .log.1, .log.2.gz terlihat di logs/ |
| Log dikirim ke Elasticsearch via Filebeat | Konfigurasi output ES ada di filebeat.yml |

### ❌ Gap yang Masih Ada

#### GAP-016-01 — Log DLQ Consumer Membengkak Tidak Terkendali (KRITIS)
> **Dampak**: Disk bisa penuh, Filebeat mati, kehilangan semua log

- **Masalah**: dcim_dlq_consumer.log = 251 MB (aktif) + 407 MB (rotasi) = >650 MB total dari satu service.
- **Tindakan**: (1) Investigasi kenapa volume DLQ sangat tinggi. (2) Aktifkan logrotate ketat untuk file ini.

#### GAP-016-02 — Format Log Mayoritas Masih Plaintext (Bukan JSON Terstruktur)
> **Dampak**: Filebeat tidak bisa parse log dengan benar → tidak bisa di-query di Kibana

- **Masalah**: Mayoritas script Python menggunakan logging standar (plaintext). Filebeat dikonfigurasi dengan parser ndjson, sehingga log plaintext tidak bisa di-parse dengan benar.
- **Tindakan**: Implementasi dcim_logger.py (modul logger sentral berformat JSON), migrasi script-script utama secara bertahap.

#### GAP-016-03 — Log itop_cache_sync.log Dimiliki root (Bukan infra)
> **Dampak**: Filebeat tidak bisa membaca file ini

- **Masalah**: itop_cache_sync.log memiliki permission root:root. Semua log lain dimiliki infra:infra.
- **Tindakan**: `sudo chown infra:infra /home/infra/dcim_metrics_project/logs/itop_cache_sync.log`. Selidiki service systemd yang terkait dan pastikan menggunakan User=infra.

#### GAP-016-04 — Log hikvision_poller.log Berada di Direktori scripts/ (Bukan logs/)
> **Dampak**: Melanggar standar direktori log; risiko tidak terpantau

- **Masalah**: scripts/hikvision_poller.log (47 MB) berada di luar direktori logs/.
- **Tindakan**: Perbaiki path output log di scripts/hikvision_poller.py → logs/hikvision_poller.log.

#### GAP-016-05 — Log Systemd Services Tidak Dikirim ke Elasticsearch
> **Dampak**: Log dari dcim-normalizer.service, dcim-enrichment-api.service, dll. tidak terpusat

- **Masalah**: Filebeat belum dikonfigurasi untuk membaca journal dari service systemd DCIM.
- **Tindakan**: Tambahkan input journald di Filebeat untuk service-service DCIM utama.

#### GAP-016-06 — Belum Ada Dashboard Kibana untuk Log Terpusat
> **Dampak**: Tidak ada single pane of glass untuk memantau log semua komponen

- **Tindakan**: Buat Dashboard Kibana dengan visualisasi: log level distribution, top error sources, DLQ volume trend, timeline error events.

---

## MT-017 — Identification of Critical Logs & Events

**Tujuan**: Klasifikasikan log dan peristiwa yang penting untuk peringatan, kepatuhan, forensik, dan analitik AI.

### ✅ Yang Sudah Berjalan

| Komponen | Bukti Aktual |
|---|---|
| Threshold alerts untuk metrik perangkat (suhu, battery, CPU) | dcim-threshold-alerter.service aktif |
| DLQ consumer memisahkan event gagal parsing | dcim-dlq-consumer.service aktif |
| Kibana Watcher/Alert untuk metrik kritis sudah dibuat | create_threshold_alerts.py sudah dijalankan |

### ❌ Gap yang Masih Ada

#### GAP-017-01 — Belum Ada Klasifikasi Formal Log (Log Taxonomy)
> **Dampak**: Tidak ada panduan retensi log; semua log diperlakukan sama

- **Tindakan**: Buat docs/operations/log-taxonomy-and-retention-policy.md yang mendefinisikan kategori log (Operational/Security/Audit/Debug) dan kebijakan retensi per kategori.

#### GAP-017-02 — Tidak Ada Alert untuk Kegagalan Pipeline DCIM Itu Sendiri
> **Dampak**: NiFi mati, Enrichment API error, Kafka lag tidak terdeteksi proaktif

- **Event kritis yang belum di-alert**:
  - Volume DLQ > threshold (indikasi parsing error masif)
  - enrichment_status = NOT_IN_CMDB dalam jumlah besar (Redis tidak sinkron)
  - Tidak ada data dari device tertentu > X menit (device/Telegraf mati)
  - Kafka consumer group lag > threshold
- **Tindakan**: Buat Kibana Alert Rules tambahan untuk event-event pipeline di atas.

#### GAP-017-03 — Tidak Ada Alert untuk Configuration Drift / CMDB Mismatch
> **Dampak**: Perubahan konfigurasi tidak resmi tidak terdeteksi

- **Tindakan**: Kibana Alert dengan kondisi: hostname ≠ name di dcim.enriched.events → notifikasi.

#### GAP-017-04 — Log Security Events Tidak Dipisahkan
> **Dampak**: Tidak ada data untuk kepatuhan (compliance) dan forensik keamanan

- **Tindakan**: (1) Definisikan daftar security events untuk DCIM. (2) Konfigurasi Filebeat pipeline untuk tag event.category: security. (3) Buat index dcim-security-events-*.

#### GAP-017-05 — Belum Ada Notifikasi Alert ke Luar Elasticsearch
> **Dampak**: Alert hanya visible di Kibana; tim ops tidak mendapat notifikasi proaktif

- **Masalah**: Semua alert hanya menulis ke index dcim-alerts. Tidak ada integrasi Telegram/Email/PagerDuty.
- **Tindakan**: Konfigurasi Kibana Connector ke minimal satu saluran notifikasi (Telegram Bot atau SMTP Email).

---

## Prioritas Tindakan yang Direkomendasikan

| Prioritas | Gap ID | Tindakan | Estimasi |
|---|---|---|---|
| 🔴 Kritis | GAP-016-01 | Investigasi & atasi lonjakan volume DLQ Consumer | 1 hari |
| 🔴 Kritis | GAP-015-02 | Debug & perbaiki audit_data_quality.py (hasil 0%) | 1 hari |
| 🟠 Tinggi | GAP-015-01 | Verifikasi inherit_tags di semua Telegraf SNMP conf | 0.5 hari |
| 🟠 Tinggi | GAP-017-02 | Buat Kibana Alert untuk kesehatan pipeline | 2 hari |
| 🟠 Tinggi | GAP-017-05 | Integrasikan Kibana Alert ke Telegram/Email | 1 hari |
| 🟡 Sedang | GAP-016-02 | Implementasi dcim_logger.py (JSON structured logging) | 3 hari |
| 🟡 Sedang | GAP-016-05 | Tambah input journald di Filebeat | 0.5 hari |
| 🟡 Sedang | GAP-017-01 | Buat Log Taxonomy & Retention Policy document | 1 hari |
| 🟡 Sedang | GAP-017-03 | Buat Kibana Alert untuk CMDB Drift | 1 hari |
| 🟢 Rendah | GAP-016-03 | Perbaiki ownership itop_cache_sync.log | 0.1 hari |
| �� Rendah | GAP-016-04 | Pindahkan hikvision_poller.log ke logs/ | 0.1 hari |
| 🟢 Rendah | GAP-015-03 | Dokumentasikan batasan data historis untuk tim AI | 0.5 hari |
| 🟢 Rendah | GAP-015-04 | Tunggu hingga ~2026-06-20 untuk 30 hari data | Otomatis |
| 🟢 Rendah | GAP-015-05 | Koordinasi pengisian data finansial dengan finance | 1-2 hari + koordinasi |
| 🟢 Rendah | GAP-016-06 | Buat Dashboard Kibana untuk log terpusat | 2 hari |
| 🟢 Rendah | GAP-017-04 | Pisahkan log security events ke index tersendiri | 2 hari |
