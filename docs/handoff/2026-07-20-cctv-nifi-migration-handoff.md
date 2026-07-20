# Handoff: Migrasi CCTV/NVR Kembali ke NiFi ExecuteProcess

> **Dari:** Fakhri (Tim DCIM Infra)
> **Untuk:** Agent berikutnya
> **Tanggal:** 2026-07-20
> **Prioritas:** P2 — menyelaraskan data collection CCTV/NVR dengan perangkat lain
> **Referensi:**
> - `docs/architecture/v4.5-pipeline-architecture.md`
> - `docs/architecture/v4.5-pipeline-architecture-komparasi.md`
> - `docs/standar_dcim/ai-team-access.md`
> - `dcim-wiki/` — knowledge base referensi acuan

---

## 1. Konteks

### 1.1 Apa yang Terjadi

Pada commit `0021a56` (2026-07-20), CCTV/NVR data ingestion diubah dari **NiFi ExecuteProcess** menjadi **systemd bridge standalone** (`dcim-cctv-kafka-bridge.service` + `.timer`) karena terjadi issue: **NiFi flow tidak memiliki ExecuteProcess untuk CCTV**, sehingga data CCTV berhenti mengalir.

Perbaikan sementara: membuat `cctv_kafka_bridge.py` — wrapper yang menjalankan `cctv_poller.py` lalu mempublikasikan output ke Kafka topic `dcim.raw.device.isapi`. Dijalankan via systemd timer setiap 2 menit.

**Target**: Kembalikan CCTV/NVR ke NiFi ExecuteProcess agar **seluruh 5 device types menggunakan arsitektur yang sama** (1 jalur: NiFi → Kafka).

### 1.2 Kondisi Saat Ini

| Komponen | Status |
|----------|--------|
| `cctv_poller.py` | ✅ Bekerja — polling 31 CCTV + 1 NVR via Hikvision ISAPI, output JSON lines ke stdout |
| `cctv_kafka_bridge.py` | ✅ Bekerja — wrapper yang memanggil poller + publish ke Kafka |
| `dcim-cctv-kafka-bridge.service` | ✅ Running (oneshot) |
| `dcim-cctv-kafka-bridge.timer` | ✅ Running (every 2 min) |
| NiFi secrets | ✅ `hikvision_cam_pass` + `hikvision_nvr_pass` sudah ada di `docker-compose.yml` |
| Kafka topic | ✅ `dcim.raw.device.isapi` — dikonsumsi normalizer |
| Metric mapping | ✅ `cctv_metrics` di `configs/metric_mapping.json` |

**Yang perlu diubah**: Hapus systemd bridge, buat NiFi ExecuteProcess processor untuk `cctv_poller.py`.

---

## 2. Arsitektur Target

### 2.1 Pipeline End-to-End (v4.5)

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐     ┌──────────────┐
│   Devices    │     │  NiFi Collection │     │  Kafka (Raw) │     │  Normalizer  │
├──────────────┤     ├──────────────────┤     ├──────────────┤     ├──────────────┤
│ Server       │────▶│ ExecuteProcess   │────▶│ dcim.raw     │────▶│ Python       │
│ (Redfish)    │     │ redfish_poller   │     │ .hardware    │     │ systemd      │
│              │     │                  │     │ .server      │     │ Multi-Metric │
│ UPS          │────▶│ ExecuteProcess   │────▶│ dcim.raw     │     │ Avro output  │
│ (SNMP)       │     │ snmp_ups_poller  │     │ .power.ups   │     │              │
│              │     │                  │     │              │     │              │
│ NAS          │     │ Telegraf SNMP    │────▶│ dcim.raw     │     │              │
│ (SNMP v3)    │     │ inputs.snmp      │     │ .storage.nas │     │              │
│              │     │                  │     │              │     │              │
│ Network      │────▶│ ExecuteProcess   │────▶│ dcim.raw     │     │              │
│ (SNMP v2c)   │     │ mikrotik_poller  │     │ .network.snmp│     │              │
│              │     │                  │     │              │     │              │
│ CCTV/NVR     │────▶│ ExecuteProcess   │────▶│ dcim.raw     │     │              │
│ (ISAPI)      │     │ cctv_poller ★    │     │ .device.isapi│     │              │
└──────────────┘     └──────────────────┘     └──────────────┘     └──────────────┘
         ★ = yang akan dikerjakan agent ini
```

Semua device types menggunakan **satu jalur**: Device → Collection → Kafka Raw → Normalizer → Enrichment → Consumers → Storage.

### 2.2 Yang Sudah Bekerja (4 dari 5)

| Device | Collector | Kafka Topic | Status |
|--------|-----------|-------------|:---:|
| Server | NiFi ExecuteProcess → `redfish_poller.py` | `dcim.raw.hardware.server` | ✅ |
| UPS | NiFi ExecuteProcess → `snmp_ups_poller.py` | `dcim.raw.power.ups` | ✅ |
| NAS | Telegraf `inputs.snmp` | `dcim.raw.storage.nas` | ✅ |
| Network | NiFi ExecuteProcess → `mikrotik_poller.py` | `dcim.raw.network.snmp` | ✅ |
| **CCTV/NVR** | **systemd bridge** `cctv_kafka_bridge.py` | `dcim.raw.device.isapi` | ⚠️ |

---

## 3. Environment

### 3.1 Server

| Item | Value |
|------|-------|
| Hostname | `srv-rnd-dcim` |
| IP | `10.70.0.56` |
| User | `infra` |
| Working dir | `/home/infra/dcim_metrics_project` |

### 3.2 Infrastruktur Aktif

| Komponen | Port | Container/Service |
|----------|------|-------------------|
| Kafka Cluster (3-node, SSL) | 9092 (internal), 9094 (SSL) | `kafka1`, `kafka2`, `kafka3` |
| Schema Registry | 8081 | `schema-registry` |
| NiFi | 8443 (HTTPS) | `dcim-nifi` |
| PostgreSQL | 5432 | `dcim_sot_postgres` |
| TimescaleDB | 5433 | `dcim-timescaledb` |
| Redis | 6379 | `dcim-redis-cache` |
| Vault | 8200 | `vault` |

### 3.3 NiFi Configuration

```yaml
# nifi/docker-compose.yml — key points:
services:
  nifi:
    network_mode: "host"   # NiFi langsung akses localhost:9094 (Kafka SSL)
    volumes:
      - /home/infra/dcim_metrics_project/scripts:/opt/nifi/nifi-current/scripts:ro
    secrets:
      - hikvision_nvr_pass   # /run/secrets/dcim/hikvision_nvr_pass
      - hikvision_cam_pass   # /run/secrets/dcim/hikvision_cam_pass
```

- **Scripts mount**: `/home/infra/dcim_metrics_project/scripts` → `/opt/nifi/nifi-current/scripts` (read-only)
- **Secrets**: Credential CCTV/NVR sudah tersedia sebagai Docker secrets
- **Access**: NiFi menggunakan `network_mode: host` sehingga bisa akses Kafka di `localhost:9094`
- **NiFi URL**: `https://10.70.0.56:8443/nifi`
- **Flow definition**: `nifi/flow.json.gz`

### 3.4 CCTV Devices

| Tipe | Jumlah | IP Range | Protocol | Auth |
|------|:---:|------|----------|------|
| Kamera Hikvision | 31 | 192.168.1.2–33 (skip .32) | ISAPI HTTP:80 | Digest `admin` / `cam_pass` |
| NVR Hikvision | 1 | 192.168.1.254 | ISAPI HTTP:80 | Digest `admin` / `nvr_pass` |

Credential disimpan di:
- `/run/secrets/dcim/hikvision_cam_pass`
- `/run/secrets/dcim/hikvision_nvr_pass`

---

## 4. Yang Perlu Dikerjakan

### 4.1 Step 1: Pelajari Konteks (Wajib — 15 menit)

Sebelum menyentuh kode, baca dokumen berikut untuk memahami keseluruhan sistem:

1. **Pipeline Architecture**: `docs/architecture/v4.5-pipeline-architecture.md`
   - Fokus: §4 (L1 & L2 Collection), §6 (L4 Normalizer), §5 (Kafka Topics)
2. **Referensi Desain**: `dcim-wiki/reference-designs/block2-data-ingestion-integration.md`
   - Lihat bagaimana NiFi flow seharusnya untuk ingestion
3. **Git history**:
   ```bash
   git log --oneline --since="2026-07-15"
   git show 0021a56  # commit CCTV bridge
   git show d58ecb4  # commit multi-metric normalizer
   ```
4. **Existing NiFi pollers** sebagai referensi: `snmp_ups_poller.py`, `mikrotik_poller.py`, `redfish_poller.py`
   - Perhatikan: semua output ke **stdout** (JSON format Telegraf), NiFi ExecuteProcess membaca stdout

### 4.2 Step 2: Verifikasi `cctv_poller.py` Bekerja via NiFi

1. SSH ke `srv-rnd-dcim`
2. Test manual:
   ```bash
   cd /home/infra/dcim_metrics_project
   python3 scripts/cctv_poller.py | head -5
   ```
3. Verifikasi output adalah **JSON lines** yang valid (satu JSON object per baris)
4. Output harus mengandung `"name": "cctv_metrics"` di setiap baris

### 4.3 Step 3: Buat NiFi ExecuteProcess Processor

1. Buka NiFi UI: `https://10.70.0.56:8443/nifi`
2. Tambahkan **ExecuteProcess** processor di group yang sama dengan poller lain (UPS, Network, Server)
3. Konfigurasi:
   ```
   Command: /usr/bin/python3
   Arguments: /opt/nifi/nifi-current/scripts/cctv_poller.py
   Batch Duration: 0 sec
   Redirect Error Stream: false
   ```
4. Hubungkan output ExecuteProcess → **PublishKafkaRecord** (atau PublishKafka jika JSON mentah)
5. Target Kafka topic: `dcim.raw.device.isapi`
6. Bootstrap servers: `localhost:9094`
7. SSL config: gunakan CA cert dari `/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem`

### 4.4 Step 4: Scheduling

- Set NiFi processor scheduling ke **120 detik** (sama dengan interval polling sebelumnya)
- Atau sesuaikan dengan konfigurasi timer existing (2 menit)

### 4.5 Step 5: Verifikasi Data Mengalir

```bash
# 1. Cek Kafka topic
kafka-console-consumer --bootstrap-server localhost:9094 \
  --topic dcim.raw.device.isapi \
  --consumer.config /home/infra/dcim_metrics_project/client-ssl.properties \
  --max-messages 3

# 2. Cek normalizer log
sudo journalctl -u dcim-normalizer -f | grep "cctv"

# 3. Cek TimescaleDB
docker exec dcim-timescaledb psql -U analytics_user -d dcim_analytics \
  -c "SELECT metric_name, count(*) FROM metrics WHERE source='cctv' 
      AND time > NOW() - INTERVAL '5 minutes' GROUP BY metric_name;"
```

### 4.6 Step 6: Cleanup — Nonaktifkan Systemd Bridge

Setelah NiFi berjalan dan data mengalir:

```bash
sudo systemctl stop dcim-cctv-kafka-bridge.timer
sudo systemctl disable dcim-cctv-kafka-bridge.timer
sudo systemctl stop dcim-cctv-kafka-bridge.service
sudo systemctl disable dcim-cctv-kafka-bridge.service
```

> **Jangan hapus file** `cctv_kafka_bridge.py` dan service files — archive saja sebagai fallback.

### 4.7 Step 7: Commit & Update Docs

```bash
git add -A
git commit -m "fix: migrate CCTV/NVR back to NiFi ExecuteProcess

- Removed dcim-cctv-kafka-bridge systemd service + timer
- Added NiFi ExecuteProcess for cctv_poller.py
- CCTV/NVR now uses same ingestion path as UPS/Network/Server

Result: All 5 device types use NiFi for data collection"
```

---

## 5. Reference — Cara Poller Lain Bekerja

### 5.1 UPS Poller (`snmp_ups_poller.py`) — Contoh ExecuteProcess

```python
# snmp_ups_poller.py (simplified)
# Output: JSON lines to stdout
# NiFi ExecuteProcess runs this, captures stdout, publishes to Kafka

def main():
    # ... SNMP polling ...
    metric = {
        "name": "ups_apc",
        "tags": {"hostname": hostname, "device_type": "ups", ...},
        "fields": {"battery_capacity": 100, "output_voltage": 2310, ...},
        "timestamp": int(time.time() * 1e9)
    }
    print(json.dumps(metric))  # ← STDOUT, dibaca NiFi
```

### 5.2 Network Poller (`mikrotik_poller.py`)

```python
# mikrotik_poller.py (simplified)
# Sama: JSON lines to stdout

mikrotik_metric = {
    "name": "mikrotik",
    "tags": {...},
    "fields": {"cpu_load": 12, "memory_used_kb": 904016, ...},
    "timestamp": ...
}
print(json.dumps(mikrotik_metric))
```

### 5.3 CCTV Poller (`cctv_poller.py`) — Sudah Kompatibel

`cctv_poller.py` **sudah** mengikuti pola yang sama — output JSON lines ke stdout:

```python
# cctv_poller.py
# Output per device (31 cameras + 1 NVR = ~32 JSON lines per run):
{
    "name": "cctv_metrics",
    "tags": {"hostname": "...", "serial_number": "...", "ip": "...", ...},
    "fields": {"status_online": 1, "cpuUtilization": 45.0, "memoryUsage": 512.0, ...},
    "timestamp": 1753000000000000000
}
```

**Tidak perlu modifikasi `cctv_poller.py`** — script sudah siap sebagai NiFi ExecuteProcess.

---

## 6. Checklist Verifikasi

- [ ] `cctv_poller.py` menghasilkan output JSON lines yang valid
- [ ] NiFi ExecuteProcess processor dibuat dan terhubung ke PublishKafka
- [ ] Data muncul di Kafka topic `dcim.raw.device.isapi`
- [ ] Normalizer memproses event CCTV (cek `journalctl -u dcim-normalizer | grep cctv`)
- [ ] TimescaleDB menerima metrics: `status_online`, `cpu_utilization`, `memory_usage`, `memory_usage_pct`, `memory_available`
- [ ] Systemd bridge dinonaktifkan (`systemctl stop dcim-cctv-kafka-bridge.timer`)
- [ ] Tidak ada regresi: semua 5 device types tetap mengalir
- [ ] Pipeline latency < 5 detik (cek `event_lineage` table)

---

## 7. Troubleshooting

| Masalah | Cek |
|---------|-----|
| NiFi tidak bisa execute | Pastikan `python3` terinstall di container NiFi (`docker exec dcim-nifi which python3`). Jika tidak: rebuild NiFi image dengan Python |
| ExecuteProcess timeout | CCTV poller butuh ~30-40 detik untuk 32 device. Set Batch Duration ke 0 dan pastikan timeout cukup |
| Kafka publish gagal | Cek SSL cert path di NiFi — harus `/home/infra/dcim_metrics_project/kafka/certs/ca-cert.pem` (mount dari host) |
| Data tidak muncul di TSDB | Cek normalizer log: `sudo journalctl -u dcim-normalizer | grep -i error` |
| Credential salah | Cek secret files: `docker exec dcim-nifi cat /run/secrets/dcim/hikvision_cam_pass` |

---

## 8. Git History Terkait

```bash
# Commit yang membuat bridge (ini yang akan di-revert):
0021a56 fix: add CCTV/NVR data ingestion and fix server Redfish poller

# Commit multi-metric (mempengaruhi cara CCTV metrics diproses downstream):
d58ecb4 feat: enable secondary_metrics processing + computed power metrics

# Commit field name fix (pastikan cpuUtilization/cpu_utilization match):
a8de9b2 fix: server_redfish_util field name mismatch

# Baseline v4.4 architecture:
e985d32 feat(pipeline): kafka cluster SSL, granular topic routing, ...
```

---

*Siap dikerjakan. Pipeline downstream (Normalizer → Enrichment → TimescaleDB) tidak perlu diubah — hanya layer Collection yang berubah.*
