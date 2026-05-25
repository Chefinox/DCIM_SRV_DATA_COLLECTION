# Database Query Baseline for Agents

> **Last Updated**: 2026-05-21  
> **Version**: v3.5.5  
> **Purpose**: Referensi query PostgreSQL agar agent bisa menemukan seluruh data terkait perangkat dari `dcim_sot`.

## 1. Koneksi Database

| Item | Value |
| :--- | :--- |
| Host | `192.168.100.115` |
| Port | `5432` |
| Database | `dcim_sot` |
| Main table | `public.dcim_events` |
| Asset cache table | `public.unified_assets` |
| Server component tables | `dcim_server_disks`, `dcim_server_nics`, `dcim_server_processors`, `dcim_server_ram` |

Gunakan credential dari environment/secret store. Jangan hardcode password di script agent.

```bash
export PGHOST=192.168.100.115
export PGPORT=5432
export PGDATABASE=dcim_sot
export PGUSER=sot_admin
# export PGPASSWORD=...  # isi manual/secret manager
```

## 2. Tabel Utama

### 2.1 `dcim_events`

Fungsi: event telemetry historis + inventory snapshot + enrichment metadata.

Kolom identitas utama:

| Column | Type | Fungsi |
| :--- | :--- | :--- |
| `event_time` | timestamptz | waktu event |
| `device_type` | text | kategori perangkat: `server`, `ups`, `nas`, `network_switch`, `cctv`, `nvr` |
| `hostname` | text | hostname normalized |
| `ip` | inet | IP perangkat |
| `serial_number` | text | serial number normalized |
| `measurement` | text | source measurement |
| `metric_name` | text | nama metric normalized |
| `metric_value` | double | nilai metric |
| `raw_tags` | jsonb | tag mentah source |
| `raw_fields` | jsonb | fields mentah source |
| `source_topic` | text | Kafka topic asal |
| `enrichment_status` | text | status enrichment |
| `site`, `rack_name`, `rack_position` | text/int | metadata CMDB |
| `manufacturer`, `model`, `asset_status` | text | metadata asset |

### 2.2 `unified_assets`

Fungsi: cache asset metadata dari Ralph/CMDB.

| Column | Type | Fungsi |
| :--- | :--- | :--- |
| `serial_number` | text | key asset |
| `hostname` | text | hostname CMDB |
| `ip` | inet | management IP |
| `device_type` | text | kategori |
| `manufacturer`, `model` | text | vendor/model |
| `site`, `rack_name`, `rack_position` | text/int | lokasi |
| `asset_status` | text | status CMDB |
| `ralph_id` | integer | ID asset Ralph |
| `ralph_endpoint` | text | endpoint Ralph: `data-center-assets` / `back-office-assets` |
| `last_synced_at` | timestamptz | waktu sync terakhir |

### 2.3 Server component tables

| Table | Key | Isi |
| :--- | :--- | :--- |
| `dcim_server_disks` | `server_ip` | disk serial, model, size, firmware, slot |
| `dcim_server_nics` | `server_ip` | NIC label, MAC, speed, model |
| `dcim_server_processors` | `server_ip` | CPU model, cores, logical cores, speed |
| `dcim_server_ram` | `server_ip` | RAM model, size, speed |

## 3. Data Coverage Saat Validasi

Snapshot validasi 2026-05-21 08:14 UTC:

| Device Type | Events 24h | Hosts | Serials | Last Event |
| :--- | ---: | ---: | ---: | :--- |
| `cctv` | 44,609 | 3 | 19 | 2026-05-21 08:14:03+00 |
| `nas` | 126,626 | 6 | 6 | 2026-05-21 08:14:00+00 |
| `network_switch` | 460,560 | 5 | 5 | 2026-05-21 08:14:07+00 |
| `nvr` | 1,439 | 1 | 1 | 2026-05-21 08:14:00+00 |
| `server` | 466,241 | 10 | 5 | 2026-05-21 08:14:09+00 |
| `ups` | 1,440 | 1 | 1 | 2026-05-21 08:14:00+00 |

Measurements 24h:

| Device Type | Measurement | Events |
| :--- | :--- | ---: |
| `cctv` | `cctv_metrics` | 44,578 |
| `nas` | `dcim_nas` | 83,433 |
| `nas` | `dcim_nas_volume` | 25,908 |
| `nas` | `nas_snmp` | 17,256 |
| `network_switch` | `interface` | 431,411 |
| `network_switch` | `dcim_network_storage` | 19,176 |
| `network_switch` | `mikrotik` | 9,590 |
| `nvr` | `cctv_metrics` | 1,438 |
| `server` | `server_redfish` | 466,017 |
| `server` | `NULL` | 5 |
| `ups` | `ups_apc` | 1,439 |

## 4. Agent Query Pattern

> **Placeholder note**: syntax `:identifier`, `:hostname`, `:serial_number`, dan sejenisnya adalah placeholder untuk aplikasi/agent. Jika menjalankan langsung di `psql`, gunakan CTE `params` seperti contoh di bawah, atau ganti nilai placeholder dengan literal SQL yang aman.

### 4.1 Cari perangkat by identifier fleksibel

Gunakan query ini jika input agent bisa berupa hostname, IP, atau serial number.

```sql
WITH params AS (
  SELECT 'SRV-HCI-01'::text AS identifier  -- ganti dengan hostname/IP/serial number
), q AS (
  SELECT identifier AS ident
  FROM params
), matched_events AS (
  SELECT *
  FROM dcim_events e, q
  WHERE e.event_time > NOW() - INTERVAL '30 days'
    AND (
      e.serial_number = q.ident
      OR e.hostname ILIKE q.ident
      OR e.ip::text = q.ident
    )
), latest_identity AS (
  SELECT DISTINCT ON (device_type, COALESCE(serial_number, hostname, ip::text))
    device_type, hostname, ip, serial_number, manufacturer, model,
    site, rack_name, rack_position, asset_status, enrichment_status,
    event_time, source_topic
  FROM matched_events
  ORDER BY device_type, COALESCE(serial_number, hostname, ip::text), event_time DESC
)
SELECT *
FROM latest_identity
ORDER BY event_time DESC;
```

### 4.2 Ambil ringkasan semua perangkat aktif

Query ini memakai fallback ke `unified_assets` dan `raw_tags` supaya metadata tetap muncul ketika normalized event belum lengkap. Contoh kasus tervalidasi: UPS event tidak membawa `ip` di `dcim_events` sehingga perlu fallback ke `unified_assets.ip`; CCTV model bisa ada di `raw_tags.model`; CCTV vendor Hikvision bisa diinfer dari model `DS-*`.

```sql
WITH latest_events AS (
  SELECT DISTINCT ON (
    device_type,
    CASE
      WHEN device_type IN ('cctv', 'nvr') THEN ip::text
      ELSE COALESCE(NULLIF(NULLIF(serial_number, 'NO_SN'), 'NO_IDENTIFIER'), NULLIF(hostname, 'unknown'), ip::text)
    END
  )
    device_type,
    CASE
      WHEN device_type IN ('cctv', 'nvr') THEN ip::text
      ELSE COALESCE(NULLIF(NULLIF(serial_number, 'NO_SN'), 'NO_IDENTIFIER'), NULLIF(hostname, 'unknown'), ip::text)
    END AS device_key,
    hostname,
    ip,
    serial_number,
    manufacturer,
    model,
    raw_tags,
    site,
    rack_name,
    asset_status,
    event_time
  FROM dcim_events
  WHERE event_time > NOW() - INTERVAL '24 hours'
  ORDER BY
    device_type,
    CASE
      WHEN device_type IN ('cctv', 'nvr') THEN ip::text
      ELSE COALESCE(NULLIF(NULLIF(serial_number, 'NO_SN'), 'NO_IDENTIFIER'), NULLIF(hostname, 'unknown'), ip::text)
    END,
    event_time DESC
), event_counts AS (
  SELECT
    device_type,
    CASE
      WHEN device_type IN ('cctv', 'nvr') THEN ip::text
      ELSE COALESCE(NULLIF(NULLIF(serial_number, 'NO_SN'), 'NO_IDENTIFIER'), NULLIF(hostname, 'unknown'), ip::text)
    END AS device_key,
    COUNT(*) AS events_24h
  FROM dcim_events
  WHERE event_time > NOW() - INTERVAL '24 hours'
  GROUP BY
    device_type,
    CASE
      WHEN device_type IN ('cctv', 'nvr') THEN ip::text
      ELSE COALESCE(NULLIF(NULLIF(serial_number, 'NO_SN'), 'NO_IDENTIFIER'), NULLIF(hostname, 'unknown'), ip::text)
    END
), enriched AS (
  SELECT
    le.*,
    ec.events_24h,
    ua.hostname AS cmdb_hostname,
    ua.ip AS cmdb_ip,
    ua.manufacturer AS cmdb_manufacturer,
    ua.model AS cmdb_model,
    ua.site AS cmdb_site,
    ua.rack_name AS cmdb_rack_name,
    ua.asset_status AS cmdb_asset_status,
    ua.ralph_id,
    ua.ralph_endpoint,
    ua.last_synced_at
  FROM latest_events le
  JOIN event_counts ec
    ON ec.device_type = le.device_type
   AND ec.device_key = le.device_key
  LEFT JOIN unified_assets ua
    ON ua.serial_number = le.serial_number
    OR ua.ip = le.ip
    OR ua.hostname = le.hostname
)
SELECT
  device_type,
  device_key,
  COALESCE(hostname, cmdb_hostname) AS hostname,
  COALESCE(ip::text, cmdb_ip::text) AS ip,
  serial_number,
  COALESCE(
    NULLIF(NULLIF(manufacturer, 'Unknown'), 'unknown'),
    NULLIF(NULLIF(cmdb_manufacturer, 'Unknown'), 'unknown'),
    CASE
      WHEN device_type IN ('cctv', 'nvr')
       AND COALESCE(NULLIF(raw_tags->>'model', 'unknown'), cmdb_model, model) ILIKE 'DS-%'
      THEN 'Hikvision'
    END
  ) AS manufacturer,
  COALESCE(
    NULLIF(NULLIF(model, 'Unknown'), 'unknown'),
    NULLIF(NULLIF(cmdb_model, 'Unknown'), 'unknown'),
    NULLIF(NULLIF(raw_tags->>'model', 'Unknown'), 'unknown')
  ) AS model,
  COALESCE(site, cmdb_site) AS site,
  COALESCE(rack_name, cmdb_rack_name) AS rack_name,
  COALESCE(asset_status, cmdb_asset_status) AS asset_status,
  ralph_id,
  ralph_endpoint,
  last_synced_at,
  event_time AS last_event,
  events_24h
FROM enriched
ORDER BY device_type, hostname;
```

### 4.3 Cek kesehatan data per device type

```sql
SELECT
  device_type,
  COUNT(*) AS total_events,
  COUNT(DISTINCT hostname) AS unique_hosts,
  COUNT(DISTINCT serial_number) AS unique_serials,
  MAX(event_time) AS last_event,
  NOW() - MAX(event_time) AS age
FROM dcim_events
WHERE event_time > NOW() - INTERVAL '24 hours'
GROUP BY device_type
ORDER BY device_type;
```

### 4.4 Cek measurement yang tersedia

```sql
SELECT
  device_type,
  measurement,
  COUNT(*) AS total_events,
  COUNT(DISTINCT hostname) AS hosts,
  MAX(event_time) AS last_event
FROM dcim_events
WHERE event_time > NOW() - INTERVAL '24 hours'
GROUP BY device_type, measurement
ORDER BY device_type, total_events DESC;
```

### 4.5 Ambil raw sample terakhir perangkat

```sql
SELECT
  event_time,
  device_type,
  hostname,
  ip,
  serial_number,
  measurement,
  metric_name,
  metric_value,
  metric_unit,
  raw_tags,
  raw_fields
FROM dcim_events
WHERE event_time > NOW() - INTERVAL '24 hours'
  AND (
    serial_number = :serial_number
    OR hostname = :hostname
    OR ip = :ip::inet
  )
ORDER BY event_time DESC
LIMIT 50;
```

### 4.6 Join event terbaru dengan `unified_assets`

```sql
WITH latest AS (
  SELECT DISTINCT ON (COALESCE(serial_number, hostname, ip::text))
    *
  FROM dcim_events
  WHERE event_time > NOW() - INTERVAL '24 hours'
  ORDER BY COALESCE(serial_number, hostname, ip::text), event_time DESC
)
SELECT
  l.device_type,
  l.hostname AS event_hostname,
  ua.hostname AS cmdb_hostname,
  l.ip AS event_ip,
  ua.ip AS cmdb_ip,
  l.serial_number,
  ua.ralph_id,
  ua.ralph_endpoint,
  COALESCE(ua.asset_status, l.asset_status) AS asset_status,
  COALESCE(ua.site, l.site) AS site,
  COALESCE(ua.rack_name, l.rack_name) AS rack_name,
  l.event_time AS last_event,
  ua.last_synced_at
FROM latest l
LEFT JOIN unified_assets ua
  ON ua.serial_number = l.serial_number
  OR ua.ip = l.ip
  OR ua.hostname = l.hostname
ORDER BY l.device_type, l.hostname;
```

## 5. Query Baseline per Device Type

### 5.1 Server

#### Latest server identity + health

```sql
SELECT DISTINCT ON (serial_number)
  event_time,
  hostname,
  ip,
  serial_number,
  srv_system_name,
  manufacturer,
  model,
  srv_firmware,
  srv_bios_version,
  srv_health,
  srv_state,
  srv_reading_celsius,
  srv_power_watts,
  srv_reading_rpm,
  srv_cpu_count,
  srv_memory_total_mb,
  site,
  rack_name,
  asset_status
FROM dcim_events
WHERE device_type = 'server'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY serial_number, event_time DESC;
```

#### Server sensors recent metrics

```sql
SELECT
  event_time,
  hostname,
  serial_number,
  srv_sensor_name,
  metric_name,
  metric_value,
  metric_unit,
  srv_reading_celsius,
  srv_reading_rpm,
  srv_power_watts,
  srv_health,
  srv_state
FROM dcim_events
WHERE device_type = 'server'
  AND event_time > NOW() - INTERVAL '1 hour'
  AND (hostname = :hostname OR serial_number = :serial_number)
ORDER BY event_time DESC, srv_sensor_name
LIMIT 500;
```

#### Server components from JSONB columns

```sql
SELECT DISTINCT ON (serial_number)
  hostname,
  ip,
  serial_number,
  srv_cpu_components,
  srv_memory_components,
  srv_disk_components,
  raw_tags->'nics' AS srv_nic_components,
  event_time
FROM dcim_events
WHERE device_type = 'server'
  AND serial_number = :serial_number
ORDER BY serial_number, event_time DESC;
```

#### Server component relational tables by IP

```sql
SELECT 'disk' AS component, server_ip::text, serial_number, model_name, size_gb::text AS value, firmware_version, slot, collected_at
FROM dcim_server_disks
WHERE server_ip = :ip::inet
UNION ALL
SELECT 'nic', server_ip::text, mac_address, model_name, speed_gbps::text, NULL, label, collected_at
FROM dcim_server_nics
WHERE server_ip = :ip::inet
UNION ALL
SELECT 'cpu', server_ip::text, NULL, model_name, cores::text || ' cores / ' || logical_cores::text || ' threads', speed_mhz::text, NULL, collected_at
FROM dcim_server_processors
WHERE server_ip = :ip::inet
UNION ALL
SELECT 'ram', server_ip::text, NULL, model_name, size_mb::text || ' MB', speed_mhz::text, NULL, collected_at
FROM dcim_server_ram
WHERE server_ip = :ip::inet
ORDER BY component, collected_at DESC;
```

### 5.2 UPS

```sql
SELECT DISTINCT ON (serial_number)
  event_time,
  hostname,
  ip,
  COALESCE(serial_number, ups_serial_snmp) AS serial_number,
  manufacturer,
  COALESCE(model, ups_model_snmp) AS model,
  firmware,
  ups_firmware,
  ups_battery_capacity,
  ups_battery_runtime,
  ups_output_load,
  ups_input_voltage,
  ups_output_voltage,
  ups_battery_status,
  ups_battery_temp,
  ups_seconds_on_battery,
  site,
  rack_name,
  asset_status
FROM dcim_events
WHERE device_type = 'ups'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY serial_number, event_time DESC;
```

UPS trend:

```sql
SELECT
  date_trunc('5 minutes', event_time) AS bucket,
  hostname,
  AVG(ups_battery_capacity) AS battery_capacity_avg,
  AVG(ups_output_load) AS output_load_avg,
  AVG(ups_battery_temp) AS battery_temp_avg,
  AVG(ups_input_voltage) AS input_voltage_avg,
  AVG(ups_output_voltage) AS output_voltage_avg
FROM dcim_events
WHERE device_type = 'ups'
  AND event_time > NOW() - INTERVAL '24 hours'
GROUP BY bucket, hostname
ORDER BY bucket DESC;
```

### 5.3 NAS

```sql
SELECT DISTINCT ON (serial_number)
  event_time,
  hostname,
  ip,
  serial_number,
  manufacturer,
  model,
  firmware,
  nas_system_temp,
  nas_disk_temp,
  nas_disk_status,
  nas_disk_id,
  raw_fields,
  site,
  rack_name,
  asset_status
FROM dcim_events
WHERE device_type = 'nas'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY serial_number, event_time DESC;
```

NAS disk/volume metrics:

```sql
SELECT
  event_time,
  hostname,
  serial_number,
  measurement,
  nas_disk_id,
  nas_disk_temp,
  nas_disk_status,
  metric_name,
  metric_value,
  raw_fields
FROM dcim_events
WHERE device_type = 'nas'
  AND event_time > NOW() - INTERVAL '6 hours'
  AND (hostname = :hostname OR serial_number = :serial_number)
ORDER BY event_time DESC
LIMIT 500;
```

### 5.4 Network Switch

```sql
SELECT DISTINCT ON (serial_number)
  event_time,
  hostname,
  ip,
  serial_number,
  manufacturer,
  model,
  firmware,
  status,
  power_state,
  site,
  rack_name,
  asset_status,
  raw_tags,
  raw_fields
FROM dcim_events
WHERE device_type = 'network_switch'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY serial_number, event_time DESC;
```

Interface metrics:

```sql
SELECT
  event_time,
  hostname,
  serial_number,
  net_if_name,
  net_if_oper_status,
  net_if_admin_status,
  net_if_speed,
  net_if_in_octets,
  net_if_out_octets,
  net_if_in_errors,
  net_if_out_errors,
  raw_tags,
  raw_fields
FROM dcim_events
WHERE device_type = 'network_switch'
  AND measurement = 'interface'
  AND event_time > NOW() - INTERVAL '1 hour'
  AND (hostname = :hostname OR serial_number = :serial_number)
ORDER BY event_time DESC, net_if_name
LIMIT 1000;
```

Top interface errors:

```sql
SELECT
  hostname,
  net_if_name,
  MAX(net_if_in_errors) AS max_in_errors,
  MAX(net_if_out_errors) AS max_out_errors,
  MAX(event_time) AS last_event
FROM dcim_events
WHERE device_type = 'network_switch'
  AND measurement = 'interface'
  AND event_time > NOW() - INTERVAL '24 hours'
GROUP BY hostname, net_if_name
HAVING COALESCE(MAX(net_if_in_errors), 0) > 0
    OR COALESCE(MAX(net_if_out_errors), 0) > 0
ORDER BY (COALESCE(MAX(net_if_in_errors), 0) + COALESCE(MAX(net_if_out_errors), 0)) DESC;
```

### 5.5 CCTV

```sql
SELECT DISTINCT ON (serial_number)
  event_time,
  hostname,
  ip,
  serial_number,
  manufacturer,
  model,
  firmware,
  cctv_status_online,
  cctv_status_text,
  status,
  raw_tags,
  raw_fields,
  site,
  rack_name,
  asset_status
FROM dcim_events
WHERE device_type = 'cctv'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY serial_number, event_time DESC;
```

CCTV online/offline summary:

```sql
WITH latest AS (
  SELECT DISTINCT ON (serial_number)
    hostname, ip, serial_number, cctv_status_online, cctv_status_text, event_time
  FROM dcim_events
  WHERE device_type = 'cctv'
    AND event_time > NOW() - INTERVAL '24 hours'
  ORDER BY serial_number, event_time DESC
)
SELECT
  COUNT(*) AS total_cctv,
  COUNT(*) FILTER (WHERE cctv_status_online = 1 OR cctv_status_text ILIKE 'online') AS online,
  COUNT(*) FILTER (WHERE COALESCE(cctv_status_online, 0) <> 1 AND COALESCE(cctv_status_text, '') NOT ILIKE 'online') AS not_online,
  MAX(event_time) AS last_event
FROM latest;
```

### 5.6 NVR

```sql
SELECT DISTINCT ON (serial_number)
  event_time,
  hostname,
  ip,
  serial_number,
  manufacturer,
  model,
  firmware,
  cctv_status_online,
  cctv_status_text,
  raw_tags,
  raw_fields,
  site,
  rack_name,
  asset_status
FROM dcim_events
WHERE device_type = 'nvr'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY serial_number, event_time DESC;
```

NVR storage fields from raw JSON:

```sql
SELECT
  event_time,
  hostname,
  serial_number,
  raw_fields->>'capacity' AS capacity,
  raw_fields->>'freeSpace' AS free_space,
  raw_fields->>'Status' AS hdd_status,
  raw_fields->>'cpuUtilization' AS cpu_utilization,
  raw_fields->>'memoryUsage' AS memory_usage,
  raw_fields
FROM dcim_events
WHERE device_type = 'nvr'
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY event_time DESC
LIMIT 100;
```

## 6. Query Relasi Perangkat → CMDB → Metrics

### 6.1 Semua data terkait satu serial number

```sql
WITH ident AS (
  SELECT :serial_number::text AS sn
), asset AS (
  SELECT *
  FROM unified_assets ua, ident
  WHERE ua.serial_number = ident.sn
), event_summary AS (
  SELECT
    device_type,
    hostname,
    ip,
    serial_number,
    COUNT(*) AS events_24h,
    MAX(event_time) AS last_event,
    ARRAY_AGG(DISTINCT measurement) AS measurements
  FROM dcim_events e, ident
  WHERE e.serial_number = ident.sn
    AND e.event_time > NOW() - INTERVAL '24 hours'
  GROUP BY device_type, hostname, ip, serial_number
)
SELECT
  es.*,
  a.ralph_id,
  a.ralph_endpoint,
  a.site,
  a.rack_name,
  a.asset_status,
  a.last_synced_at
FROM event_summary es
LEFT JOIN asset a USING (serial_number);
```

### 6.2 Perangkat ada di PostgreSQL tapi belum ada di `unified_assets`

```sql
WITH latest_events AS (
  SELECT DISTINCT ON (device_type, serial_number)
    device_type, hostname, ip, serial_number, manufacturer, model, MAX(event_time) OVER (PARTITION BY device_type, serial_number) AS last_event
  FROM dcim_events
  WHERE event_time > NOW() - INTERVAL '24 hours'
    AND serial_number IS NOT NULL
    AND serial_number NOT IN ('NO_SN', 'NO_IDENTIFIER', '')
  ORDER BY device_type, serial_number, event_time DESC
)
SELECT le.*
FROM latest_events le
LEFT JOIN unified_assets ua ON ua.serial_number = le.serial_number
WHERE ua.serial_number IS NULL
ORDER BY le.device_type, le.hostname;
```

### 6.3 Perangkat known stale > 30 menit

```sql
WITH latest AS (
  SELECT
    device_type,
    COALESCE(serial_number, hostname, ip::text) AS device_key,
    MAX(hostname) AS hostname,
    MAX(ip::text) AS ip,
    MAX(event_time) AS last_event
  FROM dcim_events
  WHERE event_time > NOW() - INTERVAL '7 days'
  GROUP BY device_type, COALESCE(serial_number, hostname, ip::text)
)
SELECT
  device_type,
  device_key,
  hostname,
  ip,
  last_event,
  NOW() - last_event AS age
FROM latest
WHERE last_event < NOW() - INTERVAL '30 minutes'
ORDER BY age DESC;
```

## 7. Query Discovery & Schema Exploration

### 7.1 List tables

```sql
SELECT table_schema, table_name
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY table_name;
```

### 7.2 List columns for a table

```sql
SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'public'
  AND table_name = :table_name
ORDER BY ordinal_position;
```

### 7.3 JSONB keys per device type

```sql
SELECT key, COUNT(*) AS count
FROM dcim_events e,
LATERAL jsonb_object_keys(e.raw_fields) AS key
WHERE e.device_type = :device_type
  AND e.event_time > NOW() - INTERVAL '24 hours'
GROUP BY key
ORDER BY count DESC, key;
```

### 7.4 Sample raw JSON by measurement

```sql
SELECT
  event_time,
  device_type,
  hostname,
  serial_number,
  measurement,
  jsonb_pretty(raw_tags) AS raw_tags,
  jsonb_pretty(raw_fields) AS raw_fields
FROM dcim_events
WHERE device_type = :device_type
  AND measurement = :measurement
  AND event_time > NOW() - INTERVAL '24 hours'
ORDER BY event_time DESC
LIMIT 5;
```

## 8. Agent Decision Guide

| Intent | First Query | Follow-up |
| :--- | :--- | :--- |
| User gives hostname/IP/SN | 4.1 flexible identifier | 4.5 raw sample, then device-type query |
| Need list active devices | 4.2 active summary | 4.6 join with CMDB |
| Need pipeline health | 4.3 device type health | 4.4 measurement coverage |
| Need server inventory | 5.1 server identity | 5.1 JSONB components + relational component tables |
| Need UPS status | 5.2 UPS latest | UPS trend query |
| Need NAS disk/volume | 5.3 NAS latest | NAS disk/volume metrics query |
| Need switch interface | 5.4 switch identity | Interface metrics + top errors |
| Need CCTV status | 5.5 CCTV latest | CCTV online/offline summary |
| Need NVR health/storage | 5.6 NVR latest | NVR raw storage fields |
| Need missing CMDB assets | 6.2 missing unified asset | `scripts/ralph_cmdb_sync.py` auto-register flow |
| Need stale devices | 6.3 stale query | Check `dcim-alerts` in Elasticsearch |

## 9. Notes for Future Agents

1. Use `dcim_events` as telemetry source of truth.
2. Use `unified_assets` as CMDB/cache lookup table, but check freshness via `last_synced_at`.
3. Prefer `serial_number` for joins; fallback order: `serial_number` → `ip` → `hostname`.
4. Always filter by time window. `dcim_events` is partitioned daily and can be large.
5. For server components, prefer JSONB columns in latest `dcim_events`; component relational tables remain useful for direct inventory lookups by IP.
6. For dashboard fields, prefer normalized columns when present; use `raw_fields` only when normalized column is missing.
7. CCTV count by hostname can look low because NVR/poller may group channels; use serial-level query for camera identities.
8. Kafka short sampling can false-warn because collectors run every 120 seconds. Verify with DB/ES counts and topic offsets.
