# AI Training Data Schema (DCIM Metrics)

**Date**: 2026-06-17
**Context**: Schema ini mendefinisikan format ekspor data CSV/JSONL yang dihasilkan oleh `scripts/export_training_data.py`. Sesuai dengan arsitektur v4.1 (L13), data historis untuk training time-series kini bersumber dari **PostgreSQL (golden source)** melalui materialized views `v_train_*`, bukan lagi dari Elasticsearch.

## 1. Export Script Usage

Script untuk mengekstrak data historis dari PostgreSQL ke format CSV/JSONL:

```bash
python3 scripts/export_training_data.py \
    --device server \
    --start 2026-05-01 \
    --end 2026-05-31 \
    --format csv
```

- Output akan otomatis disimpan ke `/home/infra/dcim_metrics_project/exports/`.

## 2. Feature Schemas & MT-018 Mapping

Penamaan kolom dalam PostgreSQL (`v_train_*`) memakai konvensi `dcim_sot` kita. Di bawah ini adalah pemetaan ke nama fitur yang diminta oleh dokumen MT-018 milik tim AI.

### A. Server (UC-AI-1 & UC-AI-2)
Kolom yang diekstrak dari view `v_train_server`:

| Column Name (Kita) | MT-018 Name | Description |
|---|---|---|
| `ts` | `timestamp` | ISO 8601 Timestamp (truncated per menit) |
| `serial_number` | `serial_number` | Unique identifier (untuk join dengan iTop/Enrichment) |
| `hostname` | `hostname` | Hostname perangkat |
| `model` | `model` | Model hardware perangkat |
| `temp_celsius` | `temp_celsius` | Suhu sistem dalam Celcius |
| `power_watts` | `power_watts` | Konsumsi daya server dalam Watts |
| `fan_rpm` | `fan_rpm` | Kecepatan kipas dalam RPM |
| `cpu_util_pct` | `cpu_usage` | Persentase utilitas CPU (0-100) (via Redfish Telemetry) |
| `mem_util_pct` | `memory_usage`| Persentase utilitas Memori (0-100) |

### B. Network
Kolom yang diekstrak dari view `v_train_network`:

| Column Name (Kita) | MT-018 Name | Description |
|---|---|---|
| `ts` | `timestamp` | ISO 8601 Timestamp |
| `cpu_util_pct` | `cpu_usage` | Utilitas CPU Switch |
| `mem_util_kb` | `mem_usage` | Penggunaan memori Switch |
| `net_rx` | `ifInOctets` | Inbound traffic |
| `net_tx` | `ifOutOctets` | Outbound traffic |
| `in_errors` | `ifInErrors` | Inbound errors |
| `out_errors`| `ifOutErrors` | Outbound errors |
| `in_discards`| `ifInDiscards` | Inbound discards |
| `out_discards`| `ifOutDiscards`| Outbound discards |
| `oper_status`| `ifOperStatus` | Status antarmuka operasional |

### C. UPS (UC-AI-3)
Kolom yang diekstrak dari view `v_train_ups`:

| Column Name (Kita) | MT-018 Name | Description |
|---|---|---|
| `input_voltage` | `input_voltage` | Tegangan input |
| `output_voltage` | `output_voltage`| Tegangan output |
| `output_load` | `output_load` | Persentase beban UPS (0-100) total |
| `output_load_L1/2/3`| `output_load_L*`| Beban UPS L1/L2/L3 |
| `output_current` | `output_current`| Arus UPS (total) |
| `output_current_L*`| `output_current_L*`| Arus keluaran UPS tiap fase |
| `battery_capacity` | `battery_capacity`| Kapasitas baterai (%) |
| `battery_runtime_remain`| `battery_runtime_remain`| Sisa waktu runtime baterai |
| `battery_temp` | `battery_temp` | Suhu baterai (Celcius) |

## 3. Daftar Data Belum Tersedia (Pending Collection)

Sesuai dokumen arsitektur dan handoff, beberapa fitur yang diminta oleh tim AI dalam MT-018 / FIT041 saat ini **BELUM DIKOLEKSI** dan dikeluarkan dari scope data ingestion fase ini. Tim AI harus memaklumi absennya kolom ini atau menggunakan teknik imputasi:

| Fitur | Status | Alasan / Kendala |
|---|---|---|
| `disk_io` (read/write bytes) | Belum ada | Sensor Redfish standar tidak mengekspos, butuh agent OS |
| `smart_*` (sectors, temp) | Belum ada | Butuh poller SMART per disk |
| `gpu_util`, `gpu_mem` | Belum ada | GPU (RTX 3070Ti) tidak terkoleksi via Redfish secara native |
| `temp_inlet`, `temp_outlet` | Belum ada | Sensor environment cooling (CRAC) belum terkoleksi |
| `humidity` | N/A | **Tidak ada sensor fisik** terpasang |
| `pue`, facility power | Belum ada | Butuh meter daya facility total, bukan sekadar IT load |

## 4. Enrichment Integration

Untuk mendapatkan context tambahan relasi perangkat (seperti `location_id`, `org_id`, `criticality`), tim AI dapat melakukan **JOIN** dengan CMDB **iTop** atau query langsung ke tabel relasional di PostgreSQL (`dcim_server_disks`, dsb).
Tim AI juga dapat menggunakan **Enrichment API** (Redis) secara real-time pada saat inferensi agen AI:
`GET http://localhost:8000/enrich/{serial_number}`
