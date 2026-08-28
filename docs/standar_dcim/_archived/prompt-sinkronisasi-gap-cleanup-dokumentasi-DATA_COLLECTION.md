# Prompt Agent — Sinkronisasi, Penutupan Gap, Cleanup, & Update Dokumentasi `DCIM_SRV_DATA_COLLECTION`

> **Cara pakai:** Tempel seluruh isi ini sebagai instruksi awal ke coding agent (Claude Code/Codex/agent
> lain) yang punya akses `bash`/`git` **nyata** ke working copy lokal di host `10.70.0.56`
> (`/home/infra/dcim_metrics_project`), dengan kredensial GitHub `Chefinox` untuk push.
>
> **RUANG LINGKUP — BACA DULU:**
> - ✅ Boleh disentuh: `DCIM_SRV_DATA_COLLECTION` (repo saya sendiri, milik `Chefinox`).
> - 👀 Boleh dibaca sebagai referensi saja: `dcim-wiki` (milik `shuffahaqgzz`) — **jangan diedit/di-push**.
> - ❌ **JANGAN SENTUH SAMA SEKALI**: `dcim-core-platform`. Jangan clone, jangan fetch, jangan buka
>   branch/PR baru, jangan commit, jangan push ke repo itu dalam sesi ini — meskipun ada dokumen
>   lama (`prompt-01-push-to-dcim-core-platform.md`, `prompt-02-implementation-plan-gap-closure.md`,
>   dll.) yang menyebutkannya. Porting ke `dcim-core-platform` **ditunda**, bukan bagian dari sesi ini.

Kerjakan **6 tahap berurutan** di bawah. Setiap tahap punya "gerbang laporan" — tunjukkan hasilnya ke
saya sebelum lanjut ke tahap berikutnya, kecuali disebutkan boleh lanjut otomatis.

---

## TAHAP 1 — Sinkronisasi Git Lokal agar Selaras dengan `origin/main`

```bash
cd /home/infra/dcim_metrics_project
git remote -v                                   # pastikan remote origin = Chefinox/DCIM_SRV_DATA_COLLECTION
git fetch origin
git status --short                               # uncommitted changes?
git log --oneline origin/main..HEAD              # commit lokal belum ke-push
git log --oneline HEAD..origin/main              # origin lebih baru dari lokal?
git diff --stat origin/main..HEAD
git diff --stat HEAD..origin/main
```

- Jika ada commit lokal belum ke-push: tunjukkan daftar commit + ringkasan file yang berubah ke saya,
  tunggu konfirmasi, baru `git push origin main`.
- Jika lokal ketinggalan dari `origin/main` dan **tidak ada** uncommitted local changes yang konflik:
  boleh langsung `git pull origin main` dan lanjut.
- Jika ketinggalan **dan** ada uncommitted local changes yang berpotensi konflik: **STOP**, laporkan ke
  saya, jangan pull otomatis.

**Laporkan:** status akhir (`git log -1 --format="%h %ci %s"` dan `git status --short` harus bersih)
sebelum lanjut ke Tahap 2.

---

## TAHAP 2 — GAP Analysis (Verifikasi Ulang ke Kode, Bukan ke Label Dokumen)

Baseline gap terakhir yang sudah tervalidasi ke kode (per 10-12 Agustus 2026) — verifikasi ulang tiap
baris terhadap kondisi kode **saat ini** (mungkin sudah berubah sejak Tahap 1 pull):

| # | Area | Baseline | Yang wajib dicek ulang |
|---|---|---|---|
| 1 | Validation Engine | Terpasang di `src/skills/telemetry/normalizer/executor.py`, tapi `ValidationEngine(val_config, dry_run=True)` — event gagal validasi tetap diloloskan (`status` dipaksa `"accepted"` di `src/validation/engine.py`). | `grep -n "dry_run" src/skills/telemetry/normalizer/executor.py src/validation/engine.py` — apakah masih `True`? |
| 2 | Rate limiter poller | 5/6 poller punya `PollRateLimiter` (`redfish_poller.py`, `mikrotik_poller.py`, `nas_poller.py`, `snmp_ups_poller.py`, `cctv_poller.py`). `hikvision_poller_daemon.py` **belum**. | `grep -L "rate_limiter" scripts/*.py` |
| 3 | Impact Scoring & Data Quality Scorecard | Sudah aktif (bukan dry-run) di `src/scoring/impact.py` & `src/scoring/data_quality.py`, dipanggil dari enrichment & normalizer executor. | `grep -n "ImpactScorer\|DataQualityScorecard" src/skills/**/executor.py` |
| 4 | Virtualization/Cloud collector | Belum ada (vCenter/AWS/GCP). | `grep -rli "vcenter\|vsphere\|boto3" scripts/ src/` |
| 5 | Connector ServiceNow/Jira | Belum ada. | `grep -rli "servicenow\|jira" scripts/ src/` |
| 6 | Topic Kafka `dcim.cmdb.updates` / `dcim.asset.updates` | Belum ada topic terdedikasi. | `docker exec <kafka-container> kafka-topics.sh --bootstrap-server localhost:9092 --list \| grep -E "cmdb.updates\|asset.updates"` |
| 7 | Arsip DLQ ke S3/MinIO | Belum ada. 3 topic DLQ (`dcim.dlq.parse-failure`, `dcim.dlq.enrichment-failure`, `dcim.dlq.delivery-failure`) masih retensi Kafka biasa. | `grep -rli "minio\|boto3\|s3_bucket" scripts/ src/` |
| 8 | Circuit breaker per-connector | Hanya ada di sisi consumer/iTop sync (`src/utils/circuit_breaker.py`), poller connector masih retry-loop lokal. | `grep -rn "circuit_breaker" scripts/*.py` |
| 9 | ST-115 (Ralph↔Grafana) | Status `Stuck` sejak 10/03/2026 di task tracker. | Cek apakah sudah ada progres teknis (dashboard/config baru) sejak tanggal itu. |
| 10 | ST-346 (Kafka multi-host migration) | Status `Waiting`, sementara upgrade versi 3.7→4.1.2 sudah Done. | Cek relevansinya — apakah masih dibutuhkan atau superseded oleh cluster 3-node yang sudah ada. |

**Laporkan:** tabel di atas dengan kolom "Status terkini" (masih sama / sudah berubah) + bukti command.
Tunggu saya konfirmasi prioritas sebelum lanjut ke Tahap 3 — terutama urutan mana yang dikerjakan
duluan (default: #1 dan #2 dulu karena paling kecil risikonya dan sudah punya pola siap pakai).

---

## TAHAP 3 — Pembaruan Pipeline / Konfigurasi untuk Menutup Kekurangan

Kerjakan **satu item per commit**, jangan digabung. Untuk tiap item, tunjukkan rencana singkat dulu
sebelum implementasi (file yang akan diubah + pendekatan), tunggu konfirmasi saya untuk item yang
menyentuh perilaku produksi (item #1 di bawah termasuk kategori ini).

1. **Validation Engine enforce toggle (P1).**
   - Jangan langsung set `dry_run=False` secara blak-blakan. Buat ini **configurable** (mis. via
     `configs/validation_rules.yaml` atau env var `DII_VALIDATION_DRY_RUN`), default tetap `True`.
   - Tambahkan target DLQ topic untuk event yang di-reject validasi kalau `dry_run=False`
     (gunakan pola producer yang sama seperti `dcim.dlq.parse-failure` di `normalizer/executor.py`).
   - **Sebelum mengubah default ke `False` di production**: tarik dulu metrik
     `dii_validation_rejected_total` dan gauge `dcim_dq_*` dari Prometheus/Grafana beberapa hari
     terakhir, laporkan ke saya berapa persen event yang akan ke-reject per rule. Saya yang putuskan
     kapan enforce dinyalakan — **jangan nyalakan `dry_run=False` di production tanpa persetujuan
     eksplisit saya**, karena ini bisa langsung memblokir data masuk.

2. **Rate limiter di `hikvision_poller_daemon.py` (P2, aman langsung dikerjakan).**
   - Ikuti pola persis dari `cctv_poller.py` (`from src.utils.rate_limiter import get_limiter`).
   - Tambahkan test kecil kalau ada `tests/` yang setara untuk poller lain.

3. **Sisanya (#4–#8 di Tahap 2)** — untuk masing-masing, tunjukkan dulu ke saya rencana implementasi
   dan estimasi effort sebelum mulai coding. Ini item yang lebih besar (fitur baru, bukan tambal gap
   kecil), jadi urutan pengerjaan dan prioritas sepenuhnya saya yang tentukan setelah melihat rencana.

**Gate wajib sebelum commit tiap item (kalau tersedia di repo):**
```bash
pytest tests/ -k <nama_test_relevan>   # atau test suite yang relevan dengan modul yang diubah
```

---

## TAHAP 4 — Cleaning Project Structure `dcim_metrics_project`

Tujuan: pindahkan dokumen/file lawas ke `_archived/`, **jangan dihapus** — semua tetap bisa ditelusuri
lewat git history dan tetap ada fisik di folder archive kalau sewaktu-waktu dibutuhkan lagi.

### 4a. File `.bak.*` yang bertebaran di luar folder archive
```bash
find . -iname "*.bak*" -not -path "./_archived/*" -not -path "./kafka/backups/*" -not -path "./kafka/certs.bak*" -not -path "./.git/*"
```
Ini termasuk banyak versi lama `redfish_poller.py.bak.*` dan `server_inventory_collector.py.bak.*` di
`scripts/`, serta `docker-compose-cluster.yml.bak-*` di `kafka/`. Pindahkan semuanya ke subfolder baru
`_archived/backups-preF-series/` (atau kelompokkan per komponen kalau lebih rapi), **kecuali** backup
yang masih dipakai aktif oleh script rollback (`scripts/restore_redfish_poller.sh`,
`scripts/restore_server_inventory_collector.sh`) — cek dulu isi script itu, jangan pindahkan file yang
masih direferensikan path-nya secara hardcode tanpa menyesuaikan path di script rollback juga.

### 4b. Duplikat Task Tracker
```bash
find . -iname "*task*tracker*" -o -iname "*Tasks Tracker*"
```
Ada 3 salinan: `docs/Task Tracker/....tsv`, `docs/standar_dcim/....(1).tsv`,
`docs/standar_dcim/....(2).tsv`. Simpan **satu** versi terbaru sebagai canonical (bandingkan tanggal
modifikasi/isi, ambil yang paling baru/lengkap), pindahkan sisanya ke `_archived/misc_files/`.

### 4c. Dokumen arsitektur versi lama (superseded)
Cek `docs/architecture/24-versioning-change-management-standard.md` §4 (Log Perubahan Sistem) untuk
tahu versi mana yang aktif. Per kondisi terakhir yang saya tahu, `v4.6-pipeline-architecture.md` adalah
versi aktif, sementara `v4.4-pipeline-architecture.md`, `v4.4-pipeline-architecture-komparasi.md`,
`v4.5-pipeline-architecture.md`, `v4.5-pipeline-architecture-komparasi.md` sudah superseded (mengikuti
pola yang sudah ada di `docs/architecture/_archived/SUPERSEDED-v4.2-pipeline-architecture.md`,
`v4.3-pipeline-architecture.md`, dst.). Pindahkan v4.4 & v4.5 ke `docs/architecture/_archived/` dengan
prefix `SUPERSEDED-`, ikuti konvensi penamaan yang sudah ada. **Jangan archive versi terbaru
(saat ini v4.6, atau versi baru yang dibuat di Tahap 5) — itu harus tetap di `docs/architecture/`.**

### 4d. Dokumen perencanaan porting `dcim-core-platform` (di luar ruang lingkup untuk saat ini)
Karena porting ke `dcim-core-platform` **ditunda**, pindahkan dokumen berikut dari
`docs/standar_dcim/` ke `_archived/on-hold-core-platform-porting/` (tetap disimpan, bukan dihapus,
supaya gampang dilanjutkan nanti):
- `prompt-01-push-to-dcim-core-platform.md`
- `prompt-02-implementation-plan-gap-closure.md`
- `prompt-push-dcim-data-collection-to-core-platform.md`
- `prompt-correct-source-of-truth-and-reaudit-pr40.md`
- `prompt-tugas1-koreksi-dan-lanjut-tugas2.md`

### 4e. File besar yang tidak relevan sebagai working docs (opsional, konfirmasi dulu)
`docs/standar_dcim/` berisi file besar seperti `Lenovo ThinkSystem SR665 V3 Server_Product_Guide.pdf`
(~22MB), `ThinkSystem SR650 V3_Product_Guide.pdf` (~24MB), `IF-Use_Case_Analysis-FIT041-20260121.md`
(~2.5MB). Ini kemungkinan referensi vendor/dokumen requirement lama, bukan dokumen kerja aktif.
**Jangan pindahkan otomatis** — cukup laporkan daftarnya ke saya dengan ukuran file, biar saya yang
putuskan mana yang masih perlu tetap gampang diakses vs boleh diarchive.

**Laporkan sebelum commit:** ringkasan `git status` (jumlah file dipindah, ke mana), dan konfirmasi
tidak ada file yang **dihapus** (semua harus tetap `git mv`, bukan `rm`).

---

## TAHAP 5 — Update/Pembuatan Dokumentasi Arsitektur & Komparasi (Jika Ada Perubahan Versi)

Lakukan tahap ini **hanya jika** Tahap 3 menghasilkan perubahan yang cukup signifikan untuk naik versi
(mis. validation engine mulai enforce, poller baru, topic Kafka baru). Kalau Tahap 3 cuma menutup gap
kecil (rate limiter hikvision saja), cukup update changelog di
`24-versioning-change-management-standard.md` §4 tanpa bikin dokumen versi baru.

Jika naik versi (mis. v4.6 → v4.7):
1. Duplikat `docs/architecture/v4.6-pipeline-architecture.md` → `v4.7-pipeline-architecture.md`,
   update bagian yang berubah saja (jangan tulis ulang total — ikuti gaya dokumen yang sudah ada).
2. Duplikat `v4.6-pipeline-architecture-komparasi.md` → `v4.7-pipeline-architecture-komparasi.md`,
   perbarui tabel komparasi versi (tambahkan kolom/baris v4.7 vs v4.6).
3. Update tabel "Log Perubahan Sistem" di `24-versioning-change-management-standard.md` dengan baris
   baru: versi, tanggal, ringkasan perubahan, status.
4. Update README.md di root repo kalau ada bagian yang menyebut versi pipeline secara eksplisit.
5. Pindahkan `v4.6-pipeline-architecture.md` & `-komparasi.md` yang lama ke
   `docs/architecture/_archived/` dengan prefix `SUPERSEDED-` (baru dilakukan setelah v4.7 dikonfirmasi
   final, bukan sebelum).

**Jangan** membuat/mengubah dokumen apa pun di `dcim-wiki` atau `dcim-core-platform` di tahap ini.

---

## TAHAP 6 — Commit & Push (Update Repo ke State Terakhir)

- Commit per unit kerja kecil dan koheren (ikuti gaya commit message yang sudah ada di repo ini —
  Conventional Commits, mis. `fix(pollers): add rate limiter to hikvision_poller_daemon`,
  `chore(cleanup): archive superseded v4.4/v4.5 architecture docs and stray .bak files`,
  `docs(architecture): add v4.7-pipeline-architecture.md`).
- Jangan gabungkan commit cleanup (Tahap 4) dengan commit perubahan kode (Tahap 3) dalam satu commit
  yang sama — pisahkan supaya history tetap mudah ditelusuri.
- Sebelum push, jalankan ulang:
  ```bash
  git status --short   # harus bersih
  git log --oneline origin/main..HEAD   # daftar commit yang akan dipush, tunjukkan ke saya dulu
  ```
- Setelah saya konfirmasi, `git push origin main`.
- **Konfirmasi akhir yang wajib dilaporkan ke saya:**
  - `git log -1 --format="%h %ci %s"` dari `origin/main` setelah push (bukti repo GitHub sudah update).
  - Ringkasan semua commit yang masuk sesi ini (list singkat, bukan full diff).
  - Konfirmasi eksplisit: **tidak ada satupun perubahan yang menyentuh `dcim-core-platform`** dalam
    sesi ini.
