# Elasticsearch Discover Guide — Unified Metrics & Filtering (v3.4)

Panduan ini menjelaskan cara mencari, memfilter, dan memahami struktur metrik perangkat di Kibana Discover pada arsitektur **Unified Pipeline (Kafka -> Telegraf -> Elasticsearch)**.

## 🧱 1. Index Pattern Utama: `dcim-metrics-unified-*`

Seluruh data telemetri dari berbagai jenis perangkat keras kini digabungkan ke dalam **satu index pattern tunggal**. Anda tidak perlu lagi berpindah-pindah antar index (`telegraf-server-*`, `telegraf-mikrotik-*`, dll).

Untuk memulai pencarian:
1. Buka halaman **Discover** di Kibana.
2. Pastikan Index Pattern yang dipilih adalah **`dcim-metrics-unified-*`**.

---

## 🔍 2. Universal Tags (Global Filters)

Setiap dokumen di Elasticsearch dilengkapi dengan objek `tag` yang seragam di semua kategori perangkat (Server, UPS, Network, NAS, CCTV). Field ini adalah hasil pengayaan (*enrichment*) dari CMDB Ralph.

Tambahkan field berikut sebagai **kolom** di Discover atau gunakan sebagai filter utama:

| Field Discover | Deskripsi | Contoh Filter KQL |
| :--- | :--- | :--- |
| `tag.device_type` | Kategori Perangkat | `tag.device_type: "network_switch"` |
| `tag.hostname` | Nama Identitas Perangkat | `tag.hostname: "FIT-Core-SW"` |
| `tag.ip` | Management IP Address | `tag.ip: "172.16.35.2"` |
| `tag.serial_number` | Primary Key / SN dari Vendor | `tag.serial_number: "HFH09B9A7A3"` |
| `tag.model` | Model Perangkat Fisik | `tag.model: "CCR2004-16G-2S+"` |
| `tag.manufacturer` | Nama Vendor | `tag.manufacturer: "MikroTik"` |
| `tag.site` | Lokasi Geografis (Site) | `tag.site: "Local Instance"` |
| `tag.room_name` | Nama Ruangan | `tag.room_name: "FIT-HeadOffice Room"` |
| `tag.rack_name` | Nama Rak (Lokasi Fisik) | `tag.rack_name: "Rack Server 1"` |
| `tag.environment` | Status Environment (Production/Staging) | `tag.environment: "Production"` |
| `tag.business_unit` | Unit/Departemen Pemilik | `tag.business_unit: "IT Infrastructure Departement"` |
| `tag.enrichment_status` | Status sinkronisasi dengan CMDB | `tag.enrichment_status: "FULL"` |
| `measurement_name` | Objek nama metrik | `measurement_name: "interface"` |

---

## 📈 3. Platform Specific Metrics (Raw Fields)

Nilai metrik asli (*raw metric*) yang diambil dari perangkat fisik akan dibungkus ke dalam sebuah objek yang sesuai dengan nama `measurement_name`. **Prefix `raw_fields_` telah dihapus** agar *backward-compatible* dengan visualisasi *dashboard* Kibana bawaan.

Berikut adalah panduan field khusus untuk setiap jenis perangkat yang dapat Anda cari di Discover:

### A. Network Switch & Router (`measurement_name: "interface"`)
Digunakan untuk lalu lintas jaringan dan status port.
- **Filter KQL Utama:** `tag.device_type: "network_switch"`
- **Daftar Field:**
    - `interface.if_name` : Nama antarmuka (contoh: ether1, sfp-1)
    - `interface.ifAdminStatus` / `ifOperStatus` : Status port (Up/Down)
    - `interface.ifInOctets` : Total trafik masuk (Bytes)
    - `interface.ifOutOctets` : Total trafik keluar (Bytes)

### B. APC UPS (`measurement_name: "ups_apc"`)
Digunakan untuk memantau kesehatan baterai dan beban listrik.
- **Filter KQL Utama:** `tag.device_type: "ups"`
- **Daftar Field:**
    - `ups_apc.upsBatteryCapacity` : Kapasitas persentase baterai (%)
    - `ups_apc.upsBatteryTemp` : Suhu fisik baterai (°C)
    - `ups_apc.upsOutputVoltage` : Tegangan output listrik (Volt)

### C. Lenovo Servers (`measurement_name: "server_redfish"`)
Digunakan untuk data sensor internal sasis server.
- **Filter KQL Utama:** `tag.device_type: "server"`
- **Daftar Field:**
    - `server_redfish.power_output_watts` : Konsumsi daya saat ini (Watts)
    - `server_redfish.reading_celsius` : Suhu termal (°C)
    - `server_redfish.reading_rpm` : Putaran kipas server (RPM)
    - *(Catatan: Data inventory hardware statis seperti CPU/RAM kini berada di `dcim_sot` PostgreSQL).*

### D. Synology NAS (`measurement_name: "dcim_nas"`)
Digunakan untuk kesehatan *array storage* dan disk.
- **Filter KQL Utama:** `tag.device_type: "nas"`
- **Daftar Field:**
    - `dcim_nas.diskTemp` : Suhu fisik per hard drive (°C)
    - `dcim_nas.diskStatus` : Kode status kesehatan (Normal/Degraded)
    - `dcim_nas.storageUsed` / `storageSize` : Utilisasi kapasitas NAS

### E. CCTV & NVR (`measurement_name: "cctv_metrics"`)
Digunakan untuk pemantauan ketersediaan sistem pengawasan.
- **Filter KQL Utama:** `tag.device_type: "cctv"` atau `tag.device_type: "nvr"`
- **Daftar Field:**
    - `cctv_metrics.cpuUtilization` : Beban CPU unit (%)
    - `cctv_metrics.memoryUsage` : Penggunaan RAM unit (%)
    - `cctv_metrics.hddStatus` : Kesehatan penyimpan rekaman (HDD)

---

## 💡 4. Tips Pemecahan Masalah (Troubleshooting)

1. **"No Results Found" di Visualisasi:** 
   Pastikan Anda tidak mencari *field name* yang lama. Struktur *flat JSON* sudah tidak berlaku. Anda harus selalu menggunakan pola bersarang seperti `tag.[nama_field]` atau `[measurement].raw_fields_[nama_field]`.
   
2. **Data Baru Tidak Muncul di Dropdown Filter:**
   Jika field baru yang ditambahkan (`tag.site`, dll.) muncul dengan ikon 'tanda tanya' atau tidak muncul sama sekali di opsi sidebar:
   * Buka menu **Stack Management** -> **Data Views / Index Patterns** -> Pilih `dcim-metrics-unified-*`.
   * Klik tombol **Refresh Field List** di pojok kanan atas.

3. **Memverifikasi Struktur JSON Mentah:**
   Buka salah satu entri data di halaman Discover dengan mengeklik tanda panah `(>)` pada salah satu dokumen, lalu beralih ke *tab* **JSON**. Pastikan terdapat dua grup objek utama: `"tag": {...}` dan `"{measurement_name}": {...}`.
