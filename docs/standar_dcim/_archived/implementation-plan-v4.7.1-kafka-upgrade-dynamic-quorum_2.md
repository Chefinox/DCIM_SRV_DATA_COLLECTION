# Implementation Plan: Upgrade Kafka ke 4.1.x (Dynamic Quorum) Sebelum Lanjut Migrasi Multi-Host

> **Versi**: v4.7.1 (Addendum Teknis dari v4.7.0 — Kafka Multi-Host Cluster Migration)
> **Tanggal**: 2026-07-29 (upgrade dicoba & di-rollback), diperbarui 2026-07-30
> **Status**: **DITUNDA — AKAN DILANJUTKAN SETELAH ISU LAG iTOP TUNTAS**. Bukan dibatalkan
> permanen. Rencana upgrade dibuka kembali dengan pendekatan **bertahap** (lihat catatan
> "UPDATE 2026-07-30" di bawah), BUKAN lompat langsung 3.7.0 → 4.1.2 seperti percobaan
> sebelumnya yang gagal.
> **Relasi ke v4.7.0**: Dokumen ini BUKAN proyek baru. Ini adalah revisi/lanjutan teknis dari
> `implementation_plan.md` v4.7.0 (Kafka Multi-Host Cluster Migration), yang eksekusinya
> ditemukan terhambat masalah quorum statis Kafka 3.7.0 di tengah jalan (lihat Latar
> Belakang). Tujuan akhir v4.7.0 (3-node KRaft cluster multi-host) TIDAK BERUBAH — yang
> berubah hanya JALUR TEKNIS untuk mencapainya.
> **Menggantikan**: Pendekatan "Full Coordinated Cutover" (copy-data + restart bersamaan 3
> node, tetap di Kafka 3.7.0) yang diusulkan sebelumnya di sesi ini — DIBATALKAN, digantikan
> pendekatan upgrade + dynamic quorum yang lebih robust untuk operasi jangka panjang.
> **Koreksi versi target**: Draft awal dokumen ini sempat menyebut target `3.9.2`. Setelah
> riset lebih lanjut, dikonfirmasi bahwa **konversi quorum statis→dinamis untuk cluster yang
> SUDAH ADA baru didukung mulai rilis 4.1.x** — Kafka 3.9.0 memperkenalkan dynamic quorum
> tapi HANYA untuk quorum yang di-format baru dari awal, bukan migrasi quorum existing. Target
> versi direvisi ke **4.1.x**.

---

## Latar Belakang & Alasan Perubahan Rencana

Rolling-replacement broker 3 (Tahap 1) menemukan bahwa Kafka 3.7.0 (versi yang sedang berjalan) **tidak mendukung dynamic quorum reconfiguration** — `KAFKA_CONTROLLER_QUORUM_VOTERS` bersifat statis dan harus identik di semua node controller secara bersamaan (KIP-853 baru tersedia mulai Kafka v3.9.0). Percobaan restart satu-node menyebabkan `FATAL fault` pada Raft state machine.

Karena downtime bisa diterima saat ini (implementasi belum full production), diputuskan untuk **upgrade Kafka ke 4.1.x dulu** — versi minimal yang mendukung konversi quorum statis (existing) menjadi dynamic quorum (`add-controller`/`remove-controller`), sebelum melanjutkan migrasi multi-host. Ini menghindari kebutuhan restart 3 node secara bersamaan yang berisiko tinggi, dan menyelesaikan akar masalah secara permanen untuk operasi cluster ke depannya.

**Kenapa 4.1.x, bukan 3.9.2**: Riset awal sempat merekomendasikan `3.9.2` (versi pertama yang membawa KIP-853/dynamic quorum). Namun dikonfirmasi lebih lanjut bahwa **Kafka 3.9.0 hanya mendukung dynamic quorum untuk cluster yang di-format BARU** — TIDAK ADA jalur konversi dari quorum statis existing (seperti cluster kita) ke dynamic di versi 3.9.x. Kemampuan konversi itu baru tersedia mulai **4.1.x**. Karena cluster kita sudah terbentuk sebagai quorum statis sejak awal, `3.9.2` tidak akan menyelesaikan masalah kita — jadi target direvisi ke `4.1.x` meski itu berarti lompat melewati batas ZooKeeper-removal di `4.0`.

**Audit kompatibilitas klien sebelum upgrade (WAJIB)**: Lompatan ke garis `4.x` menghapus RPC/API lama (baseline klien naik ke Kafka 2.1+) dan menghapus API Java yang sudah deprecated sejak ≤3.6. Risiko utama ada di **NiFi** (processor `ConsumeKafka`/`PublishKafka` membawa bundle client library sendiri yang versi-terikat) — WAJIB diverifikasi kompatibel dengan broker 4.x sebelum upgrade dieksekusi. Klien Python (`confluent-kafka`/`librdkafka`) risikonya rendah, tapi tetap perlu dicek versinya. Lihat Fase A.0b.

**Catatan operasional penting**: Setelah binary diupgrade, JANGAN langsung `kafka-features.sh upgrade --release-version 4.1` (finalize). Downgrade metadata TIDAK didukung setelah finalize — wajib ada periode observasi dulu di Fase A.2 sebelum finalize di Fase A.2b.

> **UPDATE 2026-07-29 — Ruang Lingkup Direvisi**: Migrasi multi-host (Fase B & C) **DITUNDA** atas keputusan Xiao — cluster kembali dan TETAP pada arsitektur 3-broker co-located di Node 1 (v4.6.1). Upgrade ke Kafka 4.1.x **tetap dilanjutkan**, tapi ruang lingkupnya jadi jauh lebih sederhana: karena topologi TIDAK berpindah host, `KAFKA_CONTROLLER_QUORUM_VOTERS` tidak perlu diubah sama sekali (hostname Docker network `kafka1:9093`/`kafka2:9093`/`kafka3:9093` tetap sama). **Fase A.3 dan A.4 (upgrade kraft.version + konversi ke dynamic quorum) menjadi OPSIONAL** — tidak wajib dieksekusi sekarang, hanya relevan kalau migrasi multi-host dilanjutkan di kemudian hari. Fase B dan C di bawah ini dibiarkan sebagai referensi untuk nanti, TIDAK dieksekusi saat ini.

> **UPDATE 2026-07-29 (FINAL) — Upgrade DIBATALKAN**: Fase A.0 (backup + baseline) dan A.0b (audit kompatibilitas klien) berhasil LULUS. Namun percobaan Fase A.1 (rolling image upgrade, dimulai dari `kafka3` non-leader) GAGAL — container crash dengan error `INCONSISTENT_CLUSTER_ID` pada RaftManager saat `kafka3` (image 4.1.2) mencoba VoteRequest ke `kafka1`/`kafka2` (masih 3.7.0). Rollback dieksekusi dengan aman, cluster kembali sehat 100% di `3.7.0` (verified: quorum `[1,2,3]`, under-replicated & unavailable partitions kosong).
>
> Riset ke dokumentasi resmi Kafka menunjukkan upgrade langsung ke 4.1.2 dari versi manapun "seharusnya" didukung untuk cluster KRaft ≥3.3.x — namun kombinasi lompatan `3.7.0 → 4.1.2` (melompati 3.8/3.9/4.0 sekaligus dalam satu langkah) ternyata memicu edge-case yang tidak terdokumentasikan dengan jelas. Opsi upgrade bertahap lewat versi antara (`3.8 → 3.9 → 4.0 → 4.1`) dipertimbangkan, tapi **Xiao memutuskan membatalkan upgrade sepenuhnya** — prioritas dialihkan ke penanganan CPU saturation Node 1 (`ralph gunicorn` stuck) dan lag `dcim_itop_group_v8`, yang dianggap lebih mendesak daripada mengejar versi Kafka terbaru.
>
> **Status akhir cluster**: Kafka 3.7.0, 3 broker co-located di Node 1, arsitektur v4.6.1, SEHAT. Backup data volume & compose file dari Fase A.0 (sebelum percobaan upgrade) **tetap disimpan** di `/home/infra/dcim_metrics_project/kafka/backups/` sebagai referensi historis, tidak perlu dihapus. VM `kafka2`/`kafka3` (`10.70.0.57`/`10.70.0.58`) tetap dalam kondisi dormant (config + data tersimpan) untuk jaga-jaga jika migrasi multi-host maupun upgrade versi ingin dilanjutkan di masa depan.
>
> **Pekerjaan berikutnya (di luar dokumen ini)**: CPU saturation Node 1 (`ralph gunicorn` PID stuck/spin-loop) dan lag `dcim_itop_group_v8` (root cause: query auth iTop lambat 4.6-25.6 detik + waterfall 15-18 request sekuensial per event + CPU host jenuh).

> **UPDATE 2026-07-30 — Upgrade DIBUKA KEMBALI, Ditunda Sampai Isu iTop Tuntas**: Fase 1 (ralph gunicorn) sudah selesai. Fase 3 (perbaikan lag iTop — index database + perbaikan urutan `find_device()`) sedang dalam observasi lanjutan (1.5-2 jam) di dokumen v4.6.2. Xiao memutuskan: **setelah** isu lag iTop dinyatakan tuntas, upgrade Kafka ke 4.1.x dilanjutkan lagi — TAPI dengan **pendekatan bertahap** melewati versi antara, BUKAN lompat langsung seperti percobaan 29 Juli yang gagal dengan `INCONSISTENT_CLUSTER_ID`:
>
> ```
> 3.7.0 → 3.8.x → 3.9.x → 4.0.x → 4.1.x
> ```
>
> Setiap tahap: rolling upgrade image satu broker per waktu (pola sama seperti Fase A.1 sebelumnya — pre-check under-replicated kosong → ganti image → restart → verifikasi ISR pulih → lanjut broker berikutnya), lalu **verifikasi stabil dulu** (observasi beberapa saat, cek log/quorum/consumer group) sebelum naik ke versi berikutnya. Fase A.0 (backup + baseline) dan A.0b (audit kompatibilitas klien) yang sudah dilakukan sebelumnya TETAP BERLAKU sebagai referensi — tidak perlu diulang dari nol, tapi baseline sebaiknya di-refresh sebelum mulai tahap pertama karena beberapa hari sudah berlalu dan ada perubahan (index database, perbaikan kode iTop consumer).
>
> **Trigger untuk mulai**: menunggu konfirmasi eksplisit dari Xiao bahwa lag `dcim_itop_group_v8` sudah dinyatakan tuntas/stabil dari workstream v4.6.2.
>
> **UPDATE 2026-08-02 — TRIGGER TERPENUHI, UPGRADE DIMULAI**: Isu lag iTop dinyatakan TUNTAS. Bukti: total lag turun 2.27 juta pesan dalam 52 jam observasi (5,907,267 → 3,635,906), partisi 0 (CCTV, backlog terbesar) turun dari 3.2 juta → 80,818, seluruh partisi bergerak dengan laju sehat dan merata. Root cause database (dcim_events full-scan tanpa index) terbukti selesai lewat EXPLAIN ANALYZE (91.2 detik → 0.08 detik). Sisa `[SLOW]` residual (~1-2x/jam dari fallback REST API iTop) dicatat sebagai item minor terpisah (Fase 3.6 opsional di v4.6.2), TIDAK menghalangi upgrade Kafka.
>
> Upgrade bertahap Kafka `3.7.0 → 3.8.x → 3.9.x → 4.0.x → 4.1.x` DIMULAI. Baseline di-refresh dulu (Fase A.0 ulang) karena sudah ada perubahan sejak baseline lama: index MariaDB `priv_user`, index Postgres `dcim_events`, dan 2 perubahan kode consumer iTop (`find_device()` ordering, `ILIKE→LOWER()`).

**Prinsip**: Lakukan upgrade versi SELAGI topologi masih sederhana (semua broker di 1 host, 1 Docker network) — jauh lebih rendah risiko dibanding upgrade di tengah transisi multi-host.

### A.0 — Prasyarat & Backup
- Backup penuh data volume `kafka1_data`, `kafka2_data`, `kafka3_data`.
- Backup `docker-compose-cluster.yml` saat ini.
- Catat baseline kesehatan pipeline (pola yang sama seperti audit sebelumnya: LAG semua consumer group, under-replicated-partitions, sampling data).
- Konfirmasi image `apache/kafka:4.1.x` (versi patch terkini di garis 4.1) bisa ditarik — perlu domain Docker Hub/registry reachable dari Node 1.

### A.0b — Audit Kompatibilitas Klien (WAJIB, READ-ONLY, sebelum A.1)
- Cek versi processor Kafka NiFi (`ConsumeKafka_x_y`/`PublishKafka_x_y`) dan versi bundle client-nya — pastikan mendukung protokol broker 4.x.
- Cek versi `confluent-kafka`/`librdkafka` yang dipakai seluruh consumer Python.
- Jika ditemukan komponen yang jelas tidak kompatibel (versi client sangat lawas), STOP — laporkan ke Xiao, jangan lanjut ke A.1 sebelum komponen itu diupgrade/diverifikasi terpisah.

### A.1 — Rolling Image Upgrade (Satu Broker per Waktu, Quorum Voters TETAP Statis/Tidak Berubah)
Ganti `image: apache/kafka:3.7.0` → `image: apache/kafka:4.1.x` di definisi masing-masing broker, **TANPA mengubah `KAFKA_CONTROLLER_QUORUM_VOTERS` sama sekali di fase ini**. Urutan: broker non-leader dulu (kafka3-lama, lalu kafka2-lama), kafka1 (leader) terakhir.

Untuk tiap broker:
1. Pre-check `under-replicated-partitions` KOSONG.
2. `docker compose up -d --no-deps <broker>` dengan image baru.
3. Verifikasi container `Up`, log tidak ada fatal error.
4. Tunggu broker rejoin ISR sepenuhnya sebelum lanjut broker berikutnya.

### A.2 — Verifikasi Seluruh Broker Stabil di 4.1.x (Periode Observasi, BELUM Finalize)
- Ketiga broker `Up`, versi terkonfirmasi 4.1.x (`docker exec <broker> /opt/kafka/bin/kafka-topics.sh --version` atau cek log startup).
- `under-replicated-partitions` & `unavailable-partitions` KOSONG.
- Baseline kesehatan pipeline (LAG, sampling data, status NiFi processor) sama seperti sebelum upgrade.
- **WAJIB — Tes Fungsional Nyata (bukan cuma cek versi/status container)**: Audit kompatibilitas klien (lihat A.0b) hanya berbasis nomor versi, belum ada tes produce/consume nyata terhadap broker 4.1.x. Sebelum dianggap LULUS observasi:
  - NiFi: pastikan minimal satu processor `PublishKafka_2_6`/`ConsumeKafkaRecord_2_6` yang aktif berhasil produce+consume nyata pasca upgrade (bukan cuma status container `Up`), tidak ada exception protokol baru di log NiFi.
  - Tiap service Python resmi (`dcim-normalizer`, `dcim-itop-unified`, `dcim-es-consumer`, `dcim-sql-consumer`, `dcim-analytics-bridge`, `dcim-analytics-stream-processor` — perhatian khusus karena pakai `kafka-python`, `dcim-siem-es-consumer`, `dcim-threshold-alerter`): LAG tetap stabil/menurun seperti biasa, TIDAK ADA exception baru terkait protocol/API version di log service.
- **Biarkan berjalan stabil beberapa saat** (observasi, BUKAN langsung finalize) untuk pastikan tidak ada regresi tersembunyi. Cluster masih berjalan di `metadata.version` lama selama fase ini — downgrade MASIH memungkinkan jika observasi menemukan masalah.

### A.2b — Finalize Upgrade (setelah observasi A.2 dinyatakan aman oleh Xiao)
```bash
docker exec kafka1 /opt/kafka/bin/kafka-features.sh \
  --bootstrap-server localhost:9092 upgrade --release-version 4.1
```
⚠️ **TITIK TANPA JALAN BALIK** — downgrade metadata TIDAK didukung setelah ini. Hanya jalankan setelah observasi A.2 selesai dan ada approval eksplisit terpisah dari Xiao.

### A.3 — Upgrade KRaft Version Feature Flag
Berdasarkan dokumentasi resmi Kafka: KRaft version 1 men-deprecate properti `controller.quorum.voters` dan menambahkan `controller.quorum.bootstrap.servers`.
```bash
docker exec kafka1 /opt/kafka/bin/kafka-features.sh \
  --bootstrap-server localhost:9092 upgrade --feature kraft.version=1
docker exec kafka1 /opt/kafka/bin/kafka-features.sh \
  --bootstrap-server localhost:9092 describe
```
Verifikasi `kraft.version` sudah berubah ke `1` di ketiga broker.

### A.4 — Migrasi Config: `controller.quorum.voters` → `controller.quorum.bootstrap.servers`
Setelah kraft.version=1 aktif, update config SEMUA node (masih co-located di Node 1 pada fase ini) dari:
```
KAFKA_CONTROLLER_QUORUM_VOTERS=1@kafka1:9093,2@kafka2:9093,3@kafka3:9093
```
menjadi:
```
KAFKA_CONTROLLER_QUORUM_BOOTSTRAP_SERVERS=kafka1:9093,kafka2:9093,kafka3:9093
```
(Hostname Docker network TETAP dipakai di fase ini — belum pindah host. Restart bergantian per broker, verifikasi ISR pulih di antaranya, sama seperti pola A.1.)

### A.5 — Verifikasi Dynamic Quorum Aktif
```bash
docker exec kafka1 /opt/kafka/bin/kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9092 describe --status
```
Pastikan cluster tetap sehat pasca migrasi config ini. Cluster sekarang siap untuk operasi `add-controller`/`remove-controller` yang aman untuk Fase B.

**CHECKPOINT FASE A — approval wajib sebelum lanjut Fase B.**

---

## FASE B — Migrasi Multi-Host Menggunakan Dynamic Quorum

Dengan dynamic quorum aktif, broker baru bisa ditambahkan sebagai voter TANPA restart node lain, dan broker lama dihapus dari quorum dengan aman — menghindari sepenuhnya masalah "restart 3 node bersamaan" dari rencana sebelumnya.

### B.1 — Bawa Broker 3 Baru (10.70.0.58) sebagai Observer/Voter Baru
- **Opsional (rekomendasi)**: copy data volume `kafka3_data` dari kafka3-lama (Node 1) ke VM `10.70.0.58` dulu, supaya catch-up lebih cepat (tidak full network resync dari nol). Broker HARUS dalam keadaan stop bersih sebelum copy data (bukan live-copy).
- Update docker-compose kafka3 baru: image `3.9.2`, gunakan `--no-initial-controllers` (bukan `controller.quorum.voters` statis) sesuai prosedur resmi KIP-853, dengan `controller.quorum.bootstrap.servers` menunjuk ke broker yang sudah ada (`10.70.0.56:9093` cukup, karena bootstrap servers dipakai untuk discover quorum awal, tidak harus lengkap semua).
- Start container.
- Daftarkan sebagai voter resmi:
```bash
docker exec kafka1 /opt/kafka/bin/kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9092 --command-config controller.properties \
  add-controller
```
- Verifikasi catch-up replikasi (pola sama seperti sebelumnya: `under-replicated-partitions`).

### B.2 — Hapus Broker 3 LAMA dari Quorum
```bash
docker exec kafka1 /opt/kafka/bin/kafka-metadata-quorum.sh \
  --bootstrap-server localhost:9092 remove-controller \
  --controller-id 3 --controller-directory-id <directory-id-lama>
```
(Sesuai catatan dokumentasi: shutdown controller yang akan dihapus TERLEBIH DAHULU sebelum `remove-controller`, karena pre-vote/KIP-996 belum diimplementasikan di versi ini.)
- Verifikasi cluster tetap sehat, quorum tersisa `[1,2,3]` dengan node 3 sekarang di host baru.

### B.3 — Ulangi Pola B.1-B.2 untuk Broker 2 (VM 10.70.0.57)
Sama persis, ganti referensi broker 3 → broker 2.

### B.4 — Finalisasi Kafka1 (Node 1, Sisa 1 Broker)
- Update `docker-compose-cluster.yml` Node 1: hanya `kafka1`, `network_mode: host`, `ADVERTISED_LISTENERS` ke `10.70.0.56` (bukan `localhost` lagi).
- Restart kafka1 terakhir, verifikasi quorum `[1,2,3]` dengan seluruh node di host masing-masing.

**CHECKPOINT FASE B — approval wajib sebelum lanjut Fase C.**

---

## FASE C — Finalisasi Pipeline (Sama Seperti Rencana Semula)
- Update `KAFKA_CLUSTERS_0_BOOTSTRAPSERVERS` di Kafbat UI.
- Update `bootstrap.servers` di seluruh consumer/producer (`normalizer`, `es_logger`, `siem_es_consumer`, `sql_consumer`, NiFi) ke `10.70.0.56:9092,10.70.0.57:9092,10.70.0.58:9092` (atau port SSL sesuai kebutuhan).
- Verifikasi end-to-end: LAG semua consumer group, sampling data, Elasticsearch/NiFi health — bandingkan dengan baseline awal sesi ini.
- Susun rangkuman/handoff document migrasi lengkap (riwayat harian, sesuai instruksi kerja Xiao).

---

## Item Terpisah — TIDAK Termasuk Plan Ini (Dikerjakan Setelah Migrasi Selesai)
1. **Lag `dcim_itop_group_v8`** — root cause sudah ditemukan (query auth iTop lambat 4.6-25.6 detik + CPU host jenuh), solusi belum dieksekusi.
2. **CPU saturation Node 1** — proses `ralph gunicorn` (PID 4477) stuck/spin-loop, belum ditangani.
3. **Upgrade Kafka ke 4.x** — dipertimbangkan sebagai proyek terpisah setelah cluster 3.9.2 multi-host stabil di production.

---

## Ringkasan Perbandingan dengan Rencana Sebelumnya

| Aspek | Rencana Lama (Copy-Data + Restart Bersamaan, tetap 3.7.0) | Rencana Baru v4.7.1 (Upgrade ke 4.1.x + Dynamic Quorum) |
|---|---|---|
| Downtime controller | Ya, singkat, 3 node bersamaan | Tidak — rolling per broker, termasuk saat pindah host |
| Risiko config drift/typo saat restart bersamaan | Tinggi (rawan human error saat 3 node diubah serentak) | Rendah (satu-satu, dynamic quorum yang jamin konsistensi) |
| Menyelesaikan akar masalah jangka panjang | Tidak (masih static quorum, rawan terulang) | Ya (dynamic quorum, operasi cluster ke depan jauh lebih aman) |
| Kompleksitas/jumlah langkah | Lebih sedikit langkah, tapi lebih berisiko per langkah | Lebih banyak langkah, tapi masing-masing risiko rendah |
