# Prompt Agent 1 — Persiapan & Eksekusi Push Pertama ke `dcim-core-platform`

> **Cara pakai:** Tempel sebagai instruksi awal untuk coding agent (Claude Code/Codex) yang
> berjalan di mesin lokal Anda, dengan akses ke clone lokal `DCIM_SRV_DATA_COLLECTION` dan
> kredensial GitHub Anda (`Chefinox`). Agent butuh akses `bash`/`git` nyata untuk clone, fork,
> commit, dan membuka PR.

---

## KONTEKS & IDENTITAS

- Saya: **Imam Syauqi Achmad**, GitHub `Chefinox`.
- Repo sumber (privat, milik saya): `https://github.com/Chefinox/DCIM_SRV_DATA_COLLECTION.git`
- Repo acuan arsitektur (bukan milik saya, owner `shuffahaqgzz`): `https://github.com/shuffahaqgzz/dcim-wiki.git`
- Repo target kontribusi (bukan milik saya, owner `shuffahaqgzz`): `https://github.com/shuffahaqgzz/dcim-core-platform.git`

Saya kontributor eksternal ke `dcim-core-platform`, bukan owner. Semua perubahan lewat
**fork → branch → Pull Request**, tidak pernah push langsung ke `main` repo asal, dan merge/approve
sepenuhnya wewenang `shuffahaqgzz`.

---

## GERBANG PRASYARAT — JANGAN LEWATI

Sebelum menyentuh `dcim-core-platform` sama sekali, verifikasi urutan berikut satu per satu dan
laporkan hasilnya ke saya sebelum lanjut ke langkah berikutnya:

### G0 — Kredensial sudah dirotasi
Tanyakan ke saya secara eksplisit: *"Apakah Vault root token/unseal key, AppRole role_id/secret_id,
password iTop/MariaDB/PostgreSQL SoT, token Ralph API, token NetBox, dan password perangkat
(Redfish BMC, SNMP v3 UPS, NAS, Hikvision NVR/kamera) yang sempat ter-expose sudah semua
dirotasi/di-revoke?"* Jika saya belum konfirmasi ya, **STOP** — jangan lanjut ke G1, karena
riwayat git yang sudah bersih tidak ada gunanya jika kredensial lama masih valid.

### G1 — Git history `DCIM_SRV_DATA_COLLECTION` sudah bersih & sudah ter-push
```bash
cd <path-lokal-DCIM_SRV_DATA_COLLECTION>
git fetch origin
git log --all --pretty=format: --name-only | sort -u | grep -iE 'secret|vault/config|\.env($|\.)|kafka/certs|setup_secrets\.sh'
git rev-list --all | xargs -I{} git grep -lE "BEGIN (RSA |EC |)PRIVATE KEY|hvs\.[A-Za-z0-9]{15,}" {} 2>/dev/null
```
Kedua command di atas harus kosong (kecuali baris `itop/.env.example`, yang memang template aman
dan boleh tetap ada). Jika masih ada hasil, **STOP**, jangan lanjut — bersihkan dulu histori
lokal dengan `git-filter-repo` mengikuti `purge-paths.txt` yang sudah disiapkan, lalu
`git push --force --all origin` ke `Chefinox/DCIM_SRV_DATA_COLLECTION` (bukan ke
`dcim-core-platform`), baru lanjut ke G2.

### G2 — Working tree lokal mencerminkan implementasi terkini
```bash
git status
git diff --stat
git log --oneline origin/main..HEAD   # commit lokal yang belum ke-push
```
Jika ada perubahan pipeline (poller baru, schema baru, topic baru) yang belum ter-commit/ter-push,
commit dan push dulu ke `origin main` `DCIM_SRV_DATA_COLLECTION`. Laporkan ke saya ringkasan commit
terakhir (`git log -1`) sebagai bukti "state up to date" sebelum lanjut ke G3.

### G3 — Akses ke `dcim-core-platform` dikonfirmasi (fork vs collaborator)
```bash
gh auth status
gh api repos/shuffahaqgzz/dcim-core-platform/collaborators/Chefinox/permission 2>&1 || echo "TIDAK ADA akses collaborator langsung -> pakai jalur fork"
```
- Jika ada akses write langsung → boleh push branch langsung ke repo asal.
- Jika tidak (paling mungkin) → **fork dulu**:
```bash
gh repo fork shuffahaqgzz/dcim-core-platform --clone=true --remote=true
cd dcim-core-platform
```

### G4 — Pahami aturan repo target sebelum menulis apa pun
Baca penuh sebelum lanjut: `AGENTS.md`, `DATA-HANDLING.md`, `CONTRIBUTING.md`,
`docs/governance/OPEN-DECISIONS.md`, dan `docs/adr/0023-*` (connector/source-impact controls).
Jangan berasumsi isinya sama seperti yang sudah dibaca sebelumnya — file bisa berubah, baca ulang.

---

## SCOPE PUSH PERTAMA (PR #1)

PR pertama **bukan** migrasi besar — cukup langkah kecil, aman, dan mudah direview, sebagai bukti
alur kerja sebelum PR yang lebih substantif (Validation Processor, dsb., ada di prompt terpisah):

**Kandidat isi PR #1** (pilih salah satu, yang paling rendah risiko dan paling cepat direview):
- Dokumentasi desain: ringkasan pola arsitektur pipeline aktual (Kafka 3-node KRaft, Avro +
  Schema Registry, DLQ 3-topic, Circuit Breaker 3-state, Data Classification Matrix) ditulis
  ulang **sepenuhnya generik** — nama layer/pola, bukan nilai/IP/hostname/topic-name literal dari
  host produksi saya — sebagai `docs/architecture/` baru atau draft ADR baru di `dcim-core-platform`.
- **TIDAK** menyertakan kode poller/consumer/config apa pun pada PR ini — itu untuk PR susulan
  (lihat Prompt Agent 2) setelah rancangan disetujui.

## ATURAN DATA-HANDLING (WAJIB, TIDAK BOLEH DILANGGAR)

- Tidak ada credential, token, IP/hostname/FQDN nyata, nama site/rack/kamera, topologi jaringan,
  payload/log/raw data nyata dari `DCIM_SRV_DATA_COLLECTION` yang boleh masuk ke
  `dcim-core-platform` dalam bentuk apa pun.
- Semua contoh harus sintetis, mengikuti pola `fixtures/synthetic/` yang sudah ada di repo target.
- Nama pribadi sebagai penulis/kontributor: **Imam Syauqi Achmad** (nama lengkap), bukan nickname.
- Jika ragu suatu detail termasuk Restricted/Confidential atau tidak → jangan sertakan, tanyakan
  ke saya dulu.

## LANGKAH EKSEKUSI

```bash
git checkout -b docs/actual-pipeline-architecture-reference
# ... buat/tulis file dokumentasi generik di dcim-core-platform ...
make phase0-check
python scripts/check_public_repo_safety.py
git add <file-baru>
git commit -m "docs(architecture): document generic ingestion pipeline reference pattern"
git push origin docs/actual-pipeline-architecture-reference
gh pr create --repo shuffahaqgzz/dcim-core-platform \
  --title "docs: reference pattern for multi-source ingestion pipeline" \
  --body "..."
```

PR description wajib memuat:
- Scope & out-of-scope.
- **Data-handling declaration eksplisit**: konten sepenuhnya generik/sintetis, tidak memuat
  credential/IP/hostname/topologi/log nyata.
- Hasil `make phase0-check` dan `check_public_repo_safety.py`.
- Catatan: PR ini adalah langkah pembuka; gap fungsional (Validation Processor dkk.) menyusul di
  PR terpisah setelah rancangan disetujui owner.

**Jangan merge PR ini sendiri.** Setelah PR terbuka, laporkan ke saya: link PR, ringkasan isi,
dan hasil verifikasi. Tunggu review/approval dari `shuffahaqgzz`.
