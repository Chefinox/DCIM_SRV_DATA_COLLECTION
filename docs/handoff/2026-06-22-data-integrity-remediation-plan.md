# Rencana Perbaikan Integritas Data Telemetri (Handoff-ready)

> **Tanggal**: 2026-06-22 · **Host**: `srv-rnd-dcim` (10.70.0.56) · **Repo**: `/home/infra/dcim_metrics_project` (branch `main`, commit langsung).
> **Tujuan**: Memastikan data **semua kategori perangkat** masuk lengkap & ber-identitas ke `dcim_events`, **memprioritaskan server** (saat ini rusak). Dokumen ini bisa langsung dipakai agent berikutnya bila token habis.
> **Konteks arsitektur**: `docs/architecture/v4.2-pipeline-architecture.md`. **Selalu konfirmasi user** sebelum mengubah Telegraf/normalizer/timer produksi.

---

## 1. Temuan Audit (terverifikasi 2026-06-22, jendela 24 jam)

| device_type | event 24h | host | serial | tanpa-identitas | freshness | Status |
|---|---:|---:|---:|---:|---|---|
| `cctv` | 44.640 | 16 | 32 | 0 | 0 mnt | ✅ Sehat |
| `nas` | 313.764 | 6 | 6 | 0 | 0 mnt | ✅ Sehat |
| `network` | 460.800 | 5 | 5 | 0 | 0 mnt | ✅ Sehat |
| `nvr` | 1.440 | 1 | 1 | 0 | 0 mnt | ✅ Sehat |
| `ups` | 719 | 1 | 1 | 0 | 2 mnt | ✅ Sehat |
| **`server`** | 235.125 | 5 | 5 | **233.280 (99,2%)** | 0 mnt | ❌ **RUSAK** |

**Kesimpulan**: 5 kategori sehat. **Hanya server** bermasalah. Plan ini fokus memperbaiki server (WS-A/B/C) + menjaga 5 kategori lain tetap sehat sebagai guard (WS-D).

### Bukti akar masalah server (per measurement, 24h)
| measurement | ber-identitas | tanpa-identitas | Arti |
|---|---:|---:|---|
| `server_redfish` (suhu/power/rpm) | **0** | 233.263 | semua jatuh ke `Unknown_Host`/`NO_IDENTIFIER` |
| `server_redfish_util` (cpu/mem) | 1.848 | 0 | identitas benar, tapi **Render-02 absen** |
| `inventory_snapshot` | — | — | **basi**: terakhir 2026-06-18 (>24h, tak masuk query) |

Sampel `raw_tags` event `server_redfish`:
```json
{"name":"CMOS Battery","state":"Enabled","source":"XCC-7D76-J901GKXY","address":"10.50.0.2", ...}
```
→ **tidak ada** `hostname`/`serial_number`; serial hanya di `source` (`XCC-<model>-<SERIAL>`), IP di `address`.

---

## 2. Akar Masalah & Workstream

### WS-A (PRIORITAS 1) — Kembalikan identitas pada `server_redfish`
**Gejala**: 99% telemetri sensor server (suhu/power/fan) tak ber-`hostname`/`serial`, masuk `Unknown_Host`.
**Hipotesis**: Telegraf `inputs.redfish` tidak lagi menambah tag `host`/`serial` (di v4.2 §4.1 contoh config punya `[inputs.redfish.tags] host=...`), **atau** normalizer tidak memetakan `source`→serial & `address`→ip.

**Langkah investigasi → perbaikan**:
1. Cek config aktif: `grep -n -A5 "inputs.redfish" /etc/telegraf/telegraf*.conf` dan `configs/telegraf/servers-redfish.conf`. Pastikan tiap blok server punya `[inputs.redfish.tags]` dengan `host`/`serial_number`.
2. Cek logika resolusi identitas di normalizer: `src/skills/telemetry/normalizer/executor.py` (fungsi `resolve_device_type` / pemetaan hostname/serial). Lihat apakah ada fallback membaca `tags.source` (`XCC-*-<serial>`) atau `tags.address`.
3. **Perbaikan termurah**: tambahkan mapping di normalizer — bila `serial_number` kosong, ekstrak dari `source` (regex `XCC-.*-([A-Z0-9]+)$`) dan `ip` dari `address`. **Atau** kembalikan tag `host`/`serial_number` di config Telegraf redfish (per server).
4. Pertimbangkan jendela waktu: regresi mulai ~15 Jun. Bandingkan `git log -- configs/telegraf src/skills/telemetry/normalizer` di sekitar 15–18 Jun (commit `dd8593d`, perubahan Telegraf oleh agent lain) untuk menemukan perubahan yang menghilangkan tag.

**Verifikasi**: setelah fix + `systemctl restart telegraf dcim-normalizer`,
```sql
SELECT hostname, serial_number, count(*) FROM dcim_events
WHERE measurement='server_redfish' AND event_time>now()-interval '10 min'
GROUP BY 1,2;  -- harus muncul HCI-01..03 + Render-01/02, BUKAN Unknown_Host
```

### WS-B (PRIORITAS 2) — Pulihkan `inventory_snapshot` harian
**Gejala**: inventory terakhir 2026-06-18; field firmware/bios/cpu/nic NULL di query 24h.
**Catatan**: `dcim-server-inventory.timer` ternyata fire tiap **5 menit** (seharusnya **harian 01:00**) — dan tetap tidak menghasilkan baris baru → jalur collector→Kafka→consumer putus.

**Langkah**:
1. Jalankan manual & baca error: `python3 scripts/server_inventory_collector.py` (amati apakah produce ke topik `dcim.raw.hardware.server.inventory`).
2. Cek topik menerima: `docker exec kafka-broker /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic dcim.raw.hardware.server.inventory --max-messages 2 --timeout-ms 15000`.
3. Cek branch inventory di consumer `src/skills/telemetry/event_logger/executor.py` (apakah menulis `metric_name='inventory_snapshot'` + tabel relasional). Lihat log `dcim-sql-consumer`.
4. Perbaiki jadwal timer ke harian 01:00: `systemctl cat dcim-server-inventory.timer` → set `OnCalendar=*-*-* 01:00:00`, `daemon-reload`.

**Verifikasi**:
```sql
SELECT hostname, max(event_time) FROM dcim_events
WHERE metric_name='inventory_snapshot' GROUP BY 1;  -- harus < 25 jam utk 5 server
```
Dan tabel relasional ter-refresh: `SELECT count(*) FROM dcim_server_disks;`

### WS-C (PRIORITAS 3) — Pulihkan koleksi Render-02
**Gejala**: Render-02 (`SERVER-RENDER-02`, serial `J901F8KD`) — util terakhir 2026-06-17, sensor & inventory ikut basi. Tidak muncul di jendela 24h.
**Catatan**: Render-02 pakai kredensial **`root`** (berbeda dari 4 server lain `hndept`). Kemungkinan auth/endpoint Redfish gagal.

**Langkah**:
1. Uji koneksi Redfish Render-02: `curl -sk -u root:<pwd> https://10.50.0.<ip-render02>/redfish/v1/Systems/1 | head` (cek HTTP 200).
2. Cek config util poller & redfish input untuk Render-02 (kredensial benar? endpoint OEM metrics tersedia di unit ini?). File: `scripts/redfish_telemetry_poller.py`, `configs/telegraf/servers-redfish.conf`.
3. Pastikan Render-02 ikut WS-A & WS-B setelah identitas/inventory pulih.

**Verifikasi**: Render-02 muncul di ketiga measurement (`server_redfish`, `server_redfish_util`, `inventory_snapshot`) dengan event segar.

### WS-D (Guard) — Pastikan 5 kategori lain TETAP sehat + perbaiki drift dokumen
1. **Regression guard** — jalankan audit §1 sebelum & sesudah setiap perubahan; pastikan `cctv/nas/network/nvr/ups` tetap `no_serial=0`, `unknown_host=0`, freshness < 5 menit.
2. **Drift dokumen** (ditemukan saat audit): `device_type` aktual = **`network`**, BUKAN `network_switch`. Query di `docs/development/34-database-query-baseline-for-agents.md` §5.4 (dan tabel §2.1) memakai `'network_switch'` → **kembali 0 baris**. Perbaiki semua `network_switch` → `network` di dokumen tim AI (34-..., dan cek `ai-training-data-schema.md`). Verifikasi nilai final: `SELECT DISTINCT device_type FROM dcim_events;`

---

## 3. Urutan Eksekusi yang Disarankan
1. **WS-A** (identitas server_redfish) — dampak terbesar, paling cepat memulihkan fitur server.
2. **WS-B** (inventory harian) — memulihkan firmware/bios/komponen.
3. **WS-C** (Render-02) — lengkapi server ke-5.
4. **WS-D** sepanjang proses (guard) + commit perbaikan dokumen drift.
5. Setelah server pulih: refresh MV `v_train_server` & cek `cpu_util_pct`/`temp_celsius` terisi untuk training tim AI.

## 4. Keamanan & Rollback
- Ubah Telegraf/normalizer di **jam sepi**; simpan salinan config sebelum edit (`cp ... .bak.YYYYMMDD`).
- Setiap restart service: verifikasi tidak ada lonjakan DLQ (`SELECT count(*) FROM dlq_records WHERE received_at>now()-interval '15 min';`).
- Jangan ubah retensi/`dcim_events`/pipeline kategori lain.
- Commit per-workstream, pesan jelas (`fix(server): restore redfish identity tagging`, dst).

## 5. Verifikasi Akhir (Definition of Done)
- [ ] `server_redfish` ber-`hostname`/`serial` untuk 5 server (Unknown_Host ≈ 0).
- [ ] `inventory_snapshot` < 25 jam untuk 5 server; tabel relasional `dcim_server_*` terisi.
- [ ] Render-02 hadir di 3 measurement, segar.
- [ ] Audit §1: keenam device_type `no_serial=0`, `unknown_host=0`, fresh < 5 mnt.
- [ ] Query `docs/.../34-...` §5.1 server menampilkan 5 server dengan field terisi (bukan Unknown_Host).
- [ ] Dokumen tim AI: `network_switch` → `network` diperbaiki.

## 6. Perintah Audit Cepat (tempel-jalankan)
```bash
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"SELECT device_type, count(*) ev, count(DISTINCT serial_number) sn,
        count(*) FILTER (WHERE serial_number IN ('NO_IDENTIFIER','NO_SN') OR serial_number IS NULL) no_sn,
        count(*) FILTER (WHERE hostname='Unknown_Host' OR hostname IS NULL) unk,
        max(event_time) last
 FROM dcim_events WHERE event_time>now()-interval '24 hours'
 GROUP BY 1 ORDER BY 1;"
```

---
*Catatan: regresi server kemungkinan imbas commit 'AI readiness phase 0-4' (`dd8593d`) + perubahan Telegraf/penghapusan topik legacy sekitar 15–18 Jun 2026. Mulai investigasi dari `git log` rentang itu pada `configs/telegraf` & `src/skills/telemetry/normalizer`.*
