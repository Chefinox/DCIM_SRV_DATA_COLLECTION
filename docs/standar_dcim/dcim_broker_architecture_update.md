# Dokumentasi Pembaruan Arsitektur DCIM (Broker & CMDB Sync)
**Tanggal Pembaruan:** 21 April 2026
**Status:** Operasional (100% Active)

---

## 1. Integrasi CMDB (Ralph Sync Agent)
Telah diimplementasikan sistem **Living Inventory** yang menghubungkan kondisi fisik perangkat dengan database Ralph.
*   **Skrip Utama:** `/home/infra/dcim_metrics_project/scripts/ralph_sync_agent.py`
*   **Fungsi:** Mendeteksi perubahan Firmware secara otomatis di hardware dan melakukan `PATCH` ke API Ralph.
*   **Otomatisasi:** Berjalan setiap **1 menit** melalui Cron Job.
*   **Kredensial:** Disimpan secara terpusat di `.env`.

## 2. Arsitektur Data Pipeline (Message Broker)
Sistem telah bermigrasi dari pengiriman langsung menjadi berbasis antrean (**Full Flow**).
*   **Broker:** RabbitMQ (Berjalan di Docker Container: `rabbit-broker`).
*   **Producer (Layer 1):** Telegraf Utama (`telegraf.service`).
    *   Tugas: Mengumpulkan metrik dan mengirim ke Exchange AMQP `telegraf`.
*   **Consumer (Layer 2):** Telegraf Consumer (`telegraf-consumer.service`).
    *   Tugas: Mengambil data dari antrean RabbitMQ dan menyalurkannya ke Elasticsearch berdasarkan routing (Metrics vs Inventory).

## 3. Pembaruan Infrastruktur NAS
Akses ke penyimpanan personel telah diatur secara permanen.
*   **Mount Point:** `/mnt/nas_personel` (Terhubung ke Share `DIV - INFRASTRUCTURE`).
*   **Otomatisasi:** Terdaftar di `/etc/fstab` (Mount otomatis saat reboot).
*   **Kredensial:** Menggunakan akun `syauqi` yang tersertifikasi secara aman di `/etc/cifs-credentials`.

## 4. Konfigurasi Layanan & Keamanan
Untuk menjamin stabilitas akses ke skrip Python dan file konfigurasi di berbagai direktori:
*   **User Service:** `telegraf` dan `telegraf-consumer` kini dikonfigurasi untuk berjalan sebagai **Root**.
*   **Log & Debugging:** Aktivitas Consumer terpantau di `journalctl -u telegraf-consumer`.

---
**Penyusun:** Antigravity DCIM Agent
**Target Dashboard:** Kibana Dashboard (Relational via Serial Number)
