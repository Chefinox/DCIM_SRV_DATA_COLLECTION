# AI Training Data Schema (DCIM Metrics)

**Date**: 2026-06-11
**Context**: Schema ini mendefinisikan format ekspor data CSV/JSONL yang dihasilkan oleh `scripts/export_training_data.py`. Data ini akan digunakan oleh tim AI untuk feature engineering dan model training.

## 1. Export Script Usage

Script untuk mengekstrak data historis dari Elasticsearch ke format CSV/JSONL:

```bash
python3 scripts/export_training_data.py \
    --device server \
    --start 2026-05-01 \
    --end 2026-05-31 \
    --format csv
```

- Output akan otomatis disimpan ke `/home/infra/dcim_metrics_project/exports/`.

## 2. Feature Schemas

### A. Server (UC-AI-1 & UC-AI-2)
Kolom yang diekstrak untuk `device_type=server`:

| Column Name | ES Mapping Path | Description |
|---|---|---|
| `timestamp` | `@timestamp` | ISO 8601 Timestamp |
| `serial_number` | `tag.serial_number` | Unique identifier (untuk join dengan Enrichment API) |
| `model` | `tag.model` | Model hardware perangkat |
| `cpu_usage` | `dcim_metrics.raw_fields_cpuUtilization` | Persentase utilitas CPU (0-100) |
| `ram_usage` | `dcim_metrics.raw_fields_memoryUsage` | Total memori terpakai (dalam KB/MB) |
| `power_draw` | `dcim_metrics.raw_fields_power_output_watts` | Konsumsi daya server dalam Watts |
| `temperature` | `dcim_metrics.raw_fields_system_temp` | Suhu sistem dalam Celcius |

### B. UPS (UC-AI-3)
Kolom yang diekstrak untuk `device_type=ups`:

| Column Name | ES Mapping Path | Description |
|---|---|---|
| `timestamp` | `@timestamp` | ISO 8601 Timestamp |
| `serial_number` | `tag.serial_number` | Unique identifier UPS |
| `model` | `tag.model` | Model UPS |
| `output_load` | `dcim_metrics.raw_fields_output_load` | Persentase beban UPS (0-100) |
| `battery_temp` | `dcim_metrics.raw_fields_battery_temp` | Suhu baterai (Celcius) |
| `battery_runtime` | `dcim_metrics.raw_fields_battery_runtime_remain`| Sisa waktu runtime baterai (menit) |

## 3. Enrichment Integration

Untuk mendapatkan context tambahan (seperti `criticality`, `org`, `location`), tim AI diwajibkan menggunakan **Enrichment API** (Redis) sebagai referensi statis untuk melengkapi file CSV historis ini:
`GET http://localhost:8000/enrich/{serial_number}`

Enrichment API akan mengembalikan atribut tambahan yang diperlukan untuk context model LLM tanpa memberatkan index Elasticsearch.
