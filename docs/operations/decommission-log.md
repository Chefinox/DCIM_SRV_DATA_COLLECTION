# Decommission Log

Catatan decommission untuk layanan yang dinonaktifkan selama migrasi DCIM v3.5.6 → v4.0.0.

---

## 2026-06-11 — dcim-kafka-es-sync.service (Bypass ES Sync)

**Status**: Disabled  
**Service file**: `/etc/systemd/system/dcim-kafka-es-sync.service`  
**Script**: `scripts/kafka_to_es_sync.py`

**Deskripsi**:  
Service ini adalah bypass path yang mengirim data langsung dari `dcim.normalized.events` (Kafka) ke Elasticsearch tanpa melalui enrichment pipeline. Data yang dikirim belum memiliki metadata enrichment (site, rack, manufacturer, model).

**Alasan decommission**:  
Dalam arsitektur v4.0.0, Elasticsearch hanya menerima data dari single path: `dcim.enriched.events` → consumer → ES. Ini memastikan semua data di ES sudah ter-enrichment dengan metadata dari iTop.

**Kondisi saat decommission**:
- ES container (`es01`): Exited (255) — perlu restart terpisah
- Kibana container (`kib01`): Exited (255) — perlu restart terpisah
- `dcim-sql-consumer.service`: inactive
- Service sudah aktif sejak sebelum migrasi, mengonsumsi `dcim.normalized.events`

**Rollback**:
```bash
sudo systemctl enable --now dcim-kafka-es-sync.service
```

---

## 2026-06-11 — cmdb_to_cache_sync.py (PG → Redis Cache Sync)

**Status**: Siap dinonaktifkan (belum di-disable, menunggu cutover)  
**Service file**: `/etc/systemd/system/dcim-redis-sync.service`  
**Script**: `scripts/cmdb_to_cache_sync.py`

**Deskripsi**:  
Script ini menarik data dari PostgreSQL `unified_assets` dan menyimpannya ke Redis sebagai enrichment cache. Digantikan oleh `scripts/itop_to_cache_sync.py` yang menarik data dari iTop REST API.

**Alasan**:  
iTop menjadi metadata authority — Redis cache harus diisi dari iTop, bukan dari PostgreSQL.

**Rollback**:
```bash
sudo systemctl enable --now dcim-redis-sync.service
# Pastikan dcim-itop-redis-sync.service tetap berjalan (tidak konflik)
```

---

## 2026-06-11 — ralph_cmdb_sync.py (PG → Ralph Sync)

**Status**: Siap dinonaktifkan (belum di-disable, menunggu cutover)  
**Script**: `scripts/ralph_cmdb_sync.py`  
**Timer**: `/etc/systemd/system/dcim-ralph-sync.timer`

**Deskripsi**:  
Script ini membaca data dari PostgreSQL `dcim_events` dan menyinkronkannya ke Ralph CMDB. Digantikan oleh `scripts/itop_to_ralph_sync.py` yang membaca dari iTop REST API.

**Alasan**:  
iTop menjadi metadata authority — Ralph sync harus dari iTop, bukan dari PostgreSQL.

**Rollback**:
```bash
sudo systemctl enable --now dcim-ralph-sync.timer
```
