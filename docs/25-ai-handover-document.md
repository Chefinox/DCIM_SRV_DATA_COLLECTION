# AI Agent Handover Document: DCIM Telemetry & CMDB Pipeline

> [!IMPORTANT]
> **To the successor AI Agent**: This environment is on version **v3.2.0**. A fully automated server CMDB sync pipeline (`server_deep_sync.py`) is now active via crontab. Read all sections carefully before making any changes.

---

## 1. Environment Quick Context

- **Project Root**: `/home/infra/dcim_metrics_project/`
- **Architecture**: MT014 (Kafka-Centric Unified Pipeline)
- **Primary Tech Stack**: Apache NiFi, Kafka (v3.4), PostgreSQL (v15), Redis, FastAPI, Telegraf, Ralph CMDB.
- **OS / Host**: Linux (`srv-data-collection`)
- **Credentials**:
  - BMC/XCC (Redfish): `poller` / `F!tech0918` — for all servers `10.50.0.2–6`
  - Ralph API Token: `60bcedc875ec7b03b983082655e473e9519d40d5`
  - Ralph Web: `http://192.168.101.73:8088`

---

## 2. Critical Safety Protocols

> [!WARNING]
> **BMC Lockout Risk**: Redfish polling interval MUST remain at **≥ 120 seconds**. Lowering this will freeze XCC BMC on Lenovo servers, requiring physical intervention.

- **Config**: `/etc/telegraf/telegraf.d/servers-redfish.conf`
- **Redfish base URL pattern**: `https://10.50.0.X/redfish/v1/`
- **Credentials for Redfish**: `poller` / `F!tech0918`

---

## 3. Telemetry Pipeline Status

- **NiFi Enrichment**: Fully operational. Consumer group `nifi-enrichment-group` on `dcim.normalized.events` → 0 lag.
- **Data Flow**: `Redfish/SNMP → Telegraf → Kafka (dcim.normalized.events) → NiFi → Kafka (dcim.enriched.events) → PostgreSQL + Elasticsearch`
- **Enrichment API**: FastAPI on port `8000`. Hybrid lookup: Redis Cache → SQL `unified_assets` fallback.
- **Naming Standard**: Legacy `FALAH01-` prefix removed. Hostnames sourced from Redfish `Location.PostalAddress.Name`.

---

## 4. Server CMDB Auto-Sync (NEW — v3.2.0)

### Script

**File**: `/home/infra/dcim_metrics_project/scripts/server_deep_sync.py`
**Current Version**: V7 (Robust Pruning + Pagination Fix)

### What It Does

Polls each server's Redfish API and syncs hardware components to Ralph CMDB:

| Component     | Redfish Source                                                                                 | Ralph Field                               |
| ------------- | ---------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Hostname      | `Chassis/1 → Location.PostalAddress.Name`                                                      | `hostname`, `management_hostname`         |
| Firmware      | `Managers/1 → FirmwareVersion`                                                                 | `firmware_version`                        |
| BIOS          | `Systems/1 → BiosVersion`                                                                      | `bios_version`                            |
| Management IP | Polling IP (`10.50.0.x`)                                                                       | `ipaddresses` (is_management=True)        |
| CPU           | `Systems/1/Processors`                                                                         | `processors`                              |
| RAM           | `Systems/1/Memory` → `VendorID`                                                                | `memory`                                  |
| Disks         | `Systems/1/Storage/.../Drives` → `Name` + `PhysicalLocation.PartLocation.LocationOrdinalValue` | `disks` (model, size, SN, slot, firmware) |
| NICs          | `Systems/1/EthernetInterfaces`                                                                 | `ethernets` (label, MAC, speed)           |

### Key Business Rules

1. **Serial Number is Primary Key** — Never overwrite SN.
2. **Management IP is NOT overwritten** from manual input — it is auto-set from polling IP.
3. **Empty slots are skipped** — Only populated hardware is registered.
4. **Pruning is active** — Obsolete/duplicate components are deleted on each run using `ralph_get_all()` which handles API pagination (limit=200).
5. **Custom fields `power_consumption` and `device_temperature` are cleared** on each sync (legacy fields no longer used for servers).

### Automation

```
Crontab: */5 * * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/server_deep_sync.py
Log: /home/infra/dcim_metrics_project/logs/server_deep_sync.log
Cron Log: /home/infra/dcim_metrics_project/logs/server_deep_sync_cron.log
```

### Servers Covered

| IP        | Hostname         | Asset ID | SN       |
| --------- | ---------------- | -------- | -------- |
| 10.50.0.2 | SERVER-HCI-01    | 138      | J901GKXY |
| 10.50.0.3 | SERVER-HCI-02    | 139      | J901GKXX |
| 10.50.0.4 | SERVER-HCI-03    | 140      | J901GKXZ |
| 10.50.0.5 | SERVER-RENDER-01 | 141      | J901F8KE |
| 10.50.0.6 | SERVER-RENDER-02 | 142      | J901F8KD |

### Expected Disk Counts (Reference)

- HCI servers (10.50.0.2–4): **12 disks** each (4x SSD + 8x HDD + varies)
- Render servers (10.50.0.5–6): **4 disks** each (4x SSD)

---

## 5. Known Issues & Gotchas

| Issue                                              | Status         | Notes                                          |
| -------------------------------------------------- | -------------- | ---------------------------------------------- |
| Ralph API pagination default=10                    | ✅ Fixed (V7)  | `ralph_get_all()` handles all pages            |
| Duplicate disks from old model names (AL15SEB24EQ) | ✅ Cleaned     | Manual DELETE + pruning active                 |
| Management hostname mismatch                       | ✅ Fixed       | Sourced from IPAddress object, not asset field |
| Custom fields not clearing                         | ✅ Fixed       | Pass `null` in `custom_fields` dict            |
| BMC lockout if polling < 120s                      | ⚠️ Active Risk | Do NOT change Telegraf interval                |

---

## 6. Next Planned Steps (Priority Order)

1. **UPS Auto-Sync** via SNMP — battery health, load, output status → Ralph custom fields
2. **Mikrotik Switch Auto-Sync** via REST API / SNMP — interfaces, firmware, uptime → Ralph
3. **NAS Auto-Sync** — Synology/QNAP API → storage volumes, temperatures
4. **NVR/CCTV** — Basic data only (IP, hostname, firmware if available via ONVIF)
5. **Crontab consolidation** — All device sync scripts into a single orchestrator

### Skills Required for Next Agent

- Python 3 + `requests` library (REST/SNMP)
- SNMP v2c/v3 querying (`pysnmp` or `easysnmp`)
- Mikrotik RouterOS REST API (`/rest/` endpoint)
- Ralph CMDB API (see blueprint: `docs/29-ralph-auto-update-capabilities.md`)
- Understanding of Ralph data model: `base-objects`, `ethernets`, `ipaddresses`, custom fields
- Pagination handling for REST APIs (always use `limit=200`)

---

## 7. Maintenance & Versioning

- **Current Version**: `v3.2.0` (2026-05-04)
- **Version Control**: `git log --oneline --graph --all` in `/home/infra/dcim_metrics_project/`
- **Services**:
  ```bash
  systemctl status dcim-normalizer
  systemctl status dcim-enrichment-api
  systemctl status telegraf-consumer
  crontab -l  # Check active sync jobs
  ```

---

**Prepared by**: Antigravity (DCIM CMDB Sync Agent)
**Session Date**: 2026-05-04
**Supersedes**: Version dated 2026-04-29
