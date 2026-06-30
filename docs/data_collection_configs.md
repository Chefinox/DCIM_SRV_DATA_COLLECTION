# Daftar Konfigurasi Data Collection DCIM

Berdasarkan analisis *environment* `srv-rnd-dcim`, pipeline end-to-end (Arsitektur v4.2), dan struktur proyek `dcim_metrics_project`, berikut adalah daftar konfigurasi untuk fase pengumpulan data (L2 - Collection), fungsinya, serta letak path lokasinya.

## 1. Konfigurasi Agen Telegraf (Telemetri Real-time)
Telegraf bertugas menarik (polling) data metrik secara berkala dari perangkat (interval standar 120 detik) dan mengirimkannya ke Apache Kafka sebagai produser.

| Nama / Target | Path Lokasi | Deskripsi Fungsi |
|---|---|---|
| **Telegraf Producer / Router (Utama)** | `configs/telegraf/telegraf_producer.conf` | Merupakan file konfigurasi master (agen). Fungsinya menangani pemilahan data (routing/namepass) dan mengatur pembuangan metrik (outputs) ke berbagai spesifik topik *Raw* Kafka (mis. `dcim.raw.hardware.server`, `dcim.raw.power.ups`, dll) berdasarkan kategori perangkatnya. |
| **Server Redfish Poller** | `configs/telegraf/servers-redfish.conf` | Konfigurasi ini menggunakan `inputs.redfish` untuk menarik metrik operasional dan *health* server Lenovo (suhu, fan, power, komponen) langsung melalui jalur BMC/HTTPS (Redfish API) setiap 120 detik. |
| **UPS SNMP Poller** | `configs/telegraf/ups-apc.conf` | Menggunakan `inputs.snmp` (Protokol SNMP v3 yang terenkripsi) untuk mengekstrak informasi load daya, status baterai, voltase, dan runtime estimasi dari UPS APC Smart-UPS. |
| **CCTV & NVR Poller** | `configs/telegraf/cctv-hikvision.conf` | Konfigurasi pembungkus yang menggunakan plugin `inputs.exec`. Fungsinya menjalankan skrip Python eksternal untuk berkomunikasi dengan kamera dan NVR Hikvision menggunakan protokol ISAPI HTTP/XML, dan hasilnya diterjemahkan kembali agar bisa dicerna oleh Telegraf. |

*(Catatan Repositori: Konfigurasi pengumpulan untuk NAS dan MikroTik didokumentasikan di arsitektur (`nas-snmp.conf`, `mikrotik-snmp.conf`) namun file *source*-nya tidak ter-*track* secara langsung di dalam repositori `configs/telegraf/` git saat ini.)*

## 2. Skrip Python Kustom (Inventory & Integrasi)
Selain plugin bawaan Telegraf, environment ini menggunakan skrip Python yang dieksekusi secara periodik (lewat cron job/daemon) untuk data yang lebih kompleks dan struktural:

| Nama Skrip | Path Lokasi | Deskripsi Fungsi |
|---|---|---|
| **Hikvision ISAPI Poller** | `scripts/hikvision_poller.py` | Skrip yang dipanggil oleh `cctv-hikvision.conf` di atas. Berisi logika HTTP/XML yang murni disesuaikan dengan arsitektur Hikvision untuk membaca status masing-masing stream dan disk CCTV. |
| **Server Inventory Poller** | `scripts/dcim_inventory_poller.py` (serta `server_inventory_collector.py`) | Melakukan pemindaian *deep scan* via Redfish API (berjalan harian, mis. jam 01:00 WIB). Mengekstrak daftar inventaris komponen fisik yang sangat mendetail (Spesifikasi CPU, slot RAM, MAC NIC, Serial Disk) yang dilempar sebagai *Kafka Producer* ke `dcim.raw.hardware.server.inventory` untuk proses CMDB Automation (ke iTop & Ralph). |
| **NAS Inventory Poller** | `scripts/nas_inventory_poller.py` | Skrip pengumpulan data spesifik NAS untuk memetakan volume logical dan susunan drive secara berkala. |

## Kesimpulan Pemahaman Pipeline DCIM
- **Siklus End-to-End:** Perangkat Fisik (L1) -> Diambil oleh Config Telegraf/Skrip di atas (L2) -> Dilempar mentah ke *Kafka Raw* (L3) -> *Normalizer* Python (L4) -> Pengayaan Metadata/NiFi (L5) -> Disimpan ke Elasticsearch dan PostgreSQL (L7) -> Alerting dan CMDB Ralph/iTop.
- **Git Versioning:** Repositori saat ini berada pada branch `main` dengan modifikasi aktif untuk "AI Readiness Phase" dan sinkronisasi CMDB, sehingga beberapa skrip Polling telah bertransisi menjadi modular (`dcim_inventory_poller.py`).
