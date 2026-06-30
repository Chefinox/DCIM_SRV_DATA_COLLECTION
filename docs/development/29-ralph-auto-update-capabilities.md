# Kapabilitas Auto-Update CMDB Ralph (Unified Pipeline)

> **Last Updated**: 2026-05-21  
> **Version**: v3.5.5  
> **Script**: `scripts/ralph_cmdb_sync.py` (cron 02:00 WIB)

Dokumen ini memetakan daftar _field_ manual yang diinginkan oleh USER terhadap kemampuan pengumpulan data aktual dari perangkat fisik (Server, UPS, NAS, Network Switch, NVR, CCTV). 

**Pembaruan Arsitektur (v3.5.0 — 2026-05-18):**
Sinkronisasi CMDB menggunakan **PostgreSQL (`dcim_events`) sebagai Single Source of Truth**. Data di-*polling* oleh Telegraf/Redfish, disimpan ke PostgreSQL (kolom JSONB), lalu disinkronkan ke Ralph melalui skrip terpadu `ralph_cmdb_sync.py`.

**Fix terbaru (v3.5.0):**
- Bug A: Last Sync sekarang pakai `datetime.now()` (bukan `event_time`)
- Bug B: Server components dibaca dari JSONB columns (`srv_cpu_components`, `srv_memory_components`, `srv_disk_components`, `raw_tags->'nics'`) — bukan dari tabel relational yang kosong
- Bug C: Ethernet "Management" dilindungi dari prune di `sync_server_ethernets()`
- Remarks format include IP untuk semua device types

**Update terbaru (v3.5.5 — 2026-05-21):**
- Auto-register DC assets baru jika serial number sudah muncul di PostgreSQL tetapi belum ada di Ralph.
- Device type yang didukung auto-register: `server`, `ups`, `nas`, `network_switch`, `nvr`.
- CCTV sengaja tidak auto-register lewat flow ini karena memakai Back Office Asset dan script terpisah `scripts/register_cctv_to_ralph.py`.
- Default rack auto-register: `DEFAULT_RACK = 3`.
- Function utama: `auto_register_dc_asset(sn, hostname, device_type, model_name=None, ip=None)`.

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
| | Firmware version | 🟢 YA | Diupdate aktual dari snapshot inventory Redfish | `metric_name='inventory_snapshot'`, `srv_firmware` |
| | Bios version | 🟢 YA | Diupdate aktual dari snapshot inventory Redfish | `metric_name='inventory_snapshot'`, `srv_bios_version` |
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
| | - CPU count | 🟢 YA | Dihitung dari jumlah item processor snapshot | `jsonb_array_length(srv_cpu_components)` |
| | - Total memory | 🟢 YA | Dihitung dari total module RAM snapshot | `SUM((srv_memory_components->>'size')::int)` |
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

## Auto-Register DC Assets (v3.5.5)

Jika asset tidak ditemukan berdasarkan serial number, `ralph_cmdb_sync.py` akan mencoba membuat DC asset baru sebelum melanjutkan update metadata.

| Device Type | Ralph Model ID | Asset Type | Default Rack | Status |
| :--- | ---: | :--- | ---: | :---: |
| `server` | 26 | Data Center Asset | 3 | ✅ Active |
| `ups` | 34 | Data Center Asset | 3 | ✅ Active |
| `nas` | 16 | Data Center Asset | 3 | ✅ Active |
| `network_switch` | 6 | Data Center Asset | 3 | ✅ Active |
| `nvr` | 18 | Data Center Asset | 3 | ✅ Active |
| `cctv` | N/A | Back Office Asset | N/A | ⚠️ Separate flow |

Minimal payload auto-register:

- `sn`
- `hostname`
- `model`
- `rack`
- `remarks` with IP/source/timestamp

> [!CAUTION]
> Jangan test auto-register dengan serial dummy di production Ralph tanpa approval. Tunggu device nyata atau gunakan staging.

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
| | - MAC address | 🔴 TIDAK | Batasan SNMP (Tidak disediakan oleh agen UPS) | (Tidak tersedia) |
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
| | Firmware version | 🟢 YA | Otomatis dari `raw_tags->>'firmware'` | `firmware` |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Key pencarian (Data Center/Back Office) | `serial_number` |
| | Model name | 🟢 YA | Otomatis dari `raw_tags->>'model'` | `model` |
| | Manufacturer | 🟢 YA | Dideduksi dari Model/Remarks | `manufacturer` |
| **2. Components** | **Ethernets / Disks / RAM** | 🔴 N/A | Tidak ditarik komponen internalnya oleh ISAPI | (Tidak tersedia) |
| **3. Network** | **Ethernets (Management):** | | | |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | `ip` |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | `hostname` |

---

## CCTV Back Office Registration (v3.5.1 — 2026-05-19)

20 CCTV yang hilang dari Ralph (akibat migrasi gagal) telah di-register ulang menggunakan `scripts/register_cctv_to_ralph.py`:
- **Asset Type**: Back Office (bukan Data Center)
- **Category**: CCTV (id=22, dibuat otomatis)
- **Models**: DS-2CD1021-I, DS-2CD1043G0E-I, DS-2CD1121-I, DS-2CD1143G0E-I, DS-2CD3121G0-I
- **Property Of**: Facility Management Department
- **Region/Warehouse**: Headquarters / FIT-Head-Office
- **Important (v3.5.5)**: CCTV tidak ikut auto-register DC asset karena bukan rack-mounted Data Center Asset.

## Format Remarks per Device Type (v3.5.0+)

| Device Type | Asset Type | Format Remarks |
| :--- | :--- | :--- |
| Server | DC Asset | `Last Sync: 2026-05-20 02:00:05` |
| UPS | DC Asset | `Model: 30KH \| Last Sync: 2026-05-20 02:00:05` |
| NAS | DC Asset | `IP: 10.50.0.106 \| Manufacturer: Synology \| Model: RS2423RP \| Last Sync: 2026-05-20 02:00:05` |
| Network Switch | DC Asset | `IP: 172.16.35.1 \| Manufacturer: MikroTik \| Model: CCR2004 \| Last Sync: 2026-05-20 02:00:05` |
| NVR | DC Asset | `IP: 192.168.1.254 \| Manufacturer: Hikvision \| Model: DS-7732NXI-K4 \| Last Sync: 2026-05-20 02:00:05` |
| CCTV | Back Office | `IP: 192.168.1.x \| Model: DS-2CD1143G0E-I \| Location: Meeting_Lt.1` |

## Cron Schedule

| Schedule | Script | Fungsi |
| :--- | :--- | :--- |
| `0 1 * * *` | `scripts/server_inventory_to_pg.py` | Collect server inventory via Redfish → PostgreSQL |
| `0 2 * * *` | `scripts/ralph_cmdb_sync.py` | Sync PostgreSQL → Ralph CMDB; auto-register missing DC assets |
