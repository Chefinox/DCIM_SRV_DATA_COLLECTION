# Laporan Pemeliharaan & Integrasi Pipeline Telemetri DCIM

**Tanggal**: 2026-04-30
**Status**: Selesai & Terotomatisasi

## 1. Implementasi Retensi Data (7 Hari)

Untuk menjaga stabilitas performa database PostgreSQL (`dcim_sot`), telah diimplementasikan sistem **Table Partitioning** pada tabel `dcim_events`.

- **Mekanisme**: Tabel dibagi secara fisik menjadi partisi harian (contoh: `dcim_events_y2026_m04_d29`).
- **Otomatisasi**: Skrip `manage_partitions.py` berjalan setiap hari pukul 00:05 melalui Cron Job.
- **Dampak**:
  - Penghapusan data lama (hari ke-8) terjadi secara instan tanpa membebani CPU.
  - Ukuran tabel terjaga di kisaran ~2.5 Juta baris (statis).

## 2. Konfigurasi Interval Pengambilan Metrik

**Sebelum Perubahan:**
Interval awal dikonfigurasi berdasarkan prioritas kategori perangkat.
| Kategori Perangkat           | Interval | Alasan                                      |
| :--------------------------- | :------- | :------------------------------------------ |
| System Metrics (DCIM Server) | 10s      | Monitoring kesehatan platform utama.        |
| UPS, NAS, Network, CCTV      | 60s      | Standar monitoring infrastruktur fisik.     |
| Server (Redfish/BMC)         | 120s     | **Batas Aman**. Menghindari BMC Lockout.    |
| Inventory (Static Data)      | 300s     | Data jarang berubah (SN, Model, Kapasitas). |

**Sesudah Perubahan (Penyeragaman):**
Interval telah diseragamkan menjadi 120s untuk seluruh perangkat infrastruktur (kecuali metrik sistem internal) guna menstabilkan beban I/O.
| Kategori Perangkat                   | Interval | Alasan                                      |
| :----------------------------------- | :------- | :------------------------------------------ |
| System Metrics (DCIM Server)         | 10s      | Monitoring kesehatan platform utama.        |
| Server, UPS, NAS, Network, CCTV, NVR | 120s     | **Batas Aman/Standar Seragam**.             |
| Inventory (Static Data)              | 300s     | Data jarang berubah (SN, Model, Kapasitas). |

## 3. Hasil Pengetesan Interval Server (Redfish)

Dilakukan pengujian bertahap pada unit server Lenovo untuk menentukan batas performa BMC.

| Interval | Durasi   | Hasil                         | Kesimpulan                                  |
| :------- | :------- | :---------------------------- | :------------------------------------------ |
| **120s** | Produksi | 0% Error. Sangat Stabil.      | **Rekomendasi Utama**.                      |
| **60s**  | 1 Jam    | 0% Error. Respon masih cepat. | Batas toleransi maksimal.                   |
| **30s**  | 1 Jam    | **10,000+ Error (401)**.      | **DILARANG**. Menyebabkan pemblokiran akun. |

## 4. Integrasi & Auto-Update Ralph CMDB

Sinkronisasi dari PostgreSQL ke Ralph CMDB kini berjalan secara otomatis dengan aturan integritas data yang ketat.

- **Jadwal**: Setiap hari pukul 00:00 WIB melalui skrip `ralph_sync_agent.py`.
- **Kebijakan Update**:
  - **Identity & Specs (Auto)**: Hostname (cleanup), Firmware, BIOS, CPU, RAM.
  - **Integrity Check**: Jika Serial Number berubah, sistem akan **SKIP** dan mencatat _mismatch_ (tidak menimpa otomatis).
  - **Filter**: Data CCTV `unknown` dan data Server `Unknown Model` otomatis diblokir.
- **Audit**: Kolom _Remarks_ di Ralph sekarang mencatat detail:
  - `Updated: [list_field]` jika ada perubahan.
  - `Tidak ada perubahan terjadi` jika data sudah sinkron.

## 5. Perbaikan Monitoring Elasticsearch

- **Diagnosis**: Masalah "Secure Connection" disebabkan oleh sertifikat self-signed pada port 9200.
- **Solusi**: Disarankan penggunaan Reverse Proxy (Nginx) agar dashboard dapat diakses via port 80/443 standar tanpa kendala TLS di browser.

## 6. Daftar Otomatisasi (Crontab)

```bash
# 1. Manajemen Partisi Database (00:05)
5 0 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/manage_partitions.py

# 2. Sinkronisasi Ralph CMDB (00:00)
0 0 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/ralph_sync_agent.py
```

---

# Laporan Pemeliharaan — 2026-05-04

**Tanggal**: 2026-05-04 (Senin, 22:00–23:15 WIB)  
**Status**: ✅ Selesai & Terverifikasi  
**Dikerjakan oleh**: Antigravity (AI Agent)  
**Referensi dokumen diperbarui**: `docs/19-kafka-pipeline-architecture.md` (v3.4), `docs/31-ai-handover-v3.3.md`, `docs/32-final-architecture-v3.4.md`

---

## Task 1 — Penyelarasan Interval 120s ✅

**Waktu**: 22:29 WIB

Seluruh konfigurasi Telegraf di `/etc/telegraf/telegraf.d/` diselaraskan ulang ke interval **120 detik (2 menit)**. Beberapa file masih memiliki interval lama (60s, 1m, 300s) yang tidak konsisten.

| Config File | Interval Lama | Interval Baru |
| :--- | :--- | :--- |
| `ups-apc.conf` | 60s | **120s** |
| `mikrotik-snmp.conf` | 60s | **120s** |
| `nas-snmp.conf` | 60s | **120s** |
| `hikvision-cctv.conf` | 1m | **2m (120s)** |
| `dcim-unified-inventory.conf` | 300s | **120s** |

**Perintah yang dijalankan:**
```bash
sudo sed -i 's/interval = "60s"/interval = "120s"/g' /etc/telegraf/telegraf.d/*.conf
sudo sed -i 's/interval = "1m"/interval = "2m"/g' /etc/telegraf/telegraf.d/*.conf
sudo sed -i 's/interval = "300s"/interval = "120s"/g' /etc/telegraf/telegraf.d/*.conf
sudo systemctl restart telegraf
```

**Verifikasi**: `telegraf.service` aktif setelah restart. Data masuk ke semua topik Kafka terkonfirmasi.

---

## Task 2 — Auto-Update CMDB Ralph Harian ✅

**Waktu**: 22:31 WIB

Jadwal sinkronisasi diubah menjadi **daily** untuk menjaga integritas data dan menghindari update loop. Sebelumnya, `server_deep_sync.py` tidak ada di crontab (berhenti sejak 09:08 WIB hari ini).

**Crontab user `infra` (final):**
```cron
0 1 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/ralph_cmdb_sync.py >> /home/infra/dcim_metrics_project/logs/ralph_cmdb_sync_cron.log 2>&1
0 2 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/server_deep_sync.py >> /home/infra/dcim_metrics_project/logs/server_deep_sync_cron.log 2>&1
0 3 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/server_redfish_to_pg.py >> /home/infra/dcim_metrics_project/logs/server_redfish_to_pg_cron.log 2>&1
```

| Script | Fungsi | Jadwal |
| :--- | :--- | :--- |
| `ralph_cmdb_sync.py` | Bulk sync telemetri DB → Ralph | Daily 01:00 |
| `server_deep_sync.py` | Deep hardware inventory via Redfish → Ralph | Daily 02:00 |
| `server_redfish_to_pg.py` | Snapshot inventaris → PostgreSQL langsung | Daily 03:00 |

---

## Task 3 — Validasi Field CMDB Ralph yang Bisa Diisi ✅

**Waktu**: Sesi ini (review `server_deep_sync.py` V7 + `docs/29-ralph-auto-update-capabilities.md`)

| Field Ralph | Sumber Data | Update Rule | Keterangan |
| :--- | :--- | :--- | :--- |
| `serial_number` | Redfish / SNMP | **DO_NOT_UPDATE** | Primary key, dilarang overwrite |
| `management_ip` | Konfigurasi | **DO_NOT_UPDATE** | Dikelola manual |
| `hostname` | Redfish `Location.Name` | **AUTO_UPDATE** | Harus valid, bukan string kosong |
| `firmware_version` | Redfish `Managers/1` | **AUTO_UPDATE** | Versi XCC/BMC firmware |
| `bios_version` | Redfish `Systems/1` | **AUTO_UPDATE** | Versi BIOS |
| `processors` (CPU) | Redfish `Systems/1/Processors` | **AUTO_UPDATE** | Model, core count per socket |
| `memory` (RAM) | Redfish `Systems/1/Memory` | **AUTO_UPDATE** | Per DIMM slot, kapasitas + vendor |
| `disks` | Redfish `Systems/1/Storage` | **AUTO_UPDATE + Pruning** | Model, size, SN, slot, firmware disk |
| `ethernets` (NIC) | Redfish `EthernetInterfaces` | **AUTO_UPDATE + Pruning** | Label, MAC address, speed |
| `site` / `rack` | `unified_assets` via Redis | **UPDATE_IF_EMPTY** | Isi jika kosong, jangan timpa data manual |
| `status` / `barcode` | — | **SKIP** | Dikelola manual oleh tim operasional |
| `licenses` / `supports` | — | **SKIP** | Di luar scope otomasi |

> **Guard Rule**: Jika `serial_number` bernilai `Unknown`, `NO_SN`, atau string kosong → **SKIP seluruh record**. Tidak ada data dummy yang masuk ke Ralph.

---

## Task 4 — Validasi Pipeline End-to-End ✅

**Waktu**: 23:10 WIB

### Status Service

| Service | Status |
| :--- | :--- |
| `telegraf.service` | ✅ Running |
| `dcim-normalizer.service` | ✅ Running |
| `dcim-enrichment-api.service` | ✅ Running |
| `dcim-redis-sync.service` | ✅ Running |
| `telegraf-consumer.service` | ✅ Running |
| `dcim-sql-consumer.service` | ✅ Running |

### Enrichment Rate (30 menit terakhir)

| Status | Jumlah |
| :--- | :--- |
| `FULL` | 8.969 |
| `PARTIAL` | 23 |
| **Total** | **8.992** |

**Enrichment rate: > 99.7% FULL** — memenuhi standar AI readiness.

### Perbaikan Tambahan: CCTV/NVR Data Gap

- **Masalah**: Data CCTV/NVR terhenti sejak 04:29 WIB (gap ~18 jam).
- **Root cause**: `scripts/hikvision_poller.py` menggunakan `datetime.utcnow()` (naive timestamp, bisa offset 7 jam dari UTC saat dijalankan di server WIB).
- **Fix**: Diubah ke `datetime.now(datetime.timezone.utc)` — timezone-aware.
- **Verifikasi**: `MAX(event_time)` untuk `cctv` dan `nvr` kembali real-time setelah Telegraf restart.

### Dokumen yang Diperbarui

| Dokumen | Versi | Perubahan |
| :--- | :--- | :--- |
| `docs/19-kafka-pipeline-architecture.md` | v3.0 → **v3.4** | Interval 120s, UPS SNMPv3, section CMDB schedule + field mapping, roadmap Gantt |
| `docs/31-ai-handover-v3.3.md` | Baru | Handover lengkap untuk agent AI berikutnya |
| `docs/32-final-architecture-v3.4.md` | Baru | Diagram arsitektur detail + SOP + field mapping |
