# Prompt untuk Agent: Resolve Blocker Akses NiFi (RBAC/SSO) via Handoff GUI ke Owner

## Konteks

NiFi instance ini menggunakan **RBAC dengan login SSO email kantor** (bukan single-user credential lagi). Agent **tidak punya dan tidak akan pernah diberi** akses login GUI langsung — ini bukan hal yang bisa/boleh diakali dengan reset credential, bypass OIDC, atau escalate token Vault. Owner (Imam Syauqi Achmad) **bisa login ke GUI dan bersedia mengeksekusi langkah manual**, asal instruksinya presisi dari agent.

Baca dulu sebelum mulai:
1. `docs/handoff/2026-08-18-agent-handoff-siem-fix-validation.md` — laporan terakhir, berisi klaim yang masih perlu diverifikasi ulang.
2. `prompt-agent-nifi-access-recovery-and-fix.md` — prompt sebelumnya soal blocker akses.
3. Repo `dcim-wiki` untuk skema RBAC/SSO/Vault yang berlaku.

## Batasan Keras (Do Not)

- **JANGAN mencoba login, reset password, generate token admin, atau bypass RBAC/OIDC dengan cara apapun** — termasuk command CLI (`set-single-user-credentials`), curl langsung ke NiFi API pakai kredensial tebakan, atau modifikasi `login-identity-providers.xml`/`nifi.properties` untuk menonaktifkan SSO. Semua ini sudah dilarang eksplisit di sesi sebelumnya dan tetap berlaku.
- **JANGAN asumsikan kamu bisa "kerja sekitar" RBAC** dengan API token yang kamu temukan sendiri di Vault. Kalau butuh akses API, itu harus diminta resmi ke owner (lihat Tugas 0 di bawah), bukan dicari sendiri diam-diam.
- **JANGAN generate instruksi GUI yang ambigu.** Owner akan mengeksekusi manual — instruksi harus presisi (nama processor persis, urutan klik, nilai konfigurasi persis) supaya tidak ada ruang salah eksekusi di production.
- **JANGAN tandai task manapun "Done"** hanya karena kamu sudah kirim instruksi ke owner — status baru berubah setelah owner konfirmasi sudah dieksekusi DAN kamu verifikasi hasilnya sendiri lewat cara non-GUI (API read-only, log, provenance, dsb — yang mana pun yang masih bisa diakses agent).

## Alur Kerja Wajib: Diagnosis → Instruksi Presisi → Handoff → Verifikasi

Untuk setiap task yang butuh aksi di GUI NiFi, ikuti pola berikut, JANGAN loncat langsung minta owner "klik-klik random":

1. **Diagnosis dulu** pakai apapun akses yang kamu punya tanpa GUI (baca `flow.json`, container filesystem, log, git history config, Vault read-only jika ada) untuk memastikan persis apa yang perlu diubah.
2. **Susun instruksi step-by-step yang bisa dieksekusi tanpa ambiguitas**, mencakup:
   - Nama process group & processor persis (case-sensitive, sesuai yang ada di canvas).
   - Aksi persis (mis. "klik kanan canvas kosong di dalam process group Security SIEM Ingestion → Add Processor → cari 'RouteOnContent'").
   - Nilai konfigurasi persis yang harus diisi (regex, nama relationship, properti lain).
   - Urutan koneksi antar processor yang harus dibuat/diputus.
   - Langkah verifikasi visual yang owner bisa cek sendiri di GUI (mis. "pastikan processor tidak menunjukkan ikon warning segitiga sebelum di-start").
3. **Kirim instruksi ini ke owner dan STOP** — tunggu konfirmasi eksplisit dari owner bahwa langkah sudah dieksekusi, sebelum lanjut ke task berikutnya yang bergantung pada perubahan ini.
4. **Setelah owner konfirmasi**, verifikasi hasilnya sendiri via jalur yang masih bisa diakses agent tanpa GUI (baca ulang `flow.json`, cek metrik/log/provenance jika ada akses read-only, atau minta owner screenshot state terbaru kalau read-only API juga tidak tersedia).

## Tugas 0 — Konfirmasi Level Akses yang Tersedia untuk Agent

Sebelum menyusun instruksi apapun, pastikan dulu apa yang **benar-benar** bisa kamu akses tanpa GUI:

1. Cek apakah ada NiFi REST API read-only token/AppRole di Vault yang memang diperuntukkan untuk automation/monitoring (bukan admin) — kalau ada, ini bisa dipakai untuk baca status flow/metrik tanpa perlu owner screenshot manual tiap kali.
2. Kalau tidak ada token read-only sama sekali, laporkan eksplisit ke owner: verifikasi hasil perubahan GUI ke depannya akan bergantung pada owner mengirim screenshot/export `flow.json` manual setelah tiap perubahan — minta owner konfirmasi ini acceptable sebagai alur kerja.
3. Jangan lanjut ke tugas lain sebelum ini jelas.

## Tugas 1 — Instruksi GUI untuk Fix RouteOnContent (dari Task 2 sebelumnya, masih Blocked)

1. Susun instruksi presisi untuk owner menambahkan `RouteOnContent` di process group `Security SIEM Ingestion`, posisi di antara `ListenSyslog - Wazuh`/`ListenSyslog - Wazuh UDP` dan `JoltTransformJSON`:
   - Regex condition: `^\s*\{.*` dengan relationship name `is_json`.
   - Relationship `is_json` → connect ke `JoltTransformJSON` (jalur lama).
   - Relationship `unmatched` → connect langsung ke `PublishKafka - SIEM Alerts`.
   - **Sarankan owner uji dulu di canvas/process group duplikat (staging)** sebelum apply ke flow production yang sedang live — beri instruksi cara duplikasi process group dengan aman kalau NiFi versi ini mendukung.
2. Kirim instruksi ini ke owner sebagai draft langkah-langkah bernomor, minta owner review dan konfirmasi paham sebelum eksekusi (bukan langsung dieksekusi tanpa review, karena ini ubah flow production).
3. Setelah owner konfirmasi sudah dieksekusi, minta owner start processor baru + pantau minimal 15-30 menit, dan kirimkan screenshot metrik In/Out/Tasks tiap processor sebagai bukti (atau kamu ambil sendiri kalau read-only API tersedia dari Tugas 0).

## Tugas 2 — Cross-check Ulang Klaim Laporan `2026-08-18` yang Masih Bisa Diverifikasi Tanpa GUI

Sambil menunggu owner mengeksekusi Tugas 1, kerjakan verifikasi yang tidak butuh GUI:

1. **Klaim Task 3 (Kafka retry)** — cek apakah retry/backoff sudah benar-benar ditambahkan di `docker-compose.yml`/config `PublishKafka`, atau baru rekomendasi di laporan. Kalau belum diimplementasi, implementasikan (ini tidak butuh akses GUI NiFi, cukup akses filesystem/docker).
2. **Klaim Task 4 (load test ~240ms)** — minta/ambil diff `kafka_locustfile.py`, jalankan ulang test, ambil raw output, verifikasi konsistensi.
3. **Klaim Task 5 (nama repo "DCIM Metrics")** — konfirmasi ke owner repo tujuan commit yang benar; kalau salah repo, minta owner klarifikasi atau pindahkan.
4. **Vault root token exposure** (`hvs.jcix...`) — tanyakan eksplisit ke owner apakah sudah di-revoke/rotate. Ini tidak butuh GUI NiFi, tapi tetap prioritas keamanan tinggi yang belum boleh diabaikan.

## Format Laporan Akhir

Buat laporan baru: `docs/handoff/YYYY-MM-DD-agent-handoff-gui-dependent-tasks.md`, dengan struktur:

1. **Level Akses Agent Saat Ini** — hasil Tugas 0, termasuk apakah ada read-only API token.
2. **Instruksi GUI yang Dikirim ke Owner** — salin persis instruksi yang diberikan (untuk audit trail), tandai status: *Menunggu Eksekusi Owner / Dieksekusi & Terverifikasi / Dieksekusi tapi Hasil Tidak Sesuai*.
3. **Hasil Verifikasi Non-GUI** (Tugas 2) — status Task 3/4/5 dengan bukti konkret.
4. **Blocker yang Masih Terbuka** — apa saja yang masih menunggu tindakan owner, urutan prioritas.
5. **Rekomendasi untuk Owner** — termasuk apakah proses handoff GUI seperti ini perlu jadi SOP permanen selama RBAC/SSO aktif dan agent tidak punya akses login.
