# 36. Complete End-to-End Pipeline Diagram (v3.5.5)

**Tanggal**: 22 Mei 2026  
**Status**: ✅ Verified & Operational  
**Scope**: Unified DCIM Telemetry & Inventory Pipeline

---

## Diagram Arsitektur Lengkap

```mermaid
flowchart LR
    %% Clean left-to-right layout to reduce crossing lines.

    subgraph L1["🏭 1. Physical Infrastructure"]
        direction TB
        SRV["🖥️ Server<br/>5 Lenovo ThinkSystem<br/>10.50.0.2-6<br/>Redfish HTTPS :443"]
        UPS["⚡ UPS<br/>1 APC Smart-UPS 30K<br/>192.168.100.140<br/>SNMP v3 :161"]
        NAS["💾 NAS<br/>6 Synology DS Series<br/>10.50.0.105-110<br/>SNMP v3 :161"]
        NET["🔀 Network<br/>5 MikroTik CCR/CRS<br/>172.16.35.x<br/>SNMP v2c :161"]
        CAM["📷 CCTV<br/>31 Hikvision camera channels<br/>192.168.1.2-33 skip .32<br/>ISAPI HTTP :80"]
        NVR["📹 NVR<br/>1 Hikvision DS-7732<br/>192.168.1.254<br/>ISAPI HTTP :80"]
    end

    subgraph L2["📡 2. Collection - Telegraf"]
        direction TB
        C_SRV["inputs.redfish<br/>servers-redfish.conf<br/>120s"]
        C_UPS["inputs.snmp<br/>ups-apc.conf<br/>120s"]
        C_NAS["inputs.snmp<br/>nas-snmp.conf<br/>120s"]
        C_NET["inputs.snmp<br/>mikrotik-snmp.conf<br/>120s"]
        C_ISAPI["inputs.exec<br/>hikvision_poller.py<br/>120s"]
        KOUT["outputs.kafka<br/>localhost:9092<br/>JSON"]
    end

    subgraph L3["🗂️ 3. Kafka Raw Topics"]
        direction TB
        KR_SRV["dcim.raw.hardware.server"]
        KR_UPS["dcim.raw.power.ups"]
        KR_NAS["dcim.raw.storage.nas"]
        KR_NET["dcim.raw.network.snmp<br/>dcim.raw.network.interfaces"]
        KR_ISAPI["dcim.raw.device.isapi"]
    end

    subgraph L4["⚙️ 4. Normalize"]
        direction TB
        NORM["dcim-normalizer.service<br/>dcim_normalizer.py<br/>metric_mapping.json"]
        KN["dcim.normalized.events<br/>Flat CDM schema"]
    end

    subgraph L5["🔶 5. Enrich"]
        direction TB
        NF1["NiFi ConsumeKafkaRecord<br/>dcim.normalized.events"]
        NF2["NiFi LookupRecord<br/>GET /enrich/{sn}"]
        NF3["NiFi PublishKafkaRecord<br/>dcim.enriched.events"]
        API["dcim-enrichment-api.service<br/>FastAPI :8000"]
        REDIS[("Redis cache :6379<br/>asset:sn:{sn}<br/>TTL 3600s")]
        RSYNC["dcim-redis-sync.service<br/>cmdb_to_cache_sync.py<br/>60s"]
        KE["dcim.enriched.events<br/>CDM + CMDB metadata"]
    end

    subgraph L6["🗄️ 6. Persist"]
        direction TB
        ES_CONS["telegraf-consumer.service<br/>Kafka enriched → Elasticsearch"]
        SQL_CONS["dcim-sql-consumer.service<br/>dcim_sql_consumer.py<br/>Kafka enriched → PostgreSQL"]
        ITOP_CONS["dcim-itop-consumer.service<br/>dcim_itop_consumer.py<br/>Kafka enriched → iTop CI"]
    end

    subgraph L7["💾 7. Storage & Dashboard"]
        direction TB
        PG[("PostgreSQL 14<br/>localhost:5432 (Docker)<br/>dcim_sot<br/>dcim_events + unified_assets<br/>server component tables")]
        ES[("Elasticsearch 7.x<br/>10.70.0.56:9200<br/>dcim-metrics-unified-*<br/>dcim-alerts")]
        KIBANA["Kibana Dashboard<br/>10.70.0.56:5601<br/>DCIM + alerts"]
    end

    subgraph L8["📘 CMDB Automation"]
        direction TB
        INV["server_inventory_to_pg.py<br/>Daily 01:00 WIB<br/>Redfish inventory → PostgreSQL"]
        RALPH_SYNC["ralph_cmdb_sync.py<br/>Daily 02:00 WIB<br/>auto-register DC assets"]
        RALPH[("Ralph Asset Repository<br/>localhost:8082 (Docker)")]
        ITOP_SYNC["dcim_itop_inventory_sync.py<br/>Every 5 mins<br/>PostgreSQL hardware → iTop"]
        ITOP[("iTop CMDB<br/>localhost:8080")]
    end

    subgraph L9["🚨 Alerting"]
        direction TB
        ALERT["dcim-threshold-alerter.service<br/>120s<br/>6 thresholds + stale devices<br/>stale threshold 30m"]
        ALERT_IDX[("dcim-alerts<br/>Threshold alerts<br/>Device Not Reporting alerts")]
    end

    subgraph L10["⚠️ DLQ"]
        direction TB
        DLQ1["dcim.dlq.parse-failure"]
        DLQ2["dcim.dlq.enrichment-failure"]
        DLQ3["dcim.dlq.delivery-failure"]
        DLQ_CONS["dcim-dlq-consumer.service<br/>logs + retry"]
    end

    subgraph L11["🤖 AI / Agent Readiness"]
        direction TB
        QUERY_DOC["docs/development/34-database-query-baseline-for-agents.md<br/>baseline SQL patterns"]
        QUERY_SKILL[".github/skills/dcim-database-query-baseline/SKILL.md<br/>agent on-demand skill"]
    end

    %% Main telemetry flow: mostly straight left-to-right.
    SRV --> C_SRV --> KOUT --> KR_SRV
    UPS --> C_UPS --> KOUT --> KR_UPS
    NAS --> C_NAS --> KOUT --> KR_NAS
    NET --> C_NET --> KOUT --> KR_NET
    CAM --> C_ISAPI --> KOUT --> KR_ISAPI
    NVR --> C_ISAPI

    KR_SRV --> NORM
    KR_UPS --> NORM
    KR_NAS --> NORM
    KR_NET --> NORM
    KR_ISAPI --> NORM
    NORM --> KN --> NF1 --> NF2 --> NF3 --> KE

    %% Enrichment side loop kept inside enrichment layer.
    NF2 <--> API
    API <--> REDIS
    RSYNC --> REDIS
    PG -. CMDB cache source .-> RSYNC

    %% Persistence and dashboard.
    KE --> ES_CONS --> ES --> KIBANA
    KE --> SQL_CONS --> PG
    KE --> ITOP_CONS --> ITOP

    %% CMDB automation kept below storage, using dotted operational links.
    SRV -. Daily 01:00 .-> INV
    INV -. writes inventory .-> PG
    PG -. Daily 02:00 source .-> RALPH_SYNC
    RALPH_SYNC -. sync/register .-> RALPH
    PG -. Every 5 mins .-> ITOP_SYNC
    ITOP_SYNC -. sync hardware .-> ITOP

    %% Alerting kept on Elasticsearch side.
    ES --> ALERT --> ALERT_IDX --> KIBANA

    %% DLQ paths kept as dashed exception links.
    NORM -. parse error .-> DLQ1
    NF2 -. enrichment error .-> DLQ2
    SQL_CONS -. delivery error .-> DLQ3
    DLQ1 --> DLQ_CONS
    DLQ2 --> DLQ_CONS
    DLQ3 --> DLQ_CONS

    %% Agent knowledge uses docs and database, not runtime pipeline.
    QUERY_SKILL -. loads .-> QUERY_DOC
    QUERY_DOC -. query reference .-> PG

    style L1 fill:#e1f5ff
    style L2 fill:#fff4e6
    style L3 fill:#f3e5f5
    style L4 fill:#e8f5e9
    style L5 fill:#fff3e0
    style L6 fill:#e0f2f1
    style L7 fill:#fce4ec
    style L8 fill:#f1f8e9
    style L9 fill:#fff9c4
    style L10 fill:#ffebee
    style L11 fill:#e8eaf6

    classDef mainFlow stroke:#1565c0,stroke-width:2px
    classDef exceptionFlow stroke:#c62828,stroke-width:1.5px,stroke-dasharray: 5 5
    classDef opsFlow stroke:#6a1b9a,stroke-width:1.5px,stroke-dasharray: 4 4

    class SRV,UPS,NAS,NET,CAM,NVR,C_SRV,C_UPS,C_NAS,C_NET,C_ISAPI,KOUT,KR_SRV,KR_UPS,KR_NAS,KR_NET,KR_ISAPI,NORM,KN,NF1,NF2,NF3,KE,ES_CONS,SQL_CONS,PG,ES,KIBANA mainFlow
    class DLQ1,DLQ2,DLQ3,DLQ_CONS exceptionFlow
    class INV,RALPH_SYNC,RALPH,ALERT,ALERT_IDX,QUERY_DOC,QUERY_SKILL opsFlow
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
| dcim-itop-consumer.service | dcim_itop_consumer.py | dcim.enriched.events | iTop CMDB | Auto-create CIs |
| dcim-dlq-consumer.service | dcim_dlq_consumer.py | dcim.dlq.* | Logs + Retry | Error handling |
| dcim-threshold-alerter.service | dcim_threshold_alerter.py | Elasticsearch `dcim-metrics-unified-*` | Elasticsearch `dcim-alerts` | Threshold + stale-device alerting |

### 3. CMDB Sync Layer

| Script | Schedule | Protocol | Source | Target | Device Types |
|--------|----------|----------|--------|--------|--------------|
| server_inventory_to_pg.py | Daily 01:00 | Redfish HTTPS | 10.50.0.2-6 | PostgreSQL dcim_events | Server (5) |
| ralph_cmdb_sync.py | Daily 02:00 | HTTP REST | PostgreSQL | Ralph Asset Repository | All devices; auto-register DC assets except CCTV |
| dcim_itop_inventory_sync.py | Every 5 mins | HTTP REST | PostgreSQL | iTop CMDB | Server (5) hardware spec |

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
| PostgreSQL | localhost (Docker) | 5432 | dcim_sot | Historical events, CMDB cache | Partitioned (daily) |
| Elasticsearch | 10.70.0.56 | 9200 | dcim-metrics-unified-* / dcim-alerts | Time-series metrics + alerts | 90 days |
| Redis | localhost | 6379 | DB 0 | Enrichment cache | TTL 3600s |
| Ralph Asset Repository | localhost (Docker) | 8082 | N/A | Physical Asset Management | Permanent |
| iTop CMDB | localhost | 8080 | N/A | IT Service Management & Asset Inventory | Permanent |
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
PostgreSQL dcim_events → ralph_cmdb_sync.py → Ralph Asset Repository
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

- **Total Devices**: 48 monitored inventory devices (5 servers, 1 UPS, 6 NAS, 5 network, 31 CCTV/NVR registered/monitored scope; CCTV channel inventory can include 31 camera channels)
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
- Server inventory menggunakan **dual architecture**: `server_deep_sync.py` langsung ke Ralph Asset Repository (bypass PostgreSQL)
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
