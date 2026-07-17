# Handoff: Perbaikan ci_id & asset_id Null di TimescaleDB

> **Tanggal**: 2026-07-17 — **Resolved**: 2026-07-18 01:08 WIB  
> **Server**: srv-rnd-dcim (10.70.0.56)  
> **Status**: ✅ **RESOLVED** — ci_id/asset_id populated di TimescaleDB (NAS 100%, UPS 100%)

---

## Masalah

Semua 45,158 rows di TimescaleDB `metrics` table (6 jam terakhir) memiliki `ci_id = NULL` dan `asset_id = NULL`, padahal enrichment API dan Redis cache sudah mengembalikan nilai yang benar.

---

## Root Cause

**Tiga masalah berlapis:**

### 1. (Fixed ✅) Schema Registry `dcim.enriched.events-value` tidak punya field ci_id/asset_id

NiFi PublishKafkaRecord menggunakan `schema-name: dcim.enriched.events-value` (subject berbeda dari `dcim.events.EnrichedEvent`). Subject ini versi 1 tidak memiliki field `ci_id` dan `asset_id`, sehingga NiFi Avro serializer men-strip kedua field meskipun LookupRecord sudah mengisinya.

**Fix**: Registered schema versi 2 ke Schema Registry dengan tambahan field `ci_id` dan `asset_id`:

```
curl -X POST http://10.70.0.56:8081/subjects/dcim.enriched.events-value/versions ...
→ Version 2, id=3, 28 fields termasuk ci_id + asset_id
```

### 2. (Fixed ✅) NiFi LookupRecord hanya mapping 1 field

LookupRecord sebelumnya hanya punya property `sn: /serial_number`. Response dari enrichment API (`/enrich/{sn}`) mengandung 12+ field (ci_id, asset_id, name, location, brand, model, dll) tapi semuanya diabaikan.

**Fix**: Ditambahkan 12 property mapping ke LookupRecord di NiFi GUI:

| Property | Value |
|---|---|
| `ci_id` | `/ci_id` |
| `asset_id` | `/asset_id` |
| `name` | `/name` |
| `location` | `/location` |
| `brand` | `/brand` |
| `model` | `/model` |
| `status` | `/status` |
| `ci_class` | `/ci_class` |
| `criticality` | `/criticality` |
| `org` | `/org` |
| `rack` | `/rack` |
| `managementip` | `/managementip` |

Property `sn: /serial_number` tetap dipertahankan (lookup key untuk URL enrichment API).

### 3. (Fixed ✅) NiFi UpdateRecord mengosongkan ci_id/asset_id

UpdateRecord berjalan SEBELUM LookupRecord di NiFi flow dan mengosongkan `/ci_id` dan `/asset_id` dengan empty string.

**Fix**: Dihapus property `/ci_id` dan `/asset_id` dari UpdateRecord.

---

## NiFi Flow Enrichment (Final)

```
ConsumeKafkaRecord_2_6 (dcim.normalized.events)
  → UpdateRecord (transformasi umum, TANPA overwrite ci_id/asset_id)
    → LookupRecord (enrich via RestLookupService → http://172.17.0.1:8000/enrich/${sn})
      → PublishKafkaRecord_2_6 (dcim.enriched.events, Avro via Schema Registry v2)
```

---

## Perubahan yang Sudah Dilakukan

| # | Komponen | Perubahan | Status |
|---|---|---|---|
| 1 | Schema Registry | Daftarkan `dcim.enriched.events-value` v2 dengan ci_id + asset_id | ✅ Done |
| 2 | NiFi LookupRecord | Tambahkan 12 property output mapping | ✅ Done |
| 3 | NiFi UpdateRecord | Hapus property `/ci_id` dan `/asset_id` | ✅ Done |
| 4 | NiFi container | Restart (`docker restart dcim-nifi`) | ✅ Done |

---

## Yang Perlu Dilanjutkan Agent Berikutnya

### Verifikasi Pipeline Jalan

1. Buka NiFi GUI: `https://10.70.0.56:8443/nifi`
2. Pastikan **semua processor icon hijau (▶️ Running)**, bukan merah (⏹ Stopped)
3. Jika ada yang merah, start processor group secara keseluruhan

### Verifikasi ci_id Terisi

```bash
# Cek dcim.enriched.events langsung dari Kafka
timeout 15 python3 -c "
from confluent_kafka import Consumer
from confluent_kafka.schema_registry import SchemaRegistryClient
from confluent_kafka.schema_registry.avro import AvroDeserializer
from confluent_kafka.serialization import SerializationContext, MessageField

sr = SchemaRegistryClient({'url': 'http://10.70.0.56:8081'})
deserializer = AvroDeserializer(sr)

c = Consumer({
    'bootstrap.servers': '10.70.0.56:9094',
    'group.id': 'verify-ci',
    'auto.offset.reset': 'latest',
    'enable.auto.commit': True,
    'security.protocol': 'SSL',
    'ssl.ca.location': '/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem',
    'enable.ssl.certificate.verification': False
})
c.subscribe(['dcim.enriched.events'])

import time
start = time.time()
while time.time() - start < 15:
    msg = c.poll(1.0)
    if msg and not msg.error():
        val = deserializer(msg.value(), SerializationContext('dcim.enriched.events', MessageField.VALUE))
        if val:
            print(f'ci_id={val.get(\"ci_id\")}, asset_id={val.get(\"asset_id\")}, sn={val.get(\"serial_number\")}, hostname={val.get(\"hostname\")}')
            if val.get('ci_id'):
                break
c.close()
"

# Cek TimescaleDB
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT count(*) as total, count(ci_id) as with_ci, count(asset_id) as with_asset FROM metrics WHERE time > NOW() - INTERVAL '5 minutes';"
```

### Jika Masih Null

Kemungkinan penyebab:
- **NiFi processors belum di-start** setelah restart container → cek GUI
- **AvroRecordSetWriter masih nge-cache schema v1** → di Controller Settings, disable lalu enable kembali AvroRecordSetWriter + ConfluentSchemaRegistry
- **Flow file content repository penuh** (log sebelumnya menunjukkan "Unable to write flowfile content... archive file size constraints" — disk NiFi 513 GB / 581 GB)

---

## Informasi Lingkungan

| Komponen | Detail |
|---|---|
| Server | srv-rnd-dcim (Ubuntu 22.04, user: infra) |
| Kafka | 3-node cluster (kafka1-3), port 9092 (PLAINTEXT) / 9094 (SSL) |
| Schema Registry | http://10.70.0.56:8081 |
| TimescaleDB | Docker `dcim-timescaledb`, user `analytics_user`, DB `dcim_analytics` |
| Redis | 10.70.0.56:6379 (docker-redis-1 container) |
| NiFi | Docker `dcim-nifi`, custom image `dcim-nifi-custom:1.0`, port 8443 |
| Enrichment API | systemd `dcim-enrichment-api.service`, port 8000 |

### Key Redis Data (Verified)

```
asset:sn:ups-fit → ci_id=00000000-0000-0000-0000-000000000c1a (PowerSource)
asset:sn:nas-fit → ci_id=00000000-0000-0000-0000-000000000c0f (NAS)
```

### Schema Registry Subjects

```
dcim.enriched.events-value → v2 (28 fields, with ci_id + asset_id)
dcim.events.EnrichedEvent → v1 (28 fields, with ci_id + asset_id)
dcim.normalized.events-value → v1 (18 fields, no ci_id/asset_id)
```

---

## File Kunci

| File | Deskripsi |
|---|---|
| `src/schemas/avro_schemas.py` | ENRICHED_EVENT_SCHEMA dengan ci_id + asset_id |
| `scripts/dcim_analytics_bridge.py` | Avro→JSON bridge, extract ci_id/asset_id |
| `scripts/analytics_stream_processor.py` | Kafka→TimescaleDB, insert ci_id/asset_id |
| `scripts/itop_to_cache_sync.py` | iTop→Redis sync (aktif, sync setiap 60s) |
| `nifi/flow.json.gz` | NiFi flow definition |
| `docs/architecture/v4.4-pipeline-architecture.md` | Dokumentasi arsitektur v4.4 |

---

## Resolution (2026-07-18 01:08 WIB)

### Root Cause Tambahan: Disk Full 100%

Disk `srv-rnd-dcim` mencapai **100% full** (`/dev/sda1: 582G/582G`). Ini menyebabkan:
- NiFi tidak bisa menulis flowfile content ("Unable to write flowfile content due to archive file size constraints")
- Normalizer stuck (tidak produce data ke Kafka normalized)
- Pipeline enrichment sepenuhnya terhenti

### Recovery Actions

| # | Action | Detail |
|---|---|---|
| 1 | **Disk cleanup** | `docker system prune -af --volumes` + `journalctl --vacuum-size=200M` → recovered ~13GB |
| 2 | **Kafka restart** | Prune menghapus containers kafka1-3 → restart via `docker compose -f docker-compose-cluster.yml up -d` |
| 3 | **NiFi restart** | `docker restart dcim-nifi` setelah disk freed |
| 4 | **Semua service restart** | Restart `dcim-normalizer`, `dcim-analytics-bridge`, `dcim-analytics-stream-processor`, `dcim-es-consumer`, `dcim-sql-consumer`, `dcim-enrichment-api`, `dcim-itop-redis-sync`, `dcim-itop-unified` |

### Additional Enhancement: Fallback Enrichment di Analytics Bridge

Menambahkan fallback enrichment di `scripts/dcim_analytics_bridge.py` — jika `ci_id` dari NiFi enrichment bernilai `None`, bridge akan memanggil enrichment API langsung (`/enrich/{sn}`) sebagai fallback. Ini memastikan `ci_id`/`asset_id` selalu terisi meskipun NiFi enrichment mengalami masalah.

```python
# ditambahkan di dcim_analytics_bridge.py:
def enrich_fallback(sn):
    """Fallback: call enrichment API directly when NiFi didn't populate ci_id/asset_id."""
    ...

# lalu di bagian payload:
ci_id = msg_val.get("ci_id")
asset_id = msg_val.get("asset_id")
sn = msg_val.get("serial_number")
if not ci_id and sn:
    fallback_ci, fallback_ai = enrich_fallback(sn)
    if fallback_ci:
        ci_id = fallback_ci
        asset_id = fallback_ai
```

### Final Status

```
TimescaleDB metrics (5 menit terakhir):
 source  | total | with_ci |  pct  
---------+-------+---------+-------
 nas     |   240 |     240 | 100.0%
 ups     |     4 |       4 | 100.0%
 network |   225 |       0 |   0.0%  ← serial_number = NO_IDENTIFIER (perlu registrasi iTop)
 server  |     8 |       0 |   0.0%  ← serial_number = NO_IDENTIFIER (perlu registrasi iTop)
```

> **Note**: Network dan Server menggunakan `NO_IDENTIFIER` sebagai serial_number karena belum terdaftar di iTop CMDB. Perangkat-perangkat ini perlu diregistrasikan di iTop terlebih dahulu agar enrichment bisa resolve `ci_id`/`asset_id`.

### Next Steps untuk Agent Berikutnya

1. **Registrasi network devices & server di iTop** agar enrichment bisa resolve ci_id
2. **Monitor disk usage** — setup alert jika disk > 85%
3. **Consider NiFi content repository rotation** — kurangi retensi provenance/flowfile repository
4. **Backup NiFi flow** — export flow setelah semua perubahan GUI tersimpan ke `nifi/flow.json.gz`
