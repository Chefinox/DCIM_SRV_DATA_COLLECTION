# AI Training Data Schema (DCIM Metrics)

**Date**: 2026-06-15
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

## 2. Feature Schemas

Data yang diekstrak mengikuti skema tabel `v_train_*` pada PostgreSQL, yang sudah di-pivot ke bentuk *wide* (kolom per metrik) agar siap dilatih (ready-to-train).

### A. Server (UC-AI-1 & UC-AI-2)
Kolom yang diekstrak dari view `v_train_server`:

| Column Name | PostgreSQL View Path | Description |
|---|---|---|
| `ts` | `ts` | ISO 8601 Timestamp (truncated per menit) |
| `serial_number` | `serial_number` | Unique identifier (untuk join dengan iTop/Enrichment) |
| `hostname` | `hostname` | Hostname perangkat |
| `model` | `model` | Model hardware perangkat |
| `temp_celsius` | `temp_celsius` | Suhu sistem dalam Celcius |
| `power_watts` | `power_watts` | Konsumsi daya server dalam Watts |
| `fan_rpm` | `fan_rpm` | Kecepatan kipas dalam RPM |
| `cpu_util_pct` | `cpu_util_pct` | Persentase utilitas CPU (0-100) (via Redfish Telemetry) |
| `mem_util_pct` | `mem_util_pct` | Persentase utilitas Memori (0-100) |

### B. UPS (UC-AI-3)
Kolom yang diekstrak dari view `v_train_ups`:

| Column Name | PostgreSQL View Path | Description |
|---|---|---|
| `ts` | `ts` | ISO 8601 Timestamp |
| `serial_number` | `serial_number` | Unique identifier UPS |
| `hostname` | `hostname` | Hostname perangkat |
| `model` | `model` | Model UPS |
| `input_voltage` | `input_voltage` | Tegangan input |
| `output_voltage` | `output_voltage` | Tegangan output |
| `load_pct` | `load_pct` | Persentase beban UPS (0-100) |
| `battery_pct` | `battery_pct` | Kapasitas baterai (%) |
| `battery_runtime_sec` | `battery_runtime_sec` | Sisa waktu runtime baterai (detik) |
| `temp_celsius` | `temp_celsius` | Suhu baterai (Celcius) |

*(Schema serupa juga tersedia untuk nas, network, cctv, dan nvr).*

## 3. Enrichment Integration

Untuk mendapatkan context tambahan relasi perangkat (seperti `location_id`, `org_id`, `criticality`), tim AI dapat melakukan **JOIN** dengan CMDB **iTop** atau query langsung ke tabel relasional di PostgreSQL (`dcim_server_disks`, dsb).
Tim AI juga dapat menggunakan **Enrichment API** (Redis) secara real-time pada saat inferensi agen AI:
`GET http://localhost:8000/enrich/{serial_number}`
