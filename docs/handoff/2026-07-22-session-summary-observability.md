# Session Handoff Summary: Observability & Dashboarding (22 July 2026)

## 📌 Executive Summary
Pada sesi ini, kami berfokus mengimplementasikan strategi *observability* dan merancang dashboard monitoring DCIM, sesuai panduan desain yang tercantum pada repositori `dcim-wiki`. Fokus utama adalah membangun pondasi visibilitas baik untuk *Infrastructure Health* (NOC View) maupun pantauan aset IT & Fasilitas secara keseluruhan.

## 🏗️ Kondisi Arsitektur Saat Ini
1. **Data Ingestion Pipeline**: Pipeline *telemetry* telah berjalan stabil. Script poller (seperti `cctv_poller.py`, `server_inventory_collector.py`, `snmp_ups_poller.py`) mengirim data ke Kafka, dan dikonsumsi serta dimuat ke PostgreSQL (`dcim_sot` di host `10.70.0.56:5432`) melalui *Unified Consumer*.
2. **Prometheus Eksportir**: Metrik dari setiap komponen pipeline (Kafka, Redis, PostgreSQL, Node/Server, dan Elasticsearch) telah berhasil diekspor menggunakan *Prometheus Exporters* yang dikonfigurasi di dalam `observability/prometheus/prometheus.yml`.
3. **Database SoT**: Seluruh telemetri IoT dan IT (Server Redfish CPU/Mem, Sensor Baterai UPS, CPU/Memory CCTV, kapasitas NAS) secara persisten tersimpan di PostgreSQL (Tabel `dcim_events` pada database `dcim_sot`).

---

## 🚨 Peringatan Penting untuk Agent Berikutnya (CRITICAL)

> [!WARNING]
> **Prometheus dan Grafana TIDAK berjalan di host/server ini!**
> Keduanya beroperasi pada *External Host* (`10.70.0.25`).
> - **Prometheus**: `http://10.70.0.25:9090`
> - **Grafana**: `http://10.70.0.25:3001`
> 
> *Implikasi:* Jangan pernah menggunakan metode *Local File Provisioning* atau me-restart container Grafana melalui `docker-compose` di server ini untuk membuat dashboard. Semua pembuatan dashboard **HARUS** dilakukan secara remote (via API POST ke endpoint HTTP Grafana eksternal tersebut) menggunakan `admin:admin`.

---

## 📊 Dashboard yang Telah Dibuat
Kami telah mengotomatisasi penyebaran *6 Dashboards* utama ke Grafana:

### 1. NOC View (Sumber: Prometheus)
Melakukan pantauan kesehatan infrastruktur dari *ingestion pipeline*:
- **Node Exporter Full** (Server Resources)
- **PostgreSQL Database** (DB Connection & Transactions)
- **Redis Dashboard** (Cache I/O)
- **Kafka Exporter Overview** (Topics, Consumer Lag)
- **Elasticsearch - Cluster** (Log Storage)
*(Catatan: Variabel default klaster Elasticsearch telah di-patch via API agar `dcim-es` terpilih otomatis).*

### 2. IT & Facilities View (Sumber: PostgreSQL TimescaleDB)
Memanfaatkan SQL queries ke tabel `dcim_events` di database `dcim_sot` (di host ini `10.70.0.56:5432`):
- **Server Performance**: Utilisasi CPU & RAM (HCI & Render).
- **UPS Power**: Baterai & Tegangan.
- **CCTV Sensors**: Beban *compute* kamera pengawas.
- **NAS Storage**: Penggunaan kapasitas data.
*(Catatan: Datasource Grafana kustom bernama `DCIM_SOT_Postgres` telah dibuat khusus untuk melayani dashboard ini, menggantikan target keliru sebelumnya `dcim_analytics`).*

## 📚 Acuan Dokumentasi
Harap selalu merujuk dan mempelajari pedoman di dalam `/home/infra/dcim-wiki/` sebelum mengeksekusi arsitektur:
- `/home/infra/dcim-wiki/concepts/dashboard-view-design.md`
- `/home/infra/dcim-wiki/concepts/observability-strategy.md`

## 🔜 Next Steps / Rekomendasi
1. Melakukan konsolidasi *SOC View* (Security Operations Center) dan *Management View* (SLA/KPI) sesuai dengan `dashboard-view-design.md`.
2. Menyiapkan *Alerting Rules* di dalam Grafana agar sistem dapat membunyikan peringatan/Telegram Alert ketika baterai UPS kritis atau ketika CPU Server sentuh *threshold*.
