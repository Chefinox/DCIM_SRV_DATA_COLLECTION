# Commissioning & Decommissioning Automation Guide

> **Last Updated**: 2026-05-21  
> **Version**: v3.5.5  
> **Scope**: Auto-register DC assets to Ralph + stale-device alerting

## Status Saat Ini

Commissioning dan decommissioning sekarang semi-otomatis:

| Area | Status | Implementasi |
| :--- | :---: | :--- |
| New DC asset detection | ✅ Active | `scripts/ralph_cmdb_sync.py` membaca PostgreSQL `dcim_events` lalu auto-register asset missing di Ralph |
| Existing asset update | ✅ Active | Hostname, IP management, firmware, model, remarks, server components |
| CCTV registration | ⚠️ Separate flow | CCTV tetap Back Office Asset, pakai `scripts/register_cctv_to_ralph.py` |
| Stale/offline detection | ✅ Active | `scripts/dcim_threshold_alerter.py`, threshold 30 menit |
| Alert sink | ✅ Active | Elasticsearch index `dcim-alerts` |
| Service log | ✅ Active | `logs/threshold_alerts.log` |

## Commissioning Flow

### 1. Perangkat mulai mengirim telemetry

```text
Device → Telegraf/Script → Kafka Raw → Normalizer → Enrichment → PostgreSQL dcim_events
```

### 2. Ralph sync harian berjalan

Cron:

```text
0 2 * * * cd /home/infra/dcim_metrics_project && python3 scripts/ralph_cmdb_sync.py >> logs/ralph_cmdb_sync.log 2>&1
```

### 3. Jika serial number belum ada di Ralph

`scripts/ralph_cmdb_sync.py` membuat DC asset baru untuk device types berikut:

| Device Type | Ralph Model ID | Asset Type | Default Rack |
| :--- | ---: | :--- | ---: |
| `server` | 26 | Data Center Asset | 3 |
| `ups` | 34 | Data Center Asset | 3 |
| `nas` | 16 | Data Center Asset | 3 |
| `network_switch` | 6 | Data Center Asset | 3 |
| `nvr` | 18 | Data Center Asset | 3 |

Field minimal saat auto-register:

- `sn`
- `hostname`
- `model`
- `rack`
- `remarks` berisi IP, source, dan timestamp sync

### 4. Setelah asset dibuat

Sync lanjutan update detail device:

- Management IP / hostname
- Firmware
- Manufacturer / model remarks
- Server CPU/RAM/disk/NIC components
- Pruning komponen lama untuk server

## CCTV Exception

CCTV **tidak** auto-register lewat `ralph_cmdb_sync.py` karena asset type berbeda:

| CCTV | Nilai |
| :--- | :--- |
| Ralph asset type | Back Office Asset |
| Category | CCTV |
| Registration script | `scripts/register_cctv_to_ralph.py` |
| Sync behavior | Update metadata bila asset sudah ada |

Alasan: CCTV milik Back Office/Facility, bukan Data Center rack asset.

## Decommissioning / Stale Detection Flow

`dcim-threshold-alerter.service` menjalankan threshold checks + stale checks tiap 120 detik.

### Known devices

Daftar canonical hostname ada di `scripts/dcim_threshold_alerter.py` → `KNOWN_DEVICES`:

| Device Type | Expected Count |
| :--- | ---: |
| `server` | 5 |
| `ups` | 1 |
| `nas` | 6 |
| `network_switch` | 5 |
| `nvr` | 1 |

### Stale threshold

```text
STALE_THRESHOLD_MINUTES = 30
```

Jika device tidak punya event baru dalam 30 menit, alert dibuat:

| Field | Value |
| :--- | :--- |
| `alert_name` | `Device Not Reporting (<device_type>)` |
| `severity` | `warning` |
| `source` | `dcim-threshold-alerter` |
| Target index | `dcim-alerts` |

### Current validated log

```text
Checking 6 thresholds + stale device detection every 120s
Lookback window: 5m | Stale threshold: 30m
All clear - 6 thresholds + stale check passed
```

## Health Check Interpretation

### Kafka warning note

3-second Kafka sampling bisa false warning karena beberapa collector punya interval 120 detik. Jangan jadikan sample pendek sebagai bukti pipeline mati.

Gunakan sinyal berikut:

1. Consumer offsets naik di topic:
   - `dcim.raw.hardware.server`
   - `dcim.raw.power.ups`
   - `dcim.raw.storage.nas`
   - `dcim.raw.network.snmp`
   - `dcim.raw.device.isapi`
   - `dcim.normalized.events`
   - `dcim.enriched.events`
2. PostgreSQL count meningkat di `dcim_events`.
3. Elasticsearch count meningkat di `dcim-metrics-unified-*`.
4. Service logs tidak menunjukkan error berulang.

## Operational Commands

### Cek service

```bash
systemctl status dcim-threshold-alerter --no-pager
systemctl status dcim-normalizer dcim-sql-consumer dcim-kafka-es-sync --no-pager
```

### Cek stale alert log

```bash
tail -50 /home/infra/dcim_metrics_project/logs/threshold_alerts.log
```

### Cek alert di Elasticsearch

```bash
curl -k -u elastic:'PASSWORD' \
  'https://10.70.0.56:9200/dcim-alerts/_search?size=10&sort=@timestamp:desc'
```

### Cek data terbaru per device type di PostgreSQL

```sql
SELECT device_type, COUNT(*) total_events, COUNT(DISTINCT hostname) unique_hosts, MAX(event_time) last_event
FROM dcim_events
WHERE event_time > NOW() - INTERVAL '1 hour'
GROUP BY device_type
ORDER BY device_type;
```

### Dry-run logic note

Jangan membuat fake asset di Ralph untuk test tanpa approval. Validasi auto-register cukup lewat code review, syntax check, dan log produksi saat device baru benar-benar muncul.

## Log Paths

| Component | Log |
| :--- | :--- |
| Ralph sync | `/home/infra/dcim_metrics_project/logs/ralph_cmdb_sync.log` |
| Threshold/stale alerter | `/home/infra/dcim_metrics_project/logs/threshold_alerts.log` |
| Server inventory | `/home/infra/dcim_metrics_project/logs/server_inventory.log` → symlink ke `server_inventory_to_pg.log` |
| Telegraf | `/var/log/telegraf/telegraf.log` |

## Change Record

| Version | Date | Change |
| :--- | :--- | :--- |
| v3.5.5 | 2026-05-21 | Add DC asset auto-register, stale device alerting, Kafka health interpretation, logging path clarification |
