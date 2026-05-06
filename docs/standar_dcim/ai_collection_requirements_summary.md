# Rangkuman Persyaratan Integrasi Ralph CMDB untuk AI Data Collection

Dokumen ini berisi spesifikasi teknis agar output dari proses **Data Collection** dapat disinkronisasikan secara otomatis ke dalam **Ralph CMDB**.

---

## 1. Spesifikasi Output JSON (Syarat Utama)
AI Data Collection harus menghasilkan file JSON dengan struktur berikut agar dapat dibaca oleh `ralph_sync_agent.py`:

```json
[
  {
    "serial": "DS-2CD1043G0E-I...",  // Wajib: Sebagai Primary Key pencarian di Ralph
    "hostname": "CCTV-R-MEETING",    // Opsional
    "model": "DS-2CD1043G0E-I",     // Opsional
    "firmware": "V5.5.90",           // Sangat Penting: Versi firmware aktual hardware
    "status": "Online"               // Opsional
  }
]
```

## 2. Parameter API Ralph
Sistem sinkronisasi saat ini telah dikonfigurasi dengan parameter berikut:
- **URL Endpoint**: `http://192.168.101.73:8088/api/data-center-assets/`
- **Metode HTTP**: `PATCH`
- **Authentication**: Terpusat di `d:\antigravity\DCIM\configs\.env`

## 3. Aturan Pemetaan Data (Field Mapping)
Data yang diterima akan dipetakan ke field Ralph sebagai berikut:
1.  **Serial Number** (`serial`) -> Digunakan untuk mencari `id` asset di Ralph.
2.  **Firmware** (`firmware`) -> Akan memperbarui field standar `firmware_version` di Ralph.
3.  **Logging** -> Status sinkronisasi otomatis akan ditambahkan ke field `remarks` beserta timestamp update.

---

## 4. Status Kesiapan Lingkungan
- [x] **API Access**: Terverifikasi (Bisa baca dan tulis).
- [x] **Config File**: `.env` sudah siap di direktori project.
- [x] **Sync Script**: `ralph_sync_agent.py` sudah tersedia untuk eksekusi massal.
- [!] **NetBox Status**: Saat ini fokus pada Ralph (NetBox berada di PC berbeda dan akan diintegrasikan kemudian).

---
**Disusun Oleh:** Antigravity DCIM Agent
**Tanggal:** 21 April 2026
