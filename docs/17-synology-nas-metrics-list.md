# 17 - Synology NAS Metrics List

Dokumen ini merinci semua metrik yang dikumpulkan dari Synology NAS menggunakan polling API Synology DSM (REST).

## 1. Unified Inventory Metrics (`nas_inventory`)
Metrik ini distandarisasi untuk masuk ke index `dcim-inventory-*` dan `telegraf-nas-*`.

| Metric Field | Description | Unit |
| :--- | :--- | :--- |
| `model` | Model hardware NAS (mis: DS220+) | String |
| `serial_number` | Serial Number unik perangkat | String (Tag) |
| `hostname` | Nama host perangkat | String (Tag) |
| `firmware` | Versi DSM (mis: DSM 7.2-64570) | String |
| `manufacturer` | Vendor perangkat (Synology) | String |
| `cpu_vendor` | Vendor CPU (INTEL/AMD) | String |
| `cpu_series` | Seri CPU (mis: J4025) | String |
| `cpu_cores` | Jumlah core CPU | Integer |
| `ram_mb` | Total kapasitas RAM | MB |
| `temp_celsius` | Suhu sistem saat ini | Celsius |
| `uptime` | Waktu aktif perangkat | String |
| `status` | Status kesehatan sistem (Online/Offline/Normal) | String |
| `cpu_user_pct` | Utilisasi CPU (User) | Percentage |
| `cpu_sys_pct` | Utilisasi CPU (System) | Percentage |
| `mem_usage_pct` | Utilisasi RAM | Percentage |
| `net_rx_kbps` | Kecepatan Receive Jaringan | KBps |
| `net_tx_kbps` | Kecepatan Transmit Jaringan | KBps |
| `volumes_total_bytes`| Total kapasitas penyimpanan semua volume | Bytes |
| `volumes_used_bytes` | Kapasitas penyimpanan terpakai | Bytes |
| `disk_count` | Jumlah physical disk yang terdeteksi | Integer |

## 2. Storage Volume Metrics (`nas_volume`)
Metrik detail per volume (RAID/Pool).

| Metric Field | Description | Unit |
| :--- | :--- | :--- |
| `volume_id` | Identifier volume (mis: volume_1) | String (Tag) |
| `fs_type` | Tipe File System (btrfs/ext4) | String (Tag) |
| `raid_type` | Tipe RAID (raid_0, raid_1, shr, dll) | String (Tag) |
| `total_bytes` | Total kapasitas volume | Bytes |
| `used_bytes` | Kapasitas terpakai | Bytes |
| `free_bytes` | Kapasitas tersisa | Bytes |
| `status` | Status kesehatan volume (normal/degraded) | String |

## 3. Physical Disk Metrics (`nas_disk`)
Metrik detail per physical drive.

| Metric Field | Description | Unit |
| :--- | :--- | :--- |
| `disk_id` | Identifier disk (mis: sata1) | String (Tag) |
| `disk_model` | Model drive (mis: ST4000VN006) | String (Tag) |
| `temp_celsius` | Suhu drive saat ini | Celsius |
| `status` | Status kesehatan drive (normal/failing) | String |
