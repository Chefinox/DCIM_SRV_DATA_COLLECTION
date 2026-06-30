# Prompt Implementasi: Migrasi Arsitektur DCIM ke iTop sebagai Metadata Authority

---

## Konteks Proyek

Kamu adalah AI agent yang bekerja pada proyek `dcim_metrics_project` — sebuah pipeline monitoring Data Center Infrastructure Management (DCIM). Proyek ini berjalan di Ubuntu 24, menggunakan Python, Apache Kafka, Apache NiFi, Redis, PostgreSQL, dan iTop CMDB.

**Versi saat ini**: v3.5.6  
**Tujuan migrasi**: v4.0.0 — menjadikan iTop sebagai sumber metadata utama (metadata authority), menggantikan peran PostgreSQL sebagai hub sinkronisasi CMDB.

### Struktur direktori relevan

```
dcim_metrics_project/
├── configs/
│   └── .env                          # Semua kredensial (Kafka, DB, API)
├── scripts/
│   ├── cmdb_to_cache_sync.py         # AKAN DIGANTIKAN (PG → Redis)
│   ├── ralph_cmdb_sync.py            # AKAN DIGANTIKAN (PG → Ralph)
│   ├── dcim_itop_inventory_sync.py   # TETAP DIPERTAHANKAN (PG → iTop, every 5 min)
│   └── ...
├── src/
│   └── services/
│       └── apis/                     # FastAPI enrichment service
└── docs/
    └── development/                  # Tempat menyimpan dokumentasi baru
```

### Environment variables yang tersedia di `.env`

```
ITOP_BASE_URL=http://localhost:8080
ITOP_USER=...
ITOP_PASSWORD=...
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
RALPH_URL=http://localhost:8082
RALPH_API_TOKEN=...
PG_HOST=localhost
PG_PORT=5432
PG_DB=dcim_sot
PG_USER=...
PG_PASSWORD=...
```

---

## Yang TIDAK boleh diubah

Sebelum memulai, pahami komponen yang **tidak boleh disentuh**:

- `dcim_itop_inventory_sync.py` — script ini tetap berjalan, ia yang mengisi hardware metadata (serial number, model, kapasitas) ke iTop dari PostgreSQL. Tanpa ini, iTop tidak punya data cukup untuk menjadi metadata authority.
- Semua Kafka raw topics dan normalizer (`dcim-normalizer.service`)
- Konfigurasi Telegraf dan CCTV poller
- Schema PostgreSQL yang sudah ada
- Konfigurasi Elasticsearch dan Kibana
- Alerting service (`dcim-threshold-alerter.service`)
- DLQ consumers

---

## Task 1 — Buat `itop_to_cache_sync.py`

**Lokasi**: `scripts/itop_to_cache_sync.py`  
**Tujuan**: Menggantikan `cmdb_to_cache_sync.py`. Menarik data CI dari iTop REST API dan menyimpannya ke Redis sebagai enrichment cache.

### Spesifikasi

**Sumber**: iTop REST API  
Endpoint: `POST {ITOP_BASE_URL}/webservices/rest.php`  
Content-Type: `application/x-www-form-urlencoded`

Payload query iTop (OQL):
```
version=1.3
auth_user={ITOP_USER}
auth_pwd={ITOP_PASSWORD}
json_data={
  "operation": "core/get",
  "class": "Server",
  "key": "SELECT Server",
  "output_fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status,org_name"
}
```

Ulangi query untuk class: `NetworkDevice`, `StorageSystem`, `UPS`, `IPPhone` (sesuaikan dengan class yang ada di iTop instance).

**Target**: Redis  
Key format: `asset:sn:{serialnumber}` (lowercase, strip spasi)  
Value format (JSON string):
```json
{
  "sn": "...",
  "name": "...",
  "location": "...",
  "rack": "...",
  "brand": "...",
  "model": "...",
  "status": "...",
  "org": "...",
  "ci_class": "Server",
  "synced_at": "2026-06-11T00:00:00+07:00"
}
```
TTL: 3600 detik

**Perilaku wajib**:
- Jika iTop API tidak dapat dijangkau atau error, **jangan flush Redis** — log error dan skip iterasi
- Jika satu CI gagal di-parse, skip CI tersebut dan lanjutkan ke CI berikutnya
- Log summary di akhir setiap run: `Synced: X, Skipped: Y, Redis keys: Z`
- Interval run: 60 detik (gunakan `time.sleep(60)` dalam infinite loop, atau jadwalkan via systemd timer)
- Load semua kredensial dari `.env` menggunakan `python-dotenv`

**Template systemd unit** (simpan di `configs/systemd/dcim-redis-sync.service`):
```ini
[Unit]
Description=DCIM Redis Cache Sync — iTop to Redis
After=network.target docker.service

[Service]
Type=simple
User=dcim
WorkingDirectory=/opt/dcim_metrics_project
ExecStart=/usr/bin/python3 scripts/itop_to_cache_sync.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

---

## Task 2 — Buat `itop_to_ralph_sync.py`

**Lokasi**: `scripts/itop_to_ralph_sync.py`  
**Tujuan**: Menggantikan `ralph_cmdb_sync.py`. Sinkronisasi aset dari iTop ke Ralph Asset Management.

### Spesifikasi

**Sumber A — Metadata CI dari iTop** (sama seperti Task 1, gunakan fungsi yang bisa di-reuse):
- Ambil semua CI dari iTop dengan field: `name`, `serialnumber`, `location_name`, `rack_name`, `brand_name`, `model_name`, `status`

**Sumber B — Hardware component dari PostgreSQL** (untuk enrichment detail):
```sql
SELECT
    ua.serial_number,
    ua.ram_total_gb,
    ua.cpu_count,
    ua.cpu_model,
    ua.disk_total_gb
FROM unified_assets ua
WHERE ua.serial_number IS NOT NULL
```
Gunakan ini untuk melengkapi data yang dikirim ke Ralph.

**Target**: Ralph REST API  
Base URL: `{RALPH_URL}/api/`  
Header: `Authorization: Token {RALPH_API_TOKEN}`

Alur sinkronisasi per device:
1. Cari device di Ralph: `GET /api/data-center-assets/?serial_number={sn}`
2. Jika ada → `PATCH /api/data-center-assets/{id}/` dengan data terbaru
3. Jika tidak ada → `POST /api/data-center-assets/` untuk register baru

Field mapping iTop → Ralph:
```python
{
    "hostname": ci["name"],
    "serial_number": ci["serialnumber"],
    "location": ci["location_name"],
    "rack": ci["rack_name"],
    "manufacturer": ci["brand_name"],
    "model": ci["model_name"],
    "status": "in use" if ci["status"] == "production" else "free",
    # dari PostgreSQL jika tersedia:
    "memory": f"{pg_data['ram_total_gb']} GB",
    "cpu_cores": pg_data["cpu_count"],
}
```

**Perilaku wajib**:
- Jalankan satu kali (bukan daemon) — dijadwalkan via cron: `0 2 * * * python3 scripts/itop_to_ralph_sync.py`
- Jika Ralph API down, abort seluruh run dan kirim log error
- Log setiap action: `[PATCH] Server-01 (SN: XYZ123) — OK` atau `[POST] New device registered`
- Simpan summary ke `logs/itop_to_ralph_sync_YYYYMMDD.log`

---

## Task 3 — Modifikasi Enrichment API: Hapus PG Fallback

**Lokasi**: `src/services/apis/` (cari file yang mengandung endpoint `/enrich/{sn}` atau `/enrich`)

### Yang harus diubah

Cari pola kode seperti ini:
```python
# Pola yang harus DIHAPUS:
result = redis_client.get(f"asset:sn:{sn}")
if result is None:
    # fallback ke PostgreSQL
    result = db.query("SELECT ... FROM unified_assets WHERE serial_number = %s", sn)
    ...
```

Ganti dengan:
```python
result = redis_client.get(f"asset:sn:{sn}")
if result is None:
    # Cache miss — jangan fallback ke PG
    logger.warning(f"Cache miss for SN: {sn} — returning empty enrichment")
    return {"sn": sn, "enriched": False, "reason": "cache_miss"}
```

**Catatan penting**: Jangan hapus import atau dependency PostgreSQL yang mungkin digunakan untuk keperluan lain di file yang sama. Hanya hapus logika fallback pada endpoint enrichment.

Setelah perubahan, pastikan:
- Unit test endpoint `/enrich/{sn}` dengan skenario: cache hit, cache miss (harus return empty, bukan error 500)
- Tidak ada query ke tabel `unified_assets` dipanggil selama enrichment

---

## Task 4 — Nonaktifkan Bypass ES Sync

**Tujuan**: Memastikan Elasticsearch hanya menerima data dari `dcim.enriched.events` (single path), bukan dari bypass langsung.

### Langkah-langkah

**4a. Verifikasi dulu bahwa single path sudah berjalan:**
```bash
# Cek apakah telegraf-consumer atau consumer enriched→ES sudah aktif
systemctl status dcim-kafka-es-sync.service
systemctl status dcim-sql-consumer.service

# Cek consumer group yang mengonsumsi dcim.enriched.events
kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe \
  --group dcim-enriched-consumers 2>/dev/null || \
kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --list | xargs -I{} kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group {}
```

**4b. Hitung volume dokumen di ES selama 24 jam terakhir** untuk memastikan pipeline enriched berjalan:
```bash
curl -s "http://10.70.0.56:9200/dcim-metrics-unified-*/_count?pretty" \
  -H 'Content-Type: application/json' \
  -d '{"query":{"range":{"@timestamp":{"gte":"now-24h"}}}}'
```

**4c. Jika volume normal, nonaktifkan bypass:**
```bash
systemctl stop dcim-kafka-es-sync.service
systemctl disable dcim-kafka-es-sync.service
```

**4d. Buat catatan decommission** di `docs/operations/decommission-log.md`:
```markdown
## 2026-06-11 — dcim-kafka-es-sync.service

Service ini (bypass path: normalized.events → ES langsung) dinonaktifkan.
Digantikan oleh single path: enriched.events → consumer → ES.
Alasan: ES sebelumnya menerima data tanpa enrichment metadata.
Jika perlu rollback: systemctl enable --now dcim-kafka-es-sync.service
```

---

## Task 5 — Buat `itop-api-baseline-for-agents.md`

**Lokasi**: `docs/development/itop-api-baseline-for-agents.md`

Dokumen ini adalah referensi untuk AI agent yang perlu query atau update data di iTop. Isi dengan:

### Bagian yang wajib ada dalam dokumen

1. **Endpoint dan autentikasi**
   - URL: `POST {ITOP_BASE_URL}/webservices/rest.php`
   - Format: `application/x-www-form-urlencoded`
   - Parameter: `version`, `auth_user`, `auth_pwd`, `json_data`

2. **Operasi dasar** dengan contoh `json_data` payload:
   - `core/get` — membaca CI
   - `core/create` — membuat CI baru
   - `core/update` — update atribut CI
   - `core/apply_stimulus` — mengubah lifecycle state (misal: `evt_stock` → production)

3. **OQL Query examples** untuk class-class utama:
   ```sql
   -- Semua server di production
   SELECT Server WHERE status = 'production'
   
   -- Device berdasarkan serial number
   SELECT Server WHERE serialnumber = 'ABC123'
   
   -- Semua CI di rack tertentu
   SELECT DatacenterDevice WHERE rack_name = 'RACK-01'
   
   -- Network device berdasarkan IP
   SELECT NetworkDevice WHERE managementip LIKE '10.50.0.%'
   ```

4. **Field reference** per class: `Server`, `NetworkDevice`, `StorageSystem`, `UPS`, `Rack`, `DataCenter`

5. **Contoh Python snippet** untuk get dan update CI

6. **Error handling**: kode status iTop (`0` = OK, `1` = error), cara baca `message` field

---

## Task 6 — Parallel Run & Cutover Checklist

Setelah semua script selesai dibuat, buat file `docs/operations/migration-cutover-checklist.md` berisi:

```markdown
# Cutover Checklist: PG Hub → iTop Metadata Authority

## Pre-cutover (jalankan paralel selama 7 hari)
- [ ] `itop_to_cache_sync.py` berjalan paralel dengan `cmdb_to_cache_sync.py`
- [ ] Bandingkan Redis key count antara keduanya: harus dalam ±5% selisih
- [ ] `itop_to_ralph_sync.py` berjalan paralel dengan `ralph_cmdb_sync.py` (dry-run dulu)
- [ ] Verifikasi tidak ada cache miss meningkat di Enrichment API log

## Cutover day
- [ ] Stop `cmdb_to_cache_sync.py` / disable systemd unit lama
- [ ] Stop `ralph_cmdb_sync.py` / disable cron lama
- [ ] Konfirmasi `dcim-itop_inventory_sync.py` masih berjalan (JANGAN disable ini)
- [ ] Monitor Redis TTL expiry selama 2 jam pertama
- [ ] Monitor Kibana dashboard — pastikan data masih mengalir

## Rollback plan
Jika ada masalah dalam 24 jam pertama:
1. Re-enable `cmdb_to_cache_sync.py`
2. Re-enable `ralph_cmdb_sync.py`
3. Biarkan `itop_to_cache_sync.py` tetap jalan (tidak merusak apapun jika paralel)
```

---

## Urutan eksekusi yang disarankan

```
Task 5 → Task 1 → Task 3 → Task 2 → Task 4 → Task 6
```

Mulai dari dokumentasi (Task 5) agar agent punya referensi API iTop sebelum menulis kode. Lalu bangun script cache sync (Task 1) terlebih dahulu karena enrichment API (Task 3) bergantung pada Redis yang sudah diisi. Script Ralph sync (Task 2) bisa paralel dengan Task 3. Nonaktifkan bypass ES (Task 4) terakhir setelah semua pipeline baru verified.

---

## Definition of Done

Setiap task dianggap selesai jika:
- [ ] Script dapat dijalankan tanpa error pada run pertama
- [ ] Ada logging yang informatif (bukan hanya print)
- [ ] Credentials dibaca dari `.env`, tidak ada hardcoded value
- [ ] Ada penanganan error yang graceful (tidak crash jika satu service down)
- [ ] File ditempatkan di lokasi yang sesuai dengan struktur proyek
- [ ] Jika ada systemd unit baru, sudah ada template `.service` file-nya
