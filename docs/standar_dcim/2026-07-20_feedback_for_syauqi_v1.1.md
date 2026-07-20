# Feedback untuk Tim AI (Syauqi) — Verifikasi Pipeline v1.1
> **Dari:** Fakhri (Tim DCIM Infra)
> **Tanggal:** 20 Juli 2026
> **Terkait:** Update Dokumentasi Pipeline v1.1 & Status Data Analytics

Terima kasih atas update dokumentasi di `ai-pipeline-architecture.md`, `ai-team-access.md`, dan `README.md`. Secara garis besar, dokumen sudah sangat komprehensif dan *gap analysis* dari tanggal 15 Juli sudah ter-address dengan baik. 

Migration script `002_create_analytics_tables.sql` juga sudah dijalankan. 9 tabel analytics sekarang sudah tersedia di database. API Analytics (Block 7) kami sudah dipatch agar mengarah ke tabel-tabel ini.

Namun, setelah kami lakukan verifikasi langsung ke database `dcim_analytics` (TimescaleDB) hari ini (20 Juli 2026 pukul 06:24 UTC), masih ada beberapa isu kritis terkait **aliran data (data flow)** yang menghambat API kami berjalan real-time.

Berikut adalah temuan yang perlu ditindaklanjuti.

---

## 🔴 Isu Kritis (Blocker)

### 1. Data P1 (Server & UPS) Sangat Sedikit / Telat Masuk
Meskipun di dokumen `ai-team-access.md` disebutkan polling interval Server adalah 30-60 detik dan UPS adalah 60 detik, jumlah data aktual yang masuk ke database sangat sedikit untuk ukuran 1 jam terakhir.

- `total_facility_power` : Hanya ada 125 baris.
- `it_equipment_power` : Hanya ada 133 baris.
- `output_frequency` : Hanya ada 133 baris.

Dengan polling 60 detik, 1 UPS harusnya menghasilkan 60 baris dalam 1 jam. Jika ada 10 UPS, harusnya ada 600 baris/jam. Saat ini data masuk tersendat. **Efek:** Fitur Energy Optimization dan Anomaly Detection untuk Power belum bisa running secara real-time.

### 2. Metric `memory_utilization` Server Belum Masuk
Di dokumen dicantumkan `memory_utilization` sebagai bagian dari 3 metrics Server. Namun, hasil query di database menunjukkan metrik ini **belum ada sama sekali** di tabel `metrics`.
- `cpu_utilization` : Ada (90,271 baris) ✅
- `power_state` : Ada (435 baris) ✅
- `memory_utilization` : **Tidak ada / 0 baris** ❌

**Efek:** Kami tidak bisa memprediksi kehabisan kapasitas RAM (Capacity Forecasting ter-block).

---

## 🟡 Isu Medium

### 1. Polling Interval `memory_total` & `memory_used` (Network) Sangat Rendah
Hanya ada 200 baris data `memory_total` dan `memory_used` di database untuk seluruh network devices. Ini mengindikasikan poller `mikrotik_poller.py` belum berjalan optimal atau sering timeout.

---

## ✅ Yang Sudah Sesuai Ekspektasi

- Metric name alignment sudah pas (contoh: `disk_temperature`, `interface_status`, `cpu_utilization` sudah sesuai format API kami).
- `disk_temperature` (2.6M baris) dan `interface_status` (13.1M baris) masuk dengan volume yang sangat baik.
- Tabel hasil analytics (anomaly_events, predictions, dll) sudah tersedia dan permission `ai_team` sudah bisa melakukan INSERT/UPDATE.

---

## 📋 Action Items untuk Tim AI (Syauqi)

1. [ ] **Verifikasi `redfish_poller.py`**: Mengapa `memory_utilization` tidak masuk ke Kafka/TimescaleDB?
2. [ ] **Verifikasi `snmp_ups_poller.py` & Normalizer**: Mengapa frekuensi masuknya data energy (`total_facility_power`, `it_equipment_power`) sangat lambat/sedikit?
3. [ ] **Verifikasi `mikrotik_poller.py`**: Cek mengapa data memory switch tersendat.

Mohon info jika poller-poller tersebut butuh direstart atau jika ada error log di sisi NiFi/Normalizer. 

API Block 7 Analytics saat ini berjalan dalam "Fallback Mode" (menggunakan data historis 6-24 jam ke belakang) karena minimnya data real-time. Begitu 3 action items di atas selesai, API akan otomatis switch ke Real-Time Scoring.

Terima kasih.