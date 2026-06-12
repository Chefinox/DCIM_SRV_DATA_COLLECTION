# Batasan Data Historis Elasticsearch (DCIM v4.0)

**Penting untuk Tim AI/ML:**

Sistem DCIM baru saja mengalami transisi ke arsitektur v4.0 pada tanggal **12 Juni 2026**. Selama proses migrasi, seluruh *index* Elasticsearch (`dcim-metrics-unified-*`) harus diatur ulang (di-*reset*) untuk mengatasi masalah *lag* pada Kafka Consumer (`telegraf_unified_final`) dan pembengkakan log (DLQ).

Sebagai dampaknya, harap perhatikan batasan data historis berikut sebelum melakukan *training* model:

1. **Titik Awal Data (Epoch):**
   Data historis yang valid dan *clean* baru tersedia mulai tanggal **12 Juni 2026 pukul 16:00 WIB**.
   *Data sebelum tanggal ini tidak tersedia di Elasticsearch.*

2. **Periode Observasi yang Disarankan:**
   Model AI (terutama untuk prediktif) biasanya membutuhkan data historis minimal 30 hari. Karena itu, fitur AI disarankan baru dilatih/dijalankan dengan *dataset* penuh pada atau setelah tanggal **12 Juli 2026**.

3. **Kelengkapan Fitur (Features Completeness):**
   - Mulai tanggal 12 Juni 2026, fitur `serial_number`, `model`, dan `firmware` telah diseragamkan sebagai `tags` (bukan sekadar `fields`) untuk semua perangkat (Switch, NAS, UPS).
   - Pengayaan data dari iTop CMDB (berupa `brand`, `location`, `rack`, dll) akan terisi dengan kelengkapan ~100% pada *event* baru.

**Tindakan yang Diperlukan:**
- Jangan gunakan *range* waktu sebelum 12 Juni 2026 saat melakukan kueri Elasticsearch untuk *training* data.
- Sesuaikan *baseline* energi dan operasional Anda dengan data setelah transisi ini.

*Dokumen ini diterbitkan oleh tim Infrastruktur pada 12 Juni 2026.*
