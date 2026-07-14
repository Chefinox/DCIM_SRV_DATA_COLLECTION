# Versioning & Change Management Standard (FIT041)

> [!IMPORTANT]
> **Compliance**: Technical Requirements FIT041 Section 2.1.3
> **Status**: Approved for Production
> **Last Update**: 2026-07-14

## 1. Definisi Standar (Ref: 2.1.3)
Sistem DCIM wajib mengelola siklus hidup workflow dengan kontrol versi yang ketat untuk mencegah kegagalan pipeline akibat perubahan tidak terencana.

| Kode | Persyaratan | Mekanisme Implementasi |
| :--- | :--- | :--- |
| **2.1.3.1** | Penyimpanan Versi Workflow | Integrasi NiFi Registry & Git Version Control. |
| **2.1.3.2** | Metadata Perubahan | Versi, Deskripsi (Changelog), & Timestamp wajib tercatat. |
| **2.1.3.3** | Re-deploy Mandatory | Workflow yang dimodifikasi harus dihentikan dan dijalankan ulang (Re-deploy). |

## 2. Arsitektur Versioning

### A. NiFi Enrichment Flow
Seluruh Process Group di NiFi terhubung ke **NiFi Registry**. Setiap perubahan flow (drag-and-drop processor, update config) akan memicu status *Modified*.
- **Mencatat Versi**: User wajib melakukan `Commit Local Changes` sebelum perubahan dianggap permanen.
- **Log Perubahan**: Dialog komit mewajibkan pengisian deskripsi perubahan utama.

### B. Python Processing Scripts
Skrip normalisasi dan sinkronisasi dikelola melalui repository lokal Git di `/home/infra/dcim_metrics_project/`.
- **Command Audit**:
  ```bash
  git log --oneline --graph --all
  ```

## 3. Alur Kerja Perubahan (Change Management)
Setiap perubahan wajib melalui tahapan berikut:

1.  **Identifikasi**: Menentukan komponen yang akan diubah (misal: penambahan field baru).
2.  **Modifikasi**: Melakukan perubahan pada level staging/draft.
3.  **Documentation (Versioning)**:
    - Melakukan tagging versi pada repository.
    - Mencatat alasan perubahan pada log sistem.
4.  **Re-deployment**:
    - **NiFi**: Restart Process Group / Update Version in Canvas.
    - **Scripts**: `systemctl restart [service_name]`

## 4. Log Perubahan Sistem

| Versi | Waktu (WIB) | Perubahan Utama | Status |
| :--- | :--- | :--- | :--- |
| **v4.4.0** | 2026-07-14 11:00 | **Full v4.4 Active Implementation**: Migrasi penuh polling ke Apache NiFi (termasuk CCTV), penambahan SIEM consumer (`dcim-siem-es-consumer.service`), penggantian arsip batch PostgreSQL menjadi TimescaleDB Streaming Analytics, dan implementasi L14 Event Lineage Tracking. | **Active** |
| **v4.3.0** | 2026-06-25 10:00 | **AI Pipeline Refinement**: Konsolidasi arsitektur pipeline, merapikan dokumentasi. | Superseded |
| **v4.2.0** | 2026-06-22 15:00 | **AI Integration Phase**: Integrasi sistem dengan kapabilitas AI (L14 Data Provider). Penambahan read-only iTop account untuk tim AI. | Superseded |
| **v4.1.0** | 2026-06-16 11:00 | **AI Readiness Phase 1**: Penambahan fungsionalitas L13 Archival dan pengumpulan telemetri CPU Redfish (persiapan model ML). | Superseded |
| **v4.0.0** | 2026-05-26 14:00 | **Migration to iTop CMDB**: Menggantikan Ralph CMDB dengan iTop sebagai *metadata authority* utama. Implementasi 4-Layer Decoupled Architecture dengan Schema Registry & Vault. | Superseded |
| **v3.5.6** | 2026-05-26 05:50 | **CCTV Pipeline & CMDB Integration Fixes**: Bungkus poller metrics dalam format Influx JSON standard untuk mencegah data drop di database. Perbaiki discovery channel NVR untuk mengambil real serial number, model, dan firmware dari proxy channel (untuk offline/unauthorized cameras). Bersihkan 13 placeholder assets dan register ke-31 CCTV dengan real serial number di Ralph CMDB. Perbaiki regex parser check_cctv_status.py. | Superseded |
| **v3.5.5** | 2026-05-21 00:30 | **Commissioning/Decommissioning Automation**: `ralph_cmdb_sync.py` auto-register missing DC assets (`server`, `ups`, `nas`, `network_switch`, `nvr`) from PostgreSQL to Ralph. `dcim-threshold-alerter.py` adds stale-device detection (30m) and indexes alerts to `dcim-alerts`. Logging fixes: Telegraf file log `/var/log/telegraf/telegraf.log`, server inventory symlink `logs/server_inventory.log`. Kafka health check guidance updated: short 3s sampling can false-warn; use offsets + PG/ES counts. | Superseded |
| **v3.5.4** | 2026-05-20 22:00 | **Threshold Alerter**: `dcim-threshold-alerter.service` — automated range-check 6 rules (server temp, UPS battery/load, NAS disk temp, NVR memory, network CPU). Alerts indexed ke `dcim-alerts`. | Superseded |
| **v3.5.3** | 2026-05-20 17:00 | **Kibana Dashboard Fix**: Fix semua panel NVR/UPS/NAS di `dcim-monitoring` dashboard — update field references ke `raw_fields.*`, fix device_type filter, tambah NAS storage panels. Fix pie chart Device Types ke cardinality(hostname). | Superseded |
| **v3.5.2** | 2026-05-20 10:00 | **ES Disk Recovery**: Hapus 11 old indices (05.03-05.14) untuk free disk space. Clear flood stage block. Adjust watermark thresholds (flood=95%, high=90%). Fix NAS volume collection (`dcim_nas_volume` ditambahkan ke Telegraf namepass). | Superseded |
| **v3.5.1** | 2026-05-19 17:00 | **CCTV Registration**: Register 20 missing CCTV ke Ralph Back Office. Buat category CCTV + 5 model Hikvision. Update remarks dengan IP address. | Superseded |
| **v3.5.0** | 2026-05-18 16:48 | **Ralph CMDB Sync Fix (3 Bugs)**: Bug A — Last Sync pakai `datetime.now()`. Bug B — Components baca dari JSONB (bukan tabel relational kosong). Bug C — Proteksi ethernet Management dari prune. Tambah `management_ip`/`management_hostname` ke PATCH. Update server query include JSONB columns. | Superseded |
| **v3.4.2** | 2026-05-18 09:30 | **UPS Sync Fix**: `sync_ups()` fallback ke `raw_fields` JSONB. UPS query pakai `serial_number` bukan `ip`. Fix `update_management_ip()` robust orphan handling. | Merged to v3.5.0 |
| **v3.5.0-pre** | 2026-05-07 17:00 | **Hybrid Stabilization**: Rollback logika pemrosesan ke v3.4 (Proven Logic) namun tetap menggunakan struktur folder v4.0 (src/). | Superseded |
| **v4.0.0** | 2026-05-06 22:55 | **Modular Agentic Architecture**: Restrukturisasi total ke 4-Layer (Tools, Schemas, Skills, Workflows). Decoupling SQL logic dari core processing. | Superseded |
| **v3.2.0** | 2026-05-04 00:05 | Server Deep Sync V7: Pagination fix, Robust Pruning, Ethernet Speed mapping. Crontab aktif `*/5 * * * *`. | Superseded |
| **v3.1.5** | 2026-05-03 23:40 | Server Deep Sync V6: Robust Pruning (delete duplikat via SN comparison). | Superseded |
| **v3.1.4** | 2026-05-03 21:52 | Server Deep Sync V5: Pruning logic awal + Ethernet Speed mapping (SPEED_MAP). | Superseded |
| **v3.1.3** | 2026-05-03 20:08 | Server Deep Sync V4: Disk model dari `Name`, slot dari `PhysicalLocation.PartLocation`, RAM dari `VendorID`. | Superseded |
| **v3.1.2** | 2026-05-03 18:31 | Server Deep Sync V3: Management IP & Management Hostname diupdate via `/api/ipaddresses/` object. | Superseded |
| **v3.1.1** | 2026-05-03 18:02 | Server Deep Sync V2: Hostname dari `Chassis/1 → Location.PostalAddress.Name`. | Superseded |
| **v3.1.0** | 2026-05-03 17:00 | `server_deep_sync.py` pertama kali dibuat. Sinkronisasi komponen server ke Ralph CMDB. | Superseded |
| **v3.0.2** | 2026-04-29 16:35 | Sinkronisasi Hostname Ralph (Hapus prefix FALAH01-) | Active |
| **v3.0.1** | 2026-04-29 15:10 | Perbaikan Polling BMC Redfish (Safe Interval 120s) | Active |
| **v3.0.0** | 2026-04-28 09:00 | Migrasi ke Unified Kafka Pipeline (MT014 Architecture) | Baseline |

## 5. Crontab & Services Aktif

### Cron Jobs & Timers (Terjadwal)

| Timer / Cron | Script | Jadwal |
| :--- | :--- | :--- |
| `dcim-itop-ralph-sync.timer` | `scripts/itop_to_ralph_sync.py` | Harian 02:00 WIB |
| `dcim-data-quality-check.timer` | `scripts/audit_data_quality.py` | Harian 06:00 WIB |
| `dcim-telegram-alerter.timer` | `scripts/dcim_telegram_alerter.py` | Setiap 5 menit |
| `0 0 * * *` | `scripts/manage_partitions.py` | Harian 00:00 WIB |

### Systemd Services (DCIM Pipeline)

| Service | Deskripsi | Status |
| :--- | :--- | :--- |
| `telegraf.service` | Telegraf Producer (Host metrics) | Active |
| `dcim-normalizer.service` | Kafka Normalizer (raw → normalized) | Active |
| `dcim-enrichment-api.service` | FastAPI Enrichment endpoint | Active |
| `dcim-itop-redis-sync.service` | Sync iTop → Redis cache (60s) | Active |
| `dcim-es-consumer.service` | Avro enriched → Elasticsearch | Active |
| `dcim-siem-es-consumer.service` | SIEM alerts → Elasticsearch | Active |
| `dcim-sql-consumer.service` | Avro enriched → PostgreSQL | Active |
| `dcim-itop-unified.service` | iTop CMDB auto-registration | Active |
| `dcim-dlq-consumer.service` | Dead Letter Queue consumer & Lineage | Active |
| `dcim-threshold-alerter.service` | Threshold & stale device alerts | Active |
| `dcim-analytics-bridge.service` | Avro → JSON for Analytics | Active |
| `dcim-analytics-stream-processor.service` | Kafka JSON → TimescaleDB stream | Active |

### Logging Baseline (v3.5.5)

| Component | Log Path | Notes |
| :--- | :--- | :--- |
| Telegraf | `/var/log/telegraf/telegraf.log` | File logging enabled with 10MB rotation, 3 archives |
| Server inventory | `logs/server_inventory.log` | Symlink to `logs/server_inventory_to_pg.log` for compatibility |
| Ralph sync | `logs/ralph_cmdb_sync.log` | Cron output |
| Threshold/stale alerter | `logs/threshold_alerts.log` | Includes stale-device check result |

> [!NOTE]
> Untuk menambah cron job baru, selalu gunakan `crontab -e` dan pastikan script sudah diuji manual terlebih dahulu.

---
**Catatan**: Pelanggaran terhadap siklus re-deploy (mengubah flow aktif tanpa stop/start ulang) dapat menyebabkan data corrupt di Kafka.
