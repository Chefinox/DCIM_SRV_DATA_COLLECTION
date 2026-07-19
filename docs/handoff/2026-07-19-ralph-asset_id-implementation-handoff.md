# Handoff: Implementasi asset_id dari Ralph (Asset Repository)

> **Tanggal dibuat**: 2026-07-19  
> **Server**: srv-rnd-dcim (10.70.0.56)  
> **User**: infra  
> **Status**: 📋 Ready for implementation  
> **Prioritas**: P1 (tim AI butuh join metrics ke data finansial)  
> **Estimasi**: 4-6 jam kerja  

---

## Ringkasan Masalah

Saat ini `asset_id` di TimescaleDB `metrics` table **selalu sama dengan `ci_id`** — keduanya berasal dari iTop CMDB. Menurut dcim-wiki (`block2-data-ingestion-integration.md` §6), `asset_id` **seharusnya berasal dari Asset Repository (Ralph)**, bukan dari CMDB.

Dampak:
- Tim AI tidak bisa join `metrics.asset_id` ke data finansial di Ralph (harga, kontrak, warranty)
- Data lineage tidak valid untuk asset tracking

## Target

`asset_id` di Redis cache dan TimescaleDB harus menunjuk ke **Ralph Asset ID**, bukan iTop CI ID. Sementara `ci_id` tetap dari iTop.

```
Saat ini (salah):
  ci_id   = 00000000-0000-0000-0000-000000000c0f (iTop)
  asset_id = 00000000-0000-0000-0000-000000000c0f (iTop, SAMA)

Seharusnya:
  ci_id   = 00000000-0000-0000-0000-000000000c0f (iTop, TETAP)
  asset_id = <ralph-asset-uuid> (Ralph, BERBEDA)
```

---

## 1. Konteks Infrastructure

### Server

| Item | Detail |
|------|--------|
| Hostname | `srv-rnd-dcim` |
| IP | `10.70.0.56` |
| OS | Ubuntu 22.04.5 LTS |
| User | `infra` |
| Disk | **582G, ~99% full** (critical — cleanup sebelum mulai!) |

### Container & Services

| Container/Service | Port | Kredensial/Notes |
|---|---|---|
| iTop | `:8080` | `admin / Inovasi@0918` (REST API basic auth) |
| Ralph | `:8082` | Token: `60bcedc875ec7b03b983082655e473e9519d40d5` |
| Redis (enrichment cache) | `:6379` | Container `dcim-redis-cache`, db=0, no password |
| Redis (legacy) | `:6379` | Container `docker-redis-1` (HANYA untuk SIEM, jangan dipakai) |
| PostgreSQL | `:5432` | DB `dcim_sot`, user `sot_admin` |
| TimescaleDB | `:5433` | DB `dcim_analytics`, user `analytics_user`, pass: `changeme` |
| Schema Registry | `:8081` | Confluent, no auth |
| Vault | `:8200` | AppRole auth, role_id/secret_id di `vault/config/` |
| Kafka | `:9092` (PLAINTEXT internal), `:9094` (SSL) | 3-node cluster |
| NiFi | `:8443` (HTTPS) | `admin / Inovasi@0918` |

### Pipeline Services (systemd)

```bash
# Semua service aktif:
dcim-normalizer          # Raw → Normalized events (Avro)
dcim-enrichment-api      # FastAPI :8000 /enrich/{sn}
dcim-itop-redis-sync     # iTop → Redis cache (setiap 60s)
dcim-analytics-bridge    # Avro enriched → JSON analytics metrics
dcim-analytics-stream-processor  # Kafka JSON → TimescaleDB
dcim-es-consumer         # → Elasticsearch
dcim-sql-consumer        # → PostgreSQL (dcim_events)
dcim-itop-unified        # → iTop CMDB auto-create/update
```

---

## 2. Project Structure (Hanya yang Relevan)

```
/home/infra/dcim_metrics_project/
├── scripts/
│   ├── itop_to_cache_sync.py       ★ HARUS DIUBAH
│   ├── itop_to_ralph_sync.py       ★ Sumber asset_id dari Ralph
│   ├── dcim_analytics_bridge.py    ★ Consumer (terima ci_id/asset_id)
│   └── analytics_stream_processor.py  ★ Insert ke TimescaleDB
├── configs/
│   └── systemd/                    ★ Service definitions
├── vault/config/                    ★ Vault role_id/secret_id
├── docs/
│   ├── handoff/                    ★ Handoff docs
│   ├── architecture/v4.4-pipeline-architecture.md
│   └── standar_dcim/               ★ AI team docs
└── src/
    ├── schemas/avro_schemas.py     ★ Avro schema definitions
    └── skills/inventory/enrichment/executor.py  ★ Enrichment API
```

### Repository

```
Remote: git@github.com:Chefinox/DCIM_SRV_DATA_COLLECTION.git
Branch: main
HEAD: db6c6d0 (sudah di-push)
```

---

## 3. Arsitektur Pipeline v4.4 (disimpulkan)

```
[RAW] NiFi Pollers → dcim.raw.* (Kafka JSON)
        ↓
[NORM] dcim-normalizer → dcim.normalized.events (Kafka Avro)
        ↓
[ENRICH] NiFi (Consume → UpdateRecord → LookupRecord → PublishKafka)
         LookupRecord memanggil http://172.17.0.1:8000/enrich/${sn}
         ↓
         dcim.enriched.events (Kafka Avro, Schema Registry v2, 28 fields)
        ↓
[BRIDGE] dcim-analytics-bridge (Avro→JSON + fallback enrichment)
         Jika ci_id=None, panggil enrichment API langsung
         ↓
         dcim.analytics.metrics (Kafka JSON)
        ↓
[TSDB] analytics-stream-processor → TimescaleDB metrics hypertable
```

---

## 4. Flow Data ci_id/asset_id Saat Ini

```
iTop CMDB (key: integer, e.g. 3087)
  │
  │  itop_to_cache_sync.py (line 165 & 181):
  │    ci_uuid = str(uuid.UUID(int=int(ci_key)))
  │    meta = {"ci_id": ci_uuid, "asset_id": ci_uuid}  ← asset_id = ci_id
  │
  ▼
Redis cache (dcim-redis-cache, port 6379)
  │  Key: asset:sn:{serial_number}
  │  e.g. asset:sn:2410v3rczj09k → {"ci_id":"...c0f","asset_id":"...c0f"}
  │
  ▼
Enrichment API (FastAPI :8000)
  │  GET /enrich/{sn} → baca Redis, return JSON
  │
  ▼
Analytics Bridge (dcim_analytics_bridge.py)
  │  Ambil ci_id/asset_id dari payload Avro
  │  Jika None → fallback: panggil enrichment API
  │
  ▼
TimescaleDB metrics table
  │  columns: ci_id UUID, asset_id UUID
  │  Saat ini KEDUANYA SAMA (dari iTop)
```

---

## 5. Ralph Asset Repository — Yang Perlu Dipahami

### Ralph API

Ralph adalah Asset Repository untuk data finansial & lifecycle asset.

```
Base URL: http://10.70.0.56:8082
Auth: Token 60bcedc875ec7b03b983082655e473e9519d40d5
Auth Header: Authorization: Token <token>
```

### Endpoint Penting

```bash
# List all Data Center Assets
curl -s "http://10.70.0.56:8082/api/data-center-assets/" \
  -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5"

# Search by serial number (kalau ada field search)
curl -s "http://10.70.0.56:8082/api/data-center-assets/?search=2410V3RCZJ09K" \
  -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5"

# Get ethernets for an asset
curl -s "http://10.70.0.56:8082/api/ethernets/?base_object=<asset_id>" \
  -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5"
```

### Sync dari iTop ke Ralph (existing)

`itop_to_ralph_sync.py` dijalankan **harian jam 02:00 WIB** (systemd timer `dcim-itop-ralph-sync.timer`). Script ini:
1. Tarik CI dari iTop (Server, NetworkDevice, StorageSystem, PowerSource)
2. Cari asset yang cocok di Ralph berdasarkan serial number
3. Jika tidak ada → create baru di Ralph
4. Jika ada → update fields (hostname, IP, model, dll.)

**Yang belum ada**: reverse-sync Ralph → Redis cache untuk asset_id lookup.

---

## 6. Yang Perlu Dilakukan (Implementation Plan)

### Phase 1: Research Ralph API (30 min)

1. Buka Ralph web UI: `http://10.70.0.56:8082`
2. Telusuri API Ralph untuk memahami:
   - Apakah Ralph asset punya field yang bisa dipakai sebagai lookup key? (serial_number, barcode, CI ID iTop?)
   - Bagaimana relasi Ralph Asset ID → iTop CI ID?
   - Apakah ada custom field yang menyimpan iTop CI reference?

```bash
# Coba query beberapa endpoint:
curl -s "http://10.70.0.56:8082/api/data-center-assets/?limit=3" \
  -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5" | python3 -m json.tool | head -50

# Back Office assets
curl -s "http://10.70.0.56:8082/api/back-office-assets/?limit=3" \
  -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5" | python3 -m json.tool | head -30
```

### Phase 2: Design Cache Strategy (30 min)

Pilih salah satu approach:

**Option A: Update itop_to_cache_sync.py (direkomendasikan)**

Modifikasi `build_metadata()` untuk lookup Ralph asset_id saat sync berjalan:

```python
def get_ralph_asset_id(serial_number: str, ci_class: str) -> Optional[str]:
    """Look up Ralph asset ID by serial number."""
    url = f"{RALPH_API_BASE}/data-center-assets/?search={serial_number}"
    headers = {"Authorization": f"Token {RALPH_TOKEN}"}
    # ... HTTP request ...
    return asset_id or None

def build_metadata(ci_class, fields, ci_key):
    # Existing: ci_uuid from iTop
    ci_uuid = str(uuid.UUID(int=int(ci_key)))
    
    # NEW: lookup Ralph asset_id
    sn = fields.get("serialnumber", "")
    ralph_asset_id = get_ralph_asset_id(sn, ci_class) if sn else None
    
    return {
        "ci_id": ci_uuid,
        "asset_id": ralph_asset_id,  # ← dari Ralph, bukan iTop
        # ... field lainnya ...
    }
```

**Option B: Buat service terpisah ralph_to_cache_sync.py**

Sync independen yang berjalan paralel dengan itop_to_cache_sync.
Populate Redis key `asset:id:{serial}` dengan Ralph Asset ID.

### Phase 3: Implementation (2 jam)

1. **Research & verifikasi Ralph API** — pastikan ada asset dengan serial yang match
2. **Modifikasi `itop_to_cache_sync.py`**:
   - Tambah fungsi `get_ralph_asset_id(serial_number)` 
   - Update `build_metadata()` untuk set `asset_id` dari Ralph
   - Config RALPH_TOKEN via Vault atau env variable
3. **Testing**:
   ```bash
   # Jalankan sync manual
   python3 scripts/itop_to_cache_sync.py --once
   
   # Verifikasi Redis
   docker exec dcim-redis-cache redis-cli GET "asset:sn:2410v3rczj09k" | python3 -m json.tool
   # → pastikan asset_id ≠ ci_id
   ```
4. **Restart enrichment pipeline**:
   ```bash
   sudo systemctl restart dcim-itop-redis-sync dcim-analytics-bridge dcim-analytics-stream-processor
   ```

### Phase 4: Verification (30 min)

```bash
# Cek TimescaleDB — asset_id harus berbeda dari ci_id
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT ci_id, asset_id, 
       CASE WHEN ci_id = asset_id THEN 'SAMA - BROKEN' ELSE 'OK - BERBEDA' END as status,
       count(*) 
       FROM metrics 
       WHERE time > NOW() - INTERVAL '5 minutes' 
       AND ci_id IS NOT NULL 
       GROUP BY 1,2,3;"

# Cek enrichment API
curl -s http://10.70.0.56:8000/enrich/2410V3RCZJ09K | python3 -m json.tool | grep -E "ci_id|asset_id"
```

### Phase 5: Commit & Handoff (30 min)

```bash
cd /home/infra/dcim_metrics_project
git add scripts/itop_to_cache_sync.py
git commit -m "fix: asset_id now sourced from Ralph Asset Repository instead of iTop"
git push origin main
```

---

## 7. File yang Perlu Dikenali

### Key Files (wajib dibaca sebelum mulai)

| File | Mengapa Penting |
|------|----------------|
| `scripts/itop_to_cache_sync.py` | ★ Target utama modifikasi — ini yang ngisi Redis cache |
| `scripts/itop_to_ralph_sync.py` | Referensi — cara akses Ralph API |
| `scripts/dcim_analytics_bridge.py` | Consumer — cara ci_id/asset_id sampai ke Kafka |
| `scripts/analytics_stream_processor.py` | Consumer — cara ci_id/asset_id masuk TimescaleDB |
| `src/schemas/avro_schemas.py` | Avro schema — ENRICHED_EVENT_SCHEMA |

### Reference Documents (baca jika butuh konteks lebih)

| Dokumen | Kapan Dibaca |
|---------|-------------|
| `docs/handoff/2026-07-17-ci_id-asset_id-fix-handoff.md` | Sejarah perbaikan ci_id sebelumnya |
| `docs/architecture/v4.4-pipeline-architecture.md` | Arsitektur pipeline lengkap |
| `dcim-wiki/reference-designs/block2-data-ingestion-integration.md` §6 | Enrichment processor reference |
| `dcim-wiki/reference-designs/block3-asset-repository.md` | Asset Repository reference |
| `dcim-wiki/entities/asset-repository.md` | Entity detail |

---

## 8. Perhatian / Gotchas

1. **Disk 99% full** — cleanup dulu: `sudo journalctl --vacuum-size=200M && docker system prune -f`
2. **Jangan gunakan Redis container `docker-redis-1`** — itu untuk SIEM legacy. Pakai `dcim-redis-cache`
3. **Ralph basic auth berbeda** — pakai Token di header, bukan Basic Auth seperti iTop
4. **Jika Ralph tidak punya asset untuk device tertentu**: set `asset_id = None` — jangan fallback ke ci_id
5. **Schema Registry v2** — `dcim.enriched.events-value` sudah punya field `ci_id` dan `asset_id` (28 fields total)
6. **Vault** — credential disimpan di KV-v2 path `secret/dcim/*`. Access via `src/utils/secrets.py`
7. **Jangan restart Kafka** — `docker system prune` bisa hapus containers kafka1-3. Jika terjadi, restart via `docker compose -f kafka/docker-compose-cluster.yml up -d`

---

## 9. Kredensial Cepat

```bash
# iTop REST
curl -u "admin:Inovasi@0918" "http://10.70.0.56:8080/webservices/rest.php?version=1.3&json_data=..."

# Ralph REST  
curl -H "Authorization: Token 60bcedc875ec7b03b983082655e473e9519d40d5" "http://10.70.0.56:8082/api/..."

# Vault
role_id=$(cat /home/infra/dcim_metrics_project/vault/config/role_id)
secret_id=$(cat /home/infra/dcim_metrics_project/vault/config/secret_id)
# Autentikasi: POST /v1/auth/approle/login

# Redis enrichment
docker exec dcim-redis-cache redis-cli KEYS "asset:sn:*"
docker exec dcim-redis-cache redis-cli GET "asset:sn:2410v3rczj09k"

# TimescaleDB
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics

# NiFi GUI
https://10.70.0.56:8443/nifi  (admin / Inovasi@0918)
```

---

## 10. Verifikasi Pipeline Sebelum Mulai

```bash
# Pastikan semua service running
for svc in dcim-normalizer dcim-analytics-bridge dcim-analytics-stream-processor \
  dcim-enrichment-api dcim-itop-redis-sync dcim-es-consumer dcim-sql-consumer; do
  echo -n "$svc: "; systemctl is-active $svc
done

# Pastikan ci_id populated (pre-existing fix works)
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT source, count(*) total, count(ci_id) ci FROM metrics 
      WHERE time > NOW() - INTERVAL '5 minutes' GROUP BY source ORDER BY total DESC;"

# Hasil yang diharapkan: NAS 100%, Network 100%, Server 100%, UPS 100%
```

---

*Dokumen ini dibuat pada 2026-07-19 oleh agent infra.  
Pipeline dalam kondisi stabil — semua device type 100% ci_id coverage.  
Silakan lanjutkan ke Phase 1 (Research Ralph API).*
