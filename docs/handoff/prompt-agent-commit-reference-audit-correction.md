# Prompt untuk Agent: Koreksi Referensi Commit Hash di Laporan Konsolidasi Final + Audit Menyeluruh

## Konteks

Laporan konsolidasi final (`docs/handoff/2026-08-20-agent-handoff-final-hardening-and-status-consolidation.md`, commit `a144f9a`) berisi **kesalahan faktual**: hash commit `af6d6b8` yang dirujuk sebagai bukti untuk item #3 (Kafka KRaft Quorum Recovery) dan #4 (Load Test ST-394) **tidak ada di repository** — sudah diverifikasi langsung (`git cat-file -t af6d6b8` gagal, tidak ditemukan di `git log --all`).

Commit yang benar untuk kedua item itu kemungkinan besar adalah `7f7850c` (`docs: add vault cleanup and kafka quorum recovery handoff report`) — tapi **jangan asumsikan ini otomatis benar, verifikasi ulang dari isi laporan aslinya**, karena laporan konsolidasi ini adalah dasar yang akan dipakai owner untuk mengisi task tracker resmi project. Referensi yang salah di sini akan ikut salah di tracker.

## Batasan Keras (Do Not)

- **JANGAN cuma perbaiki 2 referensi yang sudah ketahuan salah** — audit **seluruh** referensi commit hash di tabel konsolidasi (14 item) dan di semua laporan handoff terkait, karena kalau ada 1 kesalahan yang lolos, ada kemungkinan ada kesalahan serupa yang belum ketahuan.
- **JANGAN tulis commit hash dari ingatan/asumsi** — setiap hash yang dicantumkan di laporan wajib diverifikasi dengan `git log`/`git show` langsung terhadap repo saat ini sebelum ditulis.
- **JANGAN ubah status Done/Blocked/Pending yang sudah ada di tabel** kecuali kamu menemukan bukti baru yang mengubahnya — task ini fokus ke akurasi referensi, bukan re-assessment status.
- **JANGAN buat commit baru yang menambah entry tanpa keterkaitan jelas** — task ini murni koreksi referensi di laporan yang sudah ada.

## Tugas 1 — Audit Seluruh Referensi Commit di Laporan Konsolidasi

1. Untuk **setiap** dari 14 item di tabel status final, ambil commit hash yang dicantumkan, lalu verifikasi dengan:
   ```bash
   git cat-file -t <hash>
   git show --stat <hash>
   ```
2. Kalau hash valid, konfirmasi isi commit itu benar-benar relevan dengan item yang diklaim (bukan cuma hash valid tapi isinya tidak nyambung).
3. Kalau hash tidak valid atau tidak relevan, cari commit yang benar dengan `git log --oneline --all -- <path file laporan terkait>` atau `git log --oneline --all --grep="<kata kunci relevan>"`, lalu ganti dengan hash yang benar.
4. Catat semua temuan (baik yang sudah benar maupun yang perlu dikoreksi) di laporan koreksi — supaya ada jejak audit yang jelas.

## Tugas 2 — Audit Referensi Commit di Laporan Handoff Lain (Bukan Cuma yang Terakhir)

1. Lakukan pengecekan yang sama untuk laporan-laporan handoff sebelumnya yang mencantumkan commit hash sebagai bukti (`2026-08-19-agent-handoff-vault-cleanup-and-kafka-quorum-recovery.md`, `2026-08-19-agent-handoff-vault-full-remediation.md`, `2026-08-20-agent-handoff-approle-per-connector-implementation.md`, `2026-08-20-agent-handoff-secrets-token-caching-fix.md`, dan laporan lain yang menyebut commit hash).
2. Kalau ditemukan hash salah di laporan-laporan lama ini juga, perbaiki juga — jangan cuma di laporan konsolidasi terakhir.

## Tugas 3 — Verifikasi Kondisi Repo Saat Ini Sesuai Kenyataan (Bukan Cuma Referensi Commit)

Owner butuh kepastian bahwa **kondisi repo `origin/main` saat ini benar-benar mencerminkan seluruh pekerjaan yang sudah dilaporkan**, sebelum dipakai mengisi report harian. Lakukan sanity check langsung terhadap state repo, bukan cuma commit log:

1. `git status` — pastikan working tree bersih, tidak ada perubahan lokal yang belum ter-commit dan tercecer.
2. Konfirmasi file-file kunci berikut benar-benar ada dan isinya sesuai klaim laporan terakhir:
   - `src/utils/secrets.py` — cek fungsi `_cache_dir()` benar-benar punya `chmod(0o700)` dan `_store_cached_token()` punya `chmod(0o600)`.
   - `vault/policies/*.hcl` — 4 file ada, isinya cuma path+capability, tidak ada secret.
   - `.gitignore` — mencakup `vault/config/init.txt`, `role_id_*`, `secret_id_*`, `vault/config/cache/`.
3. Konfirmasi tidak ada credential plaintext tersisa di working tree saat ini (bukan cuma di history) — `grep -r` untuk pola token/password yang pernah bocor sebelumnya di seluruh file ter-track.
4. Laporkan hasil `git log --oneline -20` dari `origin/main` terbaru sebagai bukti final state yang bisa langsung dicocokkan owner.

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-commit-reference-audit-and-correction.md`:

1. **Tabel Audit Referensi Commit** — kolom: Item | Hash Lama (Klaim) | Valid? | Hash Benar (Kalau Beda) | Catatan.
2. **Laporan yang Dikoreksi** — daftar file laporan mana saja yang isinya diperbaiki (kalau ada selain laporan konsolidasi terakhir).
3. **Bukti Sanity Check Repo Saat Ini** (Tugas 3) — hasil tiap pengecekan, termasuk `git log --oneline -20` terbaru.
4. **Konfirmasi Akhir**: satu kalimat tegas — apakah tabel status final di laporan konsolidasi (`2026-08-20-agent-handoff-final-hardening-and-status-consolidation.md`) **setelah koreksi ini** sudah 100% akurat dan siap dipakai owner untuk mengisi task tracker, atau masih ada yang perlu diverifikasi manual oleh owner.
