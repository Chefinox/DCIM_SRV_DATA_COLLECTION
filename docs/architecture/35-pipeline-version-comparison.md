# 35. Pipeline Version Comparison: v3.4 vs v4.0

**Tanggal**: 2026-05-07  
**Status**: Rollback to v3.4 Logic (within v4.0 Structure)

## 1. Latar Belakang: Mengapa v4.0 (Modular) Dibuat?
Arsitektur **v4.0 (Agentic Modular)** diperkenalkan untuk mempersiapkan sistem DCIM menghadapi integrasi AI yang lebih mendalam. Tujuannya adalah:
1. **Decoupling Logic**: Memisahkan driver teknis (Tools) dari logika bisnis (Skills).
2. **Scalability**: Memudahkan penambahan fitur baru (seperti AI Agent) tanpa mengganggu kode pemrosesan utama.
3. **Reusability**: Komponen seperti `PostgresClient` dapat digunakan oleh berbagai skrip sekaligus.

## 2. Perbandingan Teknis

| Fitur | v3.4 (Stable / Monolith) | v4.0 (Modular / Agentic) |
| :--- | :--- | :--- |
| **Arsitektur** | Monolitik (Skrip besar per tahap). | Modular (4-Layer: Tools, Schemas, Skills, Workflows). |
| **Performa** | Sangat Stabil & Cepat (minimal overhead). | Fleksibel (sedikit overhead karena abstraksi). |
| **Maintenance** | Sulit di-debug jika skrip bertambah besar. | Sangat mudah dikelola karena kode terfragmentasi rapi. |
| **Kesiapan AI** | Rendah (Logic terikat pada data flow). | Tinggi (Siap untuk integrasi AI Agent). |
| **Reliabilitas** | **Teruji (Proven)** dalam produksi. | Fase eksperimental (Perlu pengujian beban lanjut). |

## 3. Analisis Kelebihan & Kekurangan

### v3.4 (Legacy Logic)
*   ✅ **Kelebihan**: Logika penanganan data yang "keras" dan sudah teruji menangani ribuan pesan per detik tanpa kegagalan (SLA Tinggi).
*   ❌ **Kekurangan**: Struktur folder berantakan (`scripts/`, `phase2/`, `scratch/` tercampur) dan sulit untuk menambahkan modul cerdas (AI).

### v4.0 (Modular Structure)
*   ✅ **Kelebihan**: Struktur folder sangat rapi dan mengikuti standar industri (Clean Code). Siap untuk diekspansi menjadi sistem otonom.
*   ❌ **Kekurangan**: Perubahan pada layer abstraksi terkadang menyebabkan masalah kompatibilitas pada skrip lama yang mengharapkan input linear.

## 4. Keputusan Akhir: Hybrid v3.5 (Current)
Kita memutuskan untuk menggunakan **Struktur v4.0** (folder `src/`) namun dengan **Logika v3.4** di dalamnya. Hal ini memberikan kita:
1. Keamanan dan stabilitas pipeline yang sudah terbukti.
2. Kerapihan direktori untuk mempermudah audit dan pengembangan di masa depan.

---
**Rekomendasi**: Pertahankan struktur `src/` ini. Jika di masa depan ingin mengaktifkan fitur AI, kita cukup menambahkan `Workflow` baru tanpa merusak `Skill` v3.4 yang sudah stabil.
