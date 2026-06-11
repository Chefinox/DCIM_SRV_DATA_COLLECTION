# Cutover Checklist: PG Hub → iTop Metadata Authority

**Versi**: v3.5.6 → v4.0.0  
**Tanggal pembuatan**: 2026-06-11  
**Status**: Pre-cutover (parallel run phase)

---

## Pre-cutover (jalankan paralel selama 7 hari)

### Scripts baru (v4.0.0)
- [x] `itop_to_cache_sync.py` dibuat dan tested (44 CI synced ke Redis)
- [x] `itop_to_ralph_sync.py` dibuat dan tested (43 devices synced ke Ralph, 0 failures)
- [x] `itop-api-baseline-for-agents.md` dibuat (dokumentasi referensi iTop API)
- [x] Enrichment API dimodifikasi — PG fallback dihapus, cache-miss return `NOT_IN_CMDB`

### Parallel run
- [ ] `itop_to_cache_sync.py` berjalan paralel dengan `cmdb_to_cache_sync.py`
  - Deploy: `sudo systemctl enable --now dcim-itop-redis-sync.service` (file: `configs/systemd/dcim-itop-redis-sync.service`)
  - Monitor: `tail -f /home/infra/dcim_metrics_project/logs/itop_cache_sync.log`
  - Bandingkan Redis key count antara keduanya: harus dalam ±5% selisih
  - Cek: `redis-cli keys "asset:sn:*" | wc -l`
- [ ] `itop_to_ralph_sync.py` berjalan paralel dengan `ralph_cmdb_sync.py`
  - Jalankan manual: `python3 scripts/itop_to_ralph_sync.py`
  - Monitor: `tail -f /home/infra/dcim_metrics_project/logs/itop_to_ralph_sync_$(date +%Y%m%d).log`
  - Bandingkan jumlah device di Ralph sebelum dan sesudah
- [ ] Verifikasi tidak ada cache miss meningkat di Enrichment API log
  - Monitor: `tail -f /home/infra/dcim_metrics_project/logs/enrichment.log | grep cache_miss`

### Kriteria lolos pre-cutover
- [ ] Redis key count antara kedua sync source dalam ±5% selisih selama 3 hari berturut-turut
- [ ] Tidak ada spike cache miss di enrichment API
- [ ] `itop_to_ralph_sync.py` menghasilkan 0 failures selama 3 run berturut-turut

---

## Cutover day

### Step 1: Stop old services
- [ ] Stop `cmdb_to_cache_sync.py` / disable systemd unit lama:
  ```bash
  sudo systemctl disable --now dcim-redis-sync.service
  ```
- [ ] Stop `ralph_cmdb_sync.py` / disable cron/timer lama:
  ```bash
  sudo systemctl disable --now dcim-ralph-sync.timer
  ```

### Step 2: Verify critical services still running
- [ ] Konfirmasi `dcim-itop-inventory-sync.service` masih berjalan (JANGAN disable ini):
  ```bash
  systemctl is-active dcim-itop-inventory-sync.service
  ```
- [ ] Konfirmasi `dcim-itop-redis-sync.service` berjalan (service baru):
  ```bash
  systemctl is-active dcim-itop-redis-sync.service
  ```

### Step 3: Monitor
- [ ] Monitor Redis TTL expiry selama 2 jam pertama:
  ```bash
  watch -n 10 'redis-cli keys "asset:sn:*" | wc -l'
  ```
- [ ] Monitor enrichment API — pastikan tidak ada spike NOT_IN_CMDB:
  ```bash
  tail -f /home/infra/dcim_metrics_project/logs/enrichment.log
  ```
- [ ] Monitor Kafka topics — pastikan data masih mengalir:
  ```bash
  kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic dcim.enriched.events --max-messages 5
  ```

### Step 4: Post-cutover verification (24 jam setelah cutover)
- [ ] Redis key count stabil (tidak dropping)
- [ ] Enrichment API response time normal
- [ ] Tidak ada error baru di log

---

## Rollback plan

Jika ada masalah dalam 24 jam pertama setelah cutover:

### Step 1: Re-enable old scripts
```bash
sudo systemctl enable --now dcim-redis-sync.service
sudo systemctl enable --now dcim-ralph-sync.timer
```

### Step 2: Restore enrichment API PG fallback
```bash
cd /home/infra/dcim_metrics_project
git checkout HEAD~1 src/skills/inventory/enrichment/executor.py
sudo systemctl restart dcim-enrichment-api.service
```

### Step 3: Leave new scripts running
- `itop_to_cache_sync.py` tetap jalan — tidak merusak apapun jika paralel
- `itop_to_ralph_sync.py` tetap jalan — tidak merusak apapun jika paralel

### Step 4: Re-enable ES bypass (jika diperlukan)
```bash
sudo systemctl enable --now dcim-kafka-es-sync.service
```

---

## Service Inventory

### Service baru (v4.0.0)
| Service | Script | Schedule | Status |
|---|---|---|---|
| `dcim-itop-redis-sync.service` | `scripts/itop_to_cache_sync.py` | Continuous (60s loop) | Siap deploy |
| cron/systemd timer | `scripts/itop_to_ralph_sync.py` | Daily 02:00 | Siap deploy |

### Service lama (v3.5.6) — akan dinonaktifkan
| Service | Script | Status saat ini |
|---|---|---|
| `dcim-redis-sync.service` | `scripts/cmdb_to_cache_sync.py` | Active (akan di-disable) |
| `dcim-ralph-sync.timer` | `scripts/ralph_cmdb_sync.py` | Active (akan di-disable) |
| `dcim-kafka-es-sync.service` | `scripts/kafka_to_es_sync.py` | **Sudah disabled** |

### Service yang TIDAK BOLEH diubah
| Service | Script | Alasan |
|---|---|---|
| `dcim-itop-inventory-sync.service` | `scripts/dcim_itop_inventory_sync.py` | Mengisi hardware metadata ke iTop |
| `dcim-normalizer.service` | Normalizer | Pipeline core |
| `dcim-cctv-poller.service` | CCTV poller | Data collection |
| `dcim-threshold-alerter.service` | Threshold alerter | Alerting |
| `dcim-itop-unified.service` | iTop consumer | Kafka → iTop sync |
| `dcim-sql-consumer.service` | SQL consumer | Kafka → PG sync |
| `dcim-dlq-consumer.service` | DLQ consumer | Dead letter queue |
