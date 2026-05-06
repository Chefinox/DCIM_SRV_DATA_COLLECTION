# Panduan Observabilitas DCIM: Data View Gabungan
**Target Arsitektur:** Broker-Based Unified Ingestion
**Primary Key (Glue):** `serial_number.keyword`

---

## 1. Konfigurasi Data View
Untuk melihat seluruh ekosistem dalam satu layar, gunakan pola berikut di Kibana Stack Management:
*   **Index Pattern:** `dcim-inventory-*,telegraf-*`
*   **Time Field:** `@timestamp`

---

## 2. Cara Kerja Korelasi (The "Join" Logic)
Data di bagi menjadi dua kategori dokumen yang bisa saling berinteraksi via `serial_number`:

### A. Dokumen Inventaris (dcim-inventory-*)
Berisi data statis/spek perangkat.
*   **Field Penting:** `model`, `manufacturer`, `firmware`, `status`, `product_name`.

### B. Dokumen Metrik (telegraf-*)
Berisi data dinamis/performa.
*   **Field Penting:** `cpu_usage`, `temperature`, `power_watts`, `voltage`.

---

## 3. Filter & Pencarian yang Direkomendasikan

| Tujuan Analisis | Filter (KQL Query) | Field untuk Ditampilkan (Columns) |
| :--- | :--- | :--- |
| **Kesehatan 1 Perangkat** | `serial_number: "J901F8KE"` | `@timestamp`, `measurement_name`, `value` |
| **Berdasarkan Lokasi** | `tag.site: "SITE-A"` | `host`, `tag.ip`, `cpu_usage` |
| **Berdasarkan Kategori** | `tag.category: "infrastructure"` | `serial_number`, `ups_status`, `ups_load` |
| **Mencari Isu Firmware** | `NOT firmware: "v1.2"` | `host`, `firmware`, `serial_number` |

---

## 4. Katalog Metrik Berdasarkan Perangkat

### 🖥️ Servers (Redfish)
*   `server_redfish.power_output_watts`: Konsumsi daya riil.
*   `server_redfish.cpu_usage`: Beban prosesor.
*   `server_redfish.ambient_temp`: Suhu udara sekitar server.

### 🔋 UPS (APC SNMP)
*   `ups_input_voltage`: Tegangan listrik masuk.
*   `ups_load_percent`: Beban penggunaan daya UPS.
*   `ups_battery_runtime`: Sisa waktu baterai (detik).

### 💾 NAS (Synology API)
*   `volume_used_percent`: Kapasitas penyimpanan terpakai.
*   `disk_temperature`: Suhu hardisk fisik.

---

## 5. Visualisasi Dashboard (Lens)
Untuk membuat table "Excel-like" yang menggabungkan Spek + Performa:
1.  Klik **Create Dashboard** -> **Create Visualization**.
2.  Pilih Chart type: **Table**.
3.  Rows: **`serial_number`** dan **`host`**.
4.  Metrics: **`Last(firmware)`**, **`Average(cpu_usage)`**, **`Max(power_watts)`**.

---
**Tips:** Selalu sertakan field `serial_number` di setiap tabel agar Anda bisa melakukan navigasi lintas-index dengan sekali klik.
