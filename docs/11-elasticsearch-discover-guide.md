# Elasticsearch Discover Guide — Unified Metrics & Filtering

Panduan ini menjelaskan cara mencari dan memfilter metrik perangkat menggunakan standar **8-Points Universal Metrics**.

## 🧱 Universal Tags (Global Filters)

Setiap dokumen di Elasticsearch sekarang memiliki tag berikut yang seragam di semua kategori (UPS, Server, MikroTik, CCTV). Gunakan tag ini untuk pencarian cepat:

| Tag Field | Description | Example Kibana Filter |
| :--- | :--- | :--- |
| `tag.serial_number` | **Primary Key** (Unik per perangkat) | `tag.serial_number : "J901F8KE"` |
| `tag.model` | Model/Tipe Hardware | `tag.model : "30KH"` |
| `tag.hostname` | Nama Identity Perangkat | `tag.hostname : "FIT-Core-SW"` |
| `tag.ip` | Management IP Address | `tag.ip : "10.50.0.5"` |
| `tag.device_type` | Kategori (server, ups, mikrotik, cctv) | `tag.device_type : "server"` |
| `tag.category` | Grup (infrastructure, security) | `tag.category : "infrastructure"` |
| `tag.firmware` | Versi OS/Firmware/BIOS | `tag.firmware : "7.16.2"` |

---

## 🔑 Unified Inventory (Index: `dcim-inventory-*`)

Gunakan index ini untuk melihat **Master List Asset** seluruh infrastruktur dalam satu tabel. Index ini menggabungkan data dari Redfish, SNMP, dan ISAPI.

### Langkah-langkah di Kibana Discover:
1. Pilih Index Pattern: `dcim-inventory-*`.
2. Tambahkan kolom dari sidebar: `tag.serial_number`, `tag.hostname`, `tag.model`, `tag.status`.
3. Filter berdasarkan `tag.category` : `"infrastructure"` untuk melihat aset server/network.

| Field Utama | Deskripsi |
| :--- | :--- |
| `tag.serial_number` | Serial Number dari Vendor (Primary Identifier) |
| `dcim_inventory.manufacturer` | Vendor perangkat (mis: Lenovo, Synology) |
| `dcim_inventory.processor_count` | Jumlah socket prosesor (khusus server) |
| `dcim_inventory.processor_logical_count`| Jumlah core thread prosesor (khusus server) |
| `dcim_inventory.status` | Status Online/Offline/Health |
| `dcim_inventory.power_state` | Status Power (On/Off) |
| `nas_inventory.volumes_total_bytes` | Total kapasitas penyimpanan NAS |

---

## 📈 Platform Specific Metrics

Selain Tag Universal di atas, setiap platform memiliki metrik detilnya sendiri:

### 1. APC UPS (`telegraf-ups-*`)
- **Filter Utama:** `tag.device_type : "ups"`
- **Daftar Field Populer:**
    - `ups_apc.ups_apc.battery_capacity`: Kapasitas baterai (%)
    - `ups_apc.ups_apc.battery_temp`: Suhu baterai (°C)
    - `ups_apc.ups_apc.input_voltage`: Tegangan input (Volt)
    - `ups_apc.ups_apc.output_load`: Beban UPS saat ini (%)
    - `ups_apc.ups_apc.battery_runtime_remain`: Sisa waktu backup (Detik)

### 2. Lenovo Servers (`telegraf-server-*`)
- **Filter Utama:** `tag.device_type : "server"`
- **Daftar Field Populer:**
    - `server_redfish.server_redfish.power_output_watts`: Konsumsi daya (Watts)
    - `server_redfish.server_redfish.reading_celsius`: Nilai suhu sensor (°C)
    - `server_redfish.server_redfish.reading_rpm`: Kecepatan kipas (RPM)
    - `server_redfish.server_redfish.reading_volts`: Tegangan sensor (V)
    - `tag.name`: Nama sensor (Contoh: "AmbientTemp", "CPU1Temp", "Fan1FrontTach")
    - `tag.health`: Status kesehatan komponen (OK, Warning, Critical)

### 3. MikroTik Switches (`telegraf-mikrotik-*`)
- **Filter Utama:** `tag.device_type : "mikrotik"`
- **Daftar Field Populer:**
    - `interface.if_name`: Nama interface (ether1, sfp-sfpplus1, dll)
    - `interface.if_speed`: Kecepatan link (bps)
    - `interface.if_in_octets`: Total data masuk (Bytes)
    - `interface.if_out_octets`: Total data keluar (Bytes)
    - `interface.if_in_errors`: Paket error masuk (Count)
    - `mikrotik.mikrotik.cpu_load`: Beban CPU MikroTik (%)

### 4. Synology NAS (`telegraf-nas-*`)
- **Filter Utama:** `tag.device_type : "nas"`
- **Daftar Field Populer:**
    - `nas_volume.nas_volume.used_bytes`: Kapasitas terpakai per-volume
    - `nas_volume.nas_volume.total_bytes`: Kapasitas total per-volume
    - `nas_volume.nas_volume.status`: Kondisi RAID (normal, degraded)
    - `nas_disk.nas_disk.temp_celsius`: Suhu fisik hard drive (°C)
    - `nas_disk.nas_disk.disk_model`: Model vendor hard drive
    - `nas_inventory.nas_inventory.uptime`: Waktu aktif NAS (Detik/String)

### 5. Hikvision Security (`cctv-metrics-*`)
- **Filter Utama:** `tag.category : "security"`
- **Daftar Field Populer:**
    - `status`: Status Online/Offline kamera
    - `system_status.CPUList.CPU.cpuUtilization`: Penggunaan CPU NVR (%)
    - `system_status.MemoryList.Memory.memoryUsage`: Penggunaan RAM NVR (%)
    - `storage.hddList.hdd.freeSpace`: Sisa HDD rekaman (MB)
    - `storage.hddList.hdd.hddStatus`: Kondisi kesehatan HDD NVR
    - `device_info.firmwareVersion`: Versi firmware kamera

---

## 💡 Tips Cepat
- **Refresh Field List:** Jika tag `u_` atau tag baru tidak muncul, buka *Stack Management* -> *Index Patterns* lalu klik **Refresh** pada index pattern terkait.
- **Dumping JSON:** Klik tombol ekspansi (>) di sebelah baris data untuk melihat struktur JSON lengkap dan memastikan semua tag universal (`tag.serial_number`, dll) terisi.
