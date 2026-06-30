# Handoff: DCIM AI-Readiness v4.1 – Session 2 (2026-06-16 ~23:45 WIB)

## Referensi Plan Utama
- **Plan file:** `/home/infra/.claude/plans/merry-riding-abelson.md`
- **Handoff sebelumnya:** `docs/handoff/2026-06-16-ai-readiness-v41-implementation-handoff.md`

---

## Status Per Workstream

### ✅ Workstream B: Redfish Telemetry Poller – SCRIPT SELESAI, PIPELINE BELUM

**Apa yang sudah dikerjakan:**
1. **Endpoint Redfish** dikonfirmasi berfungsi di semua 5 server:
   - CPU: `.../Systems/1/Oem/Lenovo/Metrics/CPUSubsystemPerformance`
   - Memory: `.../Systems/1/Oem/Lenovo/Metrics/MemorySubsystemPerformance`
   - Menggunakan `Container[0].MetricValue`

2. **Script `scripts/redfish_telemetry_poller.py`** sudah di-rewrite total:
   - Mengambil data dari 5 server (HCI-01..03, Render-01..02)
   - Output dalam format Influx line protocol: `server_redfish_util,host=<name> cpuUtilization=<val>,memoryUsage=<val>`
   - Semua server menggunakan user `hndept` / `F!tech@0918`
   - Script sudah diverifikasi berjalan manual sukses (`sudo python3 scripts/redfish_telemetry_poller.py`)
   - Ada debug logging ke `/tmp/redfish_poller.log`

3. **Telegraf config `servers-redfish.conf`** sudah diupdate:
   - `inputs.redfish` untuk 5 server dengan `computer_system_id = "1"` (diperlukan agar tidak crash)
   - `inputs.exec` untuk poller script dengan `timeout = "45s"`, `interval = "120s"`, `data_format = "influx"`
   - File sudah di-copy ke `/etc/telegraf/telegraf.d/servers-redfish.conf`
   - Backup file lama: `server-redfish-inventory.conf.bak2`
   - Scratch copy: `/home/infra/dcim_metrics_project/scratch/servers-redfish.conf`

4. **Verifikasi Telegraf `--test`:** ✅ menghasilkan output `server_redfish_util` dengan benar

5. **Telegraf service** berjalan stabil (tidak crash-loop lagi) sejak restart terakhir

**❗ MASALAH YANG BELUM TERSELESAIKAN:**

Data `server_redfish_util` **TIDAK SAMPAI ke Kafka topic `dcim.raw.hardware.server`** dan akibatnya **TIDAK MASUK ke PostgreSQL `dcim_events`**.

**Fakta-fakta debugging:**
- Poller berjalan tiap 120s (terbukti dari `/tmp/redfish_poller.log`: 23:34:00, 23:36:00)
- `telegraf --test` menghasilkan `server_redfish_util` dengan measurement name yang benar
- Kafka consumer di `dcim.raw.hardware.server` mengembalikan **0 new messages** (tested 3x)
- `telegraf.conf` output sudah memiliki `namepass = ["servers_redfish", "redfish_*", "server_redfish", "server_redfish_util"]`
- Telegraf log sangat noisy (debug `inputs.disk`), sulit melihat apakah ada error output kafka
- Query `dcim_events WHERE metric_name IN ('cpu_utilization', 'memory_utilization')` selalu mengembalikan 0 rows

**Hipotesis yang belum diuji:**
1. Telegraf mungkin tidak include `telegraf.d/` directory saat berjalan sebagai service (perlu cek `cat /proc/<pid>/cmdline`)
2. Data mungkin masuk ke topic `dcim.metrics.raw` (legacy) tapi bukan ke `dcim.raw.hardware.server` (granular)
3. Normalizer mungkin tidak subscribe ke topic yang benar, atau tidak memproses measurement `server_redfish_util`
4. SQL Consumer mungkin tidak insert data `server_redfish_util` ke `dcim_events` karena logika filtering

**Langkah debugging yang disarankan:**
```bash
# 1. Cek apakah Telegraf memuat semua config termasuk telegraf.d/
cat /proc/$(pgrep telegraf)/cmdline | tr '\0' ' '

# 2. Cek apakah data masuk ke legacy topic
docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic dcim.metrics.raw \
  --max-messages 5 --timeout-ms 30000

# 3. Matikan debug disk logging yang sangat noisy
# Di /etc/telegraf/telegraf.conf, cari [agent] section, ubah debug = false

# 4. Cek normalizer log khusus untuk server_redfish_util
sudo journalctl -u dcim-normalizer.service --no-pager | grep -i "server_redfish_util"

# 5. Periksa SQL Consumer
cat /home/infra/dcim_metrics_project/src/skills/telemetry/event_logger/executor.py
sudo journalctl -u dcim-sql-consumer.service --no-pager -n 50
```

---

### ⏳ Workstream C: Aktifkan Archival (ES → PG) – BELUM DIMULAI

**Yang harus dilakukan:**
1. Jalankan backfill: `python3 scripts/es_to_pg_archive.py --mode backfill` (background)
2. Setelah backfill selesai, refresh 6 Materialized Views:
   ```sql
   REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_server_health;
   REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_network_traffic;
   REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_power_efficiency;
   REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_storage_usage;
   REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_environmental;
   REFRESH MATERIALIZED VIEW CONCURRENTLY v_train_cctv_status;
   ```
3. Pasang systemd timer untuk archival periodik (config di `configs/systemd/dcim-metrics-archive.timer`)

---

### ⏳ Workstream A: Unifikasi Server Inventory ke Kafka – BELUM DIMULAI

**Yang harus dilakukan:**
1. Refactor collector scripts
2. Mapping normalizer
3. Extend consumer
4. Set up systemd timer

---

### ⏳ Workstream D: Rapikan Config Drift & Commit – BELUM DIMULAI

**Yang harus dilakukan:**
1. Sinkronisasi config files
2. Final commit ke git repo

---

## Constraint Penting (JANGAN DILANGGAR)

1. **JANGAN ubah table `dcim_events`** / retensi 7 hari
2. **JANGAN hapus jalur inventory lama** sebelum jalur Kafka tervalidasi penuh
3. **Semua klaim "selesai" WAJIB dibuktikan** dengan query/log aktual

## Kredensial

| Service     | User       | Password         |
|-------------|-----------|------------------|
| PostgreSQL  | sot_admin | Inovasi@0918     |
| Redfish BMC | hndept    | F!tech@0918      |

## File-File Kunci

| File | Peran |
|------|-------|
| `/etc/telegraf/telegraf.conf` | Master Telegraf config (outputs ke Kafka) |
| `/etc/telegraf/telegraf.d/servers-redfish.conf` | Input redfish + exec poller |
| `/home/infra/dcim_metrics_project/scripts/redfish_telemetry_poller.py` | Custom OEM poller script |
| `/home/infra/dcim_metrics_project/configs/metric_mapping.json` | Mapping metric normalizer |
| `/home/infra/dcim_metrics_project/src/skills/telemetry/normalizer/executor.py` | Normalizer Kafka consumer |
| `/home/infra/dcim_metrics_project/src/skills/telemetry/event_logger/executor.py` | SQL Consumer → PostgreSQL |

## Service-Service Terkait

```
telegraf.service                 → Metric collector
dcim-normalizer.service          → Kafka normalizer (raw → normalized)
dcim-sql-consumer.service        → Kafka → PostgreSQL writer
dcim-enrichment-api.service      → Enrichment API
dcim-threshold-alerter.service   → Alerting
```
