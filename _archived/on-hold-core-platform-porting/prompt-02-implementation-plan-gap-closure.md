# Prompt Agent 2 — Implementation Plan: Menutup Gap Arsitektur DCIM Data Ingestion

> **Cara pakai:** Ini prompt **self-contained** untuk sesi chat baru dengan agent baru (tidak
> mengasumsikan agent tahu histori percakapan sebelumnya). Tempel seluruh isi ini sebagai pesan
> pertama. Agent butuh akses lokal ke tiga repo di bawah, `bash`/`git`, dan idealnya `gh` CLI
> dengan auth `Chefinox`.

---

## KONTEKS (baca dulu, jangan asumsikan tahu)

Saya **Imam Syauqi Achmad** (GitHub: `Chefinox`), developer pipeline data collection DCIM
produksi. Tiga repo yang relevan:

1. **`https://github.com/Chefinox/DCIM_SRV_DATA_COLLECTION.git`** — milik saya, implementasi
   aktual pipeline (NiFi ingestion, Kafka 3-node KRaft SSL, Avro + Schema Registry, normalizer,
   enrichment FastAPI+Redis, konsumen ke PostgreSQL/Elasticsearch/TimescaleDB/iTop CMDB, DLQ
   3-topic, Circuit Breaker 3-state, Data Classification Matrix 4-level, HashiCorp Vault).
   History git repo ini sudah dibersihkan dari kredensial (per audit sebelumnya) — **tetap jangan
   pernah menganggap file apa pun di sini otomatis aman untuk disalin ke repo lain**; selalu cek
   ulang isi file sebelum dipakai sebagai referensi porting.
2. **`https://github.com/shuffahaqgzz/dcim-wiki.git`** — milik pihak lain (`shuffahaqgzz`),
   berisi reference design arsitektur DCIM Core Platform. Dokumen kunci:
   `reference-designs/block2-data-ingestion-integration.md` dan
   `comparisons/impl-repo-data-ingestion-alignment.md`.
3. **`https://github.com/shuffahaqgzz/dcim-core-platform.git`** — milik pihak lain
   (`shuffahaqgzz`), repo publik tempat kontribusi akan di-PR-kan. Diatur ketat oleh `AGENTS.md`,
   `DATA-HANDLING.md`, `CONTRIBUTING.md`, `docs/governance/OPEN-DECISIONS.md`, dan ADR di
   `docs/adr/`. Saya kontributor eksternal (bukan owner) — semua perubahan lewat **fork → branch →
   Pull Request**, tidak pernah push langsung ke `main`, dan merge/approve wewenang `shuffahaqgzz`.

**Prinsip metodologi yang wajib diikuti sepanjang tugas ini:**
- **Jangan berasumsi** suatu gap sudah selesai hanya karena nama fitur "terdengar mirip" —
  verifikasi langsung ke kode (`grep`, baca isi file, jalankan test) sebelum menandai status.
- **Gunakan data aktual dari pipeline** (source code, config, hasil `git log`/`grep`) sebagai
  bukti, bukan ringkasan/dokumen turunan yang mungkin sudah usang atau terlalu optimis.
  *(Catatan penting: pernah ditemukan dokumen internal proyek yang mengklaim skor alignment ~97%
  dengan menandai "Validation: ALIGNED" padahal saat dicek langsung ke `normalizer/executor.py`
  dan `scripts/audit_data_quality.py`, tidak ada satu pun logic range-check, regex format
  validation, dedup, atau freshness-check. Jangan ulangi kesalahan ini — verifikasi granular per
  requirement, bukan per label fitur.)*
- Semua konten yang di-porting ke `dcim-core-platform` harus **generik/sintetis** — tidak boleh
  ada credential, IP/hostname/FQDN nyata, nama site/rack/kamera, topologi jaringan, atau
  payload/log nyata dari `DCIM_SRV_DATA_COLLECTION`.
- Atribusi nama di dokumen/ADR/PR: **Imam Syauqi Achmad** (nama lengkap), bukan nickname.

---

## TAHAP 0 — Verifikasi Ulang Baseline Gap (jangan skip meski sudah pernah diaudit)

Sebelum membuat rencana implementasi, verifikasi ulang status tiap gap di bawah langsung ke kode
aktual di `DCIM_SRV_DATA_COLLECTION`. Baseline dari audit terakhir (per 10 Agustus 2026):

| # | Bagian | Skor terakhir | Gap P1/P2 |
|---|---|---:|---|
| 1 | Ingestion & Collectors | 85% | Virtualization/Cloud collector (VMware/AWS/GCP) belum ada; circuit breaker per-connector masih retry-loop lokal |
| 2 | Kafka Broker & Topics | 100% | Topic naming per-source-type vs spec single-topic (Tercakup PR B) |
| 3 | **Validation & Normalizer** | **100%** | Tercakup PR A |
| 4 | Enrichment & CMDB Lookup | 100% | Impact Scoring Engine (criticality × severity) Tercakup PR D |
| 5 | Persistence, Lineage, DLQ & Monitoring | 100% | Data Quality Scorecard 6-dimensi (Tercakup PR D); DLQ & Lineage Architecture (Tercakup PR E) |

Untuk setiap baris di atas: `grep`/baca kode terkait di `DCIM_SRV_DATA_COLLECTION`, konfirmasi
apakah gap ini **masih benar ada** per kondisi kode terkini (implementasi mungkin sudah berubah
sejak audit terakhir). Update tabel ini dengan temuan aktual sebelum lanjut ke Tahap 1. Jika ada
perbedaan dengan baseline di atas, laporkan ke saya dan jelaskan bukti kodenya.

---

## TAHAP 1 — Prioritas & Urutan PR

Urutkan pekerjaan berdasarkan skor terendah dan tingkat risiko/kompleksitas porting, target satu
PR per unit kerja kecil dan coherent:

1. **PR A (P1, wajib duluan) — Validation Processor generik**
   Rancang modul validasi generik untuk `dcim-core-platform`: range check per metric type, format
   validation (regex IP/MAC/UUID), duplicate detection (window-based, algoritma generik — tidak
   perlu Redis spesifik, cukup interface abstrak), freshness/staleness check, dan Prometheus
   counter/histogram untuk data yang ditolak. Ini port **pola/logic**, bukan kode
   `normalizer/executor.py` saya secara verbatim — tulis ulang sebagai implementasi baru yang
   idiomatik untuk struktur `dcim-core-platform` (ikuti pola `connectors/redfish/adapter.py` yang
   sudah ada: synthetic fixture-driven, test-covered).

2. **PR B (P2) — Kafka topic naming & schema versioning doc**
   Dokumentasikan strategi penamaan topic granular per-source-type dan pendekatan schema
   versioning Avro sebagai referensi desain, dengan nama topic **generik** (bukan nama topic
   literal dari pipeline saya).

3. **PR C (P2) — Fixture-replay connector tambahan**
   Tambahkan adapter sintetis untuk pola NAS storage dan CCTV/ISAPI, mengikuti struktur
   `connectors/redfish/` dan `connectors/snmp/` yang sudah ada (README + `__init__.py` +
   `adapter.py`, tanpa kemampuan network/write nyata).

4. **PR D (P2) — Impact Scoring & Data Quality Scorecard**
   Dokumentasikan/implementasikan pola kalkulasi impact score (criticality × severity) dan
   6-dimensi data quality scorecard (Completeness, Timeliness, Accuracy, Consistency, Validity,
   Uniqueness) sebagai referensi generik, mengarah ke ekspor metrik Prometheus.

5. **PR E (P3, opsional/menyusul) — Lineage & DLQ 3-topic pattern doc**
   Dokumentasikan pola `LineageTracker` dan struktur 3-topic DLQ sebagai referensi arsitektur,
   tanpa nama tabel/topic/host literal.

Untuk setiap PR: sebelum mulai menulis kode, tunjukkan dulu ke saya rencana file yang akan
dibuat/diubah dan ringkasan pendekatannya — tunggu konfirmasi sebelum implementasi penuh.

---

## TAHAP 2 — Alur Kerja per-PR (berlaku untuk semua PR A–E)

1. Pastikan fork/clone `dcim-core-platform` up to date dengan `origin/main` (atau
   `upstream/main` jika pakai fork).
2. Baca ulang `AGENTS.md`, `DATA-HANDLING.md`, `docs/governance/OPEN-DECISIONS.md`, dan ADR
   relevan — jangan asumsikan sudah hafal dari sesi sebelumnya.
3. Buat branch: `feat/<scope>`, `docs/<scope>`, atau `adr/<decision>` sesuai konvensi.
4. Implementasi kecil, koheren, satu concern per PR. Tambahkan test di `tests/` untuk setiap
   perubahan kode.
5. Tambahkan/perbarui fixture di `fixtures/synthetic/` bila perlu — nilai harus sintetis murni.
6. Jalankan gate wajib sebelum commit:
   ```bash
   make phase0-check
   python scripts/check_public_repo_safety.py
   ```
   Kegagalan pada public-safety scan = stop condition, jangan lanjut sebelum bersih.
7. Commit (Conventional Commits) → push branch → `gh pr create` dengan deskripsi memuat: scope,
   ADR/issue terkait, hasil verifikasi, **data-handling declaration eksplisit**, known limitations.
8. **Jangan merge sendiri.** Laporkan link PR ke saya dan tunggu review `shuffahaqgzz`.
9. Jangan menyelesaikan item `docs/governance/OPEN-DECISIONS.md` secara sepihak — jika PR
   menyentuh open decision, buat draft ADR dan tandai perlu approval owner.

---

## LAPORAN YANG SAYA HARAPKAN DARI AGENT

Setelah Tahap 0 selesai (sebelum mulai coding PR mana pun), berikan ke saya:
- Tabel gap terverifikasi ulang (Tahap 0) dengan bukti kode konkret per baris.
- Urutan PR final yang diusulkan (boleh menyesuaikan urutan Tahap 1 jika ada temuan baru).

Setelah tiap PR dibuka, berikan ke saya:
- Link PR, branch, daftar file yang diubah.
- Hasil `make phase0-check` dan public-safety scan.
- Bagian gap mana yang tercakup PR ini, dan apa yang masih tersisa untuk PR berikutnya.
