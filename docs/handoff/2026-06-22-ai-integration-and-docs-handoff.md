# Handoff — AI Integration, Doc Alignment & E2E Testing (2026-06-22)

> **Untuk**: agent/engineer berikutnya. **Dari**: sesi sebelumnya (token menipis).
> **Host**: `srv-rnd-dcim` (10.70.0.56) · **Repo**: `/home/infra/dcim_metrics_project` · branch `main` (trunk-based, commit langsung ke main).
> **Baca dulu**: `docs/architecture/v4.2-pipeline-architecture.md` (sumber kebenaran arsitektur).

---

## 1. Konteks & Keputusan yang DIKUNCI user

1. **Host = PENYEDIA DATA, bukan tempat menjalankan AI.** Training & inference dilakukan **tim AI di infrastruktur mereka**, akses **dari luar** (read-only PG / opsional Kafka). **TIDAK ADA** model/agen/inference AI yang boleh di-deploy di host ini, tidak ada proses AI dengan akses shell/direktori. (v4.2 §16 = L14.)
2. **Penamaan ikut konvensi kita** (`dcim_*`, `v_train_*`), bukan nama dari MT-018.
3. **Data belum dikoleksi → cukup di-LIST**, jangan bangun collector baru. Humidity tidak ada (out of scope).
4. **v4.0 & v4.1 tidak diubah**; semua perubahan di v4.2 (jejak versi terpisah & auditable).

---

## 2. ⚠️ ACTION ITEM #1 (KRITIS) — Cabut inference AI on-host

Terverifikasi: **`dcim-ai-inference.service` sedang `active` DAN `enabled`** di host ini, menjalankan `src/skills/ai/anomaly_inference/executor.py`. Ini **melanggar keputusan #1** (dipasang oleh commit lama `dd8593d` "AI readiness phase 0-4"). **Belum dicabut** karena perlu konfirmasi user.

Tindakan yang disarankan (konfirmasi user dulu):
```bash
sudo systemctl disable --now dcim-ai-inference.service
sudo rm -f /etc/systemd/system/dcim-ai-inference.service
sudo systemctl daemon-reload
# arsipkan kode agar tidak dijalankan lagi di host:
git mv src/skills/ai/anomaly_inference _archived/deprecated_ai_inference 2>/dev/null || \
  mv src/skills/ai/anomaly_inference _archived/deprecated_ai_inference
```
Verifikasi: `systemctl is-enabled dcim-ai-inference.service` → harus `not-found`/error; `systemctl list-units | grep ai-inference` → kosong.
> Wadah hasil `dcim_server_anomalies` **tetap dipertahankan** — tim AI menulis ke sana dari luar. Yang dicabut hanya proses inference on-host.

---

## 3. Yang SUDAH dikerjakan sesi ini (commit di `main`, BELUM di-push)

| Commit | Isi |
|---|---|
| `050c4c1` | chore: arsipkan script legacy + hapus junk shell-error |
| `2ddd193` | docs: tambah **v4.2** dengan L14 dikoreksi (data-provider, tanpa AI on-host) |
| `35b45a9` | feat: **role DB read-only `dcim_ai_reader`** untuk tim AI (L14) |
| `9815287` | docs: selaraskan baseline AI + v4.2 ke implementasi aktual |
| `9bd45eb` | docs(ops): langkah akun iTop read-only + **panduan tes E2E v4.2** |

> Total **5 commit di atas `origin/main` belum di-push.** Repo punya ~130 perubahan working-tree lain dari agent sebelumnya (logs/configs/src) yang **sengaja TIDAK di-commit**; staging selalu **selektif per-file**.

### Artefak penting yang dibuat
- `sql/ai_access_role.sql` — DDL idempoten role `dcim_ai_reader` (least privilege: SELECT `v_train_*`/arsip/`dcim_failure_events`; SELECT+INSERT+UPDATE **hanya** `dcim_server_anomalies`; conn limit 10).
- `configs/ai_reader.credentials` — kredensial PG tim AI (**gitignored**, 0600). **Belum diserahkan** ke tim AI.
- `docs/development/ai-team-data-access-connection-guide.md` — panduan koneksi tim AI.
- `docs/operations/itop-readonly-account-for-ai-team.md` — langkah buat akun iTop read-only.
- `docs/operations/pipeline-e2e-testing-guide-v4.2.md` — tes E2E (sukses/DLQ/alert).

---

## 4. Kondisi sistem aktual (terverifikasi sesi ini)

- **PostgreSQL `dcim_sot`** (container `dcim_sot_postgres`): `dcim_events` (retensi 7 hari, partisi harian), `dcim_metrics_archive` (~117 jt baris: m04≈0,2jt/m05≈46,3jt/m06≈71,3jt), 6× `v_train_*` (server/ups/nas/network/cctv/nvr) berisi data, `dcim_failure_events` (kosong=wajar), `dcim_server_anomalies` (wadah, kosong).
- **L13 archive AKTIF**: `scripts/es_to_pg_archive.py` + `dcim-metrics-archive.timer` harian 03:00.
- **Role DB**: `sot_admin` (superuser) + **`dcim_ai_reader`** (baru, read-only) — uji privilege LULUS (read ok, write tabel inti ditolak, DDL ditolak).
- **`v_train_server`**: `cpu_util_pct`/`mem_util_pct` masih **NULL** (utilisasi CPU/RAM server belum terkoleksi via Redfish — di-LIST sbagai gap di v4.2 §15.4, TIDAK dibangun sekarang). Kolom suhu/power/fan terisi.
- **Kafka** (container `kafka-broker`, `/opt/kafka/bin/*.sh`): topik raw `dcim.raw.hardware.server(.inventory)`, `dcim.raw.power.ups`, `dcim.raw.storage.nas`, `dcim.raw.network.{snmp,interfaces}`, `dcim.raw.device.isapi`; `dcim.normalized.events`; `dcim.enriched.events`; DLQ `dcim.dlq.{parse,enrichment,delivery}-failure`. (Ada juga topik lama/duplikat seperti `dcim.raw.server`, `dcim-metrics`, `dcim.telemetry.*` — warisan, perlu audit terpisah.)
- **Service aktif**: normalizer, enrichment-api, sql-consumer, telegraf-consumer, itop-unified, itop-redis-sync, dlq-consumer, threshold-alerter (+ **ai-inference yang harus dicabut**, lihat §2).

---

## 5. ACTION ITEMS sisa (butuh keputusan/akses user)

| # | Aksi | Catatan |
|---|---|---|
| 1 | **Cabut `dcim-ai-inference.service`** | lihat §2 — perlu `sudo`, konfirmasi user |
| 2 | **Push 5 commit** ke `origin/main` | user belum minta push; jalankan `git push origin main` bila disetujui |
| 3 | **Serahkan kredensial PG** tim AI | dari `configs/ai_reader.credentials` via kanal aman |
| 4 | **Buat akun iTop read-only** | ikuti `docs/operations/itop-readonly-account-for-ai-team.md` (UI iTop, perlu admin) |
| 5 | **Keputusan Kafka eksternal** | bila tim AI mau stream real-time, perlu buka `advertised.listeners` Kafka (kini kemungkinan localhost-only) — perubahan jaringan, konfirmasi dulu |
| 6 | **(Opsional) audit topik Kafka warisan** | `dcim.raw.server`, `dcim-metrics`, `dcim.telemetry.*` tampak tak terpakai |

---

## 6. Cara verifikasi cepat (smoke test)

```bash
# Pipeline hidup (data aktual <5 menit):
docker exec dcim_sot_postgres psql -U sot_admin -d dcim_sot -c \
"SELECT device_type, count(*) e5m, max(event_time) last FROM dcim_events
 WHERE event_time > now()-interval '5 min' GROUP BY 1 ORDER BY 1;"

# Role tim AI berfungsi (read ok):
docker exec -e PGPASSWORD="$(grep PASSWORD configs/ai_reader.credentials|cut -d= -f2)" \
  dcim_sot_postgres psql -U dcim_ai_reader -h 127.0.0.1 -d dcim_sot \
  -tAc "SELECT 'rows='||count(*) FROM v_train_server;"
```
Tes E2E lengkap (sukses/DLQ/alert): ikuti `docs/operations/pipeline-e2e-testing-guide-v4.2.md`.

---

## 7. Catatan utang teknis (di luar scope, dicatat saja)
- Kredensial hardcoded di beberapa script (mis. ES password di `scripts/dcim_threshold_alerter.py`, iTop di script sync). Pindahkan ke secret store.
- `configs/.env` **tidak** gitignored — risiko bocor; pertimbangkan ignore + rotasi.
- ~130 perubahan working-tree belum di-commit dari sesi agent sebelumnya — perlu ditinjau apakah dibuang atau di-commit terpisah.
