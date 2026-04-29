# Versioning & Change Management Standard (FIT041)

> [!IMPORTANT]
> **Compliance**: Technical Requirements FIT041 Section 2.1.3
> **Status**: Approved for Production
> **Last Update**: 2026-04-29

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

## 4. Log Perubahan Sistem (Sample)

| Versi | Waktu (WIB) | Perubahan Utama | Status |
| :--- | :--- | :--- | :--- |
| **v3.1.2** | 2026-04-29 16:35 | Sinkronisasi Hostname Ralph (Hapus prefix FALAH01-) | Active |
| **v3.1.1** | 2026-04-29 15:10 | Perbaikan Polling BMC Redfish (Safe Interval 120s) | Active |
| **v3.0.0** | 2026-04-28 09:00 | Migrasi ke Unified Kafka Pipeline (MT014 Architecture) | Baseline |

---
**Catatan**: Pelanggaran terhadap siklus re-deploy (mengubah flow aktif tanpa stop/start ulang) dapat menyebabkan data corrupt di Kafka.
