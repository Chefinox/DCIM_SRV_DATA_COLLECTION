# (MT-018) Traditional ML Model Configuration Documentation

# 1. System Configuration Overview

Tujuan konfigurasi sistem ini adalah membangun pipeline anomaly detection berbasis mechine learning yang terdiri dari:

1. Telemetry ingestion
2. Data preprocessing
3. Model training 
4. Model artifact packaging
5. Inference pipeline
6. Adaptive retraining

Arsitektur pipeline:

```
Telemetry Collector
        ↓
PostgreSQL / TimescaleDB
        ↓
Dataset Preparation
        ↓
Model Training
        ↓
Artifact Packaging
        ↓
Inference Engine
        ↓
server_anomalies table
```

Arsitektur ini menjadi fondasi sistem anomaly detection yang kemudian berkembang menjadi AI monitoring platform lifecycle-aware [(MT-019) Anomaly Detection Framework](assets://./workspace/0712d6e7-fc27-4d65-b0fa-2e8581ad87c2/jLnCyJBpKVVWT18Ci96Ep).



***

## 2. Infrastructure Configurasi

## Operating System

```
Ubuntu 24.04 LTS
```

Digunakan sebagai host sistem ML dan database.

## Python Environment

Virtual environment:

```
ragavenv
```

Aktivasi environment:

```shellscript
source ragavenv/bin/activate
```

## Python Dependencies

Library yang digunakan:

```
pandas
numpy
scikit-learn
sqlalchemy
psycopg2
joblib
```

Instalasi:

```shellscript
pip install pandas numpy scikit-learn sqlalchemy psycopg2-binary joblib
```



***

# 3. Database Configuration

Database digunakan untuk menyimpan:

* telemetry metrics
* anomaly prediction

Database:

```
PostgreSQL 16
```

## Telemetry Table

Table:

```sql
server_metrics
```

Struktur

```sql
CREATE TABLE server_metrics (
    time TIMESTAMPTZ NOT NULL,
    hostname TEXT,
    cpu_usage FLOAT,
    memory_usage FLOAT,
    disk_io FLOAT,
    temperature FLOAT,
    gpu_util FLOAT,
    gpu_mem_used FLOAT,
    gpu_mem_total FLOAT,
    net_rx FLOAT,
    net_tx FLOAT
);
```

## Anomaly Output Table

Table:

```sql
server_anomalies
```

Struktur:

```sql
CREATE TABLE server_anomalies (
    time TIMESTAMPTZ,
    cpu_usage FLOAT,
    memory_usage FLOAT,
    disk_io FLOAT,
    net_rx FLOAT,
    net_tx FLOAT,
    anomaly BOOLEAN
);
```



***

# 4. Dataset Preparation Configuration

Dataset preparation dilakukan untuk memastikan data siap digunakan oleh model machine learning.

Tahapan:

1. Drop NULL values
2. Remove non-feature columns
3. Variance filtering
4. Feature scaling
5. Train-test split

Pipeline ini juga menjadi bagian dari feature pipeline dalam arsitektur anomaly detection framework [(MT-019) Anomaly Detection Framework](assets://./workspace/0712d6e7-fc27-4d65-b0fa-2e8581ad87c2/jLnCyJBpKVVWT18Ci96Ep).



***

# 5. Training Script Configuration

File:

`notebooks/dataset_preparation.py`

Code yang digunakan:

```python
import pandas as pd
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.ensemble import IsolationForest
import numpy as np
import joblib
import os

engine = create_engine(
"postgresql+psycopg2://infra:password@127.0.0.1/dcim_ai"
)

query = """
SELECT *
FROM server_metrics
WHERE time > NOW() - INTERVAL '30 minutes'
ORDER BY time ASC;
"""

df = pd.read_sql(query, engine)

df = df.dropna()
df = df.drop(columns=["time","hostname"])

variance = df.var()
low_variance_cols = variance[variance < 1e-3].index.tolist()

df_clean = df.drop(columns=low_variance_cols)

feature_columns = df_clean.columns.tolist()

scaler = StandardScaler()
X = scaler.fit_transform(df_clean)

X_train, X_test = train_test_split(
X,
test_size=0.2,
random_state=42
)

model = IsolationForest(
n_estimators=200,
contamination=0.05,
random_state=42
)

model.fit(X_train)

joblib.dump(model,"models/isolation_forest_baseline.pkl")
joblib.dump(scaler,"models/scaler_baseline.pkl")
joblib.dump(feature_columns,"models/feature_columns.pkl")
```



***

# 6. Model Configuration

Model yang digunakan:

`Isolation Forest`

Parameter konfigurasi:

```python
IsolationForest(
n_estimators = 200,
contamination = 0.05,
random_state = 42
)
```

Penjelasan parameter:

### **n\_estimator**

Jumlah decision tree dalam model.

Lebih banyak tree menghasilkan boundary anomaly yang lebih stabil.

### contamination

Estimasi persentase anomaly pada dataset.

Digunakan untuk menentukan threshold anomaly.

### random\_state

Seed untuk memastikan training reproducible.



***

# 7. Model Artifact Configuration

Model disimpan dalam bentuk artifact.

Struktur folder:

```
models/

isolation_forest_baseline.pkl
scaler_baseline.pkl
feature_columns.pkl
```

Fungsi masing-masing artifact:

| **Artifact**     | **Fungsi**                     |
| ---------------- | ------------------------------ |
| model            | anomaly detection              |
| scaler           | normalisasi fitur              |
| feature\_columns | memastikan inference konsisten |



***

# 8. Inference Congfiguration

File:

`src/anomaly_inference.py`

Code yang digunakan:

```python
import pandas as pd
import joblib
from sqlalchemy import create_engine

model = joblib.load("models/isolation_forest_baseline.pkl")
scaler = joblib.load("models/scaler_baseline.pkl")
feature_columns = joblib.load("models/feature_columns.pkl")

engine = create_engine(
"postgresql+psycopg2://infra:password@127.0.0.1/dcim_ai"
)

query = """
SELECT *
FROM server_metrics
WHERE time > NOW() - INTERVAL '30 minutes'
ORDER BY time ASC;
"""

df = pd.read_sql(query, engine)

original_df = df.copy()

df = df.drop(columns=["time","hostname"])
df = df.dropna()

df = df[feature_columns]

X = scaler.transform(df)

pred = model.predict(X)

anomaly_flags = pred == -1

original_df = original_df.loc[df.index]
original_df["anomaly"] = anomaly_flags

original_df[
["time","cpu_usage","memory_usage","disk_io","net_rx","net_tx","anomaly"]
].to_sql(
"server_anomalies",
engine,
if_exists="append",
index=False
)
```



***

# 9. Adaptive Retraining Configuration

Untuk menangani data drift, sistem menggunakan rolling retraining.

Masalah drift dijelaskan dalam arsitektur anomaly framework [(MT-019) Anomaly Detection Framework](assets://./workspace/0712d6e7-fc27-4d65-b0fa-2e8581ad87c2/jLnCyJBpKVVWT18Ci96Ep).

### Retraining Script

File:

`src/adaptive_retrain.py`

Code:

```python
import pandas as pd
import joblib
from sqlalchemy import create_engine
from sklearn.preprocessing import StandardScaler
from sklearn.ensemble import IsolationForest

engine = create_engine(
"postgresql+psycopg2://infra:password@127.0.0.1/dcim_ai"
)

query = """
SELECT *
FROM server_metrics
WHERE time > NOW() - INTERVAL '30 minutes'
ORDER BY time ASC;
"""

df = pd.read_sql(query, engine)

df = df.drop(columns=["time","hostname"])
df = df.dropna()

variance = df.var()
low_variance_cols = variance[variance < 1e-3].index.tolist()

df_clean = df.drop(columns=low_variance_cols)

scaler = StandardScaler()
X = scaler.fit_transform(df_clean)

model = IsolationForest(
n_estimators=200,
contamination=0.05,
random_state=42
)

model.fit(X)

joblib.dump(model,"models/isolation_forest_baseline.pkl")
joblib.dump(scaler,"models/scaler_baseline.pkl")
joblib.dump(df_clean.columns.tolist(),"models/feature_columns.pkl")
```



***

# 10. Operational Commands

Training model:

```shellscript
python notebooks/dataset_preparation.py
```

Inference:

```shellscript
python src/anomaly_inference.py
```

Retraining:

```shellscript
python src/adaptive_retrain.py
```



***

# 11. Monitoring Metrics

Monitoring yang disediakan sistem:

* anomaly ratio
* inference latency
* retraining count

Monitoring ini nantinya terintegrasi dengan observability metrics dan Prometheus monitoring dalam sistem AI platform [(MT-019) Anomaly Detection Framework](assets://./workspace/0712d6e7-fc27-4d65-b0fa-2e8581ad87c2/jLnCyJBpKVVWT18Ci96Ep).



***

# 12. Configurasi Summary

| **Component**       | **File**                |
| ------------------- | ----------------------- |
| Dataset preparation | dataset\_preparation.py |
| Model training      | dataset\_preparation.py |
| Inference engine    | anomaly\_inference.py   |
| Adaptive retraining | adaptive\_retraining.py |
| Database storage    | PostgreSQL              |
| Model artifact      | model.\*.pkl            |



***

# 13. Result

Sistem anomaly detection berhasil:

* mendeteksi spike CPU
* medeteksi drift
* melakukan adaptive retraining
* menyimpan hasil anomaly ke database

Status implementasi:

```
Traditional ML Model Phase
COMPLETED
```



***

