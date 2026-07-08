# Daftar Konfigurasi Data Collection DCIM

Berdasarkan analisis *environment* `srv-rnd-dcim`, pipeline end-to-end (Arsitektur v4.2), dan struktur proyek `dcim_metrics_project`, berikut adalah daftar konfigurasi untuk fase pengumpulan data (L2 - Collection), fungsinya, serta letak path lokasinya.

## 1. Konfigurasi Apache NiFi (Telemetri Real-time)
Apache NiFi kini bertugas 100% sebagai pengumpul data (polling) secara tersentralisasi. NiFi menjalankan berbagai skrip poller eksternal dan mengirimkan hasilnya ke Apache Kafka.

| Nama / Target | Path Lokasi | Deskripsi Fungsi |
|---|---|---|
| **NiFi Server Poller** | `configs/telegraf/servers-redfish.conf.disabled` | Telah bermigrasi penuh ke NiFi (`ExecuteProcess` via `redfish_poller.py`). Konfigurasi Telegraf telah dimatikan. |
| **NiFi UPS Poller** | `configs/telegraf/ups-apc.conf.disabled` | Telah bermigrasi penuh ke NiFi (`ExecuteProcess` via `snmp_ups_poller.py`). Konfigurasi Telegraf telah dimatikan. |
| **NiFi CCTV Poller** | `configs/telegraf/cctv-hikvision.conf.disabled` | Telah bermigrasi penuh ke NiFi. Standalone daemon dan konfigurasi Telegraf telah dimatikan. |
| **Infra Self-Monitoring** | `configs/telegraf/infra-monitoring.conf` | Satu-satunya konfigurasi Telegraf yang masih hidup, ditujukan murni untuk *self-monitoring* server DCIM itu sendiri (L15), tidak melempar data ke Kafka DCIM. |


## 2. Skrip Python Kustom (Inventory & Integrasi)
Selain plugin bawaan Telegraf, environment ini menggunakan skrip Python yang dieksekusi secara periodik (lewat cron job/daemon) untuk data yang lebih kompleks dan struktural:

| Nama Skrip | Path Lokasi | Deskripsi Fungsi |
|---|---|---|
| **Hikvision ISAPI Poller** | `scripts/hikvision_poller.py` | Skrip yang dipanggil oleh `cctv-hikvision.conf` di atas. Berisi logika HTTP/XML yang murni disesuaikan dengan arsitektur Hikvision untuk membaca status masing-masing stream dan disk CCTV. |
| **Server Inventory Poller** | `scripts/dcim_inventory_poller.py` (serta `server_inventory_collector.py`) | Melakukan pemindaian *deep scan* via Redfish API (berjalan harian, mis. jam 01:00 WIB). Mengekstrak daftar inventaris komponen fisik yang sangat mendetail (Spesifikasi CPU, slot RAM, MAC NIC, Serial Disk) yang dilempar sebagai *Kafka Producer* ke `dcim.raw.hardware.server.inventory` untuk proses CMDB Automation (ke iTop & Ralph). |
| **NAS Inventory Poller** | `scripts/nas_inventory_poller.py` | Skrip pengumpulan data spesifik NAS untuk memetakan volume logical dan susunan drive secara berkala. |

## Kesimpulan Pemahaman Pipeline DCIM
- **Siklus End-to-End:** Perangkat Fisik (L1) -> Diambil 100% oleh Apache NiFi (L2) -> Dilempar mentah ke *Kafka Raw* (L3) -> *Normalizer* Python (L4) -> Pengayaan Metadata/NiFi (L5) -> Disimpan ke Elasticsearch dan PostgreSQL (L7) -> Alerting dan CMDB Ralph/iTop.
- **Status Migrasi L2:** Telegraf dan *Standalone Daemon* resmi dinonaktifkan untuk pengumpulan data telemetri DCIM. Telegraf hanya difungsikan untuk pemantauan server itu sendiri (*self-monitoring*).
