# MT-015 — Data Synchronization for AI Models
## Planning & Sub-Task Breakdown

| Field | Value |
|---|---|
| **Task ID** | MT-015 |
| **Nama** | Data Synchronization for AI Models |
| **Parent** | SM-003 |
| **Status** | In Progress |
| **Priority** | Low |
| **PIC** | Imam Syauqi Achmad |
| **Mulai** | 25/05/2026 |
| **Referensi Use Case** | IF-Use_Case_Analysis-FIT041-20260121.md |

---

## 1. Tujuan MT-015

Memastikan pipeline data yang berjalan saat ini memenuhi tiga syarat utama agar data siap dikonsumsi oleh sistem AI/ML:

1. **Konsistensi Data** — Data yang masuk ke semua penyimpanan (Redis, PostgreSQL, Elasticsearch) harus sinkron dan tidak bertentangan satu sama lain.
2. **Keselarasan Historis** — Data historis yang tersimpan di Elasticsearch harus cukup, terstruktur, dan bisa di-query untuk keperluan pelatihan model (training data).
3. **Kesiapan Fitur (Feature Readiness)** — Data yang tersedia harus memiliki atribut/field yang cukup untuk digunakan sebagai fitur (input) model ML (prediksi, anomaly detection, capacity planning).

---

## 2. Pemetaan Implementasi Saat Ini vs. Kebutuhan AI

### 2a. Use Cases AI yang Relevan (dari dokumen FIT041)

| Use Case (FIT041) | Kebutuhan Data | Status Saat Ini |
|---|---|---|
| **UC-AI-1**: Predictive Failure Alerting | Historical time-series: temp, power, fan RPM, CPU, RAM — minimal ~30-90 hari | ⚠️ **Partial** — data ada di ES tapi belum diverifikasi kelengkapan & kedalaman historisnya |
| **UC-AI-2**: Capacity Optimization | CPU, RAM, Storage utilization data per device, minimal 90 hari | ⚠️ **Partial** — data masuk tapi belum ada validasi field completeness per device type |
| **UC-AI-3**: Energy Anomaly / PUE Drift | Power draw (UPS, PDU), temperature, environment — real-time + historis | ⚠️ **Partial** — UPS & server power ada, tapi PUE baseline calculation belum ada |
| **UC-CMDB-3**: Asset Lifecycle | Purchase date, warranty, financial attributes di CMDB | ❌ **Gap** — iTop & Ralph belum diisi atribut finansial (acquisition cost, warranty expiry) |
| **UC-DataIngestion-1**: Real-time Monitoring | Latency < 5 detik dari collection ke storage | ✅ **Done** — pipeline Telegraf → Kafka → NiFi → ES sudah berjalan |
| **UC-DataIngestion-2**: CMDB Config Updates | CMDB diperbarui ≤1 jam setelah perubahan | ✅ **Done** — `dcim-itop-unified.service` + `dcim-itop-inventory-sync` berjalan |

### 2b. Gap Kritis yang Harus Diselesaikan

| # | Gap | Dampak ke AI |
|---|---|---|
| G1 | Tidak ada **schema validation** pada data yang masuk ke Elasticsearch | Model ML bisa dilatih dengan data kotor/tidak konsisten |
| G2 | Tidak ada **completeness check** — berapa % device yang punya semua field wajib (SN, location, model, metrics) | Feature vector tidak lengkap → model gagal atau bias |
| G3 | Tidak ada mekanisme **data export/snapshot** untuk training dataset | Tim AI tidak punya cara standar untuk mengambil training data |
| G4 | **Redis cache** hanya berisi metadata CI dasar, belum ada field untuk AI feature engineering (contoh: criticality level, maintenance history) | Context aset untuk LLM inference terbatas |
| G5 | Belum ada **baseline PUE** yang tersimpan — hanya data raw power | UC-AI-3 (Energy Anomaly) tidak bisa berjalan tanpa baseline |
| G6 | Atribut finansial aset (purchase date, warranty) kosong di iTop dan Ralph | UC-CMDB-3 (Asset Lifecycle) tidak bisa menghasilkan laporan akurat |

---

## 3. Sub-Tasks MT-015

### ST-015-01 — Audit & Verifikasi Kelengkapan Data Historis di Elasticsearch
**Prioritas**: High (blocking untuk semua UC AI)
**Estimasi**: 2-3 hari

**Deskripsi**:
Jalankan audit kuantitatif untuk mengetahui seberapa lengkap data historis yang ada di Elasticsearch, sebagai dasar menentukan apakah data sudah cukup untuk training AI model.

**Poin-poin kerja**:
- [ ] Cek total dokumen per device type di index `dcim-metrics-unified-*` (Server, UPS, NAS, Network, CCTV)
- [ ] Cek kedalaman data historis: berapa hari ke belakang data tersedia per device
- [ ] Cek field completeness per device type: apakah field `serial_number`, `location`, `rack`, `model`, `brand` selalu terisi
- [ ] Cek field wajib untuk AI: `cpu_usage`, `ram_usage`, `temperature`, `power_draw`, `disk_usage` — berapa % dokumen yang punya semua field ini
- [ ] Buat laporan audit dalam format Markdown di `docs/operations/data-quality-audit-YYYYMMDD.md`

**Kriteria Selesai**:
- Laporan audit tersedia dengan angka konkret (% completeness per field per device type)
- Minimum 30 hari historis tersedia untuk device kategori "critical" (Server, UPS)

---

### ST-015-02 — Perkuat Redis Cache dengan Field AI-Ready
**Prioritas**: Medium
**Estimasi**: 1-2 hari

**Deskripsi**:
Script `itop_to_cache_sync.py` saat ini hanya menarik field dasar dari iTop. Untuk kebutuhan AI (terutama LLM contextual reasoning), Redis cache perlu diperkaya dengan field tambahan.

**Poin-poin kerja**:
- [ ] Identifikasi field tambahan yang tersedia di iTop: `criticality`, `maintenance_window`, `org_name`, `business_impact`
- [ ] Update query OQL di `scripts/itop_to_cache_sync.py` untuk menarik field tambahan tersebut
- [ ] Update format JSON value di Redis dengan field baru (pastikan backward compatible)
- [ ] Dokumentasikan schema baru di `docs/development/itop-api-baseline-for-agents.md`

**Kriteria Selesai**:
- Redis key `asset:sn:*` mengandung setidaknya field: `sn`, `name`, `location`, `rack`, `brand`, `model`, `status`, `ci_class`, `org`, `criticality`, `synced_at`
- Enrichment API (`/enrich/{sn}`) mengembalikan field baru tanpa error

---

### ST-015-03 — Implementasi Baseline PUE & Energy Reference
**Prioritas**: Medium
**Estimasi**: 2-3 hari

**Deskripsi**:
Use Case AI-3 (Energy Anomaly Detection) membutuhkan baseline PUE yang tersimpan dan bisa dikomparasi dengan nilai real-time. Saat ini tidak ada mekanisme ini.

**Poin-poin kerja**:
- [ ] Definisikan formula PUE: `PUE = Total Facility Power / IT Equipment Power`
- [ ] Identifikasi sumber data Total Facility Power (UPS total output) dan IT Equipment Power (sum server power draw) di Elasticsearch
- [ ] Buat script `scripts/calculate_pue_baseline.py` yang:
  - Query ES untuk rata-rata konsumsi 7 hari terakhir
  - Hitung PUE baseline harian
  - Simpan ke file JSON di `logs/pue_baseline_YYYYMMDD.json`
- [ ] Dokumentasikan baseline di `docs/operations/energy-baseline.md`

**Kriteria Selesai**:
- Baseline PUE per hari tersedia untuk minimal 7 hari ke belakang
- Script bisa dijalankan ulang dan menghasilkan output yang konsisten

---

### ST-015-04 — Buat Mekanisme Data Export untuk AI Training
**Prioritas**: High
**Estimasi**: 2-3 hari

**Deskripsi**:
Tim AI perlu cara yang standar dan mudah untuk mengambil data training dari sistem DCIM. Saat ini tidak ada tool atau dokumentasi untuk ini.

**Poin-poin kerja**:
- [ ] Buat script `scripts/export_training_data.py` dengan parameter: `device_type`, `date_from`, `date_to`, `output_format` (csv/jsonl)
- [ ] Definisikan **feature schema** per use case AI:
  - UC-AI-1 (Predictive Failure): `[timestamp, sn, cpu_usage, ram_usage, temp_cpu, temp_ambient, disk_health, power_draw, fan_speed]`
  - UC-AI-2 (Capacity): `[timestamp, sn, cpu_usage_avg_24h, ram_usage_avg_24h, disk_usage, rack, location]`
  - UC-AI-3 (Energy): `[timestamp, ups_output_power, total_it_power, pue, temp_ambient]`
- [ ] Output ke `exports/training_YYYYMMDD_{device_type}.csv`
- [ ] Dokumentasikan schema di `docs/development/ai-training-data-schema.md`
- [ ] Buat contoh query Elasticsearch DSL untuk masing-masing use case

**Kriteria Selesai**:
- Script bisa dijalankan dan menghasilkan file CSV/JSONL tanpa error
- Dokumentasi schema tersedia dan bisa digunakan oleh tim AI

---

### ST-015-05 — Implementasi Schema Validation & Data Quality Check Harian
**Prioritas**: Medium
**Estimasi**: 2-3 hari

**Deskripsi**:
Untuk memastikan data yang masuk ke Elasticsearch berkualitas baik, perlu ada mekanisme validasi dan monitoring kualitas data yang berjalan otomatis.

**Poin-poin kerja**:
- [ ] Definisikan **required fields** per device type dalam `configs/data_quality_schema.yaml`
- [ ] Buat script `scripts/audit_data_quality.py` yang:
  - Query ES untuk dokumen dalam 24 jam terakhir
  - Cek % dokumen yang memiliki semua required fields
  - Log anomali ke `logs/data_quality_YYYYMMDD.log`
- [ ] Buat systemd timer `dcim-data-quality-check.timer` yang jalan setiap hari pukul 06:00 WIB
- [ ] Pasang template file service di `configs/systemd/dcim-data-quality-check.service`

**Kriteria Selesai**:
- Script berjalan tanpa error
- Laporan kualitas data tersedia harian di folder `logs/`
- Definisi "data berkualitas baik" terdokumentasi dalam `configs/data_quality_schema.yaml`

---

### ST-015-06 — Lengkapi Atribut Finansial & Lifecycle di iTop dan Ralph
**Prioritas**: Low
**Estimasi**: 1-2 hari kerja teknis + koordinasi

**Deskripsi**:
Use Case CMDB-3 dan kebutuhan AI untuk context aset memerlukan atribut finansial yang terisi di iTop dan Ralph. Saat ini field ini kosong.

**Poin-poin kerja**:
- [ ] Inventarisasi field finansial di iTop: `purchase_date`, `warranty_end_date`, `acquisition_cost`, `vendor`
- [ ] Buat template `docs/operations/asset-financial-data-template.csv` untuk diisi tim/finance
- [ ] Setelah data tersedia, buat script `scripts/import_financial_data_to_itop.py` untuk bulk-update via iTop REST API
- [ ] Verifikasi bahwa `itop_to_ralph_sync.py` memindahkan field finansial ke Ralph

**Kriteria Selesai**:
- ≥80% perangkat kategori Server, Network, Storage memiliki `purchase_date` dan `warranty_end_date` terisi di iTop
- Field tersinkronisasi ke Ralph

---

### ST-015-07 — Dokumentasi AI Agent Data Access Guide
**Prioritas**: Medium
**Estimasi**: 1 hari

**Deskripsi**:
Agent AI akan dikelola oleh anggota tim lain. Perlu ada panduan yang jelas tentang bagaimana agent AI bisa mengakses dan menggunakan data dari sistem DCIM.

**Poin-poin kerja**:
- [ ] Buat `docs/development/ai-agent-data-access-guide.md` yang berisi:
  - Query real-time dari Elasticsearch (endpoint, index pattern, contoh DSL query)
  - Query metadata aset dari Redis via Enrichment API (`GET http://localhost:8000/enrich/{sn}`)
  - Query metadata dari iTop via REST API (link ke `itop-api-baseline-for-agents.md`)
  - Query historis dari PostgreSQL (table `dcim_events`, schema)
  - Penjelasan field penting dan artinya
  - Contoh workflow end-to-end: "Cara mendapatkan semua data server X untuk 7 hari terakhir"
- [ ] Review dokumen bersama anggota tim AI

**Kriteria Selesai**:
- Dokumen tersedia dan divalidasi oleh setidaknya 1 anggota tim AI
- Semua contoh query bisa dijalankan dan menghasilkan data yang valid

---

## 4. Timeline Estimasi

```
Minggu 1 (12-18 Jun 2026):
  ST-015-01  Audit & Verifikasi Historis ES     ████████████  2-3 hari  ← START SINI
  ST-015-02  Perkuat Redis Cache Field AI       ████████      1-2 hari  (paralel)

Minggu 2 (19-25 Jun 2026):
  ST-015-03  Baseline PUE & Energy Reference    ████████████  2-3 hari
  ST-015-04  Mekanisme Export Training Data     ████████████  2-3 hari

Minggu 3 (26 Jun - 2 Jul 2026):
  ST-015-05  Schema Validation & Quality Check  ████████████  2-3 hari
  ST-015-06  Atribut Finansial iTop & Ralph     ████████      1-2 hari  (paralel + koordinasi)
  ST-015-07  Dokumentasi AI Agent Data Guide    ████          1 hari
```

**Total estimasi**: ~3 minggu (11-15 hari kerja efektif)

---

## 5. Definisi Done — MT-015 dinyatakan selesai jika:

- [ ] Laporan data quality audit menunjukkan ≥85% field completeness untuk device critical
- [ ] Redis cache berisi field yang cukup untuk LLM context (criticality, org, dll)
- [ ] Baseline PUE tersimpan minimal 7 hari ke belakang
- [ ] Script export training data berjalan dan terdokumentasi
- [ ] Schema validation harian berjalan otomatis via systemd timer
- [ ] ≥80% aset critical memiliki data finansial di iTop
- [ ] Dokumen panduan akses data untuk agent AI tersedia dan divalidasi

---

## 6. Dependencies & Catatan Penting

> [!IMPORTANT]
> **ST-015-01 (Audit) harus diselesaikan pertama.** Hasilnya menentukan skala pekerjaan di sub-task berikutnya. Jangan mulai coding sebelum audit selesai.

> [!NOTE]
> **ST-015-06** memerlukan koordinasi dengan tim procurement/finance untuk data aktual. Sub-task ini bisa berjalan paralel dengan sub-task teknis lainnya dan tidak perlu menunggu.

> [!NOTE]
> **Agent AI** yang akan mengkonsumsi data ini adalah milik anggota tim lain. Pastikan **ST-015-07** selesai sebelum mereka mulai development untuk menghindari miskomunikasi soal format dan cara akses data.

> [!WARNING]
> **Jangan ubah schema index Elasticsearch** yang sudah ada tanpa koordinasi. Perubahan mapping index ES bersifat destructive dan bisa merusak data historis yang sudah ada.

> [!NOTE]
> Implementasi v4.0.0 yang sudah berjalan (iTop sebagai Metadata Authority, pipeline enrichment, Cutover Checklist) adalah **fondasi yang sudah selesai** dan tidak perlu diulang. MT-015 ini membangun **lapisan AI-readiness** di atasnya.
