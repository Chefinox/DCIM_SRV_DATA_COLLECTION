# Log Taxonomy & Retention Policy (v4.0)

Dokumen ini mendefinisikan standar (taksonomi) struktur log untuk seluruh komponen DCIM dan mengatur kebijakan retensi data log terpusat di Elasticsearch.

## 1. Log Taxonomy (Format JSON Standar)

Seluruh komponen *custom* berbasis Python di ekosistem DCIM WAJIB menggunakan modul `src.observability.logging.dcim_logger` untuk menghasilkan log JSON dengan format berikut:

```json
{
  "@timestamp": "2026-06-12T16:34:10.123456Z",
  "service": "dcim-itop-consumer",
  "level": "INFO",
  "message": "Processed 10 events successfully",
  "event_type": "sync_success",          // (Opsional)
  "device_type": "Switch",               // (Opsional)
  "hostname": "sw-core-01",              // (Opsional)
  "exception": "Traceback..."            // (Otomatis ditambahkan jika ada Error)
}
```

### 1.1 Mandatory Fields
- `@timestamp`: Waktu terjadinya *event* dalam format ISO-8601 (UTC).
- `service`: Nama modul/service yang menghasilkan log (misal: `itop-redis-sync`, `telegram-alerter`).
- `level`: Tingkat log (`INFO`, `WARN`, `ERROR`, `DEBUG`).
- `message`: Deskripsi *event* atau error (harus jelas dan dapat dibaca manusia).

### 1.2 Routing Tags (Khusus Filebeat)
Filebeat akan membaca log dan merutekannya ke index yang berbeda berdasarkan *tags/fields*:
- **Aplikasi (Default)** → `dcim-logs-app-*`
- **Keamanan (Security)** → `dcim-security-events-*` (Jika log mengandung kata kunci otentikasi gagal, atau akses tidak sah).

## 2. Retention Policy (Kebijakan Penyimpanan Log)

Mengingat volume log harian dapat mencapai ukuran GB (terutama dengan adanya *Poller* berfrekuensi tinggi), data log akan dikelola menggunakan Elasticsearch *Index Lifecycle Management (ILM)*.

### 2.1 Fase Penyimpanan (Tiers)
| Tipe Log | Index Pattern | Hot Phase (Read/Write) | Warm Phase (Read-Only) | Cold Phase (Archive) | Delete (Penghapusan) |
|---|---|---|---|---|---|
| **DCIM Metrics** | `dcim-metrics-unified-*` | 14 Hari | 30 Hari | Tidak ada | **45 Hari** |
| **App Logs (INFO/WARN)** | `dcim-logs-app-*` | 7 Hari | 14 Hari | Tidak ada | **21 Hari** |
| **Error/DLQ Logs** | `dcim-logs-error-*` | 30 Hari | 60 Hari | Tidak ada | **90 Hari** |
| **Security Events** | `dcim-security-events-*` | 30 Hari | 90 Hari | 365 Hari | **1 Tahun** |

### 2.2 Penjelasan Retensi
- **Metrics:** Dibatasi hingga 45 hari karena memakan *storage* paling besar. Tim AI diwajibkan melakukan ekstraksi atau peringkasan (aggregasi) data jika butuh tren tahunan.
- **Log Aplikasi:** Log operasional harian seperti sinkronisasi sukses hanya relevan selama 1-3 minggu.
- **Log Keamanan (ST-017-04):** Log yang berkaitan dengan upaya intrusi atau perubahan kredensial disimpan lebih lama (1 tahun) demi kebutuhan *Audit & Compliance*.

## 3. Implementasi
Kebijakan ini di- *enforce* pada sisi pengiriman melalui **Filebeat**, dan pada sisi Elasticsearch melalui **Index Lifecycle Policies**.
