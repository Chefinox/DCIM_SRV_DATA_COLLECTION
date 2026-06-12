# AI Agent Data Access Guide

**Version**: 1.0
**Target Audience**: AI/ML Engineers & Autonomous Agents

Dokumen ini adalah panduan teknis tentang bagaimana Agent AI dapat mengakses data operasional (DCIM), metadata aset (CMDB), dan metrics historis untuk keperluan analitik, training, maupun inference (RAG/Contextual Reasoning).

## 1. Arsitektur Sumber Data

Sistem DCIM saat ini menggunakan pendekatan desentralisasi penyimpanan, dimana agent AI harus mengambil data dari sistem yang spesifik sesuai kebutuhan:

1. **Elasticsearch (10.70.0.56:9200)**: Metrics time-series (CPU, RAM, Power, Suhu) yang sangat banyak dan beresolusi tinggi. Digunakan untuk data training dan anomali.
2. **Redis Enrichment API (localhost:8000/enrich)**: Metadata aset in-memory yang sangat cepat. Menggabungkan data dari iTop (lokasi, criticality, brand) yang siap pakai.
3. **iTop REST API (localhost:8080/webservices)**: *Source of Truth* utama untuk metadata CMDB dan Lifecycle (finansial, warranty).
4. **PostgreSQL**: Menyimpan event/log sistem internal DCIM.

---

## 2. API & Endpoint Reference

### A. Elasticsearch (Time-Series Metrics)

- **URL**: `https://10.70.0.56:9200`
- **Auth**: Basic Auth (Tanyakan ke tim Infra untuk kredensial `elastic`)
- **Index**: `dcim-metrics-unified-*`
- **Tujuan**: Mengambil raw metrics historis (misal: suhu 7 hari ke belakang).

**Contoh Query DSL: Mengambil rata-rata suhu server `J901GKXY` dalam 24 jam terakhir**
```json
POST /dcim-metrics-unified-*/_search
{
  "size": 0,
  "query": {
    "bool": {
      "filter": [
        { "term": { "tag.serial_number.keyword": "J901GKXY" } },
        { "range": { "@timestamp": { "gte": "now-24h", "lte": "now" } } }
      ]
    }
  },
  "aggs": {
    "avg_temp": {
      "avg": { "field": "dcim_metrics.raw_fields_system_temp" }
    }
  }
}
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
3. **Ambil Data Historis (Metrics)**: AI mengeksekusi query Elasticsearch DSL untuk menarik *time-series* `cpuUtilization` dan `power_output_watts` selama 7 hari ke belakang (di index `dcim-metrics-unified-*`).
   - *Alternatif*: Jika AI sedang mode training offline, gunakan file `training_YYYYMMDD_server.csv` (lihat [ai-training-data-schema.md](ai-training-data-schema.md)).
4. **Kalkulasi/Inference**: Berdasarkan metrics time-series (adakah lonjakan suhu/CPU secara konstan?) dan konteks CMDB (Server ini milik divisi A, ada di rak B), AI membuat kesimpulan atau rekomendasi.

---

## 4. Tips Penting untuk Agent

- **Gunakan `.keyword` di Elasticsearch**: Saat memfilter teks di ES, selalu gunakan akhiran `.keyword` (contoh: `tag.device_type.keyword`) untuk *exact match*.
- **Abaikan Sertifikat SSL ES**: Karena ES internal menggunakan self-signed cert, selalu set `verify=False` atau `-k` (jika menggunakan cURL) saat memanggil ES.
- **Kosongkan Asumsi Mapping**: Selalu merujuk ke schema di `configs/data_quality_schema.yaml` jika tidak yakin apa nama field metric di ES (karena versi lama dan baru mungkin berbeda formatnya).
