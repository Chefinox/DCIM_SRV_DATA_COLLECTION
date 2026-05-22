---
name: dcim-database-query-baseline
description: "Use when: querying DCIM PostgreSQL database dcim_sot; finding device data by hostname, IP, or serial number; checking dcim_events, unified_assets, server component tables, CMDB relationship, stale devices, missing CMDB assets, measurement coverage, or device health for server, ups, nas, network_switch, cctv, or nvr."
---

# DCIM Database Query Baseline

Use this skill before querying PostgreSQL `dcim_sot` for DCIM device data.

Primary long-form reference:

- `docs/development/34-database-query-baseline-for-agents.md`

## Database Baseline

| Item | Value |
| :--- | :--- |
| Host | `192.168.100.115` |
| Port | `5432` |
| Database | `dcim_sot` |
| Main telemetry table | `public.dcim_events` |
| CMDB/cache table | `public.unified_assets` |
| Server component tables | `public.dcim_server_disks`, `public.dcim_server_nics`, `public.dcim_server_processors`, `public.dcim_server_ram` |

Do not hardcode database passwords. Use environment variables, prompt-safe secret handling, `.pgpass`, or secret manager.

## Mandatory Query Rules

1. Always filter `dcim_events` by time window.
2. Prefer lookup key order: `serial_number` -> `ip` -> `hostname`.
3. Use `dcim_events` as telemetry source of truth.
4. Use `unified_assets` as CMDB/cache reference and verify `last_synced_at`.
5. Prefer normalized columns over `raw_fields` when available.
6. Use `raw_fields` and `raw_tags` only for discovery or fields not normalized yet.
7. Remember Kafka short sampling can false-warn because collectors run around every 120 seconds. Validate with PostgreSQL/Elasticsearch counts and Kafka offsets.

## Workflow

### 1. Classify user input

Determine whether user provided:

- hostname
- IP address
- serial number
- device type
- metric/measurement name
- health/completeness request
- CMDB/Ralph relationship request

### 2. Start with flexible identifier query

Use section `4.1` in `docs/development/34-database-query-baseline-for-agents.md` when input may be hostname, IP, or serial number.

Expected result fields:

- `device_type`
- `hostname`
- `ip`
- `serial_number`
- `manufacturer`
- `model`
- `site`
- `rack_name`
- `asset_status`
- `enrichment_status`
- `event_time`
- `source_topic`

### 3. Branch by device type

After `device_type` known, use matching baseline section:

| Device type | Baseline section | Purpose |
| :--- | :--- | :--- |
| `server` | `5.1` | identity, health, sensors, CPU/RAM/disk/NIC inventory |
| `ups` | `5.2` | battery, runtime, load, voltage, temperature |
| `nas` | `5.3` | system temp, disk temp/status, volume/disk metrics |
| `network_switch` | `5.4` | identity, interface status, octets, speed, errors |
| `cctv` | `5.5` | camera online/offline status and serial identity |
| `nvr` | `5.6` | NVR health/status and storage raw fields |

### 4. Join telemetry with CMDB/cache

Use section `4.6` or `6.1` when user asks:

- where device lives
- Ralph ID
- rack/site
- asset status
- CMDB mismatch
- source of metadata

Join preference:

1. `serial_number`
2. `ip`
3. `hostname`

### 5. Health and completeness checks

Use:

- section `4.2` for active device summary
- section `4.3` for data health per device type
- section `4.4` for measurement coverage
- section `6.3` for stale devices older than 30 minutes
- section `6.2` for devices in PostgreSQL but missing from `unified_assets`

### 6. Schema and JSONB discovery

Use section `7` when:

- column unknown
- source data shape unknown
- `raw_fields` needs inspection
- measurement-specific payload must be sampled

## Quick Decision Matrix

| User asks | First action | Follow-up |
| :--- | :--- | :--- |
| "Cari device X" | Section `4.1` | Section `4.5`, then device-specific section |
| "Cek health pipeline DB" | Section `4.3` | Section `4.4` |
| "List perangkat aktif" | Section `4.2` | Section `4.6` |
| "Cek CMDB/Ralph relation" | Section `4.6` | Section `6.1` |
| "Ada device belum masuk CMDB?" | Section `6.2` | inspect `scripts/ralph_cmdb_sync.py` |
| "Ada perangkat stale?" | Section `6.3` | check Elasticsearch index `dcim-alerts` |
| "Server inventory" | Section `5.1` | relational component tables by IP |
| "Switch port/interface" | Section `5.4` | top interface errors query |
| "CCTV/NVR status" | Section `5.5` or `5.6` | serial-level latest query |

## Safe Execution Pattern

Before running SQL from terminal:

1. Use environment variables for connection settings.
2. Avoid printing secrets.
3. Limit result size with `LIMIT` for raw samples.
4. Use recent time windows first: `1 hour`, `24 hours`, `7 days`, `30 days`.
5. For large scans, aggregate first before selecting raw rows.

Example environment baseline:

```bash
export PGHOST=192.168.100.115
export PGPORT=5432
export PGDATABASE=dcim_sot
export PGUSER=sot_admin
# PGPASSWORD from secure input/secret only
```

## Output Expectations

When answering user, summarize:

- matched device identity
- latest event age
- data source table/query section used
- CMDB/Ralph relation if checked
- anomalies: stale, missing CMDB, missing serial, no recent events, low measurement coverage
- next recommended operational check
