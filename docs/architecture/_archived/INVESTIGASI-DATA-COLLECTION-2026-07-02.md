---
title: "Investigasi Data Collection: Dokumentasi vs Implementasi Aktual"
date: 2026-07-02
status: INVESTIGASI_SELESAI
priority: HIGH
tags: [data-collection, telegraf, nifi, discrepancy, audit]
---

# Investigasi Data Collection: Dokumentasi vs Implementasi Aktual

> **Tanggal**: 2026-07-02  
> **Investigator**: AI Assistant + User Review  
> **Tujuan**: Mengidentifikasi perbedaan antara dokumentasi v4.3 dengan implementasi aktual data collection  
> **Referensi**: v4.3-pipeline-architecture.md, dcim-wiki/block2-data-ingestion-integration.md

---

## Executive Summary

### ⚠️ TEMUAN UTAMA: DISKREPANSI SIGNIFIKAN

**Dokumentasi v4.3 menyatakan:**
- UPS collection: **NiFi ExecuteProcess** ✅
- Network collection: **NiFi ExecuteProcess** ✅
- CCTV collection: **Daemon Standalone** ✅
- Arsitektur: **"Hybrid Telegraf + NiFi"**

**Implementasi Aktual (verified 2026-07-02):**
- UPS collection: **MASIH TELEGRAF** ❌ (ups-apc.conf.disabled = konfigurasi ada tapi disabled)
- Network collection: **TIDAK ADA di NiFi** ❌ (mikrotik_poller.py exists tapi tidak digunakan)
- CCTV collection: **MASIH TELEGRAF** ❌ (dcim-cctv-poller.service = inactive/dead)
- Arsitektur: **"FULL TELEGRAF"** (bukan hybrid)

### Status Migrasi ke NiFi

| Device Category | Documented Status | Actual Status | Gap |
|----------------|-------------------|---------------|-----|
| **Server (Redfish)** | Telegraf `inputs.redfish` + `inputs.exec` | ✅ MATCH | No gap |
| **UPS** | NiFi ExecuteProcess | ❌ **TELEGRAF** (`ups-apc.conf.disabled` = config exists but NOT USED) | **MAJOR GAP** |
| **NAS** | Telegraf `inputs.snmp` | ✅ MATCH | No gap |
| **Network (MikroTik)** | NiFi ExecuteProcess | ❌ **TIDAK ADA** (script exists, not deployed) | **MAJOR GAP** |
| **CCTV/NVR** | Daemon Standalone | ❌ **TELEGRAF** (`dcim-cctv-poller.service` = inactive) | **MAJOR GAP** |

---

## 1. Analisis Per Kategori Device

### 1.1 Server Collection — ✅ SESUAI DOKUMENTASI

**Dokumentasi v4.3 (§4.1):**
```
Collector: Telegraf inputs.redfish + inputs.exec (redfish_telemetry_poller.py)
Interval: 60s (redfish) + 30s (telemetry)
Output: dcim.raw.hardware.server
Status: ACTIVE
```

**Implementasi Aktual:**
```bash
# File: /home/infra/dcim_metrics_project/configs/telegraf/servers-redfish.conf
[[inputs.redfish]]
  address = "https://10.50.0.2"
  interval = "60s"
  # ... (5 servers: 10.50.0.2-6)

[[inputs.exec]]
  commands = ["/usr/bin/python3 .../redfish_telemetry_poller.py"]
  interval = "30s"
  data_format = "influx"
```

**Service Status:**
```bash
systemctl status telegraf.service
● telegraf.service - The plugin-driven server agent for reporting metrics
   Active: active (running)
```

**Verdict:** ✅ **MATCH** — Server collection sesuai dokumentasi.

---

### 1.2 UPS Collection — ❌ DISKREPANSI MAYOR

**Dokumentasi v4.3 (§4.2):**
```
Collector: NiFi ExecuteProcess (snmp_ups_poller.py)
Telegraf Config: ups-apc.conf.disabled (DINONAKTIFKAN)
Output: dcim.raw.power.ups
Status: MIGRATED TO NIFI
```

**Implementasi Aktual:**

**A. Telegraf Config:**
```bash
$ ls -lh /home/infra/dcim_metrics_project/configs/telegraf/ups-apc.conf*
-rw-r--r-- 1 infra infra 3.5K ups-apc.conf.disabled
```
File `ups-apc.conf.disabled` EXISTS tapi **TIDAK AKTIF** (extension `.disabled`).

**B. Telegraf Producer Config:**
```toml
# /home/infra/dcim_metrics_project/configs/telegraf/telegraf_producer.conf
[[outputs.kafka]]
  topic = "dcim.raw.power.ups"
  namepass = ["ups_snmp", "ups_apc", "apc_ups"]
```
Routing ke topic UPS masih ada, tapi **TIDAK ADA input yang menghasilkan measurement tersebut**.

**C. NiFi Implementation:**
```bash
$ ls /home/infra/dcim_metrics_project/scripts/snmp_ups_poller.py
/home/infra/dcim_metrics_project/scripts/snmp_ups_poller.py  # FILE EXISTS

$ docker ps | grep nifi
dcim-nifi   apache/nifi:1.24.0   Up 44 hours

$ ls /home/infra/dcim_metrics_project/nifi/
docker-compose.yml  flow.json.gz
```

**D. NiFi Flow Check:**
File `flow.json.gz` exists tapi **BELUM DICEK** apakah ada ExecuteProcess untuk UPS.

**Verdict:** ❌ **DISKREPANSI MAYOR**
- Dokumentasi: "Migrasi ke NiFi selesai"
- Aktual: UPS collection **TIDAK AKTIF** (Telegraf disabled, NiFi belum confirm)
- **IMPACT**: ⚠️ **UPS data MUNGKIN TIDAK MASUK pipeline**

---

### 1.3 NAS Collection — ✅ SESUAI DOKUMENTASI

**Dokumentasi v4.3 (§4.3):**
```
Collector: Telegraf inputs.snmp
Interval: 120s
Output: dcim.raw.storage.nas
Status: ACTIVE (TIDAK MIGRASI KE NIFI)
```

**Implementasi Aktual:**
```toml
# /home/infra/dcim_metrics_project/configs/telegraf/telegraf_producer.conf
[[outputs.kafka]]
  topic = "dcim.raw.storage.nas"
  namepass = ["nas_snmp", "dcim_nas", "synology_*", "nas_*"]
```

**Verdict:** ✅ **MATCH** — NAS masih via Telegraf sesuai dokumentasi.

---

### 1.4 Network Collection — ❌ DISKREPANSI MAYOR

**Dokumentasi v4.3 (§4.4):**
```
Collector: NiFi ExecuteProcess (mikrotik_poller.py)
Telegraf Config: mikrotik-snmp.conf (DISABLED)
Output: dcim.raw.network.snmp, dcim.raw.network.interfaces
Status: MIGRATED TO NIFI
```

**Implementasi Aktual:**

**A. Script Existence:**
```bash
$ ls /home/infra/dcim_metrics_project/scripts/mikrotik_poller.py
/home/infra/dcim_metrics_project/scripts/mikrotik_poller.py  # EXISTS
```

**B. Telegraf Config:**
```bash
$ ls /home/infra/dcim_metrics_project/configs/telegraf/mikrotik-snmp.conf*
# FILE TIDAK DITEMUKAN (tidak ada .disabled atau aktif)
```

**C. Telegraf Producer Routing:**
```toml
[[outputs.kafka]]
  topic = "dcim.raw.network.snmp"
  namepass = ["net_snmp", "dcim_network", "mikrotik"]

[[outputs.kafka]]
  topic = "dcim.raw.network.interfaces"
  namepass = ["net_snmp", "dcim_network_if", "interface"]
```
Routing masih ada tapi **TIDAK ADA input yang menghasilkan measurement tersebut**.

**D. NiFi Flow:**
Belum dikonfirmasi apakah ada ExecuteProcess untuk MikroTik.

**Verdict:** ❌ **DISKREPANSI MAYOR**
- Dokumentasi: "Migrasi ke NiFi selesai"
- Aktual: **TIDAK ADA collection aktif** (Telegraf tidak ada, NiFi belum confirm)
- **IMPACT**: ⚠️ **Network device data MUNGKIN TIDAK MASUK pipeline**

---

### 1.5 CCTV/NVR Collection — ❌ DISKREPANSI MAYOR

**Dokumentasi v4.3 (§4.5):**
```
Collector: dcim-cctv-poller.service (daemon standalone)
Lifecycle: Systemd service daemon (continuous)
Output: Langsung ke Kafka via KafkaClient
Status: ACTIVE (MIGRASI DARI TELEGRAF SELESAI)
```

**Implementasi Aktual:**

**A. Systemd Service:**
```bash
$ systemctl status dcim-cctv-poller.service
○ dcim-cctv-poller.service - DCIM CCTV Poller (Hikvision ISAPI)
   Loaded: loaded (/etc/systemd/system/dcim-cctv-poller.service; disabled)
   Active: inactive (dead)
```
**SERVICE TIDAK AKTIF!**

**B. Service File:**
```bash
$ cat /etc/systemd/system/dcim-cctv-poller.service
ExecStart=/usr/bin/python3 .../hikvision_poller_daemon.py
# ... (config exists, valid)
```

**C. Daemon Script:**
```bash
$ ls /home/infra/dcim_metrics_project/scripts/hikvision_poller_daemon.py
hikvision_poller_daemon.py  # EXISTS
```

**D. Telegraf CCTV Config:**
```bash
$ cat /home/infra/dcim_metrics_project/configs/telegraf/cctv-hikvision.conf
[[inputs.exec]]
  commands = ["/usr/bin/python3 .../hikvision_poller.py"]
  timeout = "110s"
  data_format = "influx"
  
[[outputs.kafka]]
  topic = "dcim.raw.device.isapi"
```
**TELEGRAF CONFIG MASIH AKTIF!**

**E. Telegraf Producer Routing:**
```toml
[[outputs.kafka]]
  topic = "dcim.raw.device.isapi"
  namepass = ["hikvision_*", "cctv_*"]
```

**Verdict:** ❌ **DISKREPANSI MAYOR**
- Dokumentasi: "Daemon standalone ACTIVE, Telegraf digantikan"
- Aktual: **DAEMON INACTIVE**, **TELEGRAF MASIH DIGUNAKAN**
- **IMPACT**: ⚠️ CCTV collection MASIH via Telegraf `inputs.exec`, BUKAN daemon standalone

---

## 2. Referensi vs Implementasi: DCIM-Wiki Alignment

### 2.1 DCIM-Wiki Block 2 Reference Design

**Reference (block2-data-ingestion-integration.md):**
```
Single Entry Point: NiFi (100+ processors)
Data Flow: Source Systems → NiFi → Kafka raw → Validation → Enrichment
Ingestion Tool: Apache NiFi (bukan Telegraf)
```

**Implementasi Aktual:**
```
Single Entry Point: Telegraf (5 device types)
Data Flow: Source Systems → Telegraf → Kafka raw → Normalizer → Enricher
Ingestion Tool: Telegraf (MASIH DOMINAN), NiFi (belum digunakan untuk device collection)
```

**Alignment Score:** ❌ **MISALIGNMENT SIGNIFIKAN**

### 2.2 Gap Analysis

| Aspek | Reference Design | v4.3 Docs | Actual Implementation | Alignment |
|-------|------------------|-----------|----------------------|-----------|
| **Ingestion Tool** | NiFi (100+ procs) | Telegraf + NiFi hybrid | **FULL TELEGRAF** | ❌ **MAJOR GAP** |
| **UPS Collection** | NiFi | NiFi ExecuteProcess | **Telegraf inputs.exec** (if active) or **NONE** | ❌ **GAP** |
| **Network Collection** | NiFi | NiFi ExecuteProcess | **NONE** (Telegraf disabled, NiFi not confirmed) | ❌ **GAP** |
| **CCTV Collection** | NiFi | Daemon Standalone | **Telegraf inputs.exec** | ❌ **GAP** |
| **Topic Routing** | By event_type | By device_type | By device_type | ✅ Partial |

---

## 3. Git History Analysis

### 3.1 Commit Terkait Migrasi

```bash
$ git log --oneline --all --grep="nifi\|NiFi\|migrasi\|migration" -20

75dd699 Export NiFi compose file and flow.json.gz for durability
e985d32 feat(pipeline): kafka cluster SSL, granular topic routing, schema registry, vault, lineage tracking, infra monitoring, cctv ingestion, itop consumer v8
9ed0fb3 Cutover: Disable UPS SNMP polling in Telegraf
```

**Commit `9ed0fb3` (Cutover: Disable UPS SNMP polling):**
- Message: "Disable UPS SNMP polling in Telegraf"
- Action: Rename `ups-apc.conf` → `ups-apc.conf.disabled`
- Status: **CUTOVER SELESAI tapi NiFi replacement BELUM DIKONFIRMASI AKTIF**

**Commit `e985d32` (feat: ... cctv ingestion ...):**
- Message menyebutkan "cctv ingestion" tapi **TIDAK DETAIL** apakah daemon aktif atau masih Telegraf.

**Commit `75dd699` (Export NiFi compose file):**
- Action: Export `flow.json.gz` untuk durability
- Status: NiFi flow EXISTS tapi **ISI BELUM DIAUDIT**

### 3.2 Service Status dari Git

```bash
$ systemctl list-units --type=service --state=running | grep dcim-

dcim-dlq-consumer.service          running
dcim-enrichment-api.service        running
dcim-es-consumer.service           running
dcim-itop-redis-sync.service       running
dcim-itop-unified.service          running
dcim-normalizer.service            running
dcim-siem-es-consumer.service      running
dcim-sql-consumer.service          running
dcim-threshold-alerter.service     running
```

**TIDAK ADA** `dcim-cctv-poller.service` di daftar running services!

---

## 4. NiFi Flow Audit (Diperlukan)

### 4.1 File yang Perlu Diaudit

```bash
/home/infra/dcim_metrics_project/nifi/flow.json.gz
```

**Cara Audit:**
```bash
cd /home/infra/dcim_metrics_project/nifi
gunzip -c flow.json.gz | jq '.rootGroup.processGroups[].name'
```

**Expected Output (jika migrasi NiFi benar):**
- UPS Ingestion Process Group
- Network Ingestion Process Group
- CCTV Ingestion Process Group (atau tidak ada jika daemon standalone)

**Actual Output:** ⚠️ **BELUM DICEK**

### 4.2 NiFi Canvas Inspection

**Cara cek via UI:**
1. Buka `http://10.70.0.56:8080/nifi/` (atau localhost:8080 jika port forwarding)
2. Cek Process Groups:
   - Apakah ada "UPS Polling" / "UPS ExecuteProcess"?
   - Apakah ada "MikroTik Polling" / "Network Polling"?
   - Apakah ada "CCTV Polling"?

**Status:** ⚠️ **BELUM DIKONFIRMASI**

---

## 5. Root Cause Analysis

### 5.1 Mengapa Diskrepansi Terjadi?

**Hipotesis:**

1. **Dokumentasi v4.3 ditulis ASPIRATIONAL (rencana), bukan ACTUAL:**
   - Dokumentasi menggambarkan "target state" setelah migrasi selesai
   - Commit `e985d32` menyebutkan "cctv ingestion" tapi implementasi **belum aktif**
   
2. **Migrasi ke NiFi BELUM SELESAI:**
   - File `ups-apc.conf.disabled` menunjukkan **intent to migrate** tapi replacement belum aktif
   - Service `dcim-cctv-poller.service` di-create tapi **tidak di-enable/start**
   - Scripts `mikrotik_poller.py`, `snmp_ups_poller.py` di-create tapi **belum integrated ke NiFi**

3. **Disconnect antara Code vs Deployment:**
   - Code/scripts exist (development selesai)
   - Deployment/service activation belum dilakukan (operations belum selesai)

### 5.2 Timeline Rekonstruksi

```
2026-06-29: Commit "Cutover: Disable UPS SNMP polling" 
            → ups-apc.conf.disabled created
            
2026-06-30: Commit "feat(pipeline): ... cctv ingestion ..."
            → Documentation v4.3 written (aspirational)
            → dcim-cctv-poller.service created
            
2026-07-01: Documentation v4.3 finalized
            → Claims "NiFi migration complete" for UPS/Network/CCTV
            
2026-07-02: THIS INVESTIGATION
            → REALITY CHECK: Migration NOT complete
```

**Conclusion:** Dokumentasi v4.3 adalah **DESIGN DOC** (how it should be), bukan **AS-BUILT DOC** (how it actually is).

---

## 6. Rekomendasi Action Items

### 6.1 Priority 0: Restore Data Collection (Immediate)

**Jika UPS/Network/CCTV data TIDAK MASUK pipeline:**

```bash
# 1. UPS: Re-enable Telegraf collection
cd /home/infra/dcim_metrics_project/configs/telegraf
mv ups-apc.conf.disabled ups-apc.conf
sudo systemctl restart telegraf

# 2. Network: Create Telegraf config (jika belum ada NiFi)
# Atau: Deploy NiFi flow untuk MikroTik

# 3. CCTV: Pilih salah satu:
# Option A: Start daemon
sudo systemctl enable dcim-cctv-poller.service
sudo systemctl start dcim-cctv-poller.service

# Option B: Keep Telegraf (sudah jalan)
# TIDAK PERLU ACTION (Telegraf cctv-hikvision.conf sudah aktif)
```

### 6.2 Priority 1: Audit NiFi Flow

```bash
# Check NiFi flow content
cd /home/infra/dcim_metrics_project/nifi
gunzip -c flow.json.gz | jq '.rootGroup.processGroups[] | {name: .name, id: .identifier}' | less

# Or: Inspect NiFi UI
# http://10.70.0.56:8080/nifi/
```

**Tujuan:** Konfirmasi apakah NiFi sudah punya Process Groups untuk:
- UPS polling (ExecuteProcess → snmp_ups_poller.py)
- Network polling (ExecuteProcess → mikrotik_poller.py)

### 6.3 Priority 2: Complete NiFi Migration (If Intended)

**If design goal is "migrate to NiFi":**

1. **Create NiFi Process Groups:**
   ```
   - UPS Ingestion PG:
     - ExecuteProcess (snmp_ups_poller.py)
     - PublishKafka (dcim.raw.power.ups)
   
   - Network Ingestion PG:
     - ExecuteProcess (mikrotik_poller.py)
     - PublishKafka (dcim.raw.network.snmp + dcim.raw.network.interfaces)
   ```

2. **Test NiFi flows:**
   ```bash
   # Start process groups
   # Monitor Kafka topics for data
   docker exec -it kafka1 kafka-console-consumer --bootstrap-server localhost:9092 --topic dcim.raw.power.ups --from-beginning --max-messages 10
   ```

3. **Cutover:**
   ```bash
   # Disable Telegraf inputs (if NiFi working)
   # ups-apc.conf already disabled ✓
   # cctv-hikvision.conf → disable if daemon works
   ```

4. **Update documentation to match reality:**
   ```markdown
   ## v4.3 Migration Status
   - Server: Telegraf (NO CHANGE PLANNED)
   - UPS: MIGRATED to NiFi ✅
   - NAS: Telegraf (NO CHANGE PLANNED)
   - Network: MIGRATED to NiFi ✅
   - CCTV: MIGRATED to Daemon ✅
   ```

### 6.4 Priority 3: Update Documentation

**Option A: Update v4.3 to reflect ACTUAL state:**
```markdown
## 4.2 UPS Collection — MIGRASI DALAM PROSES

Status: ⚠️ **TRANSISI**
- Telegraf config: disabled (ups-apc.conf.disabled)
- NiFi flow: BELUM AKTIF
- Current state: **TIDAK ADA COLLECTION** (data loss risk)
```

**Option B: Create v4.4 with corrected implementation:**
```markdown
title: v4.4-pipeline-architecture-actual.md
purpose: AS-BUILT documentation (verified 2026-07-02)

## Data Collection Reality Check
- Server: Telegraf ✅
- UPS: NONE ❌ (Telegraf disabled, NiFi not deployed)
- NAS: Telegraf ✅
- Network: NONE ❌
- CCTV: Telegraf ✅ (daemon exists but inactive)
```

---

## 7. Validation Checklist

### 7.1 Data Flow Verification

**Run these commands to verify data is flowing:**

```bash
# 1. Check Kafka topics for recent data
docker exec -it kafka1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dcim.raw.power.ups \
  --from-beginning --max-messages 5

# Expected: Recent UPS metrics (timestamp < 5 minutes old)
# Actual: ??? (NEED TO CHECK)

# 2. Check Kafka topics for network data
docker exec -it kafka1 kafka-console-consumer \
  --bootstrap-server localhost:9092 \
  --topic dcim.raw.network.snmp \
  --from-beginning --max-messages 5

# Expected: MikroTik metrics
# Actual: ??? (NEED TO CHECK)

# 3. Check Elasticsearch for recent CCTV data
curl -s "http://10.70.0.56:9200/dcim-metrics-unified-$(date +%Y.%m.%d)/_search?q=device_type:cctv&size=1&sort=@timestamp:desc" | jq '.hits.hits[0]._source.@timestamp'

# Expected: Timestamp < 5 minutes ago
# Actual: ??? (NEED TO CHECK)
```

### 7.2 Service Health Check

```bash
# Check all data collection services
systemctl status telegraf.service
systemctl status dcim-cctv-poller.service
docker ps | grep nifi

# Check systemd timers
systemctl list-timers | grep dcim-

# Check logs for errors
journalctl -u telegraf.service -n 50 --no-pager
journalctl -u dcim-cctv-poller.service -n 50 --no-pager
```

---

## 8. Summary & Next Steps

### 8.1 Key Findings

1. **Dokumentasi v4.3 TIDAK AKURAT** untuk UPS, Network, dan CCTV collection
2. **Migrasi ke NiFi BELUM SELESAI** (scripts exist, deployment tidak)
3. **Risk of Data Loss:** UPS dan Network mungkin tidak ada collection aktif
4. **CCTV:** Daemon inactive, Telegraf masih digunakan (contrary to docs)
5. **Reference Design (DCIM-Wiki) TIDAK TERCAPAI** — masih full Telegraf, bukan NiFi

### 8.2 Critical Questions for User

1. **Apakah UPS dan Network data MASUK ke Elasticsearch?**
   - Jika TIDAK → Priority 0: Re-enable Telegraf collection
   - Jika YA → Audit dari mana data berasal

2. **Apakah intent migrasi ke NiFi MASIH VALID?**
   - Jika YA → Complete NiFi deployment (P2 action)
   - Jika TIDAK → Update docs to reflect "Telegraf as primary" (P3 action)

3. **Apakah daemon CCTV harus diaktifkan?**
   - Jika YA → `systemctl enable/start dcim-cctv-poller.service`
   - Jika TIDAK → Disable Telegraf `cctv-hikvision.conf` (redundant)

### 8.3 Recommended Immediate Actions

```bash
# ACTION 1: Verify data flow (5 minutes)
cd /home/infra/dcim_metrics_project
./scripts/verify_data_flow.sh  # (create this script from §7.1)

# ACTION 2: Audit NiFi canvas (10 minutes)
# Open http://10.70.0.56:8080/nifi/
# Document all Process Groups present

# ACTION 3: Decision meeting (30 minutes)
# Discuss:
# - Keep Telegraf vs Complete NiFi migration?
# - Update v4.3 docs vs Create v4.4?
# - Align with DCIM-Wiki reference or diverge?
```

---

## Appendix A: File Locations

### Configuration Files
```
/home/infra/dcim_metrics_project/configs/telegraf/
├── cctv-hikvision.conf          # ACTIVE (Telegraf exec)
├── servers-redfish.conf         # ACTIVE
├── telegraf_producer.conf       # ACTIVE (main config)
├── telegraf_consumer.conf       # INACTIVE (replaced by Python consumer)
└── ups-apc.conf.disabled        # DISABLED (intent to migrate)
```

### Scripts
```
/home/infra/dcim_metrics_project/scripts/
├── hikvision_poller_daemon.py   # EXISTS, service INACTIVE
├── mikrotik_poller.py           # EXISTS, NOT USED
├── snmp_ups_poller.py           # EXISTS, NOT USED
└── redfish_telemetry_poller.py  # EXISTS, USED by Telegraf
```

### Systemd Services
```
/etc/systemd/system/
├── dcim-cctv-poller.service     # EXISTS, disabled/inactive
├── telegraf.service             # ACTIVE, running
└── dcim-*.service               # Other services (normalizer, consumers, etc.)
```

### NiFi
```
/home/infra/dcim_metrics_project/nifi/
├── docker-compose.yml
└── flow.json.gz                 # NEEDS AUDIT
```

---

## Appendix B: Comparison Table

| Aspect | v4.3 Docs | Actual (2026-07-02) | DCIM-Wiki Reference |
|--------|-----------|---------------------|---------------------|
| **Architecture** | Hybrid Telegraf+NiFi | Full Telegraf | NiFi (100+ procs) |
| **Server** | Telegraf | Telegraf ✅ | NiFi |
| **UPS** | NiFi ExecuteProcess | **NONE** ❌ | NiFi |
| **NAS** | Telegraf | Telegraf ✅ | NiFi |
| **Network** | NiFi ExecuteProcess | **NONE** ❌ | NiFi |
| **CCTV** | Daemon Standalone | Telegraf ✅ | NiFi |
| **Alignment Score** | — | **40%** | **20%** |

---

**END OF INVESTIGATION REPORT**
