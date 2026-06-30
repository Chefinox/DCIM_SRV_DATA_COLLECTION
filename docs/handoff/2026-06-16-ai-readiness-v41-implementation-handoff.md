# SESSION SUMMARY / HANDOFF — AI Readiness v4.1 Implementation

## 1. Session Metadata
- **Title:** Perbaikan pekerjaan agent lain + Unifikasi pipeline server (AI Readiness v4.1)
- **Date:** 2026-06-16
- **Host:** `srv-rnd-dcim` (10.70.0.56), project `/home/infra/dcim_metrics_project`
- **Status:** **In Progress — plan SUDAH DISETUJUI, implementasi BELUM dimulai** (berhenti di awal Workstream B karena token habis)

## 2. High-Level Summary
Sesi sebelumnya memverifikasi hasil commit agent lain (`193df6c` "AI Readiness v4.1") dan menemukan **tidak ada jalur data yang hidup**: tabel arsip kosong, poller Redfish util salah endpoint (404→fallback 0.0), timer arsip tak terpasang, config drift. User memutuskan menyatukan ingestion server ke satu jalur Kafka (best practice). Rencana implementasi **lengkap sudah disetujui** dan tersimpan di **`/home/infra/.claude/plans/merry-riding-abelson.md`** (BACA INI DULU — itu sumber kebenaran). Agent berikutnya tinggal eksekusi sesuai plan.

## 3. RENCANA RESMI (sudah approved)
👉 **`/home/infra/.claude/plans/merry-riding-abelson.md`** — 4 workstream:
- **A. Unifikasi inventory** → `server_inventory_to_pg.py` jadi Kafka producer (topik `dcim.raw.hardware.server.inventory`), normalizer mapping `server_inventory`→`inventory_snapshot`, consumer `event_logger` diperluas (tulis dcim_events JSONB + Clear&Replace tabel relasional), systemd timer 01:00.
- **B. Fix poller util** (`scripts/redfish_telemetry_poller.py`) — endpoint benar + buang fallback 0.0.
- **C. Aktifkan archival** — backfill `es_to_pg_archive.py` + pasang `dcim-metrics-archive.timer`.
- **D. Config drift + commit.**

## 4. Keputusan user yang DIKUNCI (jangan tawar ulang)
- Inventory: **full-unify** (consumer yang tulis tabel relasional), **topik dedicated**, **lewat enrichment**.
- Collector: **utilisasi = inputs.exec via Telegraf** (seperti CCTV/NVR, mekanisme sudah benar, hanya fix script); **inventory = standalone Kafka producer** (dokumen nested, jadwal 01:00), BUKAN inputs.exec.
- PostgreSQL = golden source AI training; iTop = relasi antar-perangkat.

## 5. FAKTA TEKNIS TERVERIFIKASI (penting untuk eksekusi)

### Poller fix (Workstream B) — struktur endpoint SUDAH ditemukan
- Server **reachable** (HTTP 200, 0,2s). Endpoint LAMA `/redfish/v1/Systems/1/Oem/Lenovo/SystemUtilization` = **404 (tidak ada)**. Itu sebab 0.0, BUKAN "simulasi".
- Endpoint BENAR (berisi data nyata):
  - CPU: `https://{ip}/redfish/v1/Systems/1/Oem/Lenovo/Metrics/CPUSubsystemPerformance`
  - Memory: `.../Metrics/MemorySubsystemPerformance`
- **Struktur JSON**: key `Container` = list of `{Timestamp, TimestampWithTZ, Duration, MetricValue, MetricType:"Avg"}`. **`Container[0]` = sampel TERBARU** (30-detik, TimeScope "Previous_hour"). Ambil `Container[0]["MetricValue"]` = % util.
  - Contoh nyata HCI-01: CPU `Container[0].MetricValue = 9`.
- Poller harus: ambil `Container[0].MetricValue` untuk CPU & memory; bila gagal/timeout → **skip server (jangan emit baris)**, JANGAN emit 0.0.
- Tetap output Influx line protocol, measurement `server_redfish_util`, dijalankan Telegraf inputs.exec (routing namepass sudah ada di `/etc/telegraf/telegraf.conf`).
- **BELUM diverifikasi**: struktur MemorySubsystemPerformance & endpoint di Render-01 (10.50.0.5, user `hndept`) & Render-02 (10.50.0.6, user `root`). Cek dulu sebelum finalize.

### Servers (untuk poller & collector)
```
10.50.0.2 SERVER-HCI-01 (hndept), 10.50.0.3 HCI-02 (hndept), 10.50.0.4 HCI-03 (hndept),
10.50.0.5 RENDER-01 (hndept), 10.50.0.6 RENDER-02 (root)   pass: F!tech@0918
```

### Normalizer (Workstream A2) — terverifikasi
- `src/skills/telemetry/normalizer/executor.py`: subscribe regex `^dcim\.raw\..*` (auto-consume topik baru). Consumer group `dcim_python_normalizer_group`. Output → `dcim.normalized.events`.
- **Nested `fields` (processors/memory/disks/nics) SURVIVE utuh ke `raw_fields`** (baris ~166). Tidak perlu ubah kode normalizer.
- ⚠️ Topik `dcim.raw.hardware.server.inventory` **TIDAK match** prefix `dcim.raw.server` di `resolve_device_type()`. **Producer WAJIB set `tags.device_type="server"`** eksplisit.
- Tambah blok `"server_inventory"` di `configs/metric_mapping.json` → `{"metric_name":"inventory_snapshot","metric_field":null}`. Verifikasi apakah normalizer baca `configs/metric_mapping.json` atau `src/skills/telemetry/normalizer/metric_mapping.json` (cek mana yang aktif).

### Consumer (Workstream A3) — terverifikasi
- `src/skills/telemetry/event_logger/executor.py`: consume `dcim.enriched.events`, group `dcim-postgres-consumer-v2`, batch 50, `upsert()` ON CONFLICT (event_id,event_time). **Tidak ada branching; 0 sentuh tabel relasional.**
- Tambah branch `metric_name=='inventory_snapshot'`: (1) map `raw_fields.processors/memory/disks`→`srv_cpu/memory/disk_components` JSONB, `nics`→`raw_tags.nics`, isi `srv_firmware/srv_bios_version`; upsert dcim_events. (2) Clear&Replace 4 tabel relasional.
- **Reuse pola SQL & kolom dari `scripts/server_inventory_to_pg.py:259-314`** (JANGAN pakai `src/skills/inventory/redfish_scanner/executor.py` — dormant & ~50% lengkap).
- Kolom tabel relasional:
  - `dcim_server_disks(server_ip, serial_number, model_name, size_gb, firmware_version, slot)`
  - `dcim_server_ram(server_ip, model_name, size_mb, speed_mhz)`
  - `dcim_server_processors(server_ip, model_name, cores, logical_cores, speed_mhz)`
  - `dcim_server_nics(server_ip, label, mac_address, speed_gbps, model_name)`

### Producer & systemd (Workstream A1/A4) — terverifikasi
- Pola producer: `confluent_kafka.Producer({'bootstrap.servers':'127.0.0.1:9092'})`, `produce(topic, value=json.dumps(...).encode())`, `flush()` (lihat `scripts/dcim_normalizer.py:94-125`).
- Topik Kafka **auto-created** (Kafka 3.7.0).
- Inventory kini via crontab `0 1 * * *`. Konversi ke systemd timer (pola `configs/systemd/dcim-itop-ralph-sync.{service,timer}`, `OnCalendar=*-*-* 01:00:00`, Type=oneshot, User=infra). **Cek unit pre-existing** `dcim-server-inventory.{service,timer}` (tampak ada: service `static`, timer `disabled`) — update, jangan duplikat. Hapus cron lama HANYA setelah jalur Kafka tervalidasi.

### Archival (Workstream C) — aset siap
- `scripts/es_to_pg_archive.py` (mode `backfill`/`incremental`, sudah filter `@timestamp lte now` → tolak sampah future-2227). Tabel `dcim_metrics_archive` + partisi bulanan + 6 MV `v_train_*` SUDAH dibuat tapi **KOSONG**.
- Jalankan `python3 scripts/es_to_pg_archive.py --mode backfill` (≈42,9 jt dok sejak 2026-04-29; **pantau disk** `dcim_sot_postgres`; jalankan background). Lalu REFRESH 6 MV.
- Pasang `configs/systemd/dcim-metrics-archive.{service,timer}`→`/etc/systemd/system/`, `daemon-reload`, `enable --now` (incremental 03:00).

## 6. Current State / Progress
~~~text
- Plan disetujui & tersimpan di /home/infra/.claude/plans/merry-riding-abelson.md
- TodoWrite list aktif (10 item); item #1 (fix poller) in_progress, sisanya pending.
- BELUM ada satu pun file diubah/dibuat. Belum ada perintah non-readonly dijalankan.
- Terakhir: sedang verifikasi struktur endpoint memory + Render-01/02 (curl) saat token habis.
- Git: working tree kotor (74 file warisan), branch main ahead 19 commit (termasuk 193df6c), belum push.
~~~

## 7. Kredensial (live, dari .env / config aktual)
- PostgreSQL: `PGPASSWORD="Inovasi@0918" psql -h localhost -U sot_admin -d dcim_sot`
- Elasticsearch: `elastic` / `C+H+pFb*aIAqWcOo-X8q` @ `https://localhost:9200` (-k)
- Redfish servers: pass `F!tech@0918` (lihat §5)
- Kafka: `127.0.0.1:9092`; exec topics: `docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list`

## 8. Next Actions (urutan disarankan)
1. **Workstream B** (cepat, terisolasi): selesaikan verifikasi memory/Render endpoint, rewrite `redfish_telemetry_poller.py` (Container[0].MetricValue, skip-on-fail), uji manual → restart telegraf → cek `dcim_events` metric_name='cpu_utilization' berisi angka nyata.
2. **Workstream C**: backfill (background, pantau disk) + REFRESH MV + pasang timer arsip.
3. **Workstream A**: refactor collector→producer, mapping normalizer, perluas consumer, systemd timer 01:00; verifikasi end-to-end + timing <02:00; cutover (hapus cron) setelah valid.
4. **Workstream D**: sinkron config drift + commit per-workstream.

## 9. Constraints / Do-Not
- JANGAN ubah `dcim_events` / retensi 7 hari.
- JANGAN timpa dokumen v4.0 (v4.1 = file terpisah `docs/architecture/v4.1-pipeline-architecture.md`).
- JANGAN hapus jalur inventory lama sebelum jalur Kafka tervalidasi penuh (ralph/itop 02:00 baca tabel relasional).
- Verifikasi NiFi enrichment TIDAK membuang payload nested inventory (cek `dcim.enriched.events` sebelum percaya consumer).
- Semua klaim "selesai" WAJIB dibuktikan query/log aktual (user sangat teliti pada nilai 0.0/anomali).

## 10. Final Handoff Brief
~~~markdown
Plan APPROVED at /home/infra/.claude/plans/merry-riding-abelson.md — execute it. Goal: fix prior agent's non-functional v4.1 (empty archive, wrong Redfish util endpoint→0.0, uninstalled timer) AND unify server ingestion through Kafka. Nothing implemented yet. Start Workstream B: rewrite scripts/redfish_telemetry_poller.py to read Container[0].MetricValue from Oem/Lenovo/Metrics/CPUSubsystemPerformance + MemorySubsystemPerformance (verified real data), drop the 0.0 fallback (skip on failure). Then C (archival backfill + timer), then A (inventory→Kafka producer + normalizer mapping + consumer relational extension + 01:00 timer), then D (commit). Keep util as Telegraf inputs.exec; make inventory a standalone Kafka producer. Servers reachable, creds in handoff §7. Prove every result with real queries.
~~~
