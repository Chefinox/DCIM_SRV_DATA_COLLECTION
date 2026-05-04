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

| Kategori | Field (Manual List) | Status | Implementasi Skrip (V7) | Sumber Redfish |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Diambil dari `Location -> Name` | `Chassis/1` -> `Location.PostalAddress.Name` |
| | Firmware version | 🟢 YA | Diupdate aktual | `Managers/1` -> `FirmwareVersion` |
| | Bios version | 🟢 YA | Diupdate aktual | `Systems/1` -> `BiosVersion` |
| | Management IP | 🟢 YA | Update via objek `IPAddress` tertaut | IP Polling Skrip (10.50.0.x) |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname `Chassis/1` |
| **2. Components** | **Ethernets (NIC):** | | | |
| | - Mac address | 🟢 YA | Update aktual | `Systems/1/EthernetInterfaces` -> `MACAddress` |
| | - Model name | 🟢 YA | Mencoba pemetaan nama adapter | `NetworkAdapters` atau `Description` |
| | - Label | 🟢 YA | Dipakai sbg key (NIC1, NIC2) | `Id` |
| | - Speed | 🟢 YA | Dipetakan ke angka Gbps Ralph | `SpeedMbps` (Dipetakan) |
| | **Memory (RAM):** | | **(Hanya yang Terpasang)** | |
| | - Model name | 🟢 YA | Merek vendor (mis: Samsung) | `Systems/1/Memory` -> `VendorID` |
| | - Size (MiB) | 🟢 YA | Diupdate aktual | `CapacityMiB` |
| | - Speed (MHz) | 🟢 YA | Diupdate aktual | `OperatingSpeedMhz` |
| | **Processors:** | | **(Hanya yang Terpasang)** | |
| | - Model name | 🟢 YA | Diupdate aktual | `Systems/1/Processors` -> `Model` |
| | - Speed (MHz) | 🟢 YA | Diupdate aktual | `MaxSpeedMHz` |
| | - Physical cores | 🟢 YA | Diupdate aktual | `TotalCores` |
| | - Logical cores | 🟢 YA | Diupdate aktual | `TotalThreads` |
| | **Disks:** | | **(Hanya yang Terpasang)** | |
| | - Model name | 🟢 YA | Nama deskriptif disk | `Systems/1/Storage/...` -> `Name` |
| | - Size (GiB) | 🟢 YA | Diupdate aktual | `CapacityBytes` |
| | - Serial number | 🟢 YA | Diupdate aktual | `SerialNumber` |
| | - Slot number | 🟢 YA | Angka slot fisik | `PhysicalLocation.PartLocation.LocationOrdinalValue` |
| | - Firmware version | 🟢 YA | Diupdate aktual | `Revision` |
| | **Fibre Cards:** | 🔴 TIDAK | Belum diimplementasi | Tunggu server dengan FC |
| **3. Network** | **Ethernets:** | | | |
| | - Hostname | 🟢 YA | Terisi untuk NIC Management | IPAddress linked ke NIC Management |
| | - IP address | 🟡 N/A | Kosong untuk data NIC | Redfish Data NIC tidak expose IP |
| | - MAC address | 🟢 YA | Update aktual | `MACAddress` |
| | - Label | 🟢 YA | Dipakai sbg key | `Id` |

---

## Aturan Bisnis Khusus
- **Update Conditional Jaringan:** IP Management selalu diprioritaskan, namun untuk data NIC, IP dan Hostname sengaja dilewati karena arsitektur OS yang mengatur IP (bukan perangkat fisik secara langsung). Skrip telah dirancang untuk mencatat status Management Network ke dalam objek khusus `IPAddress(is_management=True)` di struktur Ralph.

---

## Tabel Komparasi Auto-Update (UPS)

| Kategori | Field (Manual List) | Status | Rencana Implementasi | Sumber SNMP (192.168.100.140) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Update aktual | `.1.3.6.1.2.1.1.5.0` (`sysName`) |
| | Firmware version | 🟢 YA | Update aktual | `.1.3.6.1.2.1.33.1.1.3.0` (`upsFirmware`) |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | IP Polling Skrip (192.168.100.140) |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Dipakai sbg key pencarian | `.1.3.6.1.2.1.33.1.1.1.0` (`upsSerial`) |
| | Model name | 🟢 YA | Sinkronisasi model | `.1.3.6.1.4.1.935.1.1.1.1.1.1.0` (`upsModel`) |
| **2. Components** | **Ethernets / Memory / CPU / Disks** | 🔴 N/A | Tidak relevan/Tidak tersedia untuk UPS | N/A |
| **3. Network** | **Ethernets (Management):** | | | |
| | - MAC address | 🔴 TIDAK | Saat ini tidak ada di config Telegraf | Butuh `ifPhysAddress` |
| | - Label | 🟡 YA | Set default ke `Management` | N/A |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | IP Polling Skrip |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | Sama dengan Hostname |

---

## Tabel Komparasi Auto-Update (NAS & Network Switch)

Kedua kategori ini sudah memiliki data inventaris dasar yang memadai di tabel `dcim_events` via Telegraf untuk dilakukan auto-update ke Ralph.

| Kategori | Field (Manual List) | Status | Rencana Implementasi (PostgreSQL -> Ralph) | Sumber PostgreSQL (`dcim_events`) |
| :--- | :--- | :---: | :--- | :--- |
| **1. Basic Info** | Hostname | 🟢 YA | Update aktual | `hostname` |
| | Firmware version | 🟢 YA | Update aktual | `raw_tags->>'firmware'` (DSM/RouterOS) |
| | Management ip | 🟢 YA | Update via objek `IPAddress` tertaut | `ip` |
| | Management hostname | 🟢 YA | Update via objek `IPAddress` tertaut | Sama dengan Hostname |
| | Serial number | 🟢 YA | Dipakai sbg key pencarian | `serial_number` |
| | Model name | 🟢 YA | Sinkronisasi model | `model` |
| | Manufacturer | 🟢 YA | Sinkronisasi vendor (Synology/Mikrotik) | `manufacturer` |
| **2. Components** | **Disks (NAS Khusus)** | 🟡 N/A | Telegraf saat ini tidak menyimpan SN tiap disk secara unik di tabel | - |
| | **Ethernets / Memory / CPU** | 🔴 N/A | Saat ini tidak ditarik mendetail per-komponen | - |
| **3. Network** | **Ethernets (Management):** | | | |
| | - IP address | 🟢 YA | Disinkronisasikan sebagai IP Management | `ip` |
| | - Hostname | 🟢 YA | Disinkronisasikan sebagai Hostname Management | `hostname` |
