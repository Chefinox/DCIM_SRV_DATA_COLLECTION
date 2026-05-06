# Kapabilitas Auto-Update CMDB Ralph (Unified Pipeline)

Dokumen ini memetakan daftar _field_ manual yang diinginkan oleh USER terhadap kemampuan pengumpulan data aktual dari perangkat fisik (Server dan UPS). 

**Pembaruan Arsitektur (v3.3.0):**
Sinkronisasi CMDB tidak lagi menggunakan metode *direct polling* dari skrip ke perangkat (seperti `server_deep_sync.py` V7). Saat ini, arsitektur menggunakan **PostgreSQL (`dcim_events`) sebagai jembatan tunggal (Single Source of Truth)**. Seluruh data di-*polling* oleh agen (`server_redfish_to_pg.py` dan Telegraf), disimpan ke PostgreSQL, lalu disinkronkan ke Ralph melalui skrip terpadu `ralph_cmdb_sync.py`.

---

## ⚠️ Protokol Penting Implementasi (BACA INI DULU)

Untuk AI Agent berikutnya atau pengembang skrip:
1. **Dilarang Mencatat Slot Kosong:** Skrip **WAJIB** melakukan filter. Hanya komponen yang terpasang fisik (Populated) yang dikirimkan ke Ralph (cek `CapacityMiB > 0` dan `Status.State != "Absent"`).
2. **Serial Number sebagai Primary Key:** SN digunakan sebagai kunci utama pencocokan komponen untuk mencegah penimpaan (overwrite) data yang salah.
3. **Robust Pruning (Pembersihan Otomatis):** Skrip secara aktif membandingkan data inventaris di PostgreSQL dengan data di Ralph. Jika ada data duplikat atau komponen lama (yang sudah dicabut), skrip akan **menghapusnya** dari Ralph.
4. **Penanganan Paginasi API Ralph:** API Ralph secara default hanya mengembalikan 10 entitas. Gunakan helper fungsi dengan `limit=200` untuk mengambil semua halaman API (seperti fungsi `ralph_get_all()` di `ralph_cmdb_sync.py`) agar *pruning* berjalan akurat pada server dengan banyak disk.
5. **Pembersihan Custom Field Usang:** Field statis seperti `power_consumption` dan `device_temperature` tidak perlu disinkronkan ke CMDB, karena metrik real-time tersebut sekarang dikelola eksklusif di Elasticsearch/Kibana.

---

## Tabel Komparasi Auto-Update (Server)

| Kategori | Field (Manual List) | Status | Implementasi (PostgreSQL -> Ralph) | Sumber PostgreSQL (`dcim_events`) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Diambil dari kolom system name | `srv_system_name` / `hostname` |
| | Firmware version | 🟢 YA | Diupdate aktual | `srv_firmware` |
| | Bios version | 🟢 YA | Diupdate aktual | `srv_bios_version` |
| | Management IP | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| **2. Components** | **Ethernets (NIC):** | | | Array JSONB: `srv_nic_components` |
| | - Mac address | 🟢 YA | Update aktual | `mac` di dalam JSONB |
| | - Model name | 🟢 YA | Mencoba pemetaan nama adapter | `model_name` di dalam JSONB |
| | - Label | 🟢 YA | Dipakai sbg key (NIC1, NIC2) | `label` di dalam JSONB |
| | - Speed | 🟢 YA | Dipetakan ke angka Gbps Ralph | `speed` di dalam JSONB |
| | **Memory (RAM):** | | **(Hanya yang Terpasang)** | Array JSONB: `srv_memory_components` |
| | - Model name | 🟢 YA | Merek vendor (mis: Samsung) | `model_name` di dalam JSONB |
| | - Size (MiB) | 🟢 YA | Diupdate aktual | `size` di dalam JSONB |
| | - Speed (MHz) | 🟢 YA | Diupdate aktual | `speed` di dalam JSONB |
| | **Processors:** | | **(Hanya yang Terpasang)** | Array JSONB: `srv_cpu_components` |
| | - Model name | 🟢 YA | Diupdate aktual | `model_name` di dalam JSONB |
| | - Speed (MHz) | 🟢 YA | Diupdate aktual | `speed` di dalam JSONB |
| | - Physical cores | 🟢 YA | Diupdate aktual | `cores` di dalam JSONB |
| | - Logical cores | 🟢 YA | Diupdate aktual | `threads` di dalam JSONB |
| | **Disks:** | | **(Hanya yang Terpasang)** | Array JSONB: `srv_disk_components` |
| | - Model name | 🟢 YA | Nama deskriptif disk | `model_name` di dalam JSONB |
| | - Size (GiB) | 🟢 YA | Diupdate aktual | `size` di dalam JSONB |
| | - Serial number | 🟢 YA | Diupdate aktual | `serial_number` di dalam JSONB |
| | - Slot number | 🟢 YA | Angka slot fisik | `slot` di dalam JSONB |
| | - Firmware version | 🟢 YA | Diupdate aktual | `firmware_version` di dalam JSONB |
| | **Fibre Cards:** | 🔴 TIDAK | Belum diimplementasi | Tunggu server dengan FC |
| **3. Network** | **Ethernets:** | | | |
| | - Hostname | 🟢 YA | Terisi untuk NIC Management | `hostname` |
| | - IP address | 🟡 N/A | Kosong untuk data NIC | (Tidak disimpan di Postgres array) |
| | - MAC address | 🟢 YA | Update aktual | `mac` dari JSONB NIC |
| | - Label | 🟢 YA | Dipakai sbg key | `label` dari JSONB NIC |

---

## Aturan Bisnis Khusus
- **Update Conditional Jaringan:** IP Management selalu diprioritaskan, namun untuk data NIC, IP dan Hostname sengaja dilewati karena arsitektur OS yang mengatur IP (bukan perangkat fisik secara langsung). Skrip telah dirancang untuk mencatat status Management Network ke dalam objek khusus `IPAddress(is_management=True)` di struktur Ralph.

---

## Tabel Komparasi Auto-Update (UPS)

| Kategori | Field (Manual List) | Status | Implementasi (PostgreSQL -> Ralph) | Sumber PostgreSQL (`dcim_events`) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Update aktual | `hostname` |
| | Firmware version | 🟢 YA | Update aktual | `ups_firmware` |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Dipakai sbg key pencarian | `ups_serial_snmp` / `serial_number` |
| | Model name | 🟢 YA | Sinkronisasi model (dicatat di Remarks) | `ups_model_snmp` |
| **2. Components** | **Ethernets / Memory / CPU / Disks** | 🔴 N/A | Tidak relevan/Tidak tersedia untuk UPS | (Tidak tersedia) |
| **3. Network** | **Ethernets (Management):** | | | |
| | - MAC address | 🔴 TIDAK | Saat ini tidak ditarik oleh Telegraf | (Tidak tersedia) |
| | - Label | 🟡 YA | Set default ke `Management` | (Hardcoded) |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | `ip` |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | `hostname` |

---

## Tabel Komparasi Auto-Update (NAS)

Data inventaris NAS ditarik oleh Telegraf menggunakan protokol SNMP (Synology MIB) dan disimpan di PostgreSQL.

| Kategori | Field (Manual List) | Status | Implementasi (PostgreSQL -> Ralph) | Sumber PostgreSQL (`dcim_events`) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Update aktual | `hostname` |
| | Firmware version | 🟢 YA | Update aktual | `raw_tags->>'firmware'` (Contoh: DSM 7.2) |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Dipakai sbg key pencarian | `serial_number` |
| | Model name | 🟢 YA | Sinkronisasi model (dicatat di Remarks) | `model` |
| | Manufacturer | 🟢 YA | Sinkronisasi vendor | `manufacturer` |
| **2. Components** | **Disks / RAM / CPU** | 🟡 N/A | Telegraf saat ini tidak menyimpan SN tiap disk secara unik | (Tidak tersedia) |
| **3. Network** | **Ethernets (Management):** | | | |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | `ip` |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | `hostname` |

---

## Tabel Komparasi Auto-Update (Network Switch)

Data inventaris Network Switch (MikroTik) ditarik oleh Telegraf dan disesuaikan di PostgreSQL.

| Kategori | Field (Manual List) | Status | Implementasi (PostgreSQL -> Ralph) | Sumber PostgreSQL (`dcim_events`) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Update aktual | `hostname` |
| | Firmware version | 🟢 YA | Update aktual | `raw_tags->>'firmware'` (Contoh: 7.14.1) |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Dipakai sbg key pencarian | `serial_number` |
| | Model name | 🟢 YA | Sinkronisasi model (dicatat di Remarks) | `model` |
| | Manufacturer | 🟢 YA | Sinkronisasi vendor | `manufacturer` |
| **2. Components** | **Ethernets / SFP** | 🔴 N/A | Saat ini tidak ditarik mendetail per-port interface di inventaris | (Tidak tersedia) |
| **3. Network** | **Ethernets (Management):** | | | |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | `ip` |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | `hostname` |

---

## Tabel Komparasi Auto-Update (CCTV & NVR)

Data inventaris CCTV dan NVR (umumnya Hikvision) ditarik menggunakan poller kustom (ISAPI/HTTP) dan disimpan di PostgreSQL. CCTV/NVR dikategorikan sebagai perangkat *endpoint* ringan yang disinkronkan menggunakan logika yang serupa dengan NAS/Switch.

| Kategori | Field (Manual List) | Status | Implementasi (PostgreSQL -> Ralph) | Sumber PostgreSQL (`dcim_events`) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Update aktual | `hostname` |
| | Firmware version | 🟢 YA | Update aktual | `raw_tags->>'firmware'` (Contoh: V5.5.114) |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Dipakai sbg key pencarian | `serial_number` |
| | Model name | 🟡 YA | Dicatat di Remarks jika tidak Unknown | `model` |
| | Manufacturer | 🟡 YA | Dicatat di Remarks jika tidak Unknown | `manufacturer` |
| **2. Components** | **Ethernets / Disks / RAM** | 🔴 N/A | Tidak ditarik komponen internalnya oleh ISAPI | (Tidak tersedia) |
| **3. Network** | **Ethernets (Management):** | | | |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | `ip` |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | `hostname` |

---
