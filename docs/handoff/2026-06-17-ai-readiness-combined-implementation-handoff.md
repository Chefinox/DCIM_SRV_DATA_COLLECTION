# HANDOFF — Implementasi AI Readiness Combined Plan (Data Ingestion & Integration scope)

## 0. CARA PAKAI DOKUMEN INI
Kamu adalah agent yang melanjutkan implementasi. **Baca dokumen ini penuh**, lalu eksekusi plan di
`/home/infra/.claude/plans/ai-readiness-combined-plan.md`. Prompt eksekusi siap-tempel ada di **§9**.

> **SCOPE TEGAS:** Tim kita = **Data Ingestion & Integration Layer**. Tugas kita **MENYIAPKAN DATA** agar siap untuk AI training/inference (tabel, materialized view, pipeline, archive). Kita **BUKAN** tim Data Science — **JANGAN** melatih model sungguhan, tuning hyperparameter, atau membangun LSTM/Prophet. Untuk inference consumer (Fase 3) cukup **mock model / threshold sementara** sebagai placeholder integrasi; model asli datang dari tim AI (MT-018). Fokus: data tersedia, bersih, ter-skema, dan mengalir.

---

## 1. ENVIRONMENT
- Host: `srv-rnd-dcim` (10.70.0.56). Jam server **WIB (UTC+7)**; `event_time` di DB/ES disimpan **UTC**. Jangan salah baca "gap" data karena offset ini.
- Project: `/home/infra/dcim_metrics_project`. Git remote `github.com:Chefinox/DCIM_SRV_DATA_COLLECTION.git`, branch `main`.
- **Kredensial live:**
  - PostgreSQL: `PGPASSWORD="Inovasi@0918" psql -h localhost -U sot_admin -d dcim_sot`
  - Elasticsearch: `elastic` / `C+H+pFb*aIAqWcOo-X8q` @ `https://localhost:9200` (pakai `-k`)
  - Redfish server: user `hndept` (kecuali Render-02=`root`), pass `F!tech@0918`
  - Kafka: `127.0.0.1:9092`. List topik: `docker exec kafka-broker /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list`

## 2. ARSITEKTUR PIPELINE (v4.1, TRIPLE-WRITE)
```
Device → Telegraf/Poller → Kafka dcim.raw.* → Normalizer (dcim.normalized.events)
   → NiFi Enrich (+Redis cache dari iTop) → dcim.enriched.events
   → ES (dcim-metrics-unified-*)  [Kibana/alerting]
   → PostgreSQL dcim_events        [GOLDEN SOURCE AI, retensi 7 HARI]
   → iTop (dari normalized)        [CMDB / relasi antar-perangkat]
```
- Normalizer: `src/skills/telemetry/normalizer/executor.py`, subscribe regex `^dcim\.raw\..*`. Nested `fields` survive utuh ke `raw_fields`.
- Consumer PG: `src/skills/telemetry/event_logger/executor.py`, consume `dcim.enriched.events`, group `dcim-postgres-consumer-v2`. **Sudah** punya branch `inventory_snapshot` (tulis JSONB + Clear&Replace `dcim_server_*`) — hasil kerja Workstream A yang sudah selesai.
- Dokumen arsitektur lengkap: `docs/architecture/v4.1-pipeline-architecture.md` (v4.0 dibiarkan utuh sebagai arsip).

## 3. KEPUTUSAN ARSITEKTUR YANG DIKUNCI (jangan tawar ulang)
- **PostgreSQL = golden source AI training; iTop = relasi antar-perangkat.**
- `dcim_events` retensi **7 hari** (auto-drop) → histori panjang dipindah ke **`dcim_metrics_archive`** (L13, format long/EAV, partisi bulanan) → di-pivot ke **materialized view `v_train_*`** per device_type.
- **Penamaan ikut konvensi kita** (`dcim_*`, `v_train_*`, `dcim_metrics_archive`). JANGAN pakai nama `server_metrics`/`server_anomalies` mentah dari MT-018 — sediakan **VIEW alias** bila perlu kompat dengan script tim AI.
- **Data belum dikoleksi → DI-LIST saja**, jangan bangun collector baru. Konfigurasi hanya pakai data yang sudah ada.
- **Humidity TIDAK ADA** (sensor fisik tidak ada) → keluar scope.

## 4. STATUS SAAT INI (sudah selesai vs belum)
**SUDAH selesai & tervalidasi (Workstream A & D, oleh agent sebelumnya):**
- Inventory server di-unify lewat Kafka: `server_inventory_collector.py` (producer) → topik `dcim.raw.hardware.server.inventory` → consumer tulis `dcim_events` (JSONB) + tabel relasional `dcim_server_{disks,ram,processors,nics}`.
- Timer `dcim-server-inventory.timer` (01:00). Config drift telegraf/metric_mapping sudah disinkron & di-commit (`193df6c` dst).
- Tabel `dcim_metrics_archive` + partisi bulanan + 6 MV `v_train_*` + auto-REFRESH di akhir `es_to_pg_archive.py`.
- Timer `dcim-metrics-archive.timer` (03:00 incremental).

**BELUM / RUSAK (ini tugasmu — lihat plan):**
- 🔴 **Backfill archive cuma 2 hari** (14 Jun→kini). ES punya **29 Apr→kini**. Bug: yang jalan versi lama; perlu ulang backfill benar.
- 🔴 **`v_train_server.cpu_util_pct` & `mem_util_pct` NULL** — util server (Redfish) belum dikoleksi (Workstream B tak pernah selesai).
- ❌ Tabel `dcim_failure_events`, `dcim_server_anomalies` belum ada.
- ❌ `v_train_network`/`v_train_ups` belum diperluas (net_rx/net_tx, output_load — datanya SUDAH ADA, tinggal pivot).
- ❌ Inference consumer belum ada.

## 5. FAKTA DATA TERVERIFIKASI (untuk konfigurasi MV — pakai ini)
- **Server (Redfish util, Fase 0.2):** endpoint BENAR `https://{ip}/redfish/v1/Systems/1/Oem/Lenovo/Metrics/CPUSubsystemPerformance` + `MemorySubsystemPerformance`. Struktur: key `Container` = list; **`Container[0].MetricValue`** = sampel TERBARU (% util). Contoh nyata HCI-01 CPU=9. Endpoint LAMA `/Oem/Lenovo/SystemUtilization` = 404 (itu sebab fallback 0.0 palsu — server sebenarnya REACHABLE).
- **Server fields ada di archive:** `reading_celsius`, `power_output_watts`, `reading_rpm`, + komponen `nics_*_speed`, `disks_*_size`, `memory_*`. (CPU/mem util server BELUM, datang dari measurement `server_redfish_util`).
- **Network fields ada:** `ifInOctets`(=net_rx), `ifOutOctets`(=net_tx), `ifInErrors`, `ifOutErrors`, `ifInDiscards`, `ifOutDiscards`, `ifOperStatus`.
- **UPS fields ada:** `output_load`(+L1/L2/L3), `input_voltage`, `output_current_L*`, `battery_capacity`, `battery_temp`, `battery_runtime_remain`.
- **MV pivot pattern** (contoh `v_train_server`): `max(field_value) FILTER (WHERE field_key='reading_celsius') AS temp_celsius` … `GROUP BY date_trunc('minute',event_time), serial_number, hostname, model`.
- Servers: `10.50.0.2 HCI-01, .3 HCI-02, .4 HCI-03, .5 RENDER-01` (user hndept), `.6 RENDER-02` (user root).

## 6. SCOPE GUARDRAILS (data ingestion only)
✅ Boleh: buat/ubah tabel & MV di `dcim_sot`, perbaiki archive/poller, perluas feature dari data existing, buat inference consumer **shell** dengan mock/threshold, deploy systemd, commit.
❌ Jangan: melatih model nyata, hyperparameter tuning, bangun forecasting LSTM/Prophet, koleksi data baru yang belum ada (disk_io, smart_*, gpu_*, env sensor, PUE) — cukup **DI-LIST** di dokumen.

## 7. DAFTAR DATA BELUM DIKOLEKSI (list saja, JANGAN bangun)
`disk_io` (server), `smart_*` (disk SMART), `gpu_util/gpu_mem` (RTX 3070Ti), `temp_inlet/outlet`/`dewpoint` (env cooling), `pue`/facility power total, NetBox rack occupancy (ada di iTop/Ralph belum diekspos). **Humidity = N/A (tak ada sensor).**

## 8. CONSTRAINTS / DO-NOT
- Jangan ubah `dcim_events` & retensi 7 hari. Jangan timpa `v4.0` doc.
- Backfill 42,9jt baris → **pantau disk** container `dcim_sot_postgres`; jalankan background, di luar jam sibuk.
- Verifikasi NiFi enrichment tak buang payload nested sebelum percaya consumer.
- **Setiap klaim "selesai" WAJIB dibuktikan query/log aktual** (user sangat teliti pada nilai 0.0/NULL/anomali).
- Commit per-fase, pesan jelas. Jangan push tanpa diminta.

---

## 9. PROMPT EKSEKUSI (siap tempel ke agent baru)
~~~text
Kamu agent Data Ingestion & Integration untuk project DCIM di /home/infra/dcim_metrics_project (host srv-rnd-dcim, 10.70.0.56). Baca dulu dokumen handoff ini penuh dan plan di /home/infra/.claude/plans/ai-readiness-combined-plan.md. Tugasmu: MENYIAPKAN DATA untuk AI training/inference — BUKAN melatih model (itu tim AI/MT-018). Untuk inference consumer cukup mock/threshold placeholder.

Eksekusi plan secara berurutan, buktikan tiap langkah dengan query/log nyata sebelum lanjut:

FASE 0 (fondasi, wajib dulu):
0.1 Perbaiki & jalankan ulang backfill scripts/es_to_pg_archive.py mode backfill agar menarik histori penuh ES (sejak 2026-04-29, exclude future-2227). Jalankan background, pantau disk dcim_sot_postgres. Verifikasi MIN(event_time) di dcim_metrics_archive ~29 Apr.
0.2 Rewrite scripts/redfish_telemetry_poller.py: ambil Container[0].MetricValue dari Oem/Lenovo/Metrics/CPUSubsystemPerformance + MemorySubsystemPerformance, buang fallback 0.0 (skip bila gagal). Uji manual ke-5 server, restart telegraf, verifikasi util server masuk dcim_events lalu cpu_util_pct/mem_util_pct di v_train_server terisi nyata.

FASE 2 (perluas MV dari data EXISTING):
- v_train_network: tambah net_rx(ifInOctets), net_tx(ifOutOctets), in_errors, out_errors, oper_status.
- v_train_ups: tambah output_load, input_voltage, output_current, battery_capacity/temp/runtime.
- v_train_server: perbaiki FILTER field_key util. REFRESH semua MV.

FASE 1 (tabel AI, konvensi kita + view alias):
- CREATE TABLE dcim_failure_events, dcim_server_anomalies (lihat DDL di plan), + VIEW server_anomalies AS SELECT * FROM dcim_server_anomalies.

FASE 3 (inference consumer SHELL, mock model):
- src/skills/ai/anomaly_inference/executor.py: Kafka consumer dcim.enriched.events (group dcim-ai-inference), micro-batch, imputation memori (forward-fill/median), mock IsolationForest/threshold, tulis ke dcim_server_anomalies. Systemd dcim-ai-inference.service.

FASE 4: verifikasi export_training_data.py baca v_train_* diperluas; update docs/development/ai-training-data-schema.md (mapping nama kita ↔ MT-018 + daftar fitur belum tersedia); commit per-fase.

Patuhi guardrails §6 & constraints §8 handoff. Jangan bangun collector untuk data di §7 (cukup list). Penamaan ikut konvensi kita (dcim_*, v_train_*).
~~~

## 10. FINAL BRIEF
~~~markdown
Scope = Data Ingestion & Integration: siapkan data AI-ready, jangan latih model. Foundation (archive+MV+inventory unify) sudah ada tapi 2 bug: backfill cuma 2 hari (harus tarik sejak 29 Apr) & util server NULL (fix Redfish poller Container[0].MetricValue). Lalu perluas MV pakai data existing (network ifInOctets/ifOutOctets, ups output_load), buat tabel dcim_failure_events & dcim_server_anomalies (+view alias), dan inference consumer SHELL bermodel mock. Data belum ada (disk_io, smart, gpu, env, pue) cukup DI-LIST. Buktikan tiap langkah dgn query nyata; commit per-fase. Plan: /home/infra/.claude/plans/ai-readiness-combined-plan.md
~~~
