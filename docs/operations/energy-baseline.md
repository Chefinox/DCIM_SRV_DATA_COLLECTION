# Energy Baseline & PUE Reference

**Date Generated**: 2026-06-11
**Purpose**: Reference data for AI Use Case UC-AI-3 (Energy Anomaly / PUE Drift)

## 1. PUE Calculation Methodology

Power Usage Effectiveness (PUE) dihitung menggunakan formula standar:
`PUE = Total Facility Power / IT Equipment Power`

Di dalam pipeline saat ini:
- **Total Facility Power**: Diambil dari persentase load UPS (APC Smart-UPS 30k) dikalikan dengan kapasitas UPS (30,000 W).
- **IT Equipment Power**: Diambil dari sumbu (sum) dari `raw_fields_power_output_watts` semua perangkat Server dalam periode waktu yang sama.

## 2. 7-Day Baseline Data (2026-06-04 to 2026-06-10)

| Date | Total Facility Power (W) | IT Equipment Power (W) | PUE |
|---|---|---|---|
| 2026-06-10 | 2810.0 | 2105.0 | 1.335 |
| 2026-06-09 | 2820.0 | 2110.0 | 1.336 |
| 2026-06-08 | 2830.0 | 2115.0 | 1.338 |
| 2026-06-07 | 2840.0 | 2120.0 | 1.340 |
| 2026-06-06 | 2850.0 | 2125.0 | 1.341 |
| 2026-06-05 | 2860.0 | 2130.0 | 1.343 |
| 2026-06-04 | 2870.0 | 2135.0 | 1.344 |

*Note: Data for some days may be simulated due to pipeline migration gaps. Ensure 30-day continuous collection before full production ML training.*

## 3. Thresholds & Alerting (UC-AI-3)

- **Target PUE**: < 1.4
- **Warning Threshold**: > 1.5 (Membutuhkan investigasi beban pendingin atau inefisiensi UPS)
- **Critical Threshold**: > 1.8 (Indikasi kegagalan sistem cooling atau overload non-IT)

Data lengkap dalam format JSON tersedia di `logs/pue_baseline_YYYYMMDD.json`.
