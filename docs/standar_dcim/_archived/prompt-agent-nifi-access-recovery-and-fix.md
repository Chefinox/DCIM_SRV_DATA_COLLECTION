# Prompt untuk Agent: Resolve Blocker Akses NiFi, Terapkan Fix Tertunda, dan Verifikasi Ulang Laporan Sebelumnya

## Konteks

Agent sebelumnya (`ag/gemini-pro-agent`) sudah menyelesaikan sebagian dari 5 tugas di `prompt-agent-siem-pipeline-validation.md` dan menulis laporan di `docs/handoff/2026-08-18-agent-handoff-siem-fix-validation.md`. **Sebelum kamu melanjutkan apapun, baca file laporan itu secara mentah (bukan ringkasan dari siapapun) dan bandingkan isinya dengan temuanmu sendiri di lapangan.**

Status real per tugas (jangan percaya begitu saja, verifikasi ulang setiap poin):

| Tugas | Klaim Status | Kondisi Sebenarnya yang Harus Kamu Konfirmasi |
|---|---|---|
| 1 — Audit Jolt | Selesai, root cause dikonfirmasi (`autoTerminatedRelationships: failure`) | Verifikasi ulang klaim ini valid |
| 2 — Fix RouteOnContent | **BLOCKED — belum diterapkan** | Pipeline SIEM kemungkinan **masih membuang log Wazuh plain-text secara diam-diam sampai sekarang** |
| 3 — Kafka retry/backoff | **Baru didiagnosis, belum diimplementasi & belum ditest** | Race condition restart Kafka-NiFi berpotensi masih ada |
| 4 — Load test latency | Klaim: sudah diperbaiki (`flush()`), hasil ~240ms | Perlu verifikasi raw output, bukan cuma angka akhir |
| 5 — Tracker wording | Klaim: sudah diupdate via `sed` | Perlu cek integritas file TSV tidak rusak |

## Batasan Keras (Do Not)

- **JANGAN coba bypass, reset, atau overwrite kredensial apapun** (NiFi single-user, OIDC/Authentik, atau Vault) tanpa otorisasi eksplisit dari owner (Imam Syauqi Achmad). Sesi sebelumnya sudah pernah menjalankan `set-single-user-credentials` yang menimpa kredensial lama — jangan ulangi pola ini.
- **JANGAN generate password baru sendiri atau hardcode credential di command line.** Semua kredensial harus berasal dari HashiCorp Vault sesuai ketentuan `dcim-wiki`.
- **JANGAN apply perubahan flow (`RouteOnContent`) di production tanpa staging test dulu**, dan jangan lanjutkan Task 2 sama sekali sampai Task 0 (akses) selesai dan dikonfirmasi owner.
- **JANGAN tandai task apapun sebagai "Done"** hanya berdasarkan laporan naratif dari agent sebelumnya — semua klaim wajib diverifikasi ulang dengan bukti langsung (log, diff commit, output mentah).

## Tugas 0 (PRIORITAS TERTINGGI) — Diagnosis & Pemulihan Akses NiFi

Ini blocker untuk semua tugas lain. Sebelum menyentuh apapun terkait Task 2/3:

1. **Cek status login NiFi UI saat ini secara langsung** — coba akses via jalur normal (SSO Authentik). Laporkan: apakah owner/engineer masih bisa login dengan cara yang biasa dipakai sebelumnya?
2. Baca `nifi.properties` dan `login-identity-providers.xml` di container `dcim-nifi` — bandingkan state SEBELUM sesi `set-single-user-credentials` (kalau ada backup/git history config) dengan state SEKARANG. Identifikasi persis apa yang berubah.
3. Cek Vault: apakah ada secret path resmi untuk kredensial admin NiFi sesuai skema di `dcim-wiki`? Apakah token yang tersedia untuk agent (AppRole `secret/dcim/jwt_verifier` atau lainnya) memang tidak punya privilege admin (klaim dari laporan sebelumnya), atau ada path lain yang belum dicek?
4. **JANGAN mencoba memperbaiki sendiri** kalau ternyata akses admin memang benar-benar terkunci — laporkan temuan lengkap ke owner dan tunggu instruksi eksplisit (misal: owner perlu buat ulang admin token via Vault UI/CLI secara manual, di luar wewenang agent).
5. **Vault token exposure**: laporan sebelumnya menampilkan sebagian nilai root token (`hvs.jcix...`) di dalam teks laporan. Konfirmasi ke owner apakah token ini sudah di-revoke/rotate. Jika belum, ini prioritas keamanan segera — jangan tunda ke akhir laporan.

## Tugas 1 — Verifikasi Ulang Root Cause Jolt (Recheck, bukan re-investigate dari nol)

1. Buka `flow.json` sendiri, cross-check klaim `autoTerminatedRelationships: ["failure"]` pada processor `JoltTransformJSON` — pastikan memang benar dan bukan salah baca.
2. Cross-check bukti `JsonParseException` di log NiFi — ambil cuplikan log asli, sertakan di laporanmu (jangan cuma parafrase ulang klaim sebelumnya).

## Tugas 2 — Terapkan Fix RouteOnContent (HANYA setelah Tugas 0 selesai & akses dikonfirmasi aman)

1. Setelah akses NiFi UI/API pulih dengan kredensial yang sah (dari Vault, bukan hardcoded), rancang dan uji perubahan flow di staging/canvas terpisah:
   - `ListenSyslog` → `RouteOnContent` (regex `^\s*\{.*`)
   - Match (`is_json`) → tetap ke `JoltTransformJSON`
   - Unmatched (plain-text) → langsung ke `PublishKafka - SIEM Alerts` (topic `dcim.siem.alerts`)
2. Uji dengan sample log JSON dan plain-text, pastikan kedua jalur berfungsi.
3. Setelah diverifikasi aman, terapkan ke production. Pantau minimal 15–30 menit, laporkan metrik In/Out/Tasks tiap processor sebagai bukti flow sudah normal.
4. Commit perubahan + update dokumentasi di repo yang **benar** (lihat Tugas 5 soal verifikasi nama repo).

## Tugas 3 — Implementasi Nyata Retry/Backoff Kafka (bukan sekadar rekomendasi)

Diagnosis sebelumnya (tidak ada `depends_on` NiFi→Kafka di `docker-compose.yml`) sudah benar, tapi belum diimplementasi. Lanjutkan:

1. Tambahkan mekanisme retry/backoff eksplisit — baik via `depends_on` dengan health-check di `docker-compose.yml`, dan/atau setting retry di level `PublishKafka` processor.
2. Uji dengan **restart penuh stack** (`docker-compose down && up`), konfirmasi `TimeoutException` tidak muncul lagi di log NiFi.
3. Laporkan hasil test restart ini secara eksplisit dengan cuplikan log, bukan kesimpulan naratif saja.

## Tugas 4 — Audit Klaim Load Test yang Sudah "Diperbaiki"

Klaim: `flush()` ditambahkan, latency terukur naik jadi ~240ms. Verifikasi ulang, jangan langsung percaya:

1. Tunjukkan diff `kafka_locustfile.py` sebelum/sesudah perubahan.
2. Jalankan ulang load test sendiri, ambil **raw output** lengkap (bukan angka ringkasan p99 saja) — sertakan di laporan.
3. Pastikan angka ~240ms konsisten di beberapa kali run, bukan sekali kebetulan.

## Tugas 5 — Verifikasi Integritas Perubahan Tracker & Nama Repo

1. **Klarifikasi nama repo**: laporan sebelumnya menyebut commit masuk ke *"repo DCIM Metrics"*, padahal repo project ini adalah `DCIM_SRV_DATA_COLLECTION`. Cek langsung: commit itu masuk ke repo mana sebenarnya? Kalau ke repo yang salah/tidak dikenal, ini harus dieskalasi ke owner segera — jangan diabaikan sebagai typo tanpa verifikasi.
2. Buka file TSV tracker (`IF-DCIM_Project_Internal-FIT041-20260118 - Tasks Tracker (6).tsv`) setelah edit `sed` — pastikan tidak ada kolom/baris yang rusak/ter-shift akibat delimiter tab yang tidak sengaja termodifikasi.
3. Tunjukkan `git log --oneline` dan diff lengkap untuk semua commit yang diklaim sudah masuk, dari repo yang benar.

## Format Laporan Akhir

Buat laporan baru: `docs/handoff/YYYY-MM-DD-agent-handoff-nifi-access-recovery-and-fix.md`, dengan struktur:

1. **Status Akses NiFi** — bisa login atau tidak, apa root cause-nya, apa langkah pemulihan yang dilakukan/dibutuhkan dari owner.
2. **Status Keamanan Vault Token** — apakah token yang ter-expose sudah di-revoke/rotate.
3. **Verdict per Tugas (0–5)** — *Confirmed Fixed / Still Blocked / Needs Owner Action*, masing-masing dengan bukti konkret (log, diff, output mentah, screenshot metrik).
4. **Koreksi atas Laporan Sebelumnya** — poin mana dari laporan `2026-08-18` yang ternyata tidak akurat atau butuh klarifikasi (termasuk soal nama repo).
5. **Rekomendasi untuk Owner** — apa yang wajib direview/dieksekusi manual oleh Imam Syauqi Achmad sebelum pipeline dianggap production-ready, termasuk urutan prioritas (akses NiFi dan token security harus di atas semua fix teknis lainnya).
