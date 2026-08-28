# Prompt untuk Agent: Investigasi & Perbaikan Pipeline Security SIEM Ingestion + Validasi Klaim Handoff Sebelumnya

## Konteks

Kamu melanjutkan pekerjaan dari agent sebelumnya pada project **DCIM_SRV_DATA_COLLECTION** (host: `srv-rnd-dcim`, `10.70.0.56`). Referensi dokumen yang harus kamu baca dulu sebelum mulai:

1. `implementation-plan-v4.7-remaining-gaps.md` — rencana penutupan gap ST-391 s/d ST-394
2. `2026-08-14-agent-handoff-nifi-virtualization-siem.md` — laporan handoff dari agent sebelumnya
3. Repo `DCIM_SRV_DATA_COLLECTION` (punya user, jadi sumber kebenaran implementasi)
4. Repo `dcim-wiki` (referensi desain, **bukan** milik user — hanya acuan, jangan diedit)

**PENTING:** Jangan asumsikan klaim di dokumen handoff sebelumnya sudah benar/selesai hanya karena tertulis "sukses" atau "solved". Beberapa klaim di dalamnya mencurigakan dan harus kamu verifikasi ulang dengan bukti nyata (provenance, bulletin, log, hasil test mentah) sebelum kamu tandai sebagai valid di laporanmu.

## Batasan Keras (Do Not)

- **JANGAN hapus processor `JoltTransformJSON`** di process group `Security SIEM Ingestion`. Owner project secara eksplisit ingin processor lama ini dipertahankan.
- **JANGAN langsung apply perubahan apapun di NiFi UI production** tanpa staging/test dulu. Semua perubahan konfigurasi flow harus diuji di environment terpisah (atau minimal di-disable/backup canvas dulu) sebelum di-enable permanen.
- **JANGAN tandai task/sub-task manapun sebagai "Done" atau "Solved"** hanya berdasarkan laporan naratif dari agent sebelumnya. Setiap klaim penyelesaian harus disertai bukti verifikasi konkret (screenshot metrik, query provenance, output test mentah, dsb) di laporanmu.
- **JANGAN ubah status Mock API (ST-391/ST-392) menjadi "Integrated/Real"** — status tetap Mock/Fixture sampai ada konektivitas nyata ke Proxmox/ServiceNow/Jira.

## Tugas 1 — Audit Kondisi Nyata Process Group "Security SIEM Ingestion"

Kondisi terakhir (screenshot terlampir) menunjukkan anomali: `ListenSyslog - Wazuh` (TCP) dan `ListenSyslog - Wazuh UDP` mencatat ±14.600 tasks dalam 5 menit terakhir, tapi `JoltTransformJSON` dan `PublishKafka - SIEM Alerts` mencatat **0 tasks** di window yang sama, dan semua connection queue menunjukkan 0 antrian (bukan menumpuk).

Lakukan langkah berikut dan laporkan hasilnya secara eksplisit (jangan disimpulkan tanpa bukti):

1. Buka konfigurasi `JoltTransformJSON` → tab **Relationships** — cek apakah relationship `failure` di-**auto-terminate** atau diarahkan ke connection lain (mis. DLQ). Laporkan konfigurasi persis yang ditemukan.
2. Buka **Provenance** untuk processor `JoltTransformJSON`, filter beberapa jam terakhir. Hitung dan laporkan jumlah event per tipe (`ROUTE`, `DROP`, `FAILURE`, dll).
3. Buka **Bulletin Board** dan tangkap semua bulletin/error terkait `JoltTransformJSON` dalam 24 jam terakhir — sertakan pesan error persis, bukan ringkasan.
4. Simpulkan: apakah flowfile plain-text dari Wazuh saat ini **hilang secara diam-diam** (silently dropped) atau tertahan di suatu tempat? Ini harus dijawab dengan bukti dari langkah 1–3, bukan asumsi.

## Tugas 2 — Perbaikan Root Cause (Bukan Sekadar Menutupi Gejala)

Setelah root cause dari Tugas 1 dikonfirmasi:

1. Rancang perubahan flow: tambahkan `RouteOnContent` **sebelum** `JoltTransformJSON`, dengan regex `^\s*\{.*` untuk mendeteksi JSON.
   - Relationship match (`is_json`) → tetap ke `JoltTransformJSON` seperti alur lama.
   - Relationship unmatched (plain-text syslog) → langsung ke `PublishKafka - SIEM Alerts` (topic `dcim.siem.alerts`), bypass Jolt.
2. **Uji dulu** perubahan ini di canvas terpisah / process group duplikat / environment staging dengan sample log plain-text dan sample log JSON, pastikan kedua jalur berfungsi sesuai ekspektasi sebelum diterapkan ke flow production.
3. Setelah diverifikasi aman, terapkan ke production dan pantau selama minimal 15–30 menit — laporkan metrik In/Out/Tasks dari setiap processor di window itu sebagai bukti flow sudah normal kembali (bandingkan dengan kondisi anomali di Tugas 1).
4. Dokumentasikan perubahan ini di repo (commit + update dokumentasi flow) dan di task tracker.

## Tugas 3 — Verifikasi Ulang Klaim "Kafka Transaction Timeout" (Dinyatakan "Sembuh Sendiri")

Handoff sebelumnya menyatakan `PublishKafka` sempat gagal dengan `TimeoutException` saat registrasi transaction ID, dan "sembuh dengan sendirinya" setelah propagasi cluster Kafka selesai. Ini bukan fix nyata — kemungkinan besar race condition saat startup (NiFi connect sebelum Kafka broker/leader election selesai).

1. Cek apakah ada dependency/health-check startup order antara NiFi dan Kafka broker di `docker-compose.yml` saat ini.
2. Jika tidak ada, tambahkan mekanisme retry/backoff eksplisit (baik di level `PublishKafka` processor settings, atau `depends_on` dengan health-check di docker-compose) agar issue ini tidak berulang setiap kali stack di-restart.
3. Uji dengan restart penuh stack (`docker-compose down && up`) dan konfirmasi tidak muncul lagi `TimeoutException` di log NiFi. Laporkan hasil test restart ini.

## Tugas 4 — Verifikasi Klaim Load Test ST-394 (p99 latency 0ms mencurigakan)

Handoff menyatakan hasil load test: throughput >3000 EPS (target 430 EPS) dengan **p99 latency 0ms**. Angka 0ms untuk round-trip nyata via Kafka + NiFi + validation engine sangat tidak masuk akal dan mengindikasikan kemungkinan salah ukur.

1. Buka `kafka_locustfile.py`, periksa definisi metrik latency yang dipakai — apakah mengukur end-to-end (publish → consume/DLQ) atau hanya waktu publish lokal ke buffer.
2. Jalankan ulang load test dan simpan **raw output** (bukan ringkasan) — sertakan di laporan.
3. Jika metode pengukuran memang salah, perbaiki instrumentasinya agar mengukur latency end-to-end yang sebenarnya, lalu jalankan ulang dan laporkan angka p99 yang valid.

## Tugas 5 — Konsistensi Status Mock/Fixture (ST-391, ST-392)

1. Cek task tracker (`IF-DCIM_Project_Internal-FIT041-20260118 - Tasks Tracker (6).tsv`) dan semua dokumentasi terkait (README, wiki internal jika ada) — pastikan status ST-391 dan ST-392 secara eksplisit tertulis sebagai **"Mock/Fixture — pipeline readiness, belum terhubung ke server real"**, bukan "Done" atau "Integrated" tanpa kualifikasi.
2. Jika ada dokumen yang ambigu (bisa dibaca seolah integrasi nyata sudah selesai), perbaiki wording-nya.

## Format Laporan Akhir

Buat laporan handoff baru (`YYYY-MM-DD-agent-handoff-siem-fix-validation.md`) dengan struktur:

1. **Ringkasan Eksekutif** — status tiap tugas (1–5) dengan verdict jelas: *Confirmed Fixed / Still Broken / Needs Further Investigation*, masing-masing disertai bukti (bukan narasi tanpa data).
2. **Bukti per Tugas** — metrik/screenshot/log/output mentah yang mendukung setiap verdict.
3. **Perubahan yang Di-commit** — daftar file yang diubah + link commit/PR.
4. **Known Issues yang Masih Terbuka** — jika ada yang belum bisa diselesaikan, jelaskan kenapa dan apa langkah selanjutnya yang disarankan (bukan diklaim selesai).
5. **Rekomendasi untuk Owner (Imam Syauqi Achmad)** — hal apa saja yang perlu direview manual sebelum dianggap production-ready.
