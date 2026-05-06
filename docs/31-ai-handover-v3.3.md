# 31. AI Agent Handover Document — v3.3 Session Summary

**Versi Dokumen**: 3.3.0 | **Tanggal**: 2026-05-04 | **Dibuat oleh**: Antigravity  
**Status**: ✅ Handover Aktif — Baca seluruh dokumen sebelum membuat perubahan apapun  
**Supersedes**: `docs/25-ai-handover-document.md` (v3.2.0)  
**Referensi Arsitektur**: `docs/19-kafka-pipeline-architecture.md`

---

## 1. Konteks Environment

- **Project Root**: `/home/infra/dcim_metrics_project/`
- **Host**: `srv-data-collection` (Linux Ubuntu, IP: `10.70.0.56`)
- **Architecture**: MT014 — Kafka-Centric Unified Pipeline (4-Layer)
- **Tech Stack**: Apache Kafka v3.4, Apache NiFi v1.24, FastAPI, Redis, PostgreSQL v15, Telegraf, Elasticsearch, Ralph CMDB

### Kredensial Produksi

| Service | User | Credential |
|---------|------|-----------|
| Redfish/BMC Lenovo XCC (server `10.50.0.2–6`) | `poller` | `F!tech0918` |
| SNMP v3 — APC UPS (`192.168.100.140`) | `hndept` | Auth: `Inovasi@0918` / Priv: `Inovasi@0918` |
| SNMP v3 — Synology NAS (`10.50.0.105–110`) | `hndept` | Auth/Priv: `F!tech0918` |
| PostgreSQL SOT | `sot_admin` | `Inovasi@0918` @ `192.168.101.73:5432` / DB: `dcim_sot` |
| Ralph CMDB API | Token | `60bcedc875ec7b03b983082655e473e9519d40d5` @ `http://192.168.101.73:8088` |
| Hikvision NVR/Cameras | `admin` | `qRvbi883=Zk[Q)@5` |

> [!WARNING]
> **BMC Lockout Risk (CRITICAL)**: Interval polling Redfish di `/etc/telegraf/telegraf.d/servers-redfish.conf` HARUS tetap ≥ **120 detik**. Menurunkan interval ini akan membekukan XCC BMC pada server Lenovo dan memerlukan intervensi fisik ke datacenter.

---

## 2. Status Pipeline Kafka (Terverifikasi 2026-05-04 21:00 WIB)

### Arsitektur 4-Layer
```
Layer 1 (Ingestion):   Perangkat fisik → Telegraf Producers → Kafka `dcim.raw.*`
Layer 2 (Normalize):   dcim-normalizer.service (Python V3) → `dcim.normalized.events`
Layer 3 (Enrich):      Apache NiFi → FastAPI :8000 → Redis :6379 → `dcim.enriched.events`
Layer 4 (Sink):        telegraf-consumer → Elasticsearch
                       dcim-sql-consumer → PostgreSQL `device_metrics`
```

### Status Service (semua aktif)

| Service | Status | PID | Keterangan |
|---------|--------|-----|-----------|
| `telegraf.service` | ✅ Running | 3886149 | Restart terakhir 16:13 WIB |
| `dcim-normalizer.service` | ✅ Running | 3974916 | Restart terakhir 18:28 WIB |
| `dcim-enrichment-api.service` | ✅ Running | 2839230 | Sejak 2026-04-30 |
| `dcim-redis-sync.service` | ✅ Running | 1798776 | Sejak 2026-04-28 |
| `telegraf-consumer.service` | ✅ Running | 3906783 | Restart terakhir 16:44 WIB |
| `dcim-sql-consumer.service` | ✅ Running | 1798444 | Sejak 2026-04-28 |
| Apache NiFi (`dcim-nifi`) | ✅ Running | 2863384 | Docker, port 8443 |
| Redis (`dcim-redis-cache`) | ✅ Running | — | Docker, port 6379, **104 keys** |
| Kafka (`kafka-broker`) | ✅ Running | — | Docker, port 9092 |

### Data Enrichment Health (5 menit terakhir saat verifikasi)

| Device Type | Enrichment Status | Event Count |
|------------|------------------|-------------|
| `server` | FULL | 330 |
| `network_switch` | FULL | 1106 |
| `nas` | FULL | 110 |
| `ups` | FULL | 5 |

**100% enrichment pada semua device type untuk jalur Kafka.**

### Layer 3: Enrichment Detail
- **Redis** diisi oleh `dcim-redis-sync.service` (delta sync setiap 5 menit)
- **Key format**: `asset:{serial_number_lowercase}`, TTL: 3600s
- **FastAPI** (`phase2/enrichment_api.py`): cek Redis → fallback SQL `unified_assets`
- **NiFi** memanggil `GET http://127.0.0.1:8000/enrich/{serial_number}` untuk setiap record

---

## 3. 🔴 MASALAH UTAMA: Ralph CMDB Auto-Update Bermasalah

> [!CAUTION]
> **`server_deep_sync.py` TIDAK ADA di crontab.** Sync otomatis ke Ralph CMDB berhenti sejak sekitar 09:08 WIB tanggal 2026-05-04. Data di Ralph CMDB mungkin sudah stale.

### Temuan

**Crontab aktif saat ini** (`crontab -l`):
```cron
*/10 * * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/server_redfish_to_pg.py >> /home/infra/dcim_metrics_project/logs/server_redfish_to_pg_cron.log 2>&1
0 1 * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/ralph_cmdb_sync.py >> /home/infra/dcim_metrics_project/logs/ralph_cmdb_sync_cron.log 2>&1
```

**Yang HILANG** (sesuai standar versioning doc `24-versioning-change-management-standard.md`):
```cron
# INI YANG HARUS ADA TAPI TIDAK:
*/5 * * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/server_deep_sync.py
```

**Bukti dari log**: `server_deep_sync.log` terakhir mencatat run jam 09:08:30 WIB, kemudian **berhenti total**. Tidak ada entri setelahnya.

### Script yang Terpengaruh

| Script | Fungsi | Status |
|--------|--------|--------|
| `scripts/server_deep_sync.py` | Sync hardware inventory server (CPU/RAM/Disk/NIC) ke Ralph CMDB via Redfish | ⚠️ **Tidak berjalan otomatis** |
| `scripts/ralph_cmdb_sync.py` | Bulk sync dari PostgreSQL `dcim_events` → Ralph (cron `0 1 * * *`) | ✅ Terjadwal (daily 01:00) |
| `scripts/server_redfish_to_pg.py` | Deep inventory Redfish → PostgreSQL langsung (bypass Kafka) | ✅ Terjadwal (setiap 10 menit, added this session) |

### Langkah Fixing untuk Agent Berikutnya

**Step 1: Verifikasi kondisi saat ini**
```bash
# Cek crontab aktif
crontab -l

# Cek apakah server_deep_sync masih bisa jalan manual
python3 /home/infra/dcim_metrics_project/scripts/server_deep_sync.py

# Cek log terakhir
tail -n 30 /home/infra/dcim_metrics_project/logs/server_deep_sync.log
```

**Step 2: Verifikasi Ralph CMDB (apakah data stale)**
```bash
# Cek via API apakah disk/RAM server sudah update
curl -s -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5" \
  "http://192.168.101.73:8088/api/data-center-assets/?sn=J901F8KE" | python3 -m json.tool | grep -E "hostname|firmware"

curl -s -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5" \
  "http://192.168.101.73:8088/api/disks/?base_object=141" | python3 -m json.tool | grep -c '"id"'
```

**Step 3: Restore crontab (setelah verifikasi manual berhasil)**
```bash
crontab -e
# Tambahkan baris ini:
*/5 * * * * /usr/bin/python3 /home/infra/dcim_metrics_project/scripts/server_deep_sync.py >> /home/infra/dcim_metrics_project/logs/server_deep_sync_cron.log 2>&1
```

**Step 4: Monitor setelah restore**
```bash
# Tunggu 5 menit, lalu cek log
tail -f /home/infra/dcim_metrics_project/logs/server_deep_sync.log
```

### Detail Script `server_deep_sync.py` (V7)

**File**: `/home/infra/dcim_metrics_project/scripts/server_deep_sync.py`  
**Versi**: V7 (Robust Pruning + Pagination Fix)  
**Credentials**: `poller` / `F!tech0918`

**Yang dilakukan per server**:
| Komponen | Sumber Redfish | Ralph Endpoint |
|----------|---------------|----------------|
| Hostname | `Chassis/1 → Location.PostalAddress.Name` | `PATCH /api/data-center-assets/{id}/` |
| Firmware XCC | `Managers/1 → FirmwareVersion` | `firmware_version` |
| BIOS | `Systems/1 → BiosVersion` | `bios_version` |
| Management IP | IP polling (`10.50.0.x`) | `POST /api/ipaddresses/` (is_management=True) |
| CPU | `Systems/1/Processors` | `/api/processors/` |
| RAM | `Systems/1/Memory → VendorID` | `/api/memory/` |
| Disk | `Systems/1/Storage/.../Drives → Name + PhysicalLocation.PartLocation.LocationOrdinalValue` | `/api/disks/` (model, size, SN, slot, firmware) |
| NIC | `Systems/1/EthernetInterfaces` | `/api/ethernets/` (label, MAC, speed) |

**Business Rules kritis**:
1. Serial Number = Primary Key, JANGAN di-overwrite
2. `ralph_get_all()` WAJIB digunakan untuk pagination (limit=200) — tidak boleh default 10
3. Pruning aktif: delete disk/NIC lama yang tidak ada di Redfish terbaru

**Server yang dicover**:
| IP | Hostname | SN | Ralph Asset ID |
|----|----------|----|---------------|
| 10.50.0.2 | SERVER-HCI-01 | J901GKXY | 138 |
| 10.50.0.3 | SERVER-HCI-02 | J901GKXX | 139 |
| 10.50.0.4 | SERVER-HCI-03 | J901GKXZ | 140 |
| 10.50.0.5 | SERVER-RENDER-01 | J901F8KE | 141 |
| 10.50.0.6 | SERVER-RENDER-02 | J901F8KD | 142 |

---

## 4. Masalah Terbuka Lainnya

| # | Masalah | Status | Tindakan yang Diperlukan |
|---|---------|--------|------------------------|
| 1 | **CCTV/NVR data gap** | ⚠️ **OPEN** | Tidak ada data `cctv`/`nvr` sejak 04:29 WIB. Tidak ada systemd unit `hikvision-poller` — kemungkinan via Telegraf `inputs.exec`. Cek: `sudo journalctl -u telegraf --since "2026-05-04 04:00" \| grep -i exec`. Script: `scripts/hikvision_poller.py`. Kamera di jaringan `192.168.1.x`. |
| 2 | **`server_deep_sync.py` tidak di crontab** | 🔴 **CRITICAL** | Lihat Section 3 — restore crontab entry |
| 3 | **Test data server `10.200.0.x`** | ℹ️ LOW | 60+ server dummy di `dcim_events` dengan `event_time` terakhir 2026-04-29. Bisa di-cleanup tapi tidak urgent. |
| 4 | **UPS SNMP direct-test timeout** | ℹ️ Monitor | `192.168.100.140` tidak punya direct route tapi data tetap masuk via Telegraf (60 events/jam). Jangan ubah konfigurasi Telegraf. |
| 5 | **NiFi consumer group rebalance** | ℹ️ Normal | Log broker menunjukkan rebalance pada restart service. Normal, monitor jika lag > 0 berkepanjangan. |

---

## 5. Perbaikan yang Dilakukan di Session Ini (2026-05-04)

| File | Perubahan | Alasan |
|------|-----------|--------|
| `scripts/server_redfish_to_pg.py` | Tambah enrichment lookup dari `unified_assets` sebelum INSERT ke `dcim_events`. Kolom `site`, `rack_name`, `enrichment_status` kini diisi. | Script ini menulis langsung ke PostgreSQL (bypass Kafka/NiFi), sehingga perlu enrichment sendiri. |
| `scripts/dcim_inventory_poller.py` | Fix typo: `F!tech@0918` → `F!tech0918` untuk `NAS_PASS_REST` dan `NAS_PASS_SNMP` | Typo menyebabkan kegagalan polling NAS via REST/SNMP |
| Crontab | Tambah `server_redfish_to_pg.py` setiap 10 menit | Agar deep inventory (disk/RAM/NIC snapshot) berjalan otomatis |

---

## 6. Prioritas Pekerjaan untuk Agent Berikutnya

### 🔴 HIGH (Selesaikan Lebih Dulu)
1. **Restore crontab `server_deep_sync.py`** — Lihat Section 3, Step 1–4
2. **Diagnose CCTV data gap** — Mengapa `hikvision_poller.py` berhenti sejak 04:29 WIB

### 🟡 MEDIUM
3. **UPS Auto-Sync ke Ralph** — Battery health, load, status via SNMP → Ralph custom fields
4. **NAS Auto-Sync ke Ralph** — Volume sizes, disk temps → Ralph
5. **MikroTik Auto-Sync ke Ralph** — Interface stats, firmware → Ralph
6. **AI/ML Feature Export** — Lihat `docs/30-ai-ml-preparation-backlog.md`. Target: export NULL-free dari `dcim_events` untuk ML pipeline

### 🟢 LOW
7. Cleanup test records `10.200.0.x` di `dcim_events`
8. Crontab consolidation — Semua sync script ke satu orchestrator

---

## 7. Lokasi File Penting

| Fungsi | Path |
|--------|------|
| Arsitektur pipeline | `docs/19-kafka-pipeline-architecture.md` |
| Dokumen ini (sebelumnya) | `docs/25-ai-handover-document.md` (v3.2.0) |
| Backlog AI/ML | `docs/30-ai-ml-preparation-backlog.md` |
| Ralph auto-update blueprint | `docs/29-ralph-auto-update-capabilities.md` |
| BMC lockout incident | `docs/28-bmc-lockout-incident.md` |
| Telegraf configs | `/etc/telegraf/telegraf.d/` |
| Python normalizer | `scripts/dcim_normalizer.py` |
| Metric mapping | `configs/metric_mapping.json` |
| Enrichment API | `phase2/enrichment_api.py` |
| CMDB→Redis sync | `phase2/cmdb_to_cache_sync.py` |
| Kafka→PostgreSQL consumer | `phase2/dcim_postgres_consumer_v2.py` |
| Server deep inventory → PG | `scripts/server_redfish_to_pg.py` |
| Server CMDB → Ralph | `scripts/server_deep_sync.py` |
| Hikvision CCTV poller | `scripts/hikvision_poller.py` |
| NAS inventory poller | `/usr/local/bin/nas_inventory_poller.py` |
| Multi-device inventory poller | `scripts/dcim_inventory_poller.py` |
| Log directory | `logs/` |

---

## 8. Quick Health Check Commands

```bash
# Status semua service
sudo systemctl status telegraf dcim-normalizer dcim-enrichment-api dcim-redis-sync telegraf-consumer dcim-sql-consumer

# Redis cache health
docker exec dcim-redis-cache redis-cli DBSIZE
docker exec dcim-redis-cache redis-cli GET "asset:j901f8ke"

# Kafka consumer groups
docker exec kafka-broker /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --all-groups \
  | grep -E "nifi-enrichment|telegraf_unified|dcim_python"

# Live enrichment check (DB)
PGPASSWORD='Inovasi@0918' psql -h 192.168.101.73 -U sot_admin -d dcim_sot \
  -c "SELECT device_type, enrichment_status, COUNT(*) FROM dcim_events WHERE event_time > NOW() - INTERVAL '5 minutes' GROUP BY 1,2 ORDER BY 1,2;"

# Cek data gap per device type
PGPASSWORD='Inovasi@0918' psql -h 192.168.101.73 -U sot_admin -d dcim_sot \
  -c "SELECT device_type, ip, MAX(event_time) FROM dcim_events GROUP BY device_type, ip ORDER BY MAX(event_time) DESC;"

# Test enrichment API
curl -s http://localhost:8000/enrich/J901F8KE

# Cek crontab aktif
crontab -l

# Cek apakah server_deep_sync masih jalan
tail -n 10 /home/infra/dcim_metrics_project/logs/server_deep_sync.log

# NiFi UI: https://localhost:8443/nifi (accept self-signed cert)
```

---

## 9. Changelog Versi

| Versi | Tanggal (WIB) | Perubahan | Agent |
|-------|--------------|-----------|-------|
| **v3.3.0** | 2026-05-04 21:00 | Session: Verifikasi penuh pipeline. Fix enrichment `server_redfish_to_pg.py`. Fix NAS credential typo. Identifikasi CCTV gap. Temukan `server_deep_sync.py` hilang dari crontab (Ralph CMDB tidak update sejak 09:08 WIB). Tambah `server_redfish_to_pg.py` ke cron (setiap 10 menit). | Antigravity |
| **v3.2.0** | 2026-05-04 00:05 | `server_deep_sync.py` V7: Pagination fix, Robust Pruning, Ethernet Speed mapping. Crontab `*/5 * * * *` aktif. | Antigravity |
| **v3.1.x** | 2026-05-03 | `server_deep_sync.py` iterasi V1–V6. | Antigravity |
| **v3.0.2** | 2026-04-29 | Normalisasi hostname (hapus prefix FALAH01-). | Antigravity |
| **v3.0.1** | 2026-04-29 | Migrasi akun Redfish ke `poller`, safe interval 120s. | Antigravity |
| **v3.0.0** | 2026-04-28 | MT014 Unified Kafka Pipeline baseline. | Antigravity |

---

**Dibuat oleh**: Antigravity (DCIM Pipeline Stabilization Agent)  
**Tanggal Session**: 2026-05-04  
**Supersedes**: `docs/25-ai-handover-document.md` (v3.2.0)  
**Review berikutnya**: Sebelum perubahan credentials atau restart service apapun
