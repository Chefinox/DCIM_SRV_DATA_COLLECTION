# Versioning & Change Management Standard (FIT041)

> [!IMPORTANT]
> **Compliance**: Technical Requirements FIT041 Section 2.1.3
> **Status**: Approved for Production
> **Last Update**: 2026-05-04

## 1. Definisi Standar (Ref: 2.1.3)
Sistem DCIM wajib mengelola siklus hidup workflow dengan kontrol versi yang ketat untuk mencegah kegagalan pipeline akibat perubahan tidak terencana.

| Kode | Persyaratan | Mekanisme Implementasi |
| :--- | :--- | :--- |
| **2.1.3.1** | Penyimpanan Versi Workflow | Integrasi NiFi Registry & Git Version Control. |
| **2.1.3.2** | Metadata Perubahan | Versi, Deskripsi (Changelog), & Timestamp wajib tercatat. |
| **2.1.3.3** | Re-deploy Mandatory | Workflow yang dimodifikasi harus dihentikan dan dijalankan ulang (Re-deploy). |

## 2. Arsitektur Versioning

### A. NiFi Enrichment Flow
Seluruh Process Group di NiFi terhubung ke **NiFi Registry**. Setiap perubahan flow (drag-and-drop processor, update config) akan memicu status *Modified*.
- **Mencatat Versi**: User wajib melakukan `Commit Local Changes` sebelum perubahan dianggap permanen.
- **Log Perubahan**: Dialog komit mewajibkan pengisian deskripsi perubahan utama.

### B. Python Processing Scripts
Skrip normalisasi dan sinkronisasi dikelola melalui repository lokal Git di `/home/infra/dcim_metrics_project/`.
- **Command Audit**:
  ```bash
  git log --oneline --graph --all
  ```

## 3. Alur Kerja Perubahan (Change Management)
Setiap perubahan wajib melalui tahapan berikut:

1.  **Identifikasi**: Menentukan komponen yang akan diubah (misal: penambahan field baru).
2.  **Modifikasi**: Melakukan perubahan pada level staging/draft.
3.  **Documentation (Versioning)**:
    - Melakukan tagging versi pada repository.
    - Mencatat alasan perubahan pada log sistem.
4.  **Re-deployment**:
    - **NiFi**: Restart Process Group / Update Version in Canvas.
    - **Scripts**: `systemctl restart [service_name]`

## 4. Log Perubahan Sistem

| Versi | Waktu (WIB) | Perubahan Utama | Status |
| :--- | :--- | :--- | :--- |
| **v3.2.0** | 2026-05-04 00:05 | Server Deep Sync V7: Pagination fix, Robust Pruning, Ethernet Speed mapping. Crontab aktif `*/5 * * * *`. | **Active** |
| **v3.1.5** | 2026-05-03 23:40 | Server Deep Sync V6: Robust Pruning (delete duplikat via SN comparison). | Superseded |
| **v3.1.4** | 2026-05-03 21:52 | Server Deep Sync V5: Pruning logic awal + Ethernet Speed mapping (SPEED_MAP). | Superseded |
| **v3.1.3** | 2026-05-03 20:08 | Server Deep Sync V4: Disk model dari `Name`, slot dari `PhysicalLocation.PartLocation`, RAM dari `VendorID`. | Superseded |
| **v3.1.2** | 2026-05-03 18:31 | Server Deep Sync V3: Management IP & Management Hostname diupdate via `/api/ipaddresses/` object. | Superseded |
| **v3.1.1** | 2026-05-03 18:02 | Server Deep Sync V2: Hostname dari `Chassis/1 → Location.PostalAddress.Name`. | Superseded |
| **v3.1.0** | 2026-05-03 17:00 | `server_deep_sync.py` pertama kali dibuat. Sinkronisasi komponen server ke Ralph CMDB. | Superseded |
| **v3.0.2** | 2026-04-29 16:35 | Sinkronisasi Hostname Ralph (Hapus prefix FALAH01-) | Active |
| **v3.0.1** | 2026-04-29 15:10 | Perbaikan Polling BMC Redfish (Safe Interval 120s) | Active |
| **v3.0.0** | 2026-04-28 09:00 | Migrasi ke Unified Kafka Pipeline (MT014 Architecture) | Baseline |

## 5. Crontab Aktif

| Schedule | Script | Log |
| :--- | :--- | :--- |
| `*/5 * * * *` | `scripts/server_deep_sync.py` | `logs/server_deep_sync_cron.log` |

> [!NOTE]
> Untuk menambah cron job baru, selalu gunakan `crontab -e` dan pastikan script sudah diuji manual terlebih dahulu.

---
**Catatan**: Pelanggaran terhadap siklus re-deploy (mengubah flow aktif tanpa stop/start ulang) dapat menyebabkan data corrupt di Kafka.
