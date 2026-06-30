# HANDOFF — Data Science & AI Engine Implementation (MT-018 / FIT041)

**Tanggal**: 17 Juni 2026
**Dari**: Tim Data Ingestion & Integration Layer
**Untuk**: Tim Data Science / AI

## 1. DATA TRAINING (Sejarah Data)

Semua data operasional dan telemetri DCIM historis (sejak April 2026) disimpan terpusat di **PostgreSQL** (`dcim_sot`), bukan lagi di Elasticsearch. Kami telah membuatkan *Materialized Views* (`v_train_server`, `v_train_network`, `v_train_ups`, dll) yang sudah merapikan (pivot) data tersebut agar berbentuk tabel *wide* (kolom per metrik) yang 100% siap dilatih (ready-to-train).

### 1.1 Cara Ekstrak Data
Gunakan skrip Python yang telah kami sediakan:
```bash
python3 /home/infra/dcim_metrics_project/scripts/export_training_data.py \
    --device server \
    --start 2026-04-29 \
    --end 2026-06-17 \
    --format csv
```
*(Hasilnya akan muncul di folder `/home/infra/dcim_metrics_project/exports/`)*

### 1.2 Catatan Ketersediaan Fitur (PENTING)
Tidak semua fitur yang diminta pada spesifikasi asli MT-018 tersedia secara fisik pada sensor data center. Fitur yang **BELUM ADA** dan **TIDAK PERLU** kamu buat *collector*-nya (gunakan imputasi, hapus fitur, atau abaikan) meliputi:
- `disk_io` (Server) & `smart_*` (Kesehatan fisik hard disk)
- `gpu_util`, `gpu_mem` (Ketiadaan dukungan monitoring GPU native via Redfish saat ini)
- `temp_inlet`, `temp_outlet` (Sensor suhu ruangan/pendingin CRAC)
- `humidity` (Sensor fisik kelembaban **tidak ada**)
- `pue` (Nilai Power Usage Effectiveness fasilitas)

Metrik yang **sudah lengkap dan valid** (termasuk utilisasi CPU & Memori server aktual dari Redfish) bisa kamu lihat dokumentasi skemanya di:
👉 `/home/infra/dcim_metrics_project/docs/development/ai-training-data-schema.md`

---

## 2. LINGKUNGAN INFERENCE (Produksi Waktu-Nyata)

Kami telah menyiapkan sebuah layanan (service) bernama `dcim-ai-inference.service` yang berjalan 24/7. Skrip intinya berlokasi di:
👉 `/home/infra/dcim_metrics_project/src/skills/ai/anomaly_inference/executor.py`

### 2.1 Arsitektur Saat Ini
1. Skrip tersebut adalah consumer **Kafka** yang memantau topik `dcim.enriched.events` (data real-time).
2. Data difilter dan dilakukan imputasi dasar (memori `forward-fill` atau median).
3. **MOCK MODEL:** Saat ini, di dalam skrip terdapat fungsi `dummy_isolation_forest_predict()` yang merupakan algoritma ambang batas (*threshold*) kasar sebagai *placeholder* (pengganti sementara).
4. Hasil prediksi (*anomaly boolean* dan *anomaly_score*) ditulis ke PostgreSQL di tabel `dcim_server_anomalies`.

### 2.2 Tugas Tim AI pada Inference
- **Ganti fungsi dummy!** Ubah logika `dummy_isolation_forest_predict()` menjadi logika pemuatan model `.pkl` (atau sejenisnya) hasil training kalian.
- Pastikan kalian tidak mengubah cara skrip membaca dari Kafka atau menulis ke tabel `dcim_server_anomalies`. Fokus ubah hanya pada bagian konversi *features* ke `model.predict()`.

---

## 3. AKSES & LINGKUNGAN (Credentials)

- **PostgreSQL**: `PGPASSWORD="Inovasi@0918" psql -h localhost -U sot_admin -d dcim_sot`
- **Tabel Hasil Prediksi**: `dcim_server_anomalies` (alias view `server_anomalies`).
- **Tabel Label Kegagalan**: `dcim_failure_events` (Kosong; disiapkan bagi kalian jika ingin membangun sistem pelabelan *supervised learning* berdasarkan catatan insiden).

---

## 4. REFERENSI DOKUMEN & RELASI PERANGKAT

Sebagai referensi komprehensif, kalian harus merujuk pada dokumentasi *AI Readiness* dan pedoman *baseline* berikut yang telah disesuaikan dengan arsitektur v4.1 terbaru:

- **AI Training Data Schema** (Pemetaan Fitur PostgreSQL ke Model MT-018):
  👉 `/home/infra/dcim_metrics_project/docs/development/ai-training-data-schema.md`
- **Data Access Guide** (Cara umum Agen mengakses PostgreSQL vs iTop):
  👉 `/home/infra/dcim_metrics_project/docs/development/ai-agent-data-access-guide.md`
- **Database Query Baseline** (Contoh-contoh Query SQL PostgreSQL yang benar):
  👉 `/home/infra/dcim_metrics_project/docs/development/34-database-query-baseline-for-agents.md`
- **Energy Baseline (PUE)** (Sebagai basis pelatihan jika ingin melatih model PUE):
  👉 `/home/infra/dcim_metrics_project/docs/operations/energy-baseline.md`
- **iTop API Baseline & Relasi Mendalam**:
  👉 `/home/infra/dcim_metrics_project/docs/development/itop-api-baseline-for-agents.md`

### 4.1 Mencari Relasi Perangkat (CMDB)
Data spasial dasar seperti `site` dan `rack_name` sudah tersedia di dalam tabel `v_train_server` sehingga kalian tidak perlu mencarinya jauh-jauh.
Namun, apabila model AI kalian membutuhkan relasi struktural (*Impact Analysis*, relasi Network Switch ke Server, atau informasi nama Kontak/PIC), kalian **harus** meng-kueri CMDB iTop (Golden Source Relasi) via API menggunakan `serial_number`. Panduannya tersedia secara detail pada **iTop API Baseline (Bagian 8)** di atas.

