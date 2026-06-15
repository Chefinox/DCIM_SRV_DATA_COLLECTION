-- Tabel arsip jangka panjang (TERPISAH dari dcim_events; tidak mengubah apa pun yang ada)
CREATE TABLE IF NOT EXISTS dcim_metrics_archive (
    event_time     timestamptz NOT NULL,   -- dari @timestamp ES
    device_type    text        NOT NULL,   -- tag.device_type
    hostname       text,                   -- tag.hostname
    ip             inet,                   -- tag.ip
    serial_number  text,                   -- tag.serial_number
    model          text,                   -- tag.model
    metric_name    text,                   -- tag.metric_name
    field_key      text,                   -- nama field, mis. 'cpuUtilization','reading_celsius'
    field_value    double precision,       -- nilai numerik (NULL bila non-numerik)
    field_value_txt text,                  -- fallback untuk nilai string
    enrichment_status text,
    es_doc_id      text,                   -- _id dokumen ES → kunci idempotensi (anti-duplikat)
    raw_source     jsonb,                  -- salinan _source utuh untuk audit
    PRIMARY KEY (event_time, es_doc_id)
) PARTITION BY RANGE (event_time);

-- Buat partisi bulanan (Mulai dari April 2026 sampai Desember 2026)
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m04 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-04-01') TO ('2026-05-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m05 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-05-01') TO ('2026-06-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m06 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m07 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m08 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-08-01') TO ('2026-09-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m09 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-09-01') TO ('2026-10-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m10 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-10-01') TO ('2026-11-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m11 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-11-01') TO ('2026-12-01');
CREATE TABLE IF NOT EXISTS dcim_metrics_archive_y2026_m12 PARTITION OF dcim_metrics_archive FOR VALUES FROM ('2026-12-01') TO ('2027-01-01');

-- Indexes untuk pencarian
CREATE INDEX IF NOT EXISTS idx_dcim_archive_device_type ON dcim_metrics_archive (device_type);
CREATE INDEX IF NOT EXISTS idx_dcim_archive_hostname ON dcim_metrics_archive (hostname);
CREATE INDEX IF NOT EXISTS idx_dcim_archive_field_key ON dcim_metrics_archive (field_key);

-- MATERIALIZED VIEWS for AI Training Data

-- Server
DROP MATERIALIZED VIEW IF EXISTS v_train_server;
CREATE MATERIALIZED VIEW v_train_server AS
SELECT
    date_trunc('minute', event_time) AS ts,
    serial_number, hostname, model,
    MAX(field_value) FILTER (WHERE field_key = 'reading_celsius')      AS temp_celsius,
    MAX(field_value) FILTER (WHERE field_key = 'power_output_watts')   AS power_watts,
    MAX(field_value) FILTER (WHERE field_key = 'reading_rpm')          AS fan_rpm,
    MAX(field_value) FILTER (WHERE field_key = 'cpuUtilization')       AS cpu_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'memoryUsage')          AS mem_util_pct
FROM dcim_metrics_archive
WHERE device_type = 'server'
GROUP BY ts, serial_number, hostname, model;

-- UPS
DROP MATERIALIZED VIEW IF EXISTS v_train_ups;
CREATE MATERIALIZED VIEW v_train_ups AS
SELECT
    date_trunc('minute', event_time) AS ts,
    serial_number, hostname, model,
    MAX(field_value) FILTER (WHERE field_key = 'input_voltage')      AS input_voltage,
    MAX(field_value) FILTER (WHERE field_key = 'output_voltage')     AS output_voltage,
    MAX(field_value) FILTER (WHERE field_key = 'load_percent')       AS load_pct,
    MAX(field_value) FILTER (WHERE field_key = 'battery_capacity')   AS battery_pct,
    MAX(field_value) FILTER (WHERE field_key = 'battery_runtime')    AS battery_runtime_sec,
    MAX(field_value) FILTER (WHERE field_key = 'temperature_celsius') AS temp_celsius
FROM dcim_metrics_archive
WHERE device_type = 'ups'
GROUP BY ts, serial_number, hostname, model;

-- NAS
DROP MATERIALIZED VIEW IF EXISTS v_train_nas;
CREATE MATERIALIZED VIEW v_train_nas AS
SELECT
    date_trunc('minute', event_time) AS ts,
    serial_number, hostname, model,
    MAX(field_value) FILTER (WHERE field_key = 'volume_used_percent')   AS vol_used_pct,
    MAX(field_value) FILTER (WHERE field_key = 'temperature_celsius')   AS temp_celsius,
    MAX(field_value) FILTER (WHERE field_key = 'cpu_load')              AS cpu_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'memory_usage_percent')  AS mem_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'network_rx_bytes')      AS net_rx_bytes,
    MAX(field_value) FILTER (WHERE field_key = 'network_tx_bytes')      AS net_tx_bytes
FROM dcim_metrics_archive
WHERE device_type = 'nas'
GROUP BY ts, serial_number, hostname, model;

-- Network
DROP MATERIALIZED VIEW IF EXISTS v_train_network;
CREATE MATERIALIZED VIEW v_train_network AS
SELECT
    date_trunc('minute', event_time) AS ts,
    serial_number, hostname, model,
    MAX(field_value) FILTER (WHERE field_key = 'cpu_load')           AS cpu_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'memory_used_kb')     AS mem_util_kb,
    MAX(field_value) FILTER (WHERE field_key = 'rx_bytes')           AS rx_bytes,
    MAX(field_value) FILTER (WHERE field_key = 'tx_bytes')           AS tx_bytes,
    MAX(field_value) FILTER (WHERE field_key = 'active_connections') AS active_connections
FROM dcim_metrics_archive
WHERE device_type = 'network'
GROUP BY ts, serial_number, hostname, model;

-- CCTV
DROP MATERIALIZED VIEW IF EXISTS v_train_cctv;
CREATE MATERIALIZED VIEW v_train_cctv AS
SELECT
    date_trunc('minute', event_time) AS ts,
    serial_number, hostname, model,
    MAX(field_value) FILTER (WHERE field_key = 'cpuUtilization')     AS cpu_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'memoryUsage')        AS mem_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'network_throughput') AS net_throughput
FROM dcim_metrics_archive
WHERE device_type = 'cctv'
GROUP BY ts, serial_number, hostname, model;

-- NVR
DROP MATERIALIZED VIEW IF EXISTS v_train_nvr;
CREATE MATERIALIZED VIEW v_train_nvr AS
SELECT
    date_trunc('minute', event_time) AS ts,
    serial_number, hostname, model,
    MAX(field_value) FILTER (WHERE field_key = 'cpuUtilization')     AS cpu_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'memoryUsage')        AS mem_util_pct,
    MAX(field_value) FILTER (WHERE field_key = 'disk_usage_percent') AS disk_used_pct
FROM dcim_metrics_archive
WHERE device_type = 'nvr'
GROUP BY ts, serial_number, hostname, model;
