# (MT-018) Traditional Machine Learning Model

# (MT-018) Traditional Machine Learning Model

# 1. Overview

## Objective

Membangun sistem anomaly detection berbasis Traditional Machine Learning untuk:

* Monitoring server metrics real-time
* Mendeteksi abnormal behavior
* Menyimpan hasil anomaly ke database
* Menyediakan fondasi AI DCIM adaptif

***

# 2. System Architecture

```scss
Telemetry Collector
        ↓
PostgreSQL + TimescaleDB
        ↓
Dataset Preparation
        ↓
Baseline Model Training
        ↓
Model Artifacts (pkl bundle)
        ↓
Inference Engine
        ↓
server_anomalies table
```

***

# 3. ML Environment Setup

## Infrastructure

* OS : Ubuntu 24.04 LTS
* Python venv: ragavenv
* Database: PostgreSQL 16 + TimescaleDB
* GPU: 2x RTX 3070 TI (not used for baseline ML)

## Python Dependencies

```nginx
pandas
numpy
scikit-learn
sqlalchemy
psycopg2
joblib
```

***

# 4. Dataset Preparation

## Data Source

Table : `server_metrics`

Columns:

* time
* hostname
* cpu\_usage
* memory\_usage
* disk\_io
* temperature
* gpu\_util
* gpu\_mem\_used
* gpu\_mem\_total
* net\_rx
* net\_tx

## Cleaning Pipeline

Steps:

* Drop NULL values
* Remove non-feature columns
* Variance analysis
* Remove low-variance features (<1e-3)
* StandardScaler normalization
* Train-test split (80/20)

## Feature Selection Result

Initial feature set:

```css
['cpu_usage', 'memory_usage', 'disk_io', 'net_rx', 'net_tx']
```

Adaptive retrain feature set:

```css
['cpu_usage', 'memory_usage', 'net_rx', 'net_tx']
```

Dengan penjelasan:

* cpu\_usage (%)
  &#x20; \* Persentase utilisasi cpu.
  &#x20; \* Indikator beban komputasi server.
  &#x20; \* Spike mendadak → indikasi runaway process / overload.
  &#x20; \* Variance tinggi → kandidat utama anomaly detection.
* memory\_usage (%)
  &#x20; \* Persentase penggunaan RAM.
  &#x20; \* Drift baseline sering terjadi akibat perubahan workload.
  &#x20; \* Penting untuk mendeteksi memory leak.
* disk\_io (bytes/sec atau cumulative IO)
  &#x20; \* Aktivitas read/write disk.
  &#x20; \* Burst tinggi → backup, indexing, database write strom.
  &#x20; \* Variance rendah → di-drop oleh variance filter.
* net\_rx (MB)
  &#x20; \* Network receive throughput.
  &#x20; \* Mendeteksi traffic spike.
  &#x20; \* Digunakan untuk mendeteksi DDoS / traffice anomaly.
* net\_tx (MB)
  &#x20; \* Network transmit throughput.
  &#x20; \* Indikator outgoing brust (backup sync, upload, replication).

***

# 5. Baseline Model Development

## Algorithm

Isolation Forest

Parameters:

```ini
n_estimators = 200  
#jumlah decision trees.
#Lebih banyak tree → boundary lebih stabil.
#Tradeoff: waktu training vs robustness.
contamination = 0.05
#Perkiraan proporsi anomaly.
#Mengatur threshold decision.
#Tidak memaksa output 5%, hanya mengatur cut-off saat training
random_state = 42
#Repoducibility.
#Menjamin hasil konsisten saat retraining.
```

## Validation

✔ CPU Spike Injection Test

Manual spike → anomaly detected

✔ Training Anomaly Ratio

≈ 5% (as configured)

***

# 6. Model Benchmarking

| Contamination | Train Time | Inference Time | Test Ratio |
| ------------- | ---------- | -------------- | ---------- |
| 0.01          | \~0.13s    | \~0.008s       | \~1%       |
| 0.05          | \~0.13s    | \~0.008s       | \~5%       |
| 0.10          | \~0.13s    | \~0.008s       | \~13%      |

Inference latency < 10ms

Suitable for real-time DCIM.

Penjelasan metrics:

* Train Time (\~0.13s)
  &#x20; \* Mengukur computational overhead.
  &#x20; \* Indikator kelayakan retraining frequent.
* Inference Time (\~0.008s)
  &#x20; \* Latency per batch.
  &#x20; \* <10ms → cocok real-time monitoring.

***

# 7. Model Packaging

## Artifact Structure

```
models/
  isolation_forest_baseline.pkl
  scaler_baseline.pkl
  feature_columns.pkl
```

## Inference Pipeline

File:

```shellscript
src/anomaly_inference.py
```

Flow

* Load model
* Load scaler
* Load feature list
* Fetch data from DB
* Transform
* Predict
* Insert into server\_anomalies

## Output Table

`server_anomalies`

Columns:

* time
* cpu\_usage
* memory\_usage
* disk\_io
* net\_rx
* net\_tx
* anomaly (boolean)

***

# 8. Adaptive Model Lifecycle Management

## Problem Encountered

Data drift:

Memory baseline:

23% → 16%

Anomaly ratio:

5% → 45%

## Solution Implemented

Rolling retraining (30-minute window)

File

```shellscript
src/adaptive_retrain.py
```

Mechanism:

* Fetch last 30 minutes
* Full retrain
* Overwrite artifact
* Maintain contamination=0.05

Training anomaly ratio stabilized ≈ 5%

## Key Insights Learned

* Static models fail in dynamic environments
* Isolation Forest sensitive to low variance
* Snapshot-based detection unstable for highly stable servers
* Distribution shift drastically impacts threshold

# 9. System Status

## Completed

* Environment Setup
* Dataset Preparation
* Baseline Model Development
* Model Benchmarking
* Model Packaging
* Adaptive Retraining

## Limitations

* Snapshot detection too sensitive
* No trend-based detection
* No drift scoring metric
* No model versioning
* No rollback mechanism

# 10. Phase Completion Summary

Traditional ML Phase Status:

✔ Functional

✔ Drift-aware (basic)

✔ Production-testable

⚠ Needs intelligence upgrade

***

# 11. Addendum v1.2.0 — Penyesuaian untuk Use Case 1, 2, 3

> **Tanggal:** 20 Mei 2026

> **Tujuan:** Menyelaraskan MT-018 dengan kebutuhan tiga use case Analytics & AI Engine (Predictive Failure Alerting, Capacity Optimization, Energy/PUE Drift).

> **Sifat:** Addendum non-destruktif — isi bagian 1–10 di atas tetap dipertahankan sebagai rekam jejak.

## 11.1 Ringkasan Gap

| Area          | Kondisi Saat Ini (Bagian 1–10)                     | Kebutuhan UC                                                                                                    | Status          |
| ------------- | -------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | --------------- |
| Feature scope | `cpu_usage, memory_usage, disk_io, net_rx, net_tx` | UC1 perlu `temperature, smart_*, fan_speed`; UC3 perlu `power_w, voltage, pue`, `temp_inlet/outlet`, `humidity` | ⚠️ Diperluas    |
| Data source   | Hardcoded ke `server_metrics`                      | UC2/UC3 butuh sumber tambahan (NetBox, PDU, environment)                                                        | ⚠️ Generalisasi |
| Algoritma     | Hanya anomaly classification (IF/LOF/OCSVM)        | UC1 butuh time-series forecasting                                                                               | ❌ Tambah        |
| Labeling      | Unsupervised only                                  | UC1 butuh supervised failure labels                                                                             | ❌ Tambah        |
| Data quality  | `dropna` saja                                      | UC3 sensor noisy → butuh imputation & outlier filtering                                                         | ❌ Tambah        |

## 11.2 Perluasan Feature Scope

Tambahkan **feature group** terpisah agar tidak mencampur metrik server dengan metrik energi/lingkungan.

| Group                        | Domain                    | Fitur                                                                                   | Sumber                      |
| ---------------------------- | ------------------------- | --------------------------------------------------------------------------------------- | --------------------------- |
| `server_compute`             | compute, memory, network  | `cpu_usage, memory_usage, disk_io, net_rx, net_tx, gpu_util, gpu_mem_used, temperature` | `server_metrics` (existing) |
| `server_health` (baru)       | storage, hardware         | `smart_reallocated_sectors, smart_temp, smart_pending_sectors, fan_speed, hwmon_temp`   | SNMP/IPMI/Redfish (UC1)     |
| `power_metrics` (baru)       | power                     | `power_w, voltage, current, energy_kwh, pue`                                            | PDU/UPS (UC3)               |
| `environment_metrics` (baru) | cooling                   | `temp_inlet, temp_outlet, humidity, dewpoint`                                           | Sensor lingkungan (UC3)     |
| `capacity_metrics` (baru)    | compute, storage, network | rolling 7d/30d/90d aggregates dari `server_compute` + rack occupancy dari NetBox        | Aggregate + NetBox (UC2)    |

> **Catatan:** Variance filter `<1e-3` yang sebelumnya men-drop `disk_io` perlu **dievaluasi ulang per-group**. Pada konteks energy, deviasi kecil tetap signifikan.

## 11.3 Generalisasi Data Source

Pipeline `dataset_preparation` saat ini terikat ke `server_metrics`. Refactor menjadi **abstract loader** dengan kontrak minimal:

```python
class MetricSource:
    domain: str             # 'server' | 'power' | 'environment'
    table: str
    feature_columns: list[str]
    timestamp_column: str = 'time'
    asset_id_column: str = 'hostname'  # atau 'device_id'
    def load(window: TimeWindow) -> pd.DataFrame: ...
```

Implementasi konkret per UC:

* `ServerMetricsSource` (existing, untuk UC1/UC2)
* `PowerMetricsSource` (baru, untuk UC3 — query tabel TimescaleDB `power_metrics`)
* `EnvironmentMetricsSource` (baru, untuk UC3)
* `NetBoxAssetSource` (baru, untuk UC2 — read-only NetBox API)

## 11.4 Forecasting Profile (Baru)

UC1 mensyaratkan deteksi **24–48 jam sebelum kegagalan**. Anomaly detection saja tidak cukup.

| Layer             | Algoritma                                                      | Output                                                             | Use For        |
| ----------------- | -------------------------------------------------------------- | ------------------------------------------------------------------ | -------------- |
| Baseline forecast | Prophet / XGBoost regression dengan lag features (1h, 6h, 24h) | `forecast_value`, `forecast_ci_low`, `forecast_ci_high` per metrik | UC1 quick-win  |
| Advanced forecast | LSTM / Temporal Fusion Transformer                             | `failure_probability_24h`, `failure_probability_48h`               | UC1 production |

**Integrasi:** output forecast disuntikkan sebagai *forecasted feature* ke ensemble anomaly existing. Anomaly pada `forecast_value` = early warning.

## 11.5 Supervised Labeling untuk Failure Events

Tambahkan tabel `failure_events` dengan kontrak:

```sql
failure_events (
  event_id UUID PK,
  asset_id TEXT,
  event_time TIMESTAMPTZ,
  failure_type TEXT,    -- 'disk', 'fan', 'thermal', 'memory', 'power'
  severity TEXT,        -- 'minor', 'major', 'critical'
  source TEXT,          -- 'manual', 'incident_ticket', 'sensor_threshold'
  evidence JSONB
)
```

Digunakan untuk:

* Training supervised model (Gradient Boosting / Random Forest) dengan window features sebelum event.
* Backtesting forecast model terhadap failure history.

## 11.6 Imputation & Noise Handling

Pipa cleaning sekarang hanya `dropna`. Tambahkan strategi per-feature:

| Strategi                       | Cocok Untuk                         | Catatan                                         |
| ------------------------------ | ----------------------------------- | ----------------------------------------------- |
| Forward-fill (max gap 5 menit) | Streaming sensor (PDU, environment) | Hindari gap-fill pada gap besar                 |
| Linear interpolation           | Metrik kontinu (suhu, voltage)      | Tandai sebagai imputed di kolom `_imputed_flag` |
| Median per-window              | Outlier filtering pada SMART data   | Lebih robust dari mean                          |
| Drop                           | Schema invalid / corrupt rows       | Logged ke `data_quality_log`                    |

## 11.7 Backward Compatibility

Semua perubahan di addendum ini **opt-in**:

* Pipeline existing `server_metrics → IF/LOF/OCSVM` tetap berjalan tanpa perubahan.
* Feature group baru dipanggil hanya bila profil `forecast`, `energy`, atau `capacity` di-aktifkan via konfigurasi training.
* Schema `failure_events` & sumber data baru bersifat **additive**.

## 11.8 Mapping ke Use Case

| UC  | Bagian Addendum yang Dipakai                                                                                                     |
| --- | -------------------------------------------------------------------------------------------------------------------------------- |
| UC1 | 11.2 (`server_health`), 11.4 (forecasting), 11.5 (labeling), 11.6 (imputation SMART)                                             |
| UC2 | 11.2 (`capacity_metrics`), 11.3 (`NetBoxAssetSource`)                                                                            |
| UC3 | 11.2 (`power_metrics`, `environment_metrics`), 11.3 (`PowerMetricsSource`, `EnvironmentMetricsSource`), 11.6 (imputation sensor) |

| Date       | Versi | Auth   | Note                                                                  |
| ---------- | ----- | ------ | --------------------------------------------------------------------- |
| 13/02/2026 | 1     | Fakhri | -                                                                     |
| 02/03/2026 | 1.1.2 | Fakhri | Perubahan tambahan penjelasan metrics                                 |
| 20/05/2026 | 1.2.0 | Fakhri | Addendum v1.2.0 — koreksi untuk UC1/UC2/UC3 (lihat Addendum di bawah) |
