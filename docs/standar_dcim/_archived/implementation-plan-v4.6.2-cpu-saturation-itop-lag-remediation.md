# Implementation Plan: Remediasi CPU Saturation (Ralph Gunicorn) & Lag iTop Consumer

> **Versi**: v4.6.2 (Patch/Hotfix dari arsitektur v4.6.1 — bukan bagian dari workstream migrasi Kafka)
> **Tanggal**: 2026-07-29
> **Status**: DRAFT — MENUNGGU APPROVAL XIAO
> **Target Host**: Node 1 (`srv-rnd-dcim` / `10.70.0.56`)
> **Konteks**: Migrasi Kafka multi-host (v4.7.0) dan upgrade versi (v4.7.1) sudah DITUTUP/DIBATALKAN. Cluster kembali stabil di Kafka 3.7.0, 3-broker co-located. Dokumen ini menangani dua isu operasional yang ditemukan selama investigasi migrasi, tapi independen dari Kafka itu sendiri.

---

## Latar Belakang & Ringkasan Temuan

Selama investigasi migrasi Kafka, ditemukan dua isu di Node 1 yang belum diperbaiki:

1. **CPU Saturation — `ralph gunicorn` worker (PID 4477)**: Worker child Gunicorn (di bawah master PID 4424, container `ralph_web`) terkonfirmasi **stuck/spin-loop** — CPU 59-94% konstan sejak 19 Juli (10+ hari nonstop), `nonvoluntary_ctxt_switches` 35 juta, single-thread. Ini bukan pola trafik HTTP normal (biasanya naik-turun mengikuti request), melainkan indikasi worker yang macet dalam loop tanpa memproses request baru secara efektif.

2. **Lag `dcim_itop_group_v8`** (consumer resmi `dcim-itop-unified.service`, PID resmi tunggal — BUKAN duplikat seperti dugaan awal): Lag jutaan pesan di partisi 0, ratusan ribu di partisi lain, terus bertambah. Root cause dua lapis:
   - **Aplikasi**: fungsi `find_device` melakukan hingga 15-18 HTTP POST sekuensial ke REST API iTop per pesan Kafka (mengecek 6 kelas CI × beberapa strategi pencarian).
   - **Backend iTop**: setiap REST call memicu re-autentikasi, dan query autentikasi (`priv_internaluser`/`priv_urp_userprofile`) tercatat di slow query log MariaDB memakan 4.6-25.6 detik meski hanya memeriksa 9-14 baris — jauh tidak wajar untuk volume data sekecil itu.
   - **Kemungkinan penguat**: CPU host yang jenuh (termasuk oleh `ralph gunicorn` yang stuck) memperlambat eksekusi PHP/MariaDB secara umum.

**Hipotesis kerja**: memperbaiki (1) dapat mengurangi tekanan CPU host secara keseluruhan, yang mungkin turut meringankan (2) — tapi (2) kemungkinan besar tetap butuh perbaikan tersendiri di level aplikasi/database karena akar masalahnya (query auth lambat + waterfall request) tidak akan hilang hanya karena CPU lebih longgar.

---

## FASE 1 — Remediasi `ralph gunicorn` (Aman, Rendah Risiko)

**Prinsip**: PID 4477 adalah **worker child**, bukan master. Gunicorn didesain agar master (PID 4424) otomatis me-respawn worker baru begitu satu worker mati — mematikan satu worker tidak mematikan service Ralph secara keseluruhan, asalkan ada worker lain atau master masih hidup.

### 1.1 — Baseline Sebelum Remediasi
- Cek jumlah worker Gunicorn aktif saat ini (`ps aux | grep gunicorn`).
- Catat resource host: `top -bn1 | head -10`, catat `%CPU idle` dan `wa` (I/O wait) sebagai baseline.
- Catat status Ralph service (`curl` ke endpoint Ralph, port sesuai `ralph_web`/`ralph_nginx`).
- Catat baseline LAG `dcim_itop_group_v8` (untuk dibandingkan setelah Fase 2).

### 1.2 — Kill Worker yang Stuck
- `kill 4477` (SIGTERM dulu, graceful).
- Tunggu 5-10 detik, verifikasi PID 4477 benar-benar mati (`ps -p 4477`).
- Jika masih hidup setelah 10 detik (mengindikasikan benar-benar stuck, tidak merespons SIGTERM), `kill -9 4477`.

### 1.3 — Verifikasi Master Respawn Worker Baru
- `ps aux | grep gunicorn` — harus muncul worker BARU dengan PID berbeda dari 4477.
- Verifikasi service Ralph tetap merespons (`curl` endpoint yang sama seperti 1.1).
- Pantau worker baru beberapa menit — pastikan tidak langsung stuck lagi (CPU wajar, bukan langsung melonjak ke 90%+ konstan).

### 1.4 — Verifikasi Dampak ke Resource Host
- `top -bn1 | head -10` — bandingkan `%idle` dan `wa` dengan baseline 1.1. Harapan: idle naik, wa turun.
- `docker stats --no-stream kafka1 kafka2 kafka3` — pastikan tidak ada dampak negatif ke broker Kafka (harusnya malah lebih longgar).

**CHECKPOINT — jika Fase 1 berhasil (worker baru sehat, resource membaik), lanjut ke Fase 2 untuk ukur dampaknya ke lag iTop SEBELUM memutuskan apakah Fase 3 (perbaikan aplikasi) diperlukan.**

---

## FASE 2 — Pengukuran Dampak ke Lag iTop (Observasi, Bukan Perbaikan)

**Tujuan**: mengukur seberapa besar CPU saturation berkontribusi terhadap lag iTop, sebelum memutuskan investasi perbaikan di level aplikasi/database.

### 2.1 — Pantau Tren LAG Selama 15-30 Menit Pasca Fase 1
```bash
docker exec kafka1 /opt/kafka/bin/kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 --describe --group dcim_itop_group_v8
```
Jalankan 3-4 kali dengan jeda 5-10 menit. Catat tren:
- **Menurun signifikan** → CPU saturation adalah kontributor besar, cukup pantau lebih lama untuk lihat apakah backlog akan habis sendiri.
- **Menurun sedikit tapi masih net bertambah** → CPU saturation berkontribusi sebagian, TAPI root cause aplikasi (query lambat + waterfall request) tetap dominan — Fase 3 kemungkinan diperlukan.
- **Stagnan/tidak berubah** → CPU saturation BUKAN kontributor utama, root cause murni di aplikasi/database — Fase 3 diperlukan.

### 2.2 — Cek Ulang Retention Risk
```bash
docker exec kafka1 /opt/kafka/bin/kafka-configs.sh \
  --bootstrap-server localhost:9092 --describe --entity-type topics --entity-name dcim.normalized.events
docker exec kafka1 /opt/kafka/bin/kafka-run-class.sh kafka.tools.GetOffsetShell \
  --broker-list localhost:9092 --topic dcim.normalized.events --time -2
```
Pastikan earliest-offset belum mendekati current-offset consumer (masih ada buffer waktu sebelum data hilang akibat retensi 7 hari).

**CHECKPOINT — laporkan hasil Fase 2 ke Xiao. Keputusan lanjut ke Fase 3 (perbaikan aplikasi/database) menunggu review bersama, KARENA Fase 3 kemungkinan butuh perubahan kode (bukan sekadar ops), yang di luar scope "eksekusi ops" biasa dan idealnya melibatkan tim yang memegang source code iTop consumer.**

---

## FASE 3 — Perbaikan Level Aplikasi/Database (KONDISIONAL, Belum Disetujui, Referensi Saja)

Item ini **TIDAK dieksekusi** sampai Fase 2 selesai dan Xiao memutuskan diperlukan. Dicatat di sini sebagai referensi opsi yang tersedia:

- **Database iTop**: investigasi kenapa query autentikasi (`priv_internaluser`/`priv_urp_userprofile`) selambat itu untuk baris sesedikit itu — kemungkinan index hilang/tidak optimal, atau MariaDB butuh tuning (buffer pool, dll). Ini murni investigasi database, read-only dulu (`EXPLAIN` query, cek index).
- **Aplikasi consumer**: pertimbangkan cache hasil autentikasi REST API iTop (token/session reuse) alih-alih re-autentikasi di SETIAP request — ini perubahan kode di `dcim_itop_unified_consumer.py`, butuh review sebelum deploy.
- **Paralelisasi `find_device`**: alih-alih 15-18 request sekuensial, pertimbangkan paralel/batch — juga perubahan kode, butuh testing lebih hati-hati (concurrency terhadap REST API iTop perlu dipastikan aman).

---

## Yang Tidak Boleh Dilakukan (Berlaku Sepanjang Dokumen Ini)
- JANGAN kill master Gunicorn (PID 4424) — hanya worker child.
- JANGAN sentuh `executor.py` (PID resmi `dcim-normalizer.service`) atau `dcim_itop_unified_consumer.py` (PID resmi `dcim-itop-unified.service`) — keduanya sudah dikonfirmasi proses resmi tunggal, bukan orphan/duplikat.
- JANGAN reset/seek offset consumer group `dcim_itop_group_v8`.
- JANGAN ubah `retention.ms` topic.
- JANGAN eksekusi Fase 3 tanpa approval eksplisit terpisah — itu perubahan kode, bukan sekadar operasional.

## Format Laporan (Setiap Fase)
- Output mentah tiap command, dengan timestamp.
- Perbandingan before/after eksplisit (bukan ringkasan naratif tanpa angka).
- Bahasa Indonesia.
- Detailkan per langkah, jangan dirangkum luas.
