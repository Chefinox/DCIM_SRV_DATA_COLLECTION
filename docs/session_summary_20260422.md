# Rangkuman Sesi Kerja — DCIM Kafka Pipeline & FIT041 Compliance
**Tanggal**: 22 April 2026  
**Durasi Sesi**: ~09:30 — 10:23 WIB  
**Status Akhir**: ✅ Pipeline aktif penuh, compliance FIT041 diperbaiki

---

## 1. Aktivitas yang Dilakukan

### 1.1 Salin Rangkuman Sesi Sebelumnya ke NAS
- File `rangkuman_sesi.md` dari sesi 34f4de49 disalin ke NAS `10.50.0.105`
- Tujuan: `DATA - PERSONEL/Syauqi/Dokumen/`
- NAS sudah ter-mount di `/mnt/nas_personel` via CIFS

---

### 1.2 Migrasi Message Broker: RabbitMQ → Apache Kafka

**Latar belakang**: Pipeline sebelumnya menggunakan RabbitMQ sebagai broker. Keputusan migrasi ke Kafka untuk mendukung AI/ML (data replay, high throughput).

**Yang dilakukan**:
1. Deploy Apache Kafka (mode **KRaft**, tanpa Zookeeper) via Docker:
   - Image: `apache/kafka:latest`
   - Compose file: `/home/infra/dcim_metrics_project/kafka/docker-compose.yml`
   - Port: `9092`

2. Update **Telegraf Producer** (`/etc/telegraf/telegraf.conf`):
   - Hapus: `outputs.amqp` (RabbitMQ) dan `outputs.elasticsearch` langsung
   - Ganti dengan: `outputs.kafka` → topic `dcim.standardized.metrics`

3. Update **Telegraf Consumer** (`/etc/telegraf/telegraf-consumer.conf`):
   - Hapus: `inputs.amqp_consumer`
   - Ganti dengan: `inputs.kafka_consumer` (consumer group: `telegraf_es_consumer`)
   - Aktifkan kembali: `outputs.elasticsearch` (dual output: inventory + per-device)

**Arsitektur Final**:
```
[Perangkat] → [Telegraf Producer] → [Kafka: dcim.standardized.metrics] → [Telegraf Consumer] → [Elasticsearch]
```

---

### 1.3 Debug & Fix: Consumer Crash Loop

**Masalah**: `telegraf-consumer.service` crash loop dengan error:
```
plugin outputs.elasticsearch: fields ["data_source_name", "driver", "table_template"] weren't used
```

**Root Cause**: `[[outputs.sql]]` di-comment di baris header (`# [[outputs.sql]]`) tapi isi block-nya **tidak ikut di-comment** → field SQL terbaca sebagai milik `[[outputs.elasticsearch]]` di atasnya.

**Fix**: Comment seluruh blok `outputs.sql` secara lengkap. Service langsung `active (running)`.

**Bukti sukses**: Index `telegraf-server-2026.04.22` (~61k docs) dan `telegraf-ups-2026.04.22` mulai terisi.

---

### 1.4 Gap Analysis vs Standar FIT041

Setelah pipeline aktif, dilakukan cek compliance terhadap dokumen `IF-Technical_Requirements-FIT041-20260119.docx`.

**Gap yang ditemukan**:

| Field | Status | Root Cause |
|:---|:---:|:---|
| `ci_id` | ❌ | Tidak ada di output poller |
| `site` | ❌ | Dihitung di poller tapi tidak ada di `tag_keys` Telegraf |
| `rack_name` | ❌ | Sama — tidak di-forward ke Telegraf |
| `source` (metode polling) | ❌ | Tidak diset |
| `enrichment_status` | ❌ | Flag FULL/PARTIAL belum ada |
| `hostname` trailing `\n` | ❌ Bug data quality |
| `model` trailing spasi | ❌ Bug data quality |
| `manufacturer` kosong | ⚠️ | Tidak diset di poller |
| UPS `battery_runtime_remain` | ❌ | OID belum diambil |
| UPS `input_voltage` | ❌ | OID belum diambil |

---

### 1.5 Fix FIT041 Compliance

**File yang diubah**:

#### A. `dcim_inventory_poller.py`
- Setiap fungsi poller (`poll_server`, `poll_ups`, `poll_mikrotik`, `poll_nas`, `poll_hikvision`) ditambahkan field `source` (`redfish` / `snmp` / `isapi`) dan `manufacturer` (Lenovo / APC / MikroTik / Synology / Hikvision)
- `run_snmpget()`: tambah `.strip()` langsung di sumber → eliminasi trailing `\n` dari SNMP string
- Main loop: tambah strip loop untuk semua string field sebelum output
- Tambah field `ci_id = serial_number` (FIT041 mandatory)
- Enrichment block diupdate: set `enrichment_status = "FULL"` jika lokasi ditemukan, `"PARTIAL"` jika tidak
- UPS OID baru: `battery_runtime_remain` dan `input_voltage`
- NAS `category` diubah dari `"infrastructure"` → `"storage"`

#### B. `/etc/telegraf/telegraf.d/dcim-unified-inventory.conf`
```toml
# Sebelum:
tag_keys = ["hostname", "serial_number", "device_type", "category", "ip"]

# Sesudah:
tag_keys = [
  "hostname", "serial_number", "ci_id",
  "device_type", "category",
  "ip", "site", "rack_name",
  "source", "enrichment_status"
]
```

**Hasil verifikasi manual (output poller)**:
```
Total devices: 37

=== UPS ===
✅ ci_id: '9E2133T16585'
✅ hostname: 'UPS-APC-30K'      ← tidak ada \n lagi
✅ model: '30KH'                ← tidak ada trailing spasi
✅ manufacturer: 'APC'
✅ site: 'FIT-Head-Office'
✅ rack_name: 'Unknown'         ← PARTIAL, IP UPS belum di location map
✅ source: 'snmp'
✅ enrichment_status: 'PARTIAL'

=== NAS ===
✅ ci_id: '2230RLRHB9A4J'
✅ site: 'FIT-Head-Office'
✅ rack_name: 'Rack Server 2 (U1-U2 Bawah)'
✅ enrichment_status: 'FULL'
```

---

## 2. Dokumentasi yang Dibuat / Diperbarui

| File | Aksi | Keterangan |
|:---|:---|:---|
| `docs/19-kafka-pipeline-architecture.md` | **Baru** | Detail teknis full Kafka: arsitektur, config, troubleshooting, status komponen |
| `docs/01-data-flow-architecture.md` | **Update** | Diagram Mermaid diperbarui + layer Kafka + referensi |
| `docs/12-brokered-metrics-pipeline.md` | **Rewrite** | Konten RabbitMQ diganti Kafka sepenuhnya |
| `docs/14-standardization-telemetry-schema.md` | **Update** | Footer & referensi broker diperbarui |

---

## 3. Status Komponen Pipeline (per 22 April 2026, 10:23 WIB)

| Komponen | Status | Keterangan |
|:---|:---:|:---|
| `kafka-broker` (Docker) | ✅ Running | Port 9092, mode KRaft |
| `telegraf.service` (Producer) | ✅ Running | Kirim ke Kafka |
| `telegraf-consumer.service` | ✅ Running | Kafka → Elasticsearch |
| Elasticsearch index update | ✅ Live | server, ups, mikrotik, dll. |
| `outputs.sql` (PostgreSQL) | ⚠️ Off | Kolom `lower_threshold_critical` tidak ada di tabel `server_redfish` |
| FIT041: `ci_id`, `site`, `rack_name` | ✅ Diperbaiki | Aktif di siklus poller berikutnya (300s) |
| Kafka → Ralph CMDB Consumer | 🔲 Belum | Target arsitektur masa depan |
| Kafka → AI/ML Consumer | 🔲 Belum | Target arsitektur masa depan |

---

## 4. Item Open (Perlu Ditindaklanjuti)

1. **UPS `enrichment_status: PARTIAL`** — IP `192.168.100.140` belum ada di location map PostgreSQL/static. Solusi: tambahkan entry ke `build_location_map()` atau ke tabel SoT.

2. **`outputs.sql` PostgreSQL dinonaktifkan** — Perlu migrasi skema tabel `server_redfish`: tambahkan kolom `lower_threshold_critical`. Command:
   ```sql
   ALTER TABLE server_redfish ADD COLUMN IF NOT EXISTS lower_threshold_critical DOUBLE PRECISION;
   ```

3. **Kafka belum HA** — Single broker (1 node). Untuk production perlu minimal 3 broker sesuai FIT041 Req 3.2.1.

4. **Consumer Ralph CMDB** — `ralph_sync_agent.py` masih membaca dari Elasticsearch langsung (bukan dari Kafka). Perlu dimigrasi jadi Kafka consumer terpisah.

---

## 5. File Kunci yang Dimodifikasi

| File | Perubahan |
|:---|:---|
| `/home/infra/dcim_metrics_project/scripts/dcim_inventory_poller.py` | FIT041 fix: ci_id, source, enrichment_status, strip, UPS OID baru |
| `/usr/local/bin/dcim_inventory_poller.py` | Sync dari scripts/ |
| `/etc/telegraf/telegraf.conf` | Output: AMQP + ES langsung → Kafka |
| `/etc/telegraf/telegraf-consumer.conf` | Input: AMQP → Kafka; ES output diaktifkan; SQL di-disable clean |
| `/etc/telegraf/telegraf.d/dcim-unified-inventory.conf` | tag_keys diperluas (site, rack_name, ci_id, source, enrichment_status) |
| `/home/infra/dcim_metrics_project/kafka/docker-compose.yml` | Baru: Deploy apache/kafka:latest KRaft mode |
