# Backlog Finalisasi DCIM Pipeline (AI/ML Preparation)

**Tanggal Mulai:** 2026-05-04
**Tujuan Utama:** Menstabilkan kualitas data (*data integrity*), memperbaiki observabilitas (Elasticsearch), dan menyiapkan dataset berstruktur tinggi di PostgreSQL untuk keperluan *AI/ML Training*.

---

## 📋 DAFTAR FASE & STATUS TUGAS

### FASE 1: Koreksi Arsitektur PostgreSQL & CMDB (Fokus Data Terstruktur)
Menyelesaikan masalah duplikasi data, nilai `NULL` pada timeseries, serta optimasi sinkronisasi perangkat keras ke CMDB.

- [x] **Task 6: Optimasi Crontab Ralph CMDB**
  - Mengubah jadwal sinkronisasi `ralph_cmdb_sync.py` dari setiap 15 menit menjadi 1 hari sekali.
- [x] **Task 1: Restrukturisasi Tabel Komponen Server (Solve NULLs)**
  - Mengubah metode penyimpanan JSONB array menjadi tabel relasional `dcim_server_components`.
  - Membuat PostgreSQL *Trigger* agar query `device_type = 'server'` dapat terisi otomatis untuk inventaris statis (menggabungkan metrik telemetri + inventaris secara rata tanpa NULL).
- [x] **Task 2: Penambahan Fitur "Last Sync" & Pruning 7 Hari di CMDB**
  - Mengupdate `ralph_cmdb_sync.py` untuk menulis waktu sinkronisasi terakhir di kolom *Remarks* (UPS dan perangkat lain).
  - Menambahkan *logic* penghapusan aset dari Ralph secara otomatis jika "Last Sync" sudah melewati batas waktu 7 hari.
- [x] **Task 7: Investigasi CCTV/NVR (`NO_SN`)**
  - Mendiagnosis konfigurasi Telegraf/SNMP untuk perangkat Hikvision/CCTV guna memperbaiki *serial number* yang tidak terbaca.

### FASE 2: Validasi Streaming & Observabilitas (Fokus Elasticsearch)
Memastikan seluruh *pipeline* data berfungsi tanpa *error* hingga visualisasi Kibana.

- [ ] **Task 8: Validasi Kafka Pipeline End-to-End**
  - Mengecek perpindahan data tanpa *bottleneck* dari topik `raw` -> `normalized` -> `enrichment`.
- [ ] **Task 4: Pengecekan Bug Elasticsearch**
  - Verifikasi log *indexing* dan mapping di Elasticsearch, menelusuri penyebab data tidak terbaca dengan baik.
- [ ] **Task 5: Perbaikan Dashboard Kibana (No Result Found)**
  - Memperbaiki pola indeks (*Index Pattern*) atau konfigurasi JSON Dashboard untuk menyesuaikan dengan field metrik terbaru.

### FASE 3: Finalisasi & Penyerahan (Handover ke AI)
Mengkondisikan agar *warehouse* siap dihubungkan langsung ke modul AI/ML.

- [ ] **Task 9: AI-Ready Data Verification**
  - Memastikan *schema* akhir `dcim_sot` di PostgreSQL bebas dari anomali, memiliki relasi tabel yang logis, dan tipe data numerik yang akurat untuk proses *training*.
- [ ] **Task 3: Pembaruan Dokumen Arsitektur & Versioning**
  - Memperbarui file `19-kafka-pipeline-architecture.md` untuk merepresentasikan arsitektur versi terbaru (V3).
  - Melakukan rekap *change management* standar.

---

## 📝 CATATAN PROGRES (LOG)
*Dokumen ini akan diupdate setiap kali sebuah Task selesai dieksekusi.*

- **[2026-05-04]**: Dokumen backlog ini dibuat. Persiapan eksekusi Fase 1 dimulai.
