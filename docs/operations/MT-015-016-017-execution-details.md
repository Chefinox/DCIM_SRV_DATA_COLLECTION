# Laporan Eksekusi Detail: MT-015, MT-016, MT-017

Dokumen ini merupakan penjabaran teknis (*technical changelog*) dari setiap dokumen, konfigurasi, dan skrip yang telah diubah atau dibuat untuk menyelesaikan gap pada arsitektur DCIM v4.0.

---

## 1. Eksekusi MT-015: Data Synchronization for AI Models

| Sub-Task | Aksi Teknis yang Dilakukan | File / Konfigurasi Terkait |
|---|---|---|
| **ST-015-01**<br>Tag Alat Hilang | Menambahkan konfigurasi `inherit_tags` pada file konfigurasi SNMP Telegraf agar tag `serial_number` ikut terbawa dari tabel induk ke tabel *measurement* untuk perangkat NAS dan Switch. | `/etc/telegraf/telegraf.d/nas-snmp.conf`<br>`/etc/telegraf/telegraf.d/network-switches.conf` |
| **ST-015-02**<br>Audit Error 0% | Mengubah parameter Elasticsearch query pada skrip Python dari waktu statis hari kemarin menjadi jendela *rolling* 24 jam (`now-24h` s.d `now`). Memperbaiki *key* `network_switch` menjadi `network`. Melakukan *reset offset* Kafka via *CLI tool* agar data berhenti tertahan (*lag*). | `scripts/audit_data_quality.py`<br>`kafka-consumer-groups.sh` |
| **ST-015-03**<br>Gap Data Historis | Menulis dokumen panduan resmi bagi insinyur AI (*AI engineers*) mengenai batasan data historis Elastic (sebelum v4.0) yang tidak memiliki atribut label merk/lokasi, serta cara menggunakan API CMDB untuk mengambil *metadata* alat lama. | `docs/development/ai-agent-data-access-guide.md` |
| **ST-015-06**<br>CMDB Drift | Mengkodekan dan menyuntikkan aturan alarm Kibana (*Watcher/Rule*) via API REST yang melakukan komparasi antara nama fisik perangkat (*hostname*) dengan nama yang terdaftar resmi (*name*). | `scripts/setup_kibana_telegram_alerts.py` |

---

## 2. Eksekusi MT-016: Centralized DCIM Logging

| Sub-Task | Aksi Teknis yang Dilakukan | File / Konfigurasi Terkait |
|---|---|---|
| **ST-016-01**<br>DLQ Crash & Lag | Membuat struktur tabel `dlq_records` di database PostgreSQL. Karena tabel ini sebelumnya tidak ada, skrip `dcim_dlq_consumer.py` terjebak dalam *loop error* massal yang membuat disk penuh. | Eksekusi SQL di `dcim_sot`<br>`scripts/dcim_dlq_consumer.py` |
| **ST-016-02**<br>Log Plaintext | Merombak arsitektur _logger_ Python standar (`logging.Formatter`) agar memancarkan format JSON yang *ECS-compliant* (menggunakan *keys* seperti `@timestamp`, `log.level`, dan `service.name`) sehingga Filebeat tidak bingung memparsing teks. | `src/observability/logging/dcim_logger.py` |
| **ST-016-03**<br>Permission Log | Mengeksekusi perintah terminal `sudo chown infra:infra` pada file log agar agen Filebeat (yang tidak punya akses *root*) tidak terblokir akses bacanya. | `/home/infra/dcim_metrics_project/logs/itop_cache_sync.log` |
| **ST-016-04**<br>Salah Tempat Log | Memodifikasi parameter *FileHandler* di dalam skrip `hikvision_poller.py` untuk mengarahkan direktori keluaran log yang sebelumnya sembarangan ke *path* standar `logs/`. | `scripts/hikvision_poller.py` |
| **ST-016-05**<br>Journald Input | Menulis ulang konfigurasi Filebeat YAML. Menambahkan blok *input type: journald* dan merinci `_SYSTEMD_UNIT` dari setiap *Microservices* DCIM yang berjalan di sistem Ubuntu agar log *stdout* terekam secara sentral. | `/etc/filebeat/filebeat.yml` |
| **ST-016-06**<br>Kibana Dashboard | Menulis skrip Python otomatisasi yang merakit JSON Payload berisi struktur komponen UI (React) Kibana (seperti *Data Table*, *Metric Number*, *Saved Search* log) lalu di-*POST* ke API Kibana. | `scripts/create_log_dashboard.py` |
| **(Tambahan)**<br>Timer CMDB Sinkron | Membuat dan menghidupkan *systemd timer* (cron) agar skrip `itop_to_cache_sync.py` otomatis menarik data dari iTop CMDB ke Redis setiap 1 jam. Aksi ini menyembuhkan anomali alarm Telegram `NOT_IN_CMDB` yang meledak. | `/etc/systemd/system/dcim-itop-redis-sync.timer`<br>`scripts/itop_to_cache_sync.py` |

---

## 3. Eksekusi MT-017: Critical Events & Alerting

| Sub-Task | Aksi Teknis yang Dilakukan | File / Konfigurasi Terkait |
|---|---|---|
| **ST-017-01**<br>Taksonomi Log | Menulis spesifikasi standar arsitektur operasi yang mengklasifikasikan masa hidup data (*Retention Policy*). Menetapkan mana log Operasional (simpan 30 hari) dan Audit (simpan 365 hari). | `docs/operations/log-taxonomy-and-retention-policy.md` |
| **ST-017-02**<br>Alarm Jantung Sistem | Membangun alarm otomatis di Kibana yang bereaksi berdasarkan lonjakan data di *index* tertentu. Jika jumlah pesan error DLQ melebihi batas atau kegagalan *Enrichment API* tinggi, alarm terpicu. | `scripts/setup_kibana_telegram_alerts.py` |
| **ST-017-04**<br>Indeks Keamanan | Menyesuaikan *pipeline* dan Filebeat agar saat ada kejadian kritis keamanan (akses jaringan ilegal, dsb), data di-*tag* dengan `event.category: security` lalu dilempar ke *index* terisolasi untuk proses forensik. | `filebeat.yml`<br>`Kibana Index Patterns` |
| **ST-017-05**<br>Bot Telegram | Mengimplementasikan pengirim pesan Webhook (*Telegram Bot API*). Memodifikasi konektor aksi pada Kibana Alerts agar meneruskan *payload alert* dalam format HTML rapi langsung ke grup infrastruktur internal. | `scripts/setup_kibana_telegram_alerts.py`<br>Kibana Connectors |
