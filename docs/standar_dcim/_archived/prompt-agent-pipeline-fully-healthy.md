# Prompt untuk Agent: Full End-to-End Health Check Pipeline — Bebas Warning di NiFi/Kafka/Service Terkait

## Konteks

Sebelum task ini sudah ada rangkaian investigasi & fix parsial pada pipeline data ingestion: audit root cause Jolt/SIEM, fix `RouteOnContent` (statusnya bisa jadi masih "Menunggu Eksekusi Owner" atau sudah dieksekusi — cek dulu), klaim fix Kafka retry, dan klaim fix load test latency. Tujuan task ini: pastikan **seluruh pipeline** benar-benar sehat — tidak ada warning/error aktif di NiFi (bulletin board, invalid processor, backpressure), Kafka (broker log, consumer lag, transaction error), maupun service pendukung lain (Elasticsearch, DLQ, Mock API adapters).

Baca dulu sebelum mulai:
1. `docs/handoff/2026-08-18-agent-handoff-siem-fix-validation.md`
2. `docs/handoff/2026-08-18-agent-handoff-gui-dependent-tasks.md`
3. Laporan-laporan handoff terbaru lainnya di `docs/handoff/`

## Batasan Keras (Do Not)

- **JANGAN klaim status pipeline "sehat"/"Done" pada task manapun tanpa bukti mentah** (metrik, log, provenance, output test). Pola laporan sebelumnya sering menyembunyikan blocker di tengah poin lain yang kelihatan sukses — jangan ulangi ini.
- **JANGAN eksekusi apapun langsung di NiFi GUI sendiri.** Kalau ada langkah yang butuh akses GUI (RBAC/SSO) dan belum dieksekusi owner, laporkan status blocked-nya secara eksplisit, jangan coba workaround akses.
- **JANGAN ubah status Mock API (ST-391/ST-392) menjadi "Real/Integrated"** — tetap Mock/Fixture, cukup pastikan simulasinya berjalan sehat.
- **JANGAN sentuh/ubah apapun terkait kredensial atau Vault token** — di luar scope task ini.

## Tugas 1 — Audit Warning/Error Aktif di Seluruh NiFi Canvas (Bukan Cuma SIEM)

1. Cek **Bulletin Board** NiFi secara global (bukan cuma di satu process group) untuk 24 jam terakhir — kumpulkan semua bulletin ERROR/WARN yang masih aktif, per process group.
2. Cek apakah ada processor berstatus **Invalid** (ikon warning segitiga) di canvas manapun — daftar semua beserta process group-nya.
3. Cek apakah ada **connection dengan queue menumpuk / backpressure** di process group manapun (bukan cuma Security SIEM Ingestion) — ini indikasi bottleneck atau processor downstream yang stuck.
4. Untuk tiap temuan di atas, identifikasi root cause dan benerin (kecuali yang butuh akses GUI — untuk itu, siapkan instruksi presisi seperti pola sebelumnya dan kirim ke owner, lalu tandai Blocked sambil menunggu).

## Tugas 2 — Status Fix Security SIEM Ingestion (RouteOnContent)

1. Konfirmasi apakah fix `RouteOnContent` sudah dieksekusi owner di GUI. Kalau belum, tandai eksplisit **Blocked — menunggu eksekusi owner**, jangan asumsikan sudah selesai.
2. Kalau sudah dieksekusi: ambil metrik In/Out/Tasks tiap processor (`ListenSyslog` x2, `RouteOnContent`, `JoltTransformJSON`, `PublishKafka - SIEM Alerts`) dari window 15-30 menit terakhir. Buktikan flow JSON dan plain-text sama-sama sampai ke tujuan tanpa drop diam-diam (cek juga tidak ada bulletin baru terkait Jolt).

## Tugas 3 — Kafka Layer: Broker, Transaction, dan Consumer Health

1. Cek log seluruh broker Kafka (`10.70.0.56:9092,9093,9094`) untuk error/warning aktif (leader election issues, under-replicated partitions, transaction timeout, dsb).
2. Konfirmasi implementasi retry/backoff NiFi→Kafka (dari task sebelumnya) benar-benar ada di `docker-compose.yml`/config `PublishKafka` — tunjukkan diff-nya kalau belum pernah diverifikasi.
3. Restart penuh stack (`docker-compose down && up`), pastikan **tidak ada** `TimeoutException` atau error startup lain muncul di log NiFi maupun Kafka setelahnya. Sertakan cuplikan log sebagai bukti.
4. Cek consumer lag di semua topic (`dcim.events.raw`, `dcim.raw.virtualization`, topic ITSM, `dcim.siem.alerts`) — pastikan tidak ada lag yang terus bertambah (indikasi consumer downstream stuck/mati).

## Tugas 4 — Validation Engine & DLQ

1. Kirim payload cacat (invalid schema) secara sengaja ke tiap jalur ingestion (Virtualization, ITSM, SIEM), konfirmasi masuk ke DLQ tanpa merusak pipeline utama atau memicu error di processor lain.
2. Sertakan bukti: jumlah pesan di DLQ per jalur, log validasi terkait.

## Tugas 5 — Mock API Adapters (ST-391 & ST-392) Tetap Sehat

1. Cek `proxmox_fixture_adapter.py` dan `itsm_fixture_api.py` masih berjalan tanpa error, poller (`virtualization_poller_nifi.py`, `servicenow.py`, `jira.py`) berhasil publish tanpa bulletin error di NiFi.
2. Kalau ada yang crash/stuck, restart dan pastikan stabil, sertakan bukti log.

## Tugas 6 — Load & Latency Ulang (Final Check)

1. Jalankan ulang `kafka_locustfile.py` (versi dengan `flush()`), minimal 2 kali run terpisah.
2. Laporkan p99 latency **raw output**, throughput EPS, dibandingkan target (430 EPS, p99 < 1s). Jangan laporkan angka tunggal tanpa raw log pendukung.

## Tugas 7 — Downstream: Elasticsearch/DB

1. Konfirmasi data yang lolos validasi dari semua jalur ingestion benar-benar sampai dan searchable di Elasticsearch/DB tujuan akhir — bukan cuma berhenti di topic Kafka. Sertakan query/hasil cek langsung.

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-pipeline-fully-healthy-check.md`:

1. **Ringkasan Warning/Error Aktif Sebelum & Sesudah Perbaikan** — daftar temuan Tugas 1, status masing-masing (Fixed/Blocked).
2. **Tabel Verdict per Komponen (Tugas 2–7)** — kolom: Komponen | Status (Healthy/Degraded/Blocked) | Bukti | Catatan.
3. **Blocker Tersisa** — kalau ada yang masih butuh eksekusi GUI owner, jelaskan detail instruksinya di sini (jangan ditinggal ambigu).
4. **Kesimpulan Kesehatan Pipeline Keseluruhan** — hanya boleh ditulis "Sehat / Bebas Warning" kalau **semua** komponen Tugas 1-7 terverifikasi Healthy dengan bukti, bukan sebagian besar.
