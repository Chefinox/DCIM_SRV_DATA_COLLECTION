# AI Agent Data Access Guide

**Version**: 1.1 (Updated 2026-06-15)
**Target Audience**: AI/ML Engineers & Autonomous Agents

Dokumen ini adalah panduan teknis tentang bagaimana Agent AI dapat mengakses data operasional (DCIM), metadata aset (CMDB), dan metrics historis untuk keperluan analitik, training, maupun inference (RAG/Contextual Reasoning).

## 1. Arsitektur Sumber Data (v4.1)

Berdasarkan keputusan arsitektur terbaru (v4.1 L13), **PostgreSQL** adalah *golden source* untuk AI Training Data, sedangkan **iTop** adalah *golden source* untuk relasi perangkat.

1. **PostgreSQL (`dcim_sot` di localhost:5432)**: Sumber utama untuk data training time-series AI historis beresolusi panjang (tabel `dcim_metrics_archive` dan materialized views `v_train_*`). PostgreSQL juga menampung raw `dcim_events` untuk rentang 7 hari terakhir.
2. **Elasticsearch (10.70.0.56:9200)**: Digunakan untuk Kibana Dashboard, Alerting real-time, dan Log JSON (`dcim-logs-app-*`). **Tidak lagi digunakan** sebagai sumber utama export training data.
3. **Redis Enrichment API (localhost:8000/enrich)**: Metadata aset in-memory yang sangat cepat. Menggabungkan data dari iTop (lokasi, criticality, brand) yang siap pakai.
4. **iTop REST API (localhost:8080/webservices)**: *Source of Truth* utama untuk metadata CMDB dan Lifecycle (finansial, warranty).

---

## 2. API & Endpoint Reference

### A. PostgreSQL (AI Training Golden Source)

- **Endpoint**: `localhost:5432`, DB: `dcim_sot`, User: `sot_admin`
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

- **URL**: `http://localhost:8080/webservices/rest.php?version=1.3`
- **Auth**: `auth_user` & `auth_pwd` (Tanyakan tim Infra)

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
   - *Alternatif Offline*: Jika AI sedang mode training offline, gunakan file `training_YYYYMMDD_server.csv` (lihat [ai-training-data-schema.md](ai-training-data-schema.md)).
4. **Kalkulasi/Inference**: Berdasarkan metrics time-series (adakah lonjakan suhu/CPU secara konstan?) dan konteks CMDB (Server ini milik divisi A, ada di rak B), AI membuat kesimpulan atau rekomendasi.

---

## 4. Tips Penting untuk Agent

- **Selalu Rujuk PostgreSQL untuk AI Data**: Hindari query ke Elasticsearch kecuali untuk mengecek log (`dcim-logs-app-*`) atau alert real-time (`dcim-alerts`).
- **Gunakan Materialized View**: Tembak langsung `v_train_*` daripada menyusun ulang tabel long/EAV manual dari `dcim_metrics_archive`.
- **Abaikan Sertifikat SSL**: Jika mengakses endpoint yang secure, selalu set `verify=False` atau `-k` untuk internal network.
