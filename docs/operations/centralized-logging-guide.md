# Panduan Observabilitas: Log DCIM Terpusat (Centralized Logging)

Dokumen ini memetakan seluruh arsitektur log yang ada pada ekosistem DCIM v4.0. Semua log yang didata dalam dokumen ini telah diintegrasikan (tersentralisasi) menggunakan **Filebeat** menuju ke **Elasticsearch** dan dapat divisualisasikan melalui **Kibana**.

## 1. Log Aplikasi Python (Microservices)
Log ini dihasilkan langsung oleh skrip kustom Python kita. Format log sudah distandardisasi menjadi JSON dengan skema (ECS - Elastic Common Schema) sehingga pencarian di Kibana menjadi lebih terstruktur.

* **Lokasi Server:** `/home/infra/dcim_metrics_project/logs/*.log`
* **Cara Mencari di Kibana (KQL):** `log.file.path : "*"` atau `service.name : "*"` pada *Index Pattern* `dcim-logs-*`.

**Daftar Log:**
| Nama Layanan / File Log | Fungsi & Deskripsi |
|---|---|
| `dcim_itop_unified_consumer.log` | Mencatat proses penangkapan data (webhook) perubahan CMDB di iTop yang dikirim lewat Kafka. |
| `itop_to_cache_sync.log` | Mencatat aktivitas siklus _cron/timer_ dari skrip sinkronisasi berkala dari iTop menuju Redis Cache. |
| `threshold_alerts.log` | Catatan deteksi anomali pada metrik (misalnya: suhu lebih dari ambang batas, alat mati/tidak lapor) dari skrip `dcim-threshold-alerter`. |
| `data_quality_*.log` | Log audit dari proses _Data Quality Check_, mencatat seberapa bersih metrik yang masuk setiap harinya. |

## 2. Log Layanan Systemd (Journald)
Setiap layanan DCIM yang terdaftar di Ubuntu dikelola oleh *Systemd*. Filebeat membaca _stdout_ dan _stderr_ (log layar/terminal) dari layanan ini untuk berjaga-jaga apabila skrip *crash*, sistem menolak untuk _start_, atau *service restart*.

* **Lokasi Server:** `journalctl -u <nama_layanan>`
* **Cara Mencari di Kibana (KQL):** `systemd.unit : "dcim-*" `

**Daftar Log:**
| Nama Service (Systemd) | Fungsi & Deskripsi |
|---|---|
| `dcim-itop-unified.service` | Layanan latar belakang untuk Webhook iTop. |
| `dcim-normalizer.service` | Pekerja (Worker) yang merapikan format data sensor raw IoT sebelum diteruskan ke proses pengayaan (*enrichment*). |
| `dcim-enrichment-api.service` | API internal (FastAPI) untuk pengecekan CMDB di Redis (pemberian _tags_ dari data iTop). |
| `dcim-dlq-consumer.service` | Penarik dan pencatat pesan yang cacat (*Dead Letter Queue*) ke dalam database PostgreSQL. |
| `dcim-telegram-alerter.service` | Pekerja pengirim peringatan instan ke grup/bot Telegram. |
| `dcim-itop-redis-sync.service` | Layanan penarik massal (Sinkronisasi penuh) data dari iTop CMDB menuju Redis Cache. |

## 3. Log Kontainer (Docker)
Seluruh infrastruktur inti DCIM berjalan di atas mesin Docker. Log kesehatan *database*, *message broker*, dan *data pipeline* terpusat dari sini.

* **Lokasi Server:** `/var/lib/docker/containers/*/*.log` atau `docker logs <nama_container>`
* **Cara Mencari di Kibana (KQL):** `container.name : "*"`

**Daftar Log:**
| Nama Kontainer | Fungsi & Deskripsi |
|---|---|
| `kafka-broker` | Mencatat kesehatan aliran antrean, *offset* konsumen, dan partisi topik Kafka. |
| `dcim-nifi` | Log penarikan, pengubahan (*transformation*), dan penulisan (ETL) data sebelum masuk ke Elasticsearch. |
| `dcim-elasticsearch` & `dcim-kibana` | Log operasional dari inti _database_ pencarian log/metrik, serta antarmuka (UI) observabilitas. |
| `dcim-redis` | Indikator *cache hit/miss* serta manajemen alokasi memori Redis. |
| `dcim_sot_postgres` | Log kueri SQL dari _Source of Truth_ (SOT) internal dan log DLQ. |
| `telegraf` | Agen pengumpul yang mentransmisikan beban _server_ (_CPU, RAM_) dan *webhook* menuju Kafka. |

## 4. Log Jaringan (Syslog via UDP 514)
Aliran _Syslog_ raw (mentah/plaintext) dari berbagai perangkat jaringan dan server fisik yang dialirkan langsung tanpa filter menuju ke penerima Syslog Filebeat.

* **Cara Mencari di Kibana (KQL):** `event.module : "syslog"` atau dengan mengeksklusi filter *Microservices*.
* **Fungsi & Deskripsi:** Menyimpan log insiden _networking_ seperti DHCP leasses, Up/Down interface status dari Router MikroTik (misal: `FIT-Core-RTR`) atau *Switch* Core. Ini akan menghasilkan lalu lintas log yang sangat masif namun esensial untuk audit jaringan lapisan bawah.

---

## 🚀 Cara Melihat Log (Navigasi Dasbor)

**1. Menggunakan Menu Dashboard Khusus (Rekomendasi)**
Anda sudah dibuatkan _Single Pane of Glass_ untuk memantau khusus log aplikasi DCIM (_Microservices_ Python).
1. Buka Kibana di peramban web: `http://10.70.0.56:5601/`
2. Buka Menu Navigation ☰ → klik **Dashboards**.
3. Pilih Dasbor bernama **"DCIM Observability - Centralized Logs"**.
4. Di dasbor tersebut, seluruh metrik jumlah Error dan Peringatan terpampang di atas, sementara data log mentah ada di bagian dasar halaman. Dasbor ini sudah disaring (*filtered*) agar **hanya menampilkan Log Microservices Python**, sehingga bebas dari timbunan pesan Syslog Router.

**2. Menggunakan Menu Discover (Pencarian Investigatif)**
Jika Anda ingin mencari suatu kata kunci secara global (misal: mencari penyebab database mati atau mencari IP tertentu):
1. Buka Menu Navigation ☰ → klik **Discover**.
2. Pastikan Anda telah mengganti *Index Pattern* (di pojok kiri menu dropdown) menjadi `dcim-logs-*`.
3. Ketikkan bahasa *Query* (KQL) di kolom *Search*. Contoh:
   * Menampilkan error dari Kafka: `container.name: "kafka-broker" AND message: "Error"`
   * Melihat seluruh proses Enrichment API: `systemd.unit: "dcim-enrichment-api.service"`
   * Melihat rekam jejak koneksi sebuah Mikrotik: `message: "FIT-Core-RTR"`
