# Data Quality Audit Report (Elasticsearch)

**Date**: 2026-06-11
**Index**: `dcim-metrics-unified-*`
**Total Documents**: ~38.4 million

## 1. Depth of Historical Data (Kedalaman Historis)

Analisis rentang waktu data yang tersedia per kategori perangkat:

| Device Type | Total Documents | Days Available | Status |
|---|---|---|---|
| Server | 10,491,181 | 21.7 days | ⚠️ Kurang dari 30 hari |
| Network Switch | 9,948,638 | 21.7 days | ⚠️ Kurang dari 30 hari |
| NAS | 2,310,596 | 21.7 days | ⚠️ Kurang dari 30 hari |
| CCTV | 937,967 | 21.6 days | ⚠️ Kurang dari 30 hari |
| UPS | 29,283 | 19.6 days | ⚠️ Kurang dari 30 hari |
| NVR | 24,538 | 21.6 days | ⚠️ Kurang dari 30 hari |

**Finding**: Data historis untuk seluruh perangkat rata-rata hanya tersedia sekitar ~21 hari ke belakang. Ini belum memenuhi syarat minimum 30 hari historis untuk device kritikal (Server, UPS) yang dibutuhkan untuk UC-AI-1 dan UC-AI-2.

## 2. Field Completeness (Kelengkapan Atribut/Tag)

Analisis keberadaan field identitas perangkat (`serial_number`, dll):

| Device Type | Serial Number | Model | Brand | Location | Rack |
|---|---|---|---|---|---|
| Server | 100% | 100% | 0% | 0% | 0% |
| Network Switch | 100% | 100% | 0% | 0% | 0% |
| NAS | 100% | 84.5% | 0% | 0% | 0% |
| CCTV | 100% | 58.9% | 0% | 0% | 0% |
| UPS | 100% | 97.3% | 0% | 0% | 0% |
| NVR | 100% | 100% | 0% | 0% | 0% |

**Finding**: Field `serial_number` dan `model` cukup lengkap. Namun, field `brand`, `location`, dan `rack` di index unified ES terlihat kosong (0%). Hal ini mungkin karena pemetaan (mapping) Telegraf yang berubah, atau field-field tersebut memang hanya diambil via Enrichment API (Redis) secara real-time dan tidak disimpan secara historis di ES.

## 3. Metrics Completeness (Kelengkapan Fitur AI)

Berdasarkan mapping Elasticsearch terbaru, struktur metrics berada di bawah `dcim_metrics.raw_fields_*`.
Karena adanya migrasi dan perubahan schema index dari Telegraf lama ke Telegraf baru (v4), data lama mungkin tidak memiliki field metrics dengan format struktur yang konsisten (sehingga query agregasi menghasilkan 0% mapping match untuk field tertentu yang diharapkan AI).

**Finding**: 
- Variasi field metrics sangat tinggi per model perangkat. (e.g. CPU bisa bernama `cpu_usage`, `cpu_load`, `cpuUtilization`).
- Dibutuhkan mapping statis / data export script (ST-015-04) yang bisa menormalisasi nama kolom ini saat tim AI mengekstrak data CSV.

## Rekomendasi / Next Steps
1. **Historical Depth**: Kita perlu menunggu 9 hari lagi untuk mencapai requirement 30 hari data, atau mensimulasikan data untuk keperluan uji coba AI.
2. **Missing Tags in ES**: Karena `location` dan `rack` tidak tersedia 100% di data historis ES, tim AI **wajib** menggunakan referensi dari iTop/Redis (Enrichment API) dengan mem-pivot berdasarkan `serial_number` jika membutuhkan context lokasi saat training model.
3. Lanjut ke eksekusi ST-015-02 (Perkuat Redis Cache) agar enrichment API bisa memberikan data yang hilang (brand, location, rack, criticality) secara komprehensif.
