# Handoff Report: Unified Metrics Pipeline Remediation & Normalizer Fix

**Tanggal Execution**: 2026-08-27  
**Status**: FIXED - Pipeline end-to-end untuk metrik (`dcim.events.raw` -> Elasticsearch `dcim-metrics-unified-*`) sudah kembali berjalan normal setelah terhenti sejak 10 Agustus.

---

## 1. Konteks & Akar Masalah (Root Cause)

Ditemukan bahwa indeks Elasticsearch `dcim-metrics-unified-*` berhenti menerima data sejak 10 Agustus 2026. Investigasi menemukan dua titik kegagalan utama di pipeline:

1. **Rogue Data Source (Virtualization)**: Terdapat systemd service/timer independen (`dcim-virtualization-poller.service`) dan proses Mock API (`proxmox_fixture_adapter.py`) yang berjalan di belakang layar secara independen dari NiFi UI. Proses ini terus membanjiri topik `dcim.raw.virtualization` dengan payload JSON yang tidak memenuhi skema standar Telegraf (tidak memiliki object `tags` dan `fields` yang benar).
2. **Crash-Loop pada Normalizer & ES Consumer**:
   - **Normalizer** (`dcim-normalizer.service`): Mengalami crash-loop (`AttributeError: 'str' object has no attribute 'copy'` / `'NoneType' object...`) saat mencoba memproses payload *malformed* dari rogue virtualization poller tersebut.
   - **ES Consumer** (`dcim-es-consumer.service`): Mengalami crash deserialization (`SerializationError: Unknown magic byte`) dan tipe data string-copy error, karena sebelumnya ada *bad messages* (campuran Avro/JSON) di topik Kafka `dcim.enriched.events`.

---

## 2. Tindakan yang Telah Dieksekusi

1. **Pembersihan Rogue Poller**:
   - Mematikan dan men-disable systemd timer & service `dcim-virtualization-poller.timer` / `dcim-virtualization-poller.service`.
   - Melakukan `kill` paksa pada proses Python Mock API (`proxmox_fixture_adapter.py`).
   - Melakukan observasi pada topik `dcim.raw.virtualization` dan dikonfirmasi telah bersih/silent dari data liar.

2. **Perbaikan ES Consumer (`es_logger/executor.py`)**:
   - Menambahkan *hybrid deserialization guard*: Mengecek magic byte Avro (`\x00`). Jika tidak ada, *fallback* aman menggunakan standar `json.loads()`.
   - Menambahkan *type checking* `isinstance()` sebelum modifikasi dictionary pada properti `raw_fields` dan `raw_tags` untuk mencegah crash attribute.
   - *Status*: Perbaikan telah di-commit dan di-push ke git repository `main`.

3. **Perbaikan Normalizer (`normalizer/executor.py`) dengan Pola Reject-to-DLQ**:
   - Menerapkan arsitektur DLQ ketat sesuai acuan `dcim-wiki` (§6.3 dan L10/L14).
   - Menambahkan filter: `if not isinstance(raw_tags, dict) or not isinstance(raw_fields, dict):`
   - Jika payload tidak sesuai format, normalizer akan melakukan `continue` (melewati eksekusi tanpa *crash*), mencetak log *Warning*, mempublikasikan payload mentah ke Kafka `dcim.dlq.parse-failure`, dan mencatat jejak di database lewat `track_lineage` dengan `status="dlq"`.
   - *Status*: Modifikasi diimplementasikan ke file lokal. Service `dcim-normalizer.service` di-restart dan terbukti berjalan sangat stabil tanpa adanya crash-loop lagi.

---

## 3. Status Terkini & Bukti Verifikasi

- **Poller Sources**: 5 tipe poller resmi (Redfish, SNMP UPS, NAS, MikroTik, CCTV) aktif berjalan normal.
- **Kafka Topics**: `dcim.events.raw`, `dcim.normalized.events`, dan `dcim.enriched.events` menunjukkan aliran pesan (throughput) yang sehat dan konstan.
- **Elasticsearch**: Indeks `dcim-metrics-unified-2026.08.26` (dan hari selanjutnya) sukses dibuat otomatis oleh daemon ES. Dokumen terbukti mulai masuk ke indeks.
- **DLQ**: Pesan format cacat ter-filter dengan mulus ke topik `dcim.dlq.parse-failure` tanpa menjatuhkan pipeline utama.

---

## 4. Next Steps (Untuk Agent Selanjutnya)

Agent selanjutnya yang akan meneruskan pekerjaan ini diharap memperhatikan hal-hal berikut:

1. **Commit Patch Normalizer**: Perbaikan *reject-to-DLQ* pada `src/skills/telemetry/normalizer/executor.py` sejauh ini baru diimplementasikan secara langsung di server lokal. **Lakukan verifikasi status file, kemudian commit dan push** perubahan tersebut ke Git dengan referensi perbaikan DLQ.
2. **Observasi DLQ (`dcim.dlq.parse-failure`)**: Pantau isi pesan pada DLQ. Cek apabila ada payload metrik dari 5 tipe perangkat resmi yang secara tidak sengaja terlempar ke DLQ akibat struktur data yang belum terpetakan. Jika terjadi, investigasi skema payload aslinya.
3. **Monitor Lag Kafka**: Pantau perintah `kafka-consumer-groups.sh` untuk group `dcim_python_normalizer_group` dan `dcim-es-consumer`. Pastikan offset `LAG` selalu mendekati 0 atau rutin diselesaikan secara *real-time*.
4. **Verifikasi Kibana (Opsional)**: Pastikan grafik pemantauan yang bergantung pada indeks `dcim-metrics-unified-*` telah kembali menampilkan data aktual dengan normal.
