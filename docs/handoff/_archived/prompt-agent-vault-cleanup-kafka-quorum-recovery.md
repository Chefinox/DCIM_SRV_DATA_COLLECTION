# Prompt untuk Agent: Cleanup Token Vault Bocor, Verifikasi Bukti Klaim Tersisa, dan Pemulihan Kafka KRaft Quorum

## Konteks

Laporan `docs/handoff/2026-08-19-agent-handoff-credential-remediation-and-kafka-recovery.md` mengandung **nilai lengkap Vault root token** (token root yang tercatat di `init.txt`) tertulis plaintext, dan laporan ini sudah ter-commit ke repo `DCIM_SRV_DATA_COLLECTION`. Ini pelanggaran berulang (kali ketiga) dari aturan "jangan pernah tulis nilai credential asli di file manapun yang di-commit" — sebelumnya sudah terjadi pada Vault token (laporan lama) dan password Elasticsearch (laporan sebelum ini).

Selain itu, dua klaim di laporan tersebut ("DLQ Writer — Confirmed Fixed" dan "Mock API Adapters — Healthy") ditulis tanpa bukti eksekusi nyata, dan Kafka cluster masih dalam status zombie/crash-loop yang butuh pemulihan manual.

## Batasan Keras (Do Not) — WAJIB DIBACA SEBELUM MENULIS FILE/LAPORAN APAPUN

- **JANGAN PERNAH menulis nilai credential asli apapun (token, password, API key, secret) secara utuh maupun terpotong sebagian yang masih bisa dikenali di file manapun yang akan di-commit** — ini sudah terjadi 3 kali (Vault token lama, ES password, Vault token lagi di laporan terbaru). Kalau perlu merujuk ke suatu secret, gunakan deskripsi netral seperti "token Vault yang tercatat di `init.txt`" tanpa mengutip nilainya sama sekali, bukan placeholder yang menyertakan sebagian nilai asli.
- **JANGAN rotate/ganti nilai password Elasticsearch maupun Vault root token** — tetap sesuai keputusan owner sebelumnya, kecuali ada instruksi eksplisit baru.
- **JANGAN tandai task manapun "Confirmed Fixed"/"Healthy"/"Done" tanpa bukti eksekusi nyata** (output test, log sebelum-sesudah, metrik). Deskripsi perubahan kode saja bukan bukti bahwa perbaikan itu benar-benar bekerja.
- **JANGAN restart/rebuild Kafka node secara blind** — ikuti prosedur pemulihan manual yang hati-hati di Tugas 3, dengan backup yang sudah ada sebagai starting point.
- **JANGAN eksekusi apapun di NiFi GUI sendiri** — RouteOnContent tetap menunggu eksekusi owner, tidak berubah.

## Tugas 1 (PRIORITAS TERTINGGI) — Cleanup Token Vault dari Laporan yang Baru Di-commit

1. Redact nilai token Vault (token root yang tercatat di `init.txt`) di file `docs/handoff/2026-08-19-agent-handoff-credential-remediation-and-kafka-recovery.md` menjadi referensi netral tanpa nilai (mis. "token root di `init.txt`"), commit perubahan ini.
2. Bersihkan riwayat git dari nilai token tersebut menggunakan `git filter-repo --replace-text` (pola sama seperti instruksi ES password sebelumnya), cakup **seluruh file** yang pernah menyebut nilai token ini secara utuh maupun sebagian, bukan cuma laporan terbaru.
3. Sertakan command yang **owner** perlu eksekusi manual di lokal (sama seperti pola sebelumnya untuk password ES) — jangan agent yang push hasil `filter-repo` sendiri.
4. **Klarifikasi status token**: laporan menyebut token ini sekarang mengembalikan 403 Permission Denied. Cek ke Vault admin API/log (kalau ada akses) apakah token ini memang sudah di-revoke oleh pihak lain, atau memang tidak pernah valid sejak awal. Laporkan temuan ini secara faktual — jangan berasumsi.

## Tugas 2 — Verifikasi Bukti Nyata untuk Klaim yang Masih Berupa Deskripsi Kode

### 2a. DLQ Writer Fix
1. Konfirmasi arsitektur threading di `mikrotik_poller.py`, `redfish_poller.py`, `nas_poller.py`, `cctv_poller.py` — apakah ada bagian yang jalan di thread/proses terpisah (async, `threading`, `multiprocessing`, subprocess lain). `sys.excepthook` **hanya menangkap exception di main thread**; kalau ada exception di thread lain, perbaikan ini tidak akan menangkapnya dan traceback plaintext masih bisa bocor ke NiFi.
2. Kalau ditemukan bagian threaded/async, tambahkan penanganan setara (mis. `threading.excepthook` untuk Python 3.8+, atau try-except eksplisit di titik masuk thread).
3. **Uji nyata**: picu exception secara sengaja di tiap script (baik di main thread maupun thread lain kalau ada), konfirmasi `DLQ_Delivery_Writer` menerima dan berhasil publish JSON error tanpa crash. Sertakan bukti log/metrik sebelum-sesudah.

### 2b. Mock API Adapters (ST-391/392)
1. Ambil bukti konkret proses masih hidup dan sehat: uptime, PID, log terbaru tanpa error, dan hasil satu kali panggilan test ke masing-masing mock endpoint (`proxmox_fixture_adapter.py`, `itsm_fixture_api.py`) yang membuktikan response masih sesuai skema yang diharapkan NiFi poller.
2. Kalau salah satu ternyata tidak merespons dengan benar, laporkan sebagai Degraded, bukan Healthy.

## Tugas 3 — Pemulihan Manual Kafka KRaft Quorum

1. Mulai dari backup yang sudah ada (`/tmp/kafka1_data.tar.gz` dsb.) — jangan buat backup ulang kalau yang lama masih valid, cukup verifikasi integritasnya dulu.
2. Investigasi `meta.properties` di tiap node (`kafka1`, `kafka2`, `kafka3`) — bandingkan `cluster.id` dan `node.id` di tiap node untuk memastikan tidak ada mismatch yang menyebabkan split-brain.
3. Kalau ditemukan corrupt/mismatch metadata yang tidak bisa direkonsiliasi otomatis, siapkan **instruksi presisi untuk owner** (bukan eksekusi sendiri kalau ini masuk kategori berisiko tinggi/ireversibel) tentang langkah rebuild quorum: node mana yang jadi source of truth, urutan reformat/restart tiap node, dan cara verifikasi quorum terbentuk kembali (`kafka-metadata-quorum.sh describe --status`).
4. Kalau setelah investigasi ternyata ada langkah yang aman untuk agent eksekusi sendiri (mis. restart satu node non-destruktif untuk re-test), lakukan bertahap satu node dalam satu waktu, cek status quorum di antara tiap langkah — jangan restart semua node bersamaan.
5. Setelah quorum pulih (baik oleh agent atau setelah owner eksekusi instruksi manual), jalankan `kafka-consumer-groups.sh --list` di semua broker, konfirmasi tidak ada timeout, dan cek consumer lag di semua topic.
6. **Baru setelah Kafka dikonfirmasi sehat**, jalankan ulang `kafka_locustfile.py` (2x run terpisah) untuk melengkapi verifikasi ST-394 yang sebelumnya "Cannot Verify Now" — sertakan raw output.

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-vault-cleanup-and-kafka-quorum-recovery.md`:

1. **Status Cleanup Token Vault** — konfirmasi redaksi di file terbaru + instruksi `filter-repo` untuk owner (sertakan command lengkap, tanpa nilai token asli tertulis di laporan ini juga).
2. **Klarifikasi Status Token** — hasil temuan Tugas 1.4.
3. **Bukti DLQ Writer Fix** — termasuk hasil audit threading dan hasil uji pemicu error nyata.
4. **Bukti Mock API Health** — uptime/log/test response konkret.
5. **Status Pemulihan Kafka Quorum** — root cause final, langkah yang diambil/masih menunggu owner, bukti quorum sehat (atau instruksi presisi kalau masih perlu eksekusi manual).
6. **Hasil Load Test ST-394** (kalau Kafka sudah sehat) — raw output dari 2x run.
7. **Kesimpulan Kesehatan Pipeline** — status jujur berdasarkan kondisi terkini, jangan dipaksakan "Sehat" kalau masih ada bagian Degraded/Blocked.
