# Prompt Korektif — Penataan Ulang Sumber Kebenaran Arsitektur & Audit Ulang PR #40

> **Konteks:** Ditemukan pola sistemik pada PR #40 (masih terbuka, belum direview
> `shuffahaqgzz`): dokumen `docs/architecture/multi-source-ingestion-pipeline.md` mengambil
> angka/perilaku teknis dari artefak milik `dcim-core-platform` sendiri (ADR-0023, ADR-0003)
> alih-alih dari implementasi nyata di host `srv-rnd-dcim`. Ini bukan cuma soal Kafka broker
> count — perlu audit ulang menyeluruh. Tempel prompt ini ke agent yang sama yang mengerjakan
> PR #40 (punya akses ke ketiga repo + working copy branch PR).

---

## KOREKSI MODEL MENTAL — WAJIB DIPAHAMI SEBELUM LANGKAH APA PUN

Peran tiga repo ini **sering disalahpahami**. Berikut definisi yang benar dan final:

| Repo | Peran yang BENAR | Peran yang SALAH (jangan dilakukan) |
|---|---|---|
| `DCIM_SRV_DATA_COLLECTION` (host `srv-rnd-dcim`) | **Sumber kebenaran fakta** — implementasi aktual yang benar-benar berjalan. Setiap angka, default, perilaku, algoritma yang diklaim sebagai "pola dari implementasi aktual" HARUS bisa ditelusuri ke file kode/config nyata di sini. | — |
| `dcim-wiki` | **Acuan arsitektur yang sudah dikerjakan/divalidasi** — dokumentasi resmi yang menjelaskan desain di balik implementasi aktual. Ini sumber kebenaran arsitektural kedua yang sah, setara/melengkapi kode di poin di atas. | — |
| `dcim-core-platform` | **HANYA** tujuan kontribusi: aturan format dokumen, safety gate (`DATA-HANDLING.md`, `check_public_repo_safety.py`), konvensi struktur folder/ADR, dan alur governance (branch/PR/review). | ❌ **BUKAN** sumber fakta tentang bagaimana pipeline seharusnya berperilaku. ADR/dokumen yang SUDAH ADA di `dcim-core-platform` (mis. ADR-0023, ADR-0003) mendeskripsikan **rencana/keputusan proyek `dcim-core-platform` sendiri** — bisa jadi berbeda dari, atau bahkan belum tervalidasi seperti, implementasi nyata Anda. Jangan pernah mengutip angka dari ADR `dcim-core-platform` sebagai representasi "pola dari pipeline aktual" tanpa cross-check ke kode nyata. |

**Aturan sourcing yang wajib diikuti untuk SETIAP klaim teknis (angka, threshold, algoritma, default) dalam dokumen apa pun yang ditulis untuk `dcim-core-platform`:**

1. Cari dulu di kode/config nyata `DCIM_SRV_DATA_COLLECTION` (host `srv-rnd-dcim`). Jika ada →
   ini sumber utama.
2. Jika tidak ada di kode (misalnya karena masih desain, belum diimplementasi), cari di
   `dcim-wiki`. Jika ada → sumber kedua yang sah, tapi sebutkan eksplisit bahwa ini "desain
   target dari `dcim-wiki`", bukan "yang sudah berjalan".
3. **Jangan pernah** mengambil nilai dari ADR/dokumen `dcim-core-platform` sendiri untuk mengisi
   klaim tentang "bagaimana pipeline aktual bekerja". `dcim-core-platform` boleh dirujuk HANYA
   untuk hal-hal yang memang tentang `dcim-core-platform` sendiri (konvensi kode, struktur folder,
   proses PR) — bukan untuk fakta arsitektur/perilaku sistem sumber.
4. Jika ada perbedaan antara apa yang tertulis di `dcim-wiki` vs apa yang benar-benar berjalan di
   kode `DCIM_SRV_DATA_COLLECTION`, **kode aktual yang menang** — laporkan perbedaan itu ke saya,
   jangan diselesaikan sepihak.

---

## TUGAS 1 — Audit Ulang Penuh PR #40 (bukan cuma bagian Kafka)

Untuk **setiap** klaim teknis spesifik (angka, threshold, algoritma, nama pola) di
`docs/architecture/multi-source-ingestion-pipeline.md`, buat tabel penelusuran sumber seperti ini,
dan tunjukkan ke saya sebelum melakukan perbaikan apa pun:

| Bagian dokumen | Klaim | Sumber saat ini (dugaan) | Sumber yang benar (setelah dicek) | Perlu diperbaiki? |
|---|---|---|---|---|
| §3.2 Polling Controls | "3–10s timeout" | ADR-0023 `dcim-core-platform` | Cek `scripts/redfish_poller.py`, `scripts/mikrotik_poller.py`, `scripts/nas_poller.py`, dll. di `DCIM_SRV_DATA_COLLECTION` — ambil nilai TIMEOUT aktual per source class | ? |
| §3.3 Circuit Breaker trigger | "5 consecutive or 50%/60s error rate" | ADR-0023 `dcim-core-platform` | **SUDAH DIKONFIRMASI SALAH** — kode aktual `src/utils/circuit_breaker.py` cuma pakai `failure_threshold=5` (consecutive count), `success_threshold=2`, `recovery_timeout=60.0`. Tidak ada logic error-rate/sliding-window sama sekali. | **YA — wajib diperbaiki** |
| §4.1 Kafka broker count | "1 (dev) / 3 (reference)" | Campuran ADR-0003 `dcim-core-platform` + asumsi | Kode/config aktual: cluster `kafka1/kafka2/kafka3` KRaft SSL, RF=3, min.ISR=2, Kafka 4.1.2, sudah production — lihat `kafka/docker-compose-cluster.yml` di `DCIM_SRV_DATA_COLLECTION` dan `docs/architecture/v4.6-pipeline-architecture.md` | **YA — sudah diketahui perlu diperbaiki** |
| §5.1 Validation Rules (8 rule) | Schema/mandatory/type/range/format/dedup/freshness/source | `dcim-wiki` §5 `block2-data-ingestion-integration.md` | Ini desain target `dcim-wiki`, BUKAN yang sudah jalan (validasi aktual di `normalizer/executor.py` cuma null-check dasar) — periksa apakah dokumen sudah melabeli ini dengan jelas sebagai target, bukan status aktual | Cek label eksplisit |
| §6 Enrichment fields | `site_id`, `rack_id`, `criticality`, dll. | ? | Cek `scripts/enrichment/*` atau service enrichment aktual di `DCIM_SRV_DATA_COLLECTION` — bandingkan dengan 8 field yang sudah dikonfirmasi audit sebelumnya (`site_id, rack_id, building_id, room_id, asset_tag, owner_dept, environment, criticality`) | ? |
| §7 Lineage stages & tabel `event_lineage` | Struktur kolom, nama stage | ? | Cek tabel `event_lineage`/`dcim_lineage` aktual (skema kolom, bukan nilai) di `DCIM_SRV_DATA_COLLECTION` | ? |
| §9 Observability metrics | Nama metric Prometheus | ? | Cek `scripts/circuit_breaker_monitor.py` dan exporter aktual — apakah nama metric ini sudah ada atau murni usulan baru? Jika murni usulan, label eksplisit sebagai proposal | ? |
| Header "References" | ADR-0004, ADR-0023, ADR-0024 | `dcim-core-platform` | Ini rujukan yang MEMANG SEHARUSNYA dari `dcim-core-platform` (karena tentang konvensi/aturan repo target) — tidak perlu diubah | Tidak |

Lengkapi kolom "?" dengan hasil pengecekan nyata (grep/baca file), bukan tebakan. Tambahkan baris
lain jika ada klaim teknis yang belum tercakup tabel di atas.

## TUGAS 2 — Perbaiki Berdasarkan Hasil Audit

Setelah tabel Tugas 1 lengkap dan saya konfirmasi, perbaiki
`docs/architecture/multi-source-ingestion-pipeline.md` dengan commit tambahan ke branch
`docs/actual-pipeline-architecture-reference` (branch PR #40 yang sudah ada — **jangan buat PR
baru**):

1. Ganti setiap angka/klaim yang sumbernya salah (dari ADR `dcim-core-platform`) dengan nilai
   yang benar-benar tertelusuri ke `DCIM_SRV_DATA_COLLECTION`/`dcim-wiki`.
2. Untuk setiap klaim yang berasal dari `dcim-wiki` sebagai **desain target** (belum tentu sudah
   berjalan), beri label eksplisit di teks — mis. "*(design target per dcim-wiki §5; not yet
   implemented in production normalizer)*" — supaya reviewer `shuffahaqgzz` tidak salah paham
   dokumen ini melaporkan status aktual.
3. Tetap ikuti aturan `DATA-HANDLING.md`: nilai yang dipakai di dokumen tetap harus digeneralisasi/
   disintesis (tidak menyalin IP, hostname, community string dsb.) — yang diperbaiki di sini adalah
   **akurasi pola/perilaku**, bukan level detail operasional.
4. Jalankan gate sebelum commit:
   ```bash
   make phase0-check
   python scripts/check_public_repo_safety.py
   ```
5. Commit dan push ke branch yang sama:
   ```bash
   git add docs/architecture/multi-source-ingestion-pipeline.md
   git commit -m "docs(architecture): correct sourcing — ground claims in actual implementation, not dcim-core-platform's own ADRs"
   git push origin docs/actual-pipeline-architecture-reference
   ```

## TUGAS 3 — Cegah Pola Ini Terulang di PR Berikutnya

Untuk semua pekerjaan lanjutan (Validation Processor implementation, connector fixture-replay,
Impact Scoring, dsb. — sesuai rencana PR A–E), terapkan aturan sourcing di atas sejak awal:
sebelum menulis satu baris kode/dokumentasi yang mengklaim "berdasarkan pola implementasi
aktual", tunjukkan dulu ke saya file/baris kode di `DCIM_SRV_DATA_COLLECTION` atau bagian
`dcim-wiki` yang menjadi sumbernya.

---

## LAPORAN YANG SAYA HARAPKAN

1. Tabel audit lengkap (Tugas 1) — sebelum ada perbaikan apa pun.
2. Setelah saya konfirmasi, ringkasan perubahan yang dibuat (Tugas 2) + hasil `make
   phase0-check`.
3. Konfirmasi bahwa aturan sourcing (Tugas 3) akan dipakai untuk sisa pekerjaan gap closure.
