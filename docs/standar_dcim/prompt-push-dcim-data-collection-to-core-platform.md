# Prompt Agent — Porting DCIM Data Collection ke `dcim-core-platform`

> **Cara pakai:** Salin seluruh isi di bawah ini sebagai instruksi awal untuk coding agent Anda
> (Claude Code / Codex / agent lain) yang dijalankan **di mesin lokal Anda**, dengan akses ke
> clone lokal ketiga repo di bawah. Jangan jalankan agent ini tanpa akses ke working copy lokal
> `DCIM_SRV_DATA_COLLECTION`, karena langkah pertama membutuhkan status git lokal Anda.

---

## KONTEKS

Saya (**Imam Syauqi Achmad**) adalah pemilik/developer solo dari tiga repository berikut:

1. **Repo implementasi aktual (privat/kerja)** — `https://github.com/Chefinox/DCIM_SRV_DATA_COLLECTION.git`
   Berisi implementasi produksi pipeline data collection DCIM: NiFi (orkestrasi koleksi),
   Kafka 3-node KRaft cluster, poller Python per-source (Redfish, SNMP/Mikrotik, Hikvision NVR,
   NAS/Synology, IPMI), normalizer, enrichment API (FastAPI + Redis), consumer ke PostgreSQL/
   Elasticsearch/iTop CMDB, DLQ 3-topik, lineage tracking, Vault untuk secret, dan modul
   `ai_agent/` (CrewAI/LangGraph). Repo ini memuat kredensial, endpoint, IP, hostname, log, dan
   data mentah operasional nyata.

2. **Repo referensi arsitektur** — `https://github.com/shuffahaqgzz/dcim-wiki.git`
   Dokumentasi reference design DCIM Core Platform. Yang paling relevan untuk tugas ini:
   - `reference-designs/block2-data-ingestion-integration.md` — spesifikasi target Data
     Ingestion & Integration Gateway.
   - `comparisons/impl-repo-data-ingestion-alignment.md` — analisis gap FR-by-FR yang sudah
     memetakan `DCIM_SRV_DATA_COLLECTION` terhadap Block 2 (skor keselarasan 69%, dengan daftar
     gap P1/P2/P3 dan rekomendasi).
   - `concepts/dcim-core-platform.md` dan `product-description/dcim-core-platform-product-description.md`
     untuk gambaran produk secara keseluruhan.

3. **Repo target (publik, safety-first)** — `https://github.com/shuffahaqgzz/dcim-core-platform.git`
   Repo pengembangan publik untuk DCIM Core Platform, saat ini di Phase 0–3 (DEV-APPROVED
   bersyarat, belum Production). Diatur ketat oleh `AGENTS.md`, `DATA-HANDLING.md`,
   `CONTRIBUTING.md`, dan ADR di `docs/adr/`. Sudah ada scaffold awal di `connectors/redfish/`
   dan `connectors/snmp/` berupa *synthetic fixture-replay adapter* (tanpa kemampuan network/
   write) sesuai ADR-0023 (connector polling & source-impact controls).

---

## ATURAN WAJIB — BACA SEBELUM MENULIS KODE APA PUN

1. **Batas data publik vs privat bersifat mutlak.** Ikuti `DATA-HANDLING.md` dan `AGENTS.md`
   di `dcim-core-platform` secara harfiah:
   - JANGAN pernah menyalin, mengetik ulang, atau menyisipkan credential, token, key, SNMP
     community string, real IP/hostname/FQDN, serial/asset tag, nama rack/site/camera, topologi
     jaringan, payload/log/capture/dump mentah, atau data operasional nyata dari
     `DCIM_SRV_DATA_COLLECTION` ke dalam `dcim-core-platform` — dalam bentuk apa pun (kode,
     fixture, dokumentasi, commit message, nama file, PR description).
   - Semua contoh data harus **sintetis** (invented identifier, reserved IP range/domain),
     mengikuti pola yang sudah dipakai di `fixtures/synthetic/` pada repo target.
   - Jika ragu apakah sesuatu termasuk Restricted/Confidential → perlakukan sebagai Restricted
     dan JANGAN dimasukkan. Berhenti dan laporkan ke saya alih-alih menebak.
   - Yang boleh dan memang tujuan tugas ini: **pola arsitektur, struktur kode, logic pipeline,
     skema event, desain topic Kafka, pendekatan validasi/enrichment/DLQ/lineage** — dijelaskan
     ulang secara generik, bukan disalin verbatim dari file privat yang memuat data nyata.

2. **Atribusi nama.** Di semua dokumen resmi, ADR, commit message, PR description, dan komentar
   kode yang mencantumkan nama saya sebagai penulis/pengambil keputusan, gunakan nama lengkap
   **"Imam Syauqi Achmad"**. Jangan gunakan nama panggilan/nickname apa pun (termasuk variasi
   seperti "isyauqi"). Username GitHub `shuffahaqgzz` boleh tetap dipakai sebagai identitas
   teknis/owner field karena itu memang identitas akun, bukan nama personal.

3. **Ikuti alur kerja governance repo target**, bukan alur bebas:
   - Jangan push langsung ke `main`. Buat branch sesuai konvensi `AGENTS.md`:
     `feat/<scope>`, `fix/<scope>`, `docs/<scope>`, `chore/<scope>`, atau `adr/<decision>`.
   - Commit memakai Conventional Commits, imperative subject.
   - Jangan mengubah item yang tercantum di `docs/governance/OPEN-DECISIONS.md` secara sepihak —
     jika perubahan menyentuh open decision, buat draft ADR dan minta approval saya sebagai
     owner, jangan langsung implementasi.
   - Selesai bekerja, buka Pull Request (jangan merge sendiri ke `main`), sertakan: scope/
     out-of-scope, issue/ADR terkait, command dan hasil verifikasi, data-handling declaration,
     known limitations.

---

## LANGKAH KERJA

### Tahap 0 — Pastikan repo implementasi saya sudah up to date (WAJIB DILAKUKAN LEBIH DULU)

Sebelum menjadikan `DCIM_SRV_DATA_COLLECTION` sebagai sumber acuan, pastikan working copy lokal
saya benar-benar mencerminkan implementasi terkini:

```bash
cd <path-lokal-DCIM_SRV_DATA_COLLECTION>
git status
git fetch origin
git log --oneline origin/main..HEAD   # commit lokal yang belum ke-push
git log --oneline HEAD..origin/main   # commit remote yang belum ada lokal
git diff --stat                        # perubahan belum ter-commit
```

- Jika ada perubahan belum ter-commit yang relevan dengan pipeline data collection (poller baru,
  perubahan schema, perubahan topic Kafka, dsb.), commit dan push dulu ke `origin` dengan pesan
  yang jelas.
- Jika ada divergence dengan remote, selesaikan dulu (rebase/merge sesuai kebiasaan saya) —
  jangan lanjut ke tahap berikutnya sebelum `origin/main` repo ini benar-benar mencerminkan
  kondisi implementasi saat ini.
- Laporkan ke saya ringkasan apa yang di-commit/push, sebelum lanjut.

### Tahap 1 — Pahami gap dan arsitektur target

1. Baca ulang `dcim-wiki/comparisons/impl-repo-data-ingestion-alignment.md` secara penuh —
   dokumen ini sudah berisi FR-by-FR mapping, gap P1/P2/P3, dan rekomendasi prioritas terhadap
   `dcim-wiki/reference-designs/block2-data-ingestion-integration.md`.
2. Baca `dcim-core-platform/AGENTS.md`, `DATA-HANDLING.md`, `CONTRIBUTING.md`,
   `docs/baseline/DEVELOPMENT-BASELINE.md`, `docs/governance/OPEN-DECISIONS.md`, dan ADR yang
   relevan dengan data ingestion/connector (`docs/adr/0002-*`, `0004-*`, `0008-*`, `0023-*`).
3. Inspeksi struktur yang sudah ada di `dcim-core-platform`: `connectors/redfish/`,
   `connectors/snmp/`, `contracts/`, `schemas/`, `fixtures/synthetic/`, `services/`,
   `docs/architecture/`. Pahami pola *synthetic fixture-replay adapter* yang sudah dipakai
   sebelum menambah kode baru — kode baru harus konsisten dengan pola ini, bukan gaya bebas dari
   repo implementasi lama.
4. Susun dan tunjukkan ke saya (sebelum menulis kode) daftar pekerjaan yang diusulkan, diprioritaskan
   memakai gap P1/P2/P3 dari dokumen alignment, contoh kandidat awal:
   - Formalisasi validation processor (range/format/duplicate/freshness) — saat ini gap P1.
   - Dokumentasi strategi Kafka topic naming & schema versioning yang sudah dijalankan di
     implementasi aktual, disederhanakan menjadi pola generik untuk repo publik.
   - Connector tambahan (mis. pola poller Hikvision/NAS/Redfish telemetry) sebagai *fixture-
     replay adapter* baru mengikuti pola `connectors/redfish/adapter.py`.
   - Dokumentasi pola DLQ 3-topik dan lineage tracking sebagai referensi desain (tanpa data nyata).

### Tahap 2 — Implementasi di `dcim-core-platform`

1. Clone/pastikan working copy lokal `dcim-core-platform` up to date dengan `origin/main`.
2. Buat branch baru sesuai konvensi (mis. `feat/data-ingestion-validation-processor`).
3. Implementasikan perubahan **sekecil dan sekoheren mungkin per PR** (jangan menggabungkan
   banyak concern), mengikuti gaya kode, typing, dan struktur test yang sudah ada.
4. Tambahkan/perbarui fixture sintetis di `fixtures/synthetic/` bila diperlukan — tidak boleh ada
   nilai yang berasal dari data real `DCIM_SRV_DATA_COLLECTION`.
5. Tambahkan/perbarui test di `tests/` untuk perubahan yang dibuat.
6. Jalankan gate verifikasi lokal:
   ```bash
   make phase0-check
   python scripts/check_public_repo_safety.py
   ```
   Semua harus lulus sebelum lanjut. Kegagalan pada public-safety scan adalah **stop condition** —
   jangan commit sebelum ini bersih.
7. Update dokumentasi terkait (README terdekat, ADR baru jika memperkenalkan keputusan arsitektur
   baru, `docs/architecture/` bila relevan) menggunakan nama **Imam Syauqi Achmad** untuk atribusi.

### Tahap 3 — Commit, push, dan PR

```bash
git add <file-yang-relevan>
git commit -m "feat(data-ingestion): <deskripsi ringkas>"
git push origin feat/<scope>
```

Buka Pull Request ke `dcim-core-platform` (branch `main`) dengan deskripsi mencakup:
- Scope dan out-of-scope.
- Issue/ADR terkait (atau catatan bahwa ini murni port arsitektur dari repo implementasi privat,
  tanpa data operasional).
- Command dan hasil verifikasi (`make phase0-check`, public-safety scan).
- **Data-handling declaration eksplisit**: nyatakan bahwa seluruh konten berasal dari pola
  arsitektur/desain, sepenuhnya sintetis, tidak memuat credential/IP/hostname/topologi/log nyata
  dari `DCIM_SRV_DATA_COLLECTION`.
- Known limitations dan gap yang masih tersisa (boleh rujuk balik ke
  `dcim-wiki/comparisons/impl-repo-data-ingestion-alignment.md`).

Jangan merge PR sendiri — status `DEV-APPROVED` hanya saya berikan sebagai owner setelah evidence
lengkap.

### Tahap 4 — Laporan akhir ke saya

Setelah PR dibuka, ringkas ke saya:
- Branch dan nomor PR.
- Daftar file yang diubah/ditambahkan.
- Hasil `make phase0-check` dan public-safety scan.
- Gap dari dokumen alignment yang tercakup oleh PR ini, dan yang masih tersisa untuk PR berikutnya.

---

## HAL YANG TIDAK BOLEH DILAKUKAN

- Jangan `git push` mentah seluruh isi atau sebagian besar `DCIM_SRV_DATA_COLLECTION` ke
  `dcim-core-platform` (mis. lewat `git remote add` + `git push --mirror`, copy folder utuh,
  atau `git subtree`/`git filter-repo` tanpa sanitasi). Itu melanggar `DATA-HANDLING.md` repo
  target dan berisiko membocorkan credential/data operasional saya.
- Jangan commit langsung ke `main` di `dcim-core-platform`.
- Jangan menyelesaikan sendiri item di `docs/governance/OPEN-DECISIONS.md`.
- Jangan mengaktifkan connector nyata (network call, SNMP SET, Redfish write/power/reset/
  firmware) — repo target hanya mengizinkan replay fixture sintetis pada tahap ini.
