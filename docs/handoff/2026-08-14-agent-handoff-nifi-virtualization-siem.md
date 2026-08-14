# Handoff Report: Block 2 Data Ingestion & NiFi Troubleshooting

**Date:** 2026-08-14  
**Author:** AI Assistant
**Target:** Next Assigned Agent / Infra Engineer

## 1. Summary of Work Done
Kami telah melakukan investigasi mendalam dan implementasi penutupan gap (Gap Closure) untuk komponen **Block 2 (Data Ingestion)** berdasarkan komparasi antara referensi desain (`dcim-wiki`) dengan implementasi arsitektur `v4.7`.

Pekerjaan yang telah diselesaikan (ST-391, ST-392, ST-394):
- **Virtualization Collector (ST-391):** Dibuatkan Mock API Proxmox (`proxmox_fixture_adapter.py`) dan script Python poller khusus NiFi (`virtualization_poller_nifi.py`). Di sisi NiFi UI, `ExecuteProcess` berhasil dijalankan dan diintegrasikan dengan `PublishKafka_2_6` menuju topic `dcim.raw.virtualization`.
- **ITSM Connectors (ST-392):** Dibuatkan Mock API ServiceNow & Jira (`itsm_fixture_api.py`) beserta script Python konektor (`servicenow.py`, `jira.py`). Script telah lulus Unit Test.
- **End-to-End Load Testing (ST-394):** Dibuatkan native Kafka Locust client (`kafka_locustfile.py`). Hasil uji coba sukses besar mencetak throughput `>3000 EPS` (Target: 430 EPS) dengan latency p99 `0ms`, dan Validation Engine terbukti membuang invalid payloads ke DLQ.
- **Task Tracker (ST-393):** S3/MinIO Archiving telah ditandai sebagai `On-Hold` di `IF-DCIM_Project_Internal-FIT041-20260118 - Tasks Tracker (6).tsv` karena ketiadaan instruktur Cloud/Object Storage.

Semua dokumen, scripts, dan perubahan pada *Task Tracker* telah di-commit ke Git.

## 2. Solved Technical Issues (Critical)
Berikut adalah daftar permasalahan teknis yang telah diselesaikan:

- **ModuleNotFoundError ('src' / 'yaml') pada Poller NiFi:**
  NiFi mengeksekusi skrip python dari directory `/opt/nifi/nifi-current/scripts/`. Ini menyebabkan *Relative Import* gagal. 
  **Fix:** `docker-compose.yml` telah diubah dengan melakukan volume mount folder `src` dan `configs` ke dalam NiFi. Kami juga menambahkan `sys.path.append("/opt/nifi/nifi-current")` secara dinamis ke seluruh skrip `*poller*.py` menggunakan *bash loop*.
- **Kafka Transaction Timeout (PublishKafka):**
  Prosesor `PublishKafka` melempar `TimeoutException` karena Kafka belum selesai meregistrasikan ID Transaksi. 
  **Fix:** Problem ini sembuh dengan sendirinya setelah Kafka selesai melakukan propagasi cluster. Konfigurasi `Use Transactions: true` tetap digunakan dan telah berjalan stabil.
- **Indentation Error di `nas_poller.py`:**
  File sempat *corrupted* karena command *sed*. 
  **Fix:** File telah ditulis ulang dengan indentasi try-except yang sempurna dan `sys.path.append` yang valid.

## 3. Pending / Active Issues (To-Do for Next Agent)
- **Security SIEM Ingestion (JoltTransformJSON Parsing Error):**
  Prosesor `JoltTransformJSON` di NiFi UI (Group: Security SIEM Ingestion) sedang mengalami kegagalan/error berulang: `Unrecognized token 'pam_unix'`.
  **Context:** Ini terjadi karena `ListenSyslog` NiFi menangkap plain-text log dari Wazuh (cth: `pam_unix session opened`), namun Jolt mengharuskan payload dalam format JSON murni.
  **Suggested Action Plan untuk Engineer/Agent di UI:**
  Engineer lokal *tidak ingin* menghapus `JoltTransformJSON` peninggalan versi lama. Solusi terbaik adalah menambahkan prosesor `RouteOnContent` sebelum Jolt. 
  Gunakan RegEx: `^\s*\{.*` untuk mengidentifikasi JSON. 
  Rute data JSON (`is_json`) arahkan ke Jolt. Rute plain-text (`unmatched`) by-pass langsung ke `PublishKafka` (topic: `dcim.siem.alerts`).

## 4. Environment Variables & Paths
- NiFi Scripts Directory: `/opt/nifi/nifi-current/scripts/`
- Python Executable untuk NiFi: `/opt/dcim-python3.12-env/bin/python`
- Kafka Brokers: `10.70.0.56:9092,10.70.0.56:9093,10.70.0.56:9094`
- Task Tracker: `docs/standar_dcim/IF-DCIM_Project_Internal-FIT041-20260118 - Tasks Tracker (6).tsv`
