# Prompt untuk Agent: Fix DLQ_Delivery_Writer Error Aktif (Root Cause via Provenance) + Instruksi GUI RouteOnContent untuk Owner

## Konteks

Screenshot terbaru dari NiFi UI (21/08/2026, ~03:25 UTC) menunjukkan dua hal:

1. **`DLQ_Delivery_Writer` masih aktif melempar error berulang tiap ~60 detik**, dengan pesan yang **sama persis** dengan bug lama yang diklaim "Partially Fixed" di laporan sebelumnya:
   ```
   JsonParseException: Unrecognized token 'File': was expecting (JSON String, Number, Array, Object or token 'null', 'true' or 'false')
   ```
   Ini indikasi kuat traceback Python mentah masih bocor ke stream yang seharusnya JSON — TAPI dari sumber yang berbeda dari 4 script yang sudah dipatch sebelumnya (`mikrotik_poller.py`, `redfish_poller.py`, `nas_poller.py`, `cctv_poller.py`). Canvas menunjukkan process group **`Virtualization Ingestion`** dan kemungkinan **`Server Redfish Ingestion`**, **`NAS Storage Ingestion`**, **`Mikrotik SNMP Ingestion`** semuanya terhubung ke `DLQ_Delivery_Writer` yang sama — perlu identifikasi persis sumbernya, jangan tebak dari nama canvas.
2. **`Security SIEM Ingestion` (RouteOnContent) masih Blocked seperti sebelumnya** — ini konsisten dengan status yang sudah diketahui, bukan regresi baru. **Owner akan mengeksekusi fix ini sendiri di GUI** — task agent untuk bagian ini murni menyiapkan instruksi presisi, BUKAN eksekusi.

## Batasan Keras (Do Not)

- **JANGAN asumsikan sumber error `DLQ_Delivery_Writer` dari nama process group di canvas** — trace pakai NiFi Provenance berdasarkan `filename` di pesan error untuk konfirmasi persis asalnya sebelum memperbaiki apapun.
- **JANGAN klaim "Fixed"/"Resolved" tanpa bukti bulletin board bersih minimal 15-30 menit berturut-turut setelah fix diterapkan** — klaim "Partially Fixed" sebelumnya ternyata masih ada error aktif sampai sekarang, jangan ulangi pola melaporkan sukses prematur.
- **JANGAN eksekusi apapun di NiFi GUI sendiri untuk task RouteOnContent** — owner akan mengerjakan ini sendiri. Tugas agent di bagian ini murni menyiapkan instruksi presisi (lihat Tugas 3).
- **JANGAN tulis credential/token apapun di laporan** — aturan ini tetap berlaku seperti biasa.

## Tugas 1 — Trace Root Cause Persis via NiFi Provenance

1. Ambil beberapa `filename` dari pesan error bulletin (`71ee7d16-3a75-4a56-a9fd-3cbdef0cad39`, `559def18-f14b-4551-89e5-0895b523846b`, `09e4bc5-5a2a-4f16-b42e-0ec318c25e91`, `d4570550-7f14-4b66-98d5-cf15aa4afc2a` — atau ambil ulang dari bulletin terbaru, jangan asumsi ini masih relevan kalau sudah lewat waktu).
2. Buka **Data Provenance** di NiFi UI (read-only, tidak mengubah canvas), cari flowfile dengan `filename` tersebut, lacak **lineage**-nya mundur — dari process group/processor mana flowfile ini pertama kali muncul.
3. Konfirmasi persis: apakah sumbernya dari `Virtualization Ingestion` (kemungkinan `virtualization_poller_nifi.py`), `Server Redfish Ingestion`, `NAS Storage Ingestion`, `Mikrotik SNMP Ingestion`, atau kombinasi beberapa — jangan berhenti di satu asumsi kalau errornya ternyata datang dari beberapa sumber berbeda.
4. Untuk tiap sumber yang terkonfirmasi, cek apakah script terkait (`virtualization_poller_nifi.py`, `itsm_fixture_api.py`/`servicenow.py`/`jira.py`, atau script lain yang relevan) **sudah atau belum** punya `sys.excepthook`/JSON-wrap exception handler seperti yang sudah dipasang di 4 script sebelumnya.

## Tugas 2 — Terapkan Fix ke Sumber yang Benar

1. Untuk tiap script yang terkonfirmasi jadi sumber (dan belum dipatch), terapkan pola yang sama seperti fix sebelumnya: bungkus exception jadi JSON event (`event_id`, `event_type=error`, `error_message`, `traceback`) via global exception handler — **konsisten dengan implementasi yang sudah ada**, jangan buat pola baru yang berbeda tanpa alasan kuat.
2. **Verifikasi juga apakah 4 script yang sebelumnya diklaim sudah dipatch benar-benar menjalankan versi terbaru** di NiFi `ExecuteProcess` saat ini (cek path script yang dieksekusi NiFi vs path yang di-commit — pastikan tidak ada versi lama yang masih ke-cache/ke-load, atau proses yang perlu di-restart supaya baca kode terbaru).
3. Setelah fix diterapkan, **pantau bulletin board minimal 15-30 menit berturut-turut**, konfirmasi tidak ada lagi error `JsonParseException: Unrecognized token` yang muncul dari sumber manapun. Sertakan timestamp mulai-selesai pemantauan sebagai bukti, bukan cuma "sudah dicoba sekali langsung sukses".
4. Cek juga isi `DLQ_Delivery_Writer` sendiri — pastikan setelah fix, dia benar-benar berhasil publish payload error yang valid ke Kafka (bukan cuma "tidak ada error baru" tapi mungkin flowfile-nya malah hilang diam-diam di tempat lain).

## Tugas 3 — Siapkan Instruksi GUI Presisi untuk RouteOnContent (Owner yang Eksekusi)

Owner akan mengerjakan fix `RouteOnContent` di canvas `Security SIEM Ingestion` sendiri. Susun instruksi **step-by-step tanpa ambiguitas** (ikuti pola dari task GUI-handoff sebelumnya), mencakup:

1. Lokasi persis: process group `Security SIEM Ingestion` (id `1bb9d9ee-019f-1000-ceb3-d457deb541e9`, sesuai screenshot canvas terbaru).
2. Langkah tambah processor baru: klik kanan area kosong dalam process group → Add Processor → cari `RouteOnContent`.
3. Konfigurasi property: `Content Matching Strategy` = `Content Must Contain Match` (atau `Regular Expression` tergantung versi NiFi 1.24.0 — cek dokumentasi processor ini persis di versi yang dipakai), regex `^\s*\{.*` dengan nama relationship dinamis `is_json`.
4. Langkah re-routing koneksi:
   - Putuskan koneksi langsung `ListenSyslog - Wazuh` (dan `- Wazuh UDP`) → `JoltTransformJSON`.
   - Sambungkan `ListenSyslog - Wazuh` (dan UDP) → `RouteOnContent` (input).
   - Dari `RouteOnContent`, relationship `is_json` → `JoltTransformJSON` (jalur lama).
   - Dari `RouteOnContent`, relationship `unmatched` → langsung ke `PublishKafka - SIEM Alerts` (bypass Jolt).
5. Langkah verifikasi visual yang owner bisa cek sendiri sebelum start: pastikan `RouteOnContent` tidak menunjukkan ikon warning segitiga (artinya semua relationship sudah ter-connect dengan benar) sebelum di-start.
6. Langkah setelah start: cara owner bisa lihat sendiri di GUI apakah berhasil (metrik In/Out/Tasks pada `RouteOnContent` dan `JoltTransformJSON` mulai bergerak, tidak lagi stuck di 0).

Kirim instruksi ini ke owner sebagai draft bernomor yang jelas, dan **STOP** — jangan eksekusi apapun di GUI, tunggu owner konfirmasi sudah dikerjakan.

## Format Laporan Akhir

Buat `docs/handoff/YYYY-MM-DD-agent-handoff-dlq-writer-root-cause-fix-and-siem-gui-instructions.md`:

1. **Hasil Trace Provenance (Tugas 1)** — sumber persis error dikonfirmasi, dengan bukti lineage flowfile, bukan asumsi dari nama canvas.
2. **Status Fix per Script** (Tugas 2) — mana yang baru dipatch, mana yang ternyata sudah dipatch tapi belum aktif (versi lama masih jalan), dengan bukti bulletin board bersih 15-30 menit.
3. **Instruksi GUI RouteOnContent** (Tugas 3) — salinan persis instruksi yang dikirim ke owner, status: Menunggu Eksekusi Owner.
4. **Kesimpulan** — apakah `DLQ_Delivery_Writer` sekarang benar-benar bersih dari error (dengan bukti), atau masih ada sumber lain yang belum tertangani.
