# Prompt untuk Agent: Remediasi Kebocoran Credential, Diagnosis Kafka Quorum, Fix DLQ Writer, dan Verifikasi Ulang Klaim Tersisa

## Konteks

Laporan `docs/handoff/2026-08-18-agent-handoff-pipeline-fully-healthy-check.md` sudah bagus dari sisi kejujuran (tidak ada klaim sehat palsu), tapi menghasilkan **temuan kritis baru**: password Elasticsearch asli (`ES_PASSWORD_REDACTED`) tertulis plaintext di dalam laporan itu sendiri dan **sudah ter-commit ke repo `DCIM_SRV_DATA_COLLECTION`**.

**Keputusan owner:** password ini **tidak akan dirotasi**. Fokus perbaikan adalah: (1) hentikan penyimpanan plaintext di config/dokumen, (2) migrasikan pengambilan credential ini ke HashiCorp Vault sesuai skema yang berlaku di `dcim-wiki`, (3) bersihkan nilai plaintext yang sudah tercantum dari commit/history lokal repo.

Selain itu masih ada 3 masalah teknis aktif yang perlu ditangani/didiagnosis:
1. Processor `DLQ_Delivery_Writer` (id `ca7d4715-019d-1000-58fd-c8ce62df081f`) gagal publish ke Kafka karena payload error message bukan JSON valid.
2. Kafka cluster menunjukkan `NotControllerException` dan admin client timeout — indikasi masalah KRaft quorum, bukan sekadar race condition startup biasa.
3. Klaim Tugas 5 (Mock API "Healthy") dan Tugas 6 (Load test "Confirmed Fixed") di laporan sebelumnya tidak disertai bukti baru — perlu diverifikasi ulang dengan bukti aktual, bukan carry-forward dari klaim lama.

## Batasan Keras (Do Not) — WAJIB DIBACA SEBELUM MENULIS FILE/LAPORAN APAPUN

- **JANGAN PERNAH menulis nilai credential asli (password, token, API key, secret apapun) di file manapun yang akan di-commit ke git** — termasuk di dalam laporan handoff, commit message, atau command yang kamu tempel sebagai contoh di dokumentasi. Ini pelanggaran yang sudah terjadi dua kali (Vault token, lalu ES password) dan tidak boleh terjadi lagi.
  - Kalau perlu menunjukkan command yang mengandung secret, gunakan placeholder eksplisit, contoh: `password = "<ES_PASSWORD_FROM_ENV>"`, dan instruksikan agar nilai sebenarnya diambil langsung dari file `.env`/Vault saat eksekusi, bukan ditulis ulang di dokumentasi.
- **JANGAN rotate/ganti nilai password Elasticsearch yang bocor** — ini keputusan final owner. Fokus perbaikan hanya pada cara penyimpanan (plaintext → Vault) dan pembersihan jejak commit, bukan mengganti nilai credential-nya.
- **JANGAN restart Kafka cluster secara blind** sebelum diagnosis root cause quorum selesai dan volume data di-backup. `NotControllerException` bisa berarti ada masalah metadata log yang, kalau di-restart paksa tanpa diagnosis, berisiko memperparah atau menyebabkan data loss.
- **JANGAN tandai task manapun "Done"/"Healthy"/"Confirmed"** tanpa bukti baru dari eksekusi saat ini — klaim yang di-carry-forward dari laporan lama tanpa verifikasi ulang tidak dihitung sebagai bukti valid.
- **JANGAN eksekusi apapun di NiFi GUI sendiri** — RouteOnContent tetap menunggu eksekusi owner, statusnya tidak berubah di task ini.

## Tugas 1 (PRIORITAS TERTINGGI) — Migrasi Credential ES ke Vault (Tanpa Rotasi) + Cleanup Commit

1. **Baca skema HashiCorp Vault untuk credential service** di `dcim-wiki` — identifikasi path/struktur secret yang seharusnya dipakai untuk credential Elasticsearch (samakan pola dengan skema yang sudah ada, mis. `secret/dcim/...`).
2. **Buat/pastikan entry Vault untuk password Elasticsearch ini** (nilai yang sudah ada, `ES_PASSWORD_REDACTED`, TIDAK diganti — cukup dipindahkan ke Vault sebagai satu-satunya sumber kebenaran).
3. **Ubah `telegraf-consumer.conf`** agar tidak lagi menyimpan password plaintext — gunakan mekanisme yang didukung Telegraf untuk ambil secret dari Vault saat runtime (mis. env var yang di-inject dari Vault agent/sidecar, atau template config, sesuai konvensi yang dipakai komponen lain di project ini). Kalau Telegraf versi yang dipakai tidak mendukung Vault langsung, gunakan pendekatan yang konsisten dengan pola existing di repo (mis. script wrapper yang fetch dari Vault lalu render config sebelum container start).
4. **Bersihkan riwayat git** dari file yang mengandung nilai password plaintext ini (`docs/handoff/2026-08-18-agent-handoff-pipeline-fully-healthy-check.md` dan file config manapun yang ikut ter-commit) menggunakan `git filter-repo` atau BFG Repo-Cleaner — bukan sekadar edit versi terbaru, karena history lama tetap menyimpan nilai aslinya.
5. Setelah dibersihkan, commit ulang versi laporan yang sama dengan password di-redact jadi placeholder (`<ES_PASSWORD_FROM_VAULT>`).
6. Restart `dcim-telegraf-consumer` dengan config baru (ambil dari Vault, nilai password tetap sama seperti sebelumnya), konfirmasi koneksi ke Elasticsearch tetap sukses (tidak ada 401 Unauthorized) — sertakan bukti log.

## Tugas 2 — Diagnosis Aman Kafka KRaft Quorum (Sebelum Restart)

1. **Backup volume data Kafka** (`kafka1`, `kafka2`, `kafka3` data directories) sebelum melakukan tindakan apapun yang bisa mengubah state cluster.
2. Ambil dan analisis log lengkap tiap node KRaft controller — cari root cause `NotControllerException`: apakah karena metadata log corrupt, network partition antar node, clock skew, atau config quorum yang salah (`controller.quorum.voters` dsb).
3. Kalau root cause sudah teridentifikasi dan solusinya memang butuh restart, lakukan dengan urutan yang aman (mis. restart satu node dulu, cek quorum terbentuk, baru lanjut node berikutnya — bukan `down && up` semua sekaligus).
4. Setelah cluster pulih, jalankan ulang `kafka-consumer-groups.sh --list`/`--describe` untuk semua consumer group, konfirmasi tidak ada lagi timeout, dan cek consumer lag di semua topic (`dcim.events.raw`, `dcim.raw.virtualization`, topic ITSM, `dcim.siem.alerts`).
5. Sertakan log sebelum dan sesudah perbaikan sebagai bukti.

## Tugas 3 — Perbaikan `DLQ_Delivery_Writer`

1. Investigasi processor `DLQ_Delivery_Writer` (id `ca7d4715-019d-1000-58fd-c8ce62df081f`) — cari tahu persis payload apa yang membuat `PublishKafkaRecord` gagal (`JsonParseException: Unrecognized token 'File'`). Kemungkinan besar ini traceback/error message Python mentah yang tidak di-escape jadi string JSON valid sebelum dikirim.
2. Perbaiki source penulis payload DLQ ini (kemungkinan di script Python poller/connector) agar error message selalu di-serialize dengan benar sebagai JSON (mis. pakai `json.dumps()` pada seluruh payload, termasuk field traceback/error, bukan string mentah yang digabung manual).
3. Uji dengan sengaja memicu error di upstream, konfirmasi `DLQ_Delivery_Writer` berhasil publish payload error tersebut ke Kafka tanpa exception. Sertakan bukti log/metrik.
4. **Catatan penting:** kalau root cause DLQ writer ini ternyata terkait/tumpang tindih dengan masalah Jolt (Tugas terpisah, masih Blocked GUI), pisahkan dengan jelas di laporan mana yang sudah fixable tanpa GUI dan mana yang masih menunggu RouteOnContent.

## Tugas 4 — Verifikasi Ulang Klaim Tersisa dengan Bukti Baru

1. **Mock API Adapters (ST-391/392):** jangan cuma tulis "Healthy" — ambil log/uptime proses `proxmox_fixture_adapter.py`, `itsm_fixture_api.py`, dan poller terkait saat ini, konfirmasi tidak ada error/crash di window terbaru. Sertakan bukti.
2. **Load & Latency Test:** jalankan ulang `kafka_locustfile.py` **sekarang**, minimal 2 kali run terpisah (baru dilakukan setelah Kafka cluster dikonfirmasi sehat dari Tugas 2 — kalau dijalankan saat cluster masih degraded, hasilnya tidak valid). Laporkan p99 latency raw output dan throughput EPS, bandingkan dengan target (430 EPS, p99 < 1s).

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-credential-remediation-and-kafka-recovery.md`:

1. **Status Migrasi Credential ke Vault** — konfirmasi credential ES sudah diambil dari Vault (bukan plaintext di config), git history sudah dibersihkan dari nilai plaintext (sertakan cara verifikasi, mis. `git log -p | grep` hasil kosong untuk nilai tersebut), dan koneksi Telegraf→ES tetap berfungsi dengan nilai password yang sama (tidak dirotasi).
2. **Root Cause & Status Kafka Quorum** — diagnosis lengkap, tindakan yang diambil, bukti cluster sehat kembali.
3. **Status Fix DLQ Writer** — bukti sebelum/sesudah.
4. **Verdict Mock API & Load Test** — dengan bukti baru, bukan carry-forward.
5. **Blocker Tersisa** — termasuk status RouteOnContent (masih menunggu GUI, tidak berubah).
6. **Kesimpulan Kesehatan Pipeline** — status jujur berdasarkan kondisi terkini, boleh masih "Degraded" kalau memang ada bagian belum tuntas — jangan dipaksakan "Sehat".
