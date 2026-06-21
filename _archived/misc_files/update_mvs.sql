DROP MATERIALIZED VIEW IF EXISTS v_train_server CASCADE;
CREATE MATERIALIZED VIEW v_train_server AS
SELECT date_trunc('minute'::text, dcim_metrics_archive.event_time) AS ts,
    dcim_metrics_archive.serial_number,
    dcim_metrics_archive.hostname,
    dcim_metrics_archive.model,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'reading_celsius'::text) AS temp_celsius,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'power_output_watts'::text) AS power_watts,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'reading_rpm'::text) AS fan_rpm,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'cpu_utilization'::text) AS cpu_util_pct,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'memory_usage'::text) AS mem_util_pct
   FROM dcim_metrics_archive
  WHERE dcim_metrics_archive.device_type = 'server'::text
  GROUP BY (date_trunc('minute'::text, dcim_metrics_archive.event_time)), dcim_metrics_archive.serial_number, dcim_metrics_archive.hostname, dcim_metrics_archive.model;

DROP MATERIALIZED VIEW IF EXISTS v_train_network CASCADE;
CREATE MATERIALIZED VIEW v_train_network AS
SELECT date_trunc('minute'::text, dcim_metrics_archive.event_time) AS ts,
    dcim_metrics_archive.serial_number,
    dcim_metrics_archive.hostname,
    dcim_metrics_archive.model,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'cpu_load'::text) AS cpu_util_pct,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'memory_used_kb'::text) AS mem_util_kb,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifInOctets'::text) AS net_rx,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifOutOctets'::text) AS net_tx,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifInErrors'::text) AS in_errors,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifOutErrors'::text) AS out_errors,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifInDiscards'::text) AS in_discards,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifOutDiscards'::text) AS out_discards,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'ifOperStatus'::text) AS oper_status,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'active_connections'::text) AS active_connections
   FROM dcim_metrics_archive
  WHERE dcim_metrics_archive.device_type = 'network'::text
  GROUP BY (date_trunc('minute'::text, dcim_metrics_archive.event_time)), dcim_metrics_archive.serial_number, dcim_metrics_archive.hostname, dcim_metrics_archive.model;

DROP MATERIALIZED VIEW IF EXISTS v_train_ups CASCADE;
CREATE MATERIALIZED VIEW v_train_ups AS
SELECT date_trunc('minute'::text, dcim_metrics_archive.event_time) AS ts,
    dcim_metrics_archive.serial_number,
    dcim_metrics_archive.hostname,
    dcim_metrics_archive.model,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'input_voltage'::text) AS input_voltage,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_voltage'::text) AS output_voltage,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_load'::text) AS output_load,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_load_L1'::text) AS output_load_L1,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_load_L2'::text) AS output_load_L2,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_load_L3'::text) AS output_load_L3,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_current'::text) AS output_current,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_current_L1'::text) AS output_current_L1,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_current_L2'::text) AS output_current_L2,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'output_current_L3'::text) AS output_current_L3,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'battery_capacity'::text) AS battery_capacity,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'battery_runtime_remain'::text) AS battery_runtime_remain,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'battery_temp'::text) AS battery_temp,
    max(dcim_metrics_archive.field_value) FILTER (WHERE dcim_metrics_archive.field_key = 'temperature_celsius'::text) AS temp_celsius
   FROM dcim_metrics_archive
  WHERE dcim_metrics_archive.device_type = 'ups'::text
  GROUP BY (date_trunc('minute'::text, dcim_metrics_archive.event_time)), dcim_metrics_archive.serial_number, dcim_metrics_archive.hostname, dcim_metrics_archive.model;

CREATE TABLE IF NOT EXISTS dcim_failure_events (
  event_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  asset_id TEXT,
  event_time TIMESTAMPTZ NOT NULL,
  failure_type TEXT,
  severity TEXT,
  source TEXT,
  evidence JSONB
);

CREATE TABLE IF NOT EXISTS dcim_server_anomalies (
  id BIGSERIAL PRIMARY KEY,
  event_time TIMESTAMPTZ NOT NULL,
  hostname TEXT,
  serial_number TEXT,
  cpu_util_pct DOUBLE PRECISION,
  mem_util_pct DOUBLE PRECISION,
  net_rx DOUBLE PRECISION,
  net_tx DOUBLE PRECISION,
  temp_celsius DOUBLE PRECISION,
  power_watts DOUBLE PRECISION,
  anomaly BOOLEAN,
  anomaly_score DOUBLE PRECISION,
  model_version TEXT
);

CREATE OR REPLACE VIEW server_anomalies AS SELECT * FROM dcim_server_anomalies;
