# 36. Complete End-to-End Pipeline Diagram (v3.5.5)

**Tanggal**: 21 Mei 2026  
**Status**: ✅ Verified & Operational  
**Scope**: Unified DCIM Telemetry & Inventory Pipeline

---

## Diagram Arsitektur Lengkap

```mermaid
flowchart TB
    subgraph DEVICES["🏭 LAYER 1: Physical Infrastructure"]
        direction LR
        SRV["🖥️ Server (5 units)<br/>Lenovo ThinkSystem<br/>10.50.0.2-6<br/><b>Protocol: Redfish HTTPS</b><br/>Port: 443"]
        UPS["⚡ UPS (1 unit)<br/>APC Smart-UPS 30K<br/>192.168.100.140<br/><b>Protocol: SNMP v3</b><br/>Port: 161"]
        NAS["💾 NAS (6 units)<br/>Synology DS Series<br/>10.50.0.105-110<br/><b>Protocol: SNMP v3</b><br/>Port: 161"]
        NET["🔀 Network (5 units)<br/>MikroTik CCR/CRS<br/>172.16.35.x<br/><b>Protocol: SNMP v2c</b><br/>Port: 161"]
        CAM["📷 CCTV (31 units)<br/>Hikvision Camera<br/>192.168.1.2-33 (skip .32)<br/><b>Protocol: ISAPI HTTP</b><br/>Port: 80"]
        NVR["📹 NVR (1 unit)<br/>Hikvision DS-7732<br/>192.168.1.254<br/><b>Protocol: ISAPI HTTP</b><br/>Port: 80"]
    end

    subgraph COLLECTION["📡 LAYER 1B: Data Collection"]
        direction TB
        
        subgraph TELEGRAF["Telegraf Producer<br/>(telegraf.service)"]
            T1["<b>inputs.redfish</b><br/>servers-redfish.conf<br/>Interval: 120s<br/>User: hndept"]
            T2["<b>inputs.snmp</b><br/>ups-apc.conf<br/>Interval: 120s<br/>Auth: SHA/AES"]
            T3["<b>inputs.snmp</b><br/>nas-snmp.conf<br/>Interval: 120s<br/>Community: public"]
            T4["<b>inputs.snmp</b><br/>mikrotik-snmp.conf<br/>Interval: 120s<br/>Community: public"]
            T5["<b>inputs.exec</b><br/>hikvision_poller.py<br/>Interval: 120s<br/>Auth: Basic"]
        end
        
        TOUT["<b>outputs.kafka</b><br/>localhost:9092<br/>Format: JSON"]
        
        T1 & T2 & T3 & T4 & T5 --> TOUT
    end

    subgraph KAFKA_RAW["🗂️ Kafka Raw Topics<br/>(kafka-broker:9092)"]
        K1["dcim.raw.hardware.server"]
        K2["dcim.raw.power.ups"]
        K3["dcim.raw.storage.nas"]
        K4["dcim.raw.network.snmp<br/>dcim.raw.network.interfaces"]
        K5["dcim.raw.device.isapi"]
    end

    subgraph NORMALIZE["⚙️ LAYER 2: Normalization"]
        NORM["<b>dcim-normalizer.service</b><br/>Script: dcim_normalizer.py<br/>Config: metric_mapping.json<br/>Input: All raw topics<br/>Output: Flat CDM Schema"]
    end

    subgraph KAFKA_NORM["🗂️ Kafka Normalized Topic"]
        KN["dcim.normalized.events<br/><i>Unified Schema:</i><br/>- event_id (UUID)<br/>- device_type<br/>- hostname<br/>- serial_number<br/>- metric_name/value<br/>- raw_tags/fields (JSONB)"]
    end

    subgraph ENRICH["🔶 LAYER 3: Enrichment"]
        direction TB
        
        subgraph NIFI["Apache NiFi 1.24<br/>(dcim-nifi:8443)"]
            NF1["ConsumeKafkaRecord_2_6<br/>Topic: dcim.normalized.events<br/>Format: JSON"]
            NF2["LookupRecord<br/>RestLookupService<br/>GET /enrich/{sn}"]
            NF3["PublishKafkaRecord_2_6<br/>Topic: dcim.enriched.events"]
            
            NF1 --> NF2 --> NF3
        end
        
        subgraph API["Enrichment API<br/>(dcim-enrichment-api.service)"]
            FAPI["<b>FastAPI :8000</b><br/>Script: enrichment_api.py<br/>Endpoint: /enrich/{sn}<br/>Response: CMDB metadata"]
        end
        
        subgraph CACHE["Cache Layer"]
            REDIS[("<b>Redis :6379</b><br/>(dcim-redis-cache)<br/>Pattern: asset:sn:{sn}<br/>TTL: 3600s")]
            SYNC["<b>dcim-redis-sync.service</b><br/>Script: cmdb_to_cache_sync.py<br/>Interval: 60s<br/>Source: PostgreSQL SOT"]
        end
        
        NF2 <--> FAPI
        FAPI <--> REDIS
        SYNC --> REDIS
    end

    subgraph KAFKA_ENR["🗂️ Kafka Enriched Topic"]
        KE["dcim.enriched.events<br/><i>Added Fields:</i><br/>- site<br/>- rack_name<br/>- rack_position<br/>- manufacturer<br/>- model<br/>- asset_status<br/>- enrichment_status"]
    end

    subgraph PERSIST["🗄️ LAYER 4: Persistence"]
        direction LR
        
        ES["<b>telegraf-consumer.service</b><br/>Script: Telegraf<br/>Input: dcim.enriched.events<br/>Output: Elasticsearch<br/>Index: dcim-metrics-unified-*"]
        
        SQL["<b>dcim-sql-consumer.service</b><br/>Script: dcim_sql_consumer.py<br/>Input: dcim.enriched.events<br/>Output: PostgreSQL<br/>Table: dcim_events (partitioned)"]
        
        DLQ["<b>dcim-dlq-consumer.service</b><br/>Script: dcim_dlq_consumer.py<br/>Input: dcim.dlq.*<br/>Output: Logs + Retry"]
    end

    subgraph STORAGE["💾 Data Storage"]
        direction TB
        
        PG[("<b>PostgreSQL 14</b><br/>Host: 192.168.100.115:5432<br/>Database: dcim_sot<br/>Tables:<br/>- dcim_events (partitioned)<br/>- dcim_server_disks<br/>- dcim_server_ram<br/>- dcim_server_processors<br/>- unified_assets")]
        
        ES_DB[("<b>Elasticsearch 7.x</b><br/>Host: 10.70.0.56:9200<br/>Index: dcim-metrics-unified-*<br/>Alert Index: dcim-alerts<br/>Retention: 90 days")]
        
        KIBANA["<b>Kibana Dashboard</b><br/>Host: 10.70.0.56:5601<br/>Dashboards:<br/>- DCIM Monitoring<br/>- Threshold Alerts<br/>- Stale Device Alerts"]
    end

    subgraph CMDB["📘 CMDB Sync Layer"]
        direction TB
        
        SRV_INV["<b>server_inventory_to_pg.py</b><br/>Schedule: Daily 01:00 WIB<br/>Protocol: Redfish HTTPS<br/>Target: 10.50.0.2-6<br/>Components:<br/>- Firmware/BIOS<br/>- Processors (model, cores)<br/>- Memory (size, speed)<br/>- Disks (SN, size, slot)<br/>- NICs (MAC, speed)<br/>Output: PostgreSQL dcim_events"]
        
        UNIFIED["<b>ralph_cmdb_sync.py</b><br/>Schedule: Daily 02:00 WIB<br/>Source: PostgreSQL dcim_events<br/>Auto-register DC Assets:<br/>server, ups, nas,<br/>network_switch, nvr<br/>CCTV: Back Office flow"]
        
        RALPH[("<b>Ralph CMDB</b><br/>Host: 192.168.100.115:8088<br/>API Token: 1cd05b8d...<br/>Endpoints:<br/>- /api/data-center-assets/<br/>- /api/back-office-assets/<br/>- /api/processors/<br/>- /api/memory/<br/>- /api/disks/<br/>- /api/ethernets/")]
    end

    subgraph DLQ_TOPICS["⚠️ Dead Letter Queue Topics"]
        DLQ1["dcim.dlq.parse-failure"]
        DLQ2["dcim.dlq.enrichment-failure"]
        DLQ3["dcim.dlq.delivery-failure"]
    end

    subgraph ALERTS["🚨 Alerting & Stale Detection"]
        ALERTER["<b>dcim-threshold-alerter.service</b><br/>Script: dcim_threshold_alerter.py<br/>Interval: 120s<br/>Checks: 6 thresholds + stale devices<br/>Stale threshold: 30m"]
        ALERT_IDX[("<b>dcim-alerts</b><br/>Threshold alerts<br/>Device Not Reporting alerts")]
    end

    %% ========================================
    %% LAYER 1: Device to Telegraf Collection
    %% ========================================
    SRV --> T1
    UPS --> T2
    NAS --> T3
    NET --> T4
    CAM --> T5
    NVR --> T5
    
    %% ========================================
    %% LAYER 1B: Telegraf to Kafka Raw Topics
    %% ========================================
    T1 --> TOUT
    T2 --> TOUT
    T3 --> TOUT
    T4 --> TOUT
    T5 --> TOUT
    
    TOUT --> K1
    TOUT --> K2
    TOUT --> K3
    TOUT --> K4
    TOUT --> K5
    
    %% ========================================
    %% LAYER 2: Normalization Pipeline
    %% ========================================
    K1 --> NORM
    K2 --> NORM
    K3 --> NORM
    K4 --> NORM
    K5 --> NORM
    
    NORM --> KN
    
    %% ========================================
    %% LAYER 3: Enrichment Pipeline
    %% ========================================
    KN --> NF1
    NF1 --> NF2
    NF2 --> NF3
    NF3 --> KE
    
    %% Enrichment API & Cache
    NF2 <--> FAPI
    FAPI <--> REDIS
    PG --> SYNC
    SYNC --> REDIS
    
    %% ========================================
    %% LAYER 4: Persistence Layer
    %% ========================================
    KE --> ES
    KE --> SQL
    
    ES --> ES_DB
    SQL --> PG
    ES_DB --> KIBANA
    ES_DB --> ALERTER
    ALERTER --> ALERT_IDX
    ALERT_IDX --> KIBANA
    
    %% ========================================
    %% CMDB Sync Layer (Unified Pipeline)
    %% ========================================
    SRV -.->|Daily 01:00| SRV_INV
    SRV_INV --> PG
    PG --> UNIFIED
    UNIFIED --> RALPH
    
    %% ========================================
    %% Error Handling (Dead Letter Queue)
    %% ========================================
    NORM -.->|parse error| DLQ1
    NF2 -.->|enrich error| DLQ2
    SQL -.->|delivery error| DLQ3
    
    DLQ1 --> DLQ
    DLQ2 --> DLQ
    DLQ3 --> DLQ

    style DEVICES fill:#e1f5ff
    style COLLECTION fill:#fff4e6
    style KAFKA_RAW fill:#f3e5f5
    style NORMALIZE fill:#e8f5e9
    style KAFKA_NORM fill:#f3e5f5
    style ENRICH fill:#fff3e0
    style KAFKA_ENR fill:#f3e5f5
    style PERSIST fill:#e0f2f1
    style STORAGE fill:#fce4ec
    style CMDB fill:#f1f8e9
    style DLQ_TOPICS fill:#ffebee
    style ALERTS fill:#fff9c4
```

---

## Tabel Ringkasan Komponen

### 1. Data Collection Layer

| Component | Type | Protocol | Port | Interval | Config File | Output |
|-----------|------|----------|------|----------|-------------|--------|
| Server Metrics | Telegraf input.redfish | Redfish HTTPS | 443 | 120s | servers-redfish.conf | dcim.raw.hardware.server |
| UPS Metrics | Telegraf input.snmp | SNMP v3 (SHA/AES) | 161 | 120s | ups-apc.conf | dcim.raw.power.ups |
| NAS Metrics | Telegraf input.snmp | SNMP v3 | 161 | 120s | nas-snmp.conf | dcim.raw.storage.nas |
| Network Metrics | Telegraf input.snmp | SNMP v2c | 161 | 120s | mikrotik-snmp.conf | dcim.raw.network.snmp |
| CCTV/NVR Metrics | Telegraf input.exec | ISAPI HTTP | 80 | 120s | hikvision_poller.py | dcim.raw.device.isapi |

### 2. Processing Services

| Service | Script | Input | Output | Function |
|---------|--------|-------|--------|----------|
| dcim-normalizer.service | dcim_normalizer.py | Kafka raw topics | dcim.normalized.events | Schema standardization |
| dcim-nifi (container) | NiFi Flow | dcim.normalized.events | dcim.enriched.events | CMDB enrichment |
| dcim-enrichment-api.service | enrichment_api.py | REST /enrich/{sn} | JSON metadata | Cache lookup |
| dcim-redis-sync.service | cmdb_to_cache_sync.py | PostgreSQL SOT | Redis cache | Cache refresh (60s) |
| telegraf-consumer.service | Telegraf | dcim.enriched.events | Elasticsearch | Time-series storage |
| dcim-sql-consumer.service | dcim_sql_consumer.py | dcim.enriched.events | PostgreSQL dcim_events | Historical storage |
| dcim-dlq-consumer.service | dcim_dlq_consumer.py | dcim.dlq.* | Logs + Retry | Error handling |
| dcim-threshold-alerter.service | dcim_threshold_alerter.py | Elasticsearch `dcim-metrics-unified-*` | Elasticsearch `dcim-alerts` | Threshold + stale-device alerting |

### 3. CMDB Sync Layer

| Script | Schedule | Protocol | Source | Target | Device Types |
|--------|----------|----------|--------|--------|--------------|
| server_inventory_to_pg.py | Daily 01:00 | Redfish HTTPS | 10.50.0.2-6 | PostgreSQL dcim_events | Server (5) |
| ralph_cmdb_sync.py | Daily 02:00 | HTTP REST | PostgreSQL | Ralph CMDB | All devices; auto-register DC assets except CCTV |

### 4. Kafka Topics

| Topic | Producer | Consumer | Schema | Retention |
|-------|----------|----------|--------|-----------|
| dcim.raw.hardware.server | Telegraf | Normalizer | Redfish native | 7 days |
| dcim.raw.power.ups | Telegraf | Normalizer | SNMP OID values | 7 days |
| dcim.raw.storage.nas | Telegraf | Normalizer | SNMP OID values | 7 days |
| dcim.raw.network.snmp | Telegraf | Normalizer | SNMP OID values | 7 days |
| dcim.raw.device.isapi | Telegraf | Normalizer | ISAPI JSON | 7 days |
| dcim.normalized.events | Normalizer | NiFi | Flat CDM | 7 days |
| dcim.enriched.events | NiFi | SQL/ES Consumers | CDM + CMDB | 7 days |
| dcim.dlq.parse-failure | Normalizer | DLQ Consumer | Error payload | 30 days |
| dcim.dlq.enrichment-failure | NiFi | DLQ Consumer | Error payload | 30 days |
| dcim.dlq.delivery-failure | SQL Consumer | DLQ Consumer | Error payload | 30 days |

### 5. Storage Backends

| System | Host | Port | Database/Index | Purpose | Retention |
|--------|------|------|----------------|---------|-----------|
| PostgreSQL | 192.168.100.115 | 5432 | dcim_sot | Historical events, CMDB cache | Partitioned (daily) |
| Elasticsearch | 10.70.0.56 | 9200 | dcim-metrics-unified-* / dcim-alerts | Time-series metrics + alerts | 90 days |
| Redis | localhost | 6379 | DB 0 | Enrichment cache | TTL 3600s |
| Ralph CMDB | 192.168.100.115 | 8088 | N/A | Asset inventory | Permanent |
| Kafka | localhost | 9092 | N/A | Message broker | 7-30 days |

---

## Data Flow Summary

### Metrics Pipeline (Real-time)
```
Device → Telegraf → Kafka Raw → Normalizer → Kafka Normalized → 
NiFi Enrichment → Kafka Enriched → Elasticsearch/PostgreSQL → Kibana
```

### Inventory Pipeline (Daily)
```
Server Redfish → server_inventory_to_pg.py → PostgreSQL dcim_events
Device (NAS/Network/CCTV) → Telegraf → Kafka → ... → PostgreSQL dcim_events
PostgreSQL dcim_events → ralph_cmdb_sync.py → Ralph CMDB
```

### Commissioning / Decommissioning Automation (v3.5.5)
```
New DC device → PostgreSQL dcim_events → ralph_cmdb_sync.py
    → if SN missing in Ralph: auto-register DC asset
    → update metadata/components/IP

Known device stops reporting → dcim-threshold-alerter.py
    → no event for 30 minutes → dcim-alerts → Kibana
```

**Auto-register includes**: `server`, `ups`, `nas`, `network_switch`, `nvr`.  
**Excluded**: `cctv` because CCTV uses Ralph Back Office Asset registration via `scripts/register_cctv_to_ralph.py`.

### Kafka Health Check Note

Collector interval is 120 seconds. Kafka sampling windows shorter than collector interval (example: 3 seconds) can produce false warnings. For health checks, prefer topic offsets plus PostgreSQL/Elasticsearch event counts.

### Enrichment Flow
```
PostgreSQL SOT → Redis Sync (60s) → Redis Cache → 
Enrichment API ← NiFi Lookup → Enriched Events
```

---

## Protocol & Authentication Summary

| Device Type | Protocol | Port | Auth Method | Credentials |
|-------------|----------|------|-------------|-------------|
| Server BMC | Redfish HTTPS | 443 | Basic Auth | hndept / F!tech@0918 |
| UPS | SNMP v3 | 161 | authPriv (SHA/AES) | poller / F!tech0918 |
| NAS | SNMP v3 | 161 | authPriv (SHA/AES) | poller / F!tech0918 |
| Network | SNMP v2c | 161 | Community String | public |
| CCTV/NVR | ISAPI HTTP | 80 | Basic Auth | admin / qRvbi883=Zk[Q)@5 |
| Ralph API | HTTP REST | 8088 | Token Auth | 1cd05b8d36e258399a52c59f1a4016addb2346a3 |
| PostgreSQL | PostgreSQL | 5432 | Password | sot_admin / Inovasi@0918 |

---

## Performance Metrics

- **Total Devices**: 38 monitored inventory devices (5 servers, 1 UPS, 6 NAS, 5 network, 21 CCTV/NVR registered/monitored scope; CCTV channel inventory can include 31 camera channels)
- **Polling Interval**: 120 seconds (2 minutes)
- **Events per Day**: ~35,280 (49 devices × 720 polls/day)
- **Kafka Throughput**: ~190 msg/min
- **Enrichment Rate**: >99% (Redis cache hit)
- **End-to-End Latency**: <5 seconds (device → Elasticsearch)
- **CMDB Sync**: Daily 02:00 WIB (automated; auto-register missing DC assets)
- **Stale Alert Threshold**: 30 minutes without event

---

**Dokumentasi ini mencerminkan arsitektur aktual yang terverifikasi pada 21 Mei 2026.**

---

## Catatan Perubahan Arsitektur (v3.4 → v3.4.1)

**Tanggal**: 12 Mei 2026  
**Perubahan**: Kembalikan server inventory ke unified pipeline (PostgreSQL sebagai Single Source of Truth)

### Masalah Sebelumnya (v3.4)
- Server inventory menggunakan **dual architecture**: `server_deep_sync.py` langsung ke Ralph CMDB (bypass PostgreSQL)
- Melanggar prinsip **Single Source of Truth** (PostgreSQL)
- Script `server_redfish_to_pg.py` broken (deprecated skill-based architecture)
- Server inventory fields di PostgreSQL tetap NULL

### Solusi (v3.4.1)
- **Script Baru**: `server_inventory_to_pg.py` (standalone, tanpa skill-based dependencies)
- **Unified Pipeline**: Server Redfish → server_inventory_to_pg.py → PostgreSQL → ralph_cmdb_sync.py → Ralph
- **Schedule**: 
  - 01:00 WIB: `server_inventory_to_pg.py` (collect inventory ke PostgreSQL)
  - 02:00 WIB: `ralph_cmdb_sync.py` (sync semua devices dari PostgreSQL ke Ralph)

### Keuntungan
- ✅ PostgreSQL kembali menjadi Single Source of Truth untuk semua devices
- ✅ Konsisten dengan arsitektur NAS/Network/CCTV/UPS
- ✅ `ralph_cmdb_sync.py` sekarang handle **semua 49 devices** (termasuk 5 servers)
- ✅ Audit trail lengkap di PostgreSQL `dcim_events`

### Script yang Deprecated
- ❌ `server_deep_sync.py` (direct sync ke Ralph, tidak digunakan lagi)
- ❌ `server_redfish_to_pg.py` (broken skill-based architecture)
