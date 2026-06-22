# AI Agent Data Access Guide

**Version**: 1.3 — selaras arsitektur **v4.2** (Updated 2026-06-22)
**Target Audience**: AI/ML Engineers & Autonomous Agents (akses dari luar host)

Dokumen ini adalah panduan teknis tentang bagaimana Agent AI dapat mengakses data operasional (DCIM), metadata aset (CMDB), dan metrics historis untuk keperluan analitik, training, maupun inference (RAG/Contextual Reasoning).

## 1. Arsitektur Sumber Data (v4.2)

Berdasarkan keputusan arsitektur v4.2 (§16 — L14 *Data Interface for AI*), host `srv-rnd-dcim` berperan sebagai **penyedia data**; training & inference dijalankan **tim AI di infrastruktur sendiri**, mengakses **dari luar** secara read-only. **PostgreSQL** adalah *golden source* untuk AI Training Data, **iTop** adalah *golden source* untuk relasi perangkat.

1. **PostgreSQL (`dcim_sot` @ 10.70.0.56:5432)** — akses pakai akun read-only **`dcim_ai_reader`** (bukan `sot_admin`): sumber utama time-series historis (`dcim_metrics_archive` + materialized views `v_train_*`), label `dcim_failure_events`, dan raw `dcim_events` (7 hari). Tim AI **menulis hasil** skor anomali hanya ke `dcim_server_anomalies`.
2. **Elasticsearch (10.70.0.56:9200)**: Kibana, alerting real-time, log JSON (`dcim-logs-app-*`). **Bukan** sumber export training.
3. **iTop REST API (10.70.0.56:8080/webservices)**: relasi CMDB & lifecycle — akses read-only pakai akun **`ai_readonly`** (lihat `itop-api-baseline-for-agents.md`).
4. **Redis Enrichment API (`localhost:8000/enrich`)**: hanya internal pipeline (NiFi). **Tidak dapat diakses dari luar host**; tim AI mengambil metadata lewat kolom enrichment di `dcim_events`/`v_train_*` atau langsung iTop.

> **Penting (v4.2)**: tidak ada proses inference AI yang berjalan di host ini. Host hanya menyediakan data (read) + wadah hasil `dcim_server_anomalies` (write dari luar).

---

## 2. API & Endpoint Reference

### A. PostgreSQL (AI Training Golden Source)

- **Endpoint**: `10.70.0.56:5432`, DB: `dcim_sot`, User: `dcim_ai_reader` (read-only; password via secret store / `configs/ai_reader.credentials`)
- **Tables/Views**: `v_train_server`, `v_train_ups`, `v_train_nas`, `v_train_network`, `v_train_cctv`, `v_train_nvr`.
- **Tujuan**: Mendapatkan data berformat *wide* yang sudah siap-latih (ready-to-train) untuk AI.

**Contoh SQL Query: Mengambil histori time-series server J901GKXY dalam 7 hari terakhir**
```sql
SELECT ts, temp_celsius, cpu_util_pct, mem_util_pct, power_watts
FROM v_train_server
WHERE serial_number = 'J901GKXY'
  AND ts >= NOW() - INTERVAL '7 days'
ORDER BY ts ASC;
```

### B. Redis Enrichment API (Fast Metadata Context)

- **URL**: `http://localhost:8000/enrich/{serial_number}`
- **Auth**: None (internal network)
- **Tujuan**: Agent AI bisa me-resolve `serial_number` menjadi objek JSON yang memiliki nama, lokasi, rack, organisasi, dan *criticality level*. Sangat berguna jika AI mendeteksi anomali suhu dan perlu tahu di mana aset itu berada secara fisik.

**Contoh Response:**
```json
{
  "sn": "J901GKXY",
  "name": "SERVER-HCI-01",
  "location": "Ruang Server",
  "rack": "Rack Server 2",
  "brand": "Lenovo",
  "ci_class": "Server",
  "criticality": "low",
  "org": "PT. Falah Inovasi Teknologi"
}
```

### C. iTop REST API (Lifecycle & Financial)

Jika AI Agent diminta untuk melakukan analisis finansial (misal: *capacity planning* berdasarkan umur garansi), AI harus melakukan query ke iTop.

- **URL**: `http://10.70.0.56:8080/webservices/rest.php?version=1.3`
- **Auth**: akun read-only **`ai_readonly`** (`auth_user`/`auth_pwd`); password via kanal aman. Jangan pakai akun `admin`.

**Contoh Payload (core/get):**
```json
{
  "operation": "core/get",
  "class": "Server",
  "key": "SELECT Server WHERE serialnumber = 'J901GKXY'",
  "output_fields": "purchase_date,end_of_warranty,business_criticity"
}
```

---

## 3. Workflow End-to-End untuk AI Agent

Berikut adalah contoh skenario **"Cara mendapatkan semua konteks & data historis Server X untuk dianalisis oleh LLM"**:

1. **Identifikasi**: AI menerima alert atau instruksi untuk menganalisis server dengan Serial Number `J901GKXY`.
2. **Ambil Konteks Fisik**: AI melakukan `GET http://localhost:8000/enrich/J901GKXY`.
   - *Hasil*: AI tahu ini adalah `Server` merk `Lenovo` di `Rack Server 2`, tingkat *criticality* `low`.
3. **Ambil Data Historis (Metrics)**: AI melakukan eksekusi SQL query ke PostgreSQL (database `dcim_sot`, view `v_train_server`) untuk menarik *time-series* `cpu_util_pct` dan `power_watts` selama 7 hari ke belakang.
   - *Alternatif Offline / Training*: Jika AI sedang mode melatih model (training) offline, gunakan alat ekspor: `python3 scripts/export_training_data.py --device server --start 2026-05-01 --end 2026-06-01` untuk mendapatkan CSV/JSONL yang siap pakai (lihat [ai-training-data-schema.md](ai-training-data-schema.md)).
4. **Kalkulasi/Inference**: Berdasarkan metrics time-series (adakah lonjakan suhu/CPU secara konstan?) dan konteks CMDB (Server ini milik divisi A, ada di rak B), AI membuat kesimpulan atau rekomendasi. Inference dijalankan **di infrastruktur tim AI**; hasil skor disimpan kembali ke tabel `dcim_server_anomalies` lewat koneksi `dcim_ai_reader` (satu-satunya tabel yang boleh ditulis dari luar).

---

## 4. Tips Penting untuk Agent

- **Selalu Rujuk PostgreSQL untuk AI Data**: Hindari query ke Elasticsearch kecuali untuk mengecek log (`dcim-logs-app-*`) atau alert real-time (`dcim-alerts`).
- **Gunakan Materialized View**: Tembak langsung `v_train_*` daripada menyusun ulang tabel long/EAV manual dari `dcim_metrics_archive`.
- **Abaikan Sertifikat SSL**: Jika mengakses endpoint yang secure, selalu set `verify=False` atau `-k` untuk internal network.
