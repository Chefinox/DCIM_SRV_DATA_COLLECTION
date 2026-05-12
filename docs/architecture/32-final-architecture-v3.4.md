# 32. Final Architecture & Data Flow Documentation (v3.4)

**Status**: ✅ Terverifikasi End-to-End | **Tanggal**: 2026-05-04 | **Agent**: Antigravity

---

## 1. Arsitektur Pipeline MT014 (Final)

Pipeline telemetri DCIM menggunakan arsitektur **4-Layer Decoupled** yang memastikan skalabilitas dan ketahanan data.

### Diagram Alur Data (Detailed Flow)
```mermaid
flowchart TD
    subgraph SRC["🏭 Layer 1 — Physical Infrastructure"]
        direction LR
        NET["🔀 Network\nMikroTik Switch/Router\nSNMP v2c/v3"]
        UPS["⚡ UPS\nAPC Smart-UPS\nSNMP v3"]
        NAS["💾 NAS\nSynology DS Series\nSNMP v3 + REST"]
        SRV["🖥️ Server\nLenovo ThinkSystem\nRedfish HTTPS"]
        CAM["📷 CCTV/NVR\nHikvision\nISAPI HTTP"]
    end

    subgraph PROD["📡 Layer 1B — Telegraf Producers"]
        TP1["inputs.snmp\nmikrotik-snmp.conf\n120s interval"]
        TP2["inputs.snmp\nups-apc.conf\n120s interval"]
        TP3["inputs.snmp\nnas-snmp.conf\n120s interval"]
        TP4["inputs.redfish\nservers-redfish.conf\n120s interval"]
        PY1["inputs.exec\nhikvision_poller.py\n120s interval"]
        OUT["outputs.kafka\n127.0.0.1:9092\nFormat: JSON"]
        
        SRC --> TP1 & TP2 & TP3 & TP4 & PY1
        TP1 & TP2 & TP3 & TP4 & PY1 --> OUT
    end

    subgraph RAW_K["🗂️ Kafka Raw Topics"]
        RT1["dcim.raw.network.snmp\ndcim.raw.network.interfaces"]
        RT2["dcim.raw.power.ups"]
        RT3["dcim.raw.storage.nas"]
        RT4["dcim.raw.server"]
        RT5["dcim.raw.device.isapi"]
    end
    OUT --> RAW_K

    subgraph NORM["⚙️ Layer 2 — Normalization"]
        NS["dcim-normalizer.service\nPython V3\n/usr/bin/python3 -u"]
        CFG["metric_mapping.json\n(Topic/Measurement Maps)"]
        NS --- CFG
        NT["dcim.normalized.events\nFlat CDM JSON\n(UUID, ts, device_type, sn)"]
    end
    RAW_K --> NS
    NS --> NT

    subgraph ENRICH["🔶 Layer 3 — Enrichment"]
        direction TB
        NIFI["Apache NiFi 1.24\nContainer: dcim-nifi\nPort: 8443 HTTPS"]
        
        subgraph NIFI_FLOW["NiFi Internal Flow"]
            NF1["ConsumeKafkaRecord\nSource: dcim.normalized.events"]
            NF2["LookupRecord\nRestLookupService\nGET /enrich/{sn}"]
            NF3["PublishKafkaRecord\nSink: dcim.enriched.events"]
            NF1 -->|success| NF2
            NF2 -->|success| NF3
        end

        subgraph API_LAYER["🐍 Enrichment Microservice"]
            API["FastAPI :8000\nenrichment_api.py\n/enrich/{sn}"]
            REDIS[("🔴 Redis :6379\ndcim-redis-cache\nasset:{sn_lower}")]
            API <--> REDIS
            API -- "Fallback" --> PG_SOT
        end

        subgraph CACHE_SYNC["🔄 Cache Sync Daemon"]
            RSYNC["dcim-redis-sync.service\ncmdb_to_cache_sync.py\n(60s Sync)"]
        end
        
        PG_SOT[(PostgreSQL SOT\n192.168.101.73)] --> RSYNC --> REDIS
        NT --> NF1
        NF2 <--> API
    end

    subgraph SINK_P["🗄️ Layer 4 — Sink & Persistence"]
        direction LR
        ES_C["telegraf-consumer.service\nOutput: Elasticsearch"]
        SQL_C["dcim-sql-consumer.service\nOutput: PostgreSQL"]
        KIBANA["📊 Kibana Dashboard"]
        
        NF3 --> ES_C & SQL_C
        ES_C --> KIBANA
        SQL_C --> PG_DB[(PostgreSQL\ndcim_events)]
    end

    subgraph CMDB_SYNC["🔄 CMDB Ralph Sync"]
        DSYNC["server_deep_sync.py\n(Daily at 02:00)"]
        RALPH["📘 Ralph CMDB\n192.168.101.73:8088"]
        
        PG_DB --> DSYNC --> RALPH
    end
```

---

## 2. Standar Operasional (SOP)

### Polling & Collection
- **Interval Standar**: Semua metrik diselaraskan pada **120 detik (2 menit)** untuk menjaga keseimbangan antara visibilitas dan beban perangkat (khususnya Redfish BMC).
- **Service**: `telegraf.service` diatur untuk restart otomatis jika gagal.

### CMDB Auto-Update (Ralph)
- **Frekuensi**: Sinkronisasi dilakukan **sekali sehari (Daily)** untuk menjaga integritas data dan menghindari "update loop".
- **Jadwal Crontab**:
  - `0 1 * * *`: `ralph_cmdb_sync.py` (Bulk telemetry sync)
  - `0 2 * * *`: `server_deep_sync.py` (Deep hardware inventory sync)
  - `0 3 * * *`: `server_redfish_to_pg.py` (Direct-to-PostgreSQL inventory snapshot)

---

## 3. Mapping Logic & Data Consistency

### Field Mapping Standard
| Field | Update Rule | Logic |
| :--- | :--- | :--- |
| `serial_number` | **PROTECTED** | Digunakan sebagai primary key, dilarang overwrite. |
| `management_ip` | **PROTECTED** | Tetap sesuai konfigurasi manual di Ralph. |
| `hostname` | **AUTO** | Mengikuti `hostname` yang terdeteksi di Redfish/SNMP. |
| `bios/firmware` | **AUTO** | Diupdate otomatis jika terdeteksi versi baru. |
| `components` | **AUTO (Pruning)** | Disk, RAM, dan CPU disinkronkan. Komponen lama yang tidak terdeteksi akan dihapus (pruning). |

### AI Readiness
- **Enrichment Rate**: > 99% data memiliki status `FULL`.
- **NULL Handling**: Skrip normalisasi menjamin field kritikal (SN, Hostname, IP) tidak bernilai null.
- **Consistency**: Sinkronisasi 7 jam (timezone bug) pada CCTV telah diperbaiki menggunakan timezone-aware UTC timestamps.

---

## 4. Troubleshooting Guide Singkat

- **Data CCTV Stale?** Cek apakah timestamp di `hikvision_poller.py` menggunakan `datetime.timezone.utc`.
- **Ralph Tidak Update?** Pastikan `server_deep_sync.py` ada di crontab user `infra`.
- **Service Mati?** Jalankan `sudo systemctl status telegraf dcim-normalizer dcim-enrichment-api dcim-redis-sync telegraf-consumer dcim-sql-consumer`.

---
**Dokumentasi ini dibuat sebagai bagian dari Phase 7 - Handover AI Agent.**
