# 39. Logging Audit & Gap Analysis

**Versi Dokumen**: 1.0 | **Tanggal**: 2026-06-02

## 1. Sumber Log Saat Ini (Current State)

| Komponen / Script | Lokasi Log | Ukuran | Sistem Rotasi | Catatan / Masalah |
|---|---|---|---|---|
| **kafka_to_es_sync.py** | `logs/kafka_to_es_sync.log` | 4.5 GB | Tidak ada | **KRITIS**: File sangat besar (4.5GB). Wajib segera dirotasi. |
| **cctv poller service** | `logs/cctv_poller_error.log` | 76 MB | Tidak ada | Cukup besar, perlu logrotate. |
| **cctv poller service** | `logs/cctv_poller.log` | 233 KB | Tidak ada | - |
| **hikvision_poller.py** | `scripts/hikvision_poller.log` | 47 MB | Tidak ada | Salah penempatan direktori (di `scripts/` bukan `logs/`), tidak ada rotasi. |
| **dcim_postgres_consumer_v2** | `logs/dcim_postgres_consumer_v2.log` | 88 MB | Tidak ada | Cukup besar. |
| **ralph_sync** | `logs/ralph_sync.log` | 91 MB | Tidak ada | Log lama dari April, masih ada. |
| **dcim_ralph_sync.py** | `logs/dcim_ralph_sync.log` | 7.0 MB | Tidak ada | - |
| **threshold alerter** | `logs/threshold_alerts.log` | 1.3 MB | Tidak ada | - |
| **Systemd Services** | `journalctl -u <service>` | N/A | Systemd default | Sulit untuk pencarian terpusat karena tidak dikirim ke Elastic Stack. |
| **Docker Containers** | Docker default json-file | Bervariasi | Docker default | Tidak ada centralized view. |

## 2. Analisis Gap

1. **Struktur Log**: Sebagian besar skrip menggunakan `logging` Python bawaan (plaintext), bukan JSON terstruktur (structured logging). Ini membuat parsing di Elasticsearch menjadi sulit.
2. **Lokasi Log**: Ada skrip yang menulis log di luar direktori `logs/` (contoh: `scripts/hikvision_poller.log`).
3. **Log Rotation**: Tidak ada `logrotate` yang aktif untuk file di dalam folder `logs/`. Hal ini menyebabkan file seperti `kafka_to_es_sync.log` membengkak hingga 4.5 GB.
4. **Sentralisasi**: Semua log masih berada di server lokal (10.70.0.56) dan belum dikirim/di-indeks ke Elasticsearch (`dcim-logs-*`) menggunakan agen pengirim (seperti Filebeat).

## 3. Rencana Aksi (Remediasi)

1. Menerapkan modul logger sentral (`dcim_logger.py`) yang menghasilkan log dalam format JSON.
2. Mengubah semua skrip Python untuk menggunakan modul logger sentral tersebut.
3. Mengatur kebijakan rotasi menggunakan `logrotate` untuk mengontrol ukuran file log secara otomatis.
4. Mengkonfigurasi Filebeat untuk mengirim seluruh log aplikasi dan services dari direktori `logs/` dan `journalctl` ke Elasticsearch.
5. Membangun Dashboard Kibana untuk log sentral DCIM.
