# MikroTik SNMP OID Technical Detailed Reference

Dokumen ini memberikan rincian teknis mendalam mengenai OID yang digunakan untuk monitoring perangkat MikroTik di infrastruktur DCIM.

> [!IMPORTANT]
> **Peringatan Universalitas**: Beberapa OID sensor kesehatan (Health) bersifat **model-specific**. OID yang bekerja di satu model (misal: CCR) mungkin akan mengembalikan error `No Such Object` pada model lain (misal: CRS312).

---

## 1. Identitas Perangkat (Global OIDs)
Gunakan OID ini untuk menarik informasi identitas dasar perangkat. Berlaku untuk semua model MikroTik.

| Nama Parameter | OID Lengkap | Tipe Data | Keterangan |
| :--- | :--- | :--- | :--- |
| **System Description** | `.1.3.6.1.2.1.1.1.0` | String | Model, OS, Build date |
| **Router Board Model** | `.1.3.6.1.4.1.14988.1.1.1.1.0` | String | Contoh: `CCR2004-16G-2S+` |
| **Serial Number** | `.1.3.6.1.4.1.14988.1.1.7.3.0` | String | Contoh: `HC707RR1T60` (Verified ✅) |
| **RouterOS Version** | `.1.3.6.1.4.1.14988.1.1.4.4.0` | String | Contoh: `7.16.2` |
| **System Uptime** | `.1.3.6.1.2.1.1.3.0` | TimeTicks | Waktu sejak reboot terakhir |

---

## 2. Sensor Kesehatan (Hardware Health)
MikroTik menggunakan tabel sensor dinamis (`mtxrHlBaseTable`). Nilai berada pada kolom `.3` (Value), dan tipe sensor pada kolom `.4`.

### A. Mapping Sensor Berdasarkan Verifikasi Lapangan
Hasil testing menunjukkan variasi index sensor antar perangkat:

| Nama Sensor | Unit | OID CCR2004 | OID CRS312 | OID CRS354/326 | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **CPU Temp** | °C | `.100.1.3.17` | `.100.1.3.52`* | - | Tergantung CPU Arch |
| **SFP Temp** | °C | `.100.1.3.50` | `.100.1.3.50` | `.100.1.3.50` | **Universal** |
| **Switch Temp** | °C | - | `.100.1.3.51` | `.100.1.3.51` | Hanya di Switch |
| **Board Temp 1** | °C | `.100.1.3.7101`| - | `.100.1.3.7101` | **Model-Specific** |
| **Fan 1 Speed** | RPM | `.100.1.3.7001`| `.100.1.3.7001` | `.100.1.3.7001` | Umum di rackmount |
| **PSU 1 State** | Enum | `.100.1.3.7401`| `.100.1.3.7401` | `.100.1.3.7401` | Umum di Dual-PSU |

*\*Catatan: OID dasar Mikrotik Health adalah `.1.3.6.1.4.1.14988.1.1.3`*

### B. Interpretasi Nilai (Status PSU & Fan)
Untuk kolom State/Status (Tipe 6), nilai integer yang diterima memiliki arti:
- **0**: **OK** (Berjalan normal / Terdeteksi).
- **1**: **Fail** (Kegagalan / Tidak terdeteksi power).
- **Lainnya**: Lihat `/system health print` untuk verifikasi spesifik firmware.

---

## 3. Rekomendasi: Pendekatan Dinamis (Table)
Untuk menghindari error `No Such Object`, sangat disarankan menggunakan konfigurasi **Table SNMP** di Telegraf daripada mendaftarkan field per index.

**Contoh Struktur Table:**
```toml
[[inputs.snmp.table]]
  name = "mikrotik_health"
  oid = ".1.3.6.1.4.1.14988.1.1.3.100.1" # mtxrHlBaseTable
  
  [[inputs.snmp.table.field]]
    name = "sensor"
    oid = ".1.3.6.1.4.1.14988.1.1.3.100.1.2" # mtxrHlBaseName
    is_tag = true

  [[inputs.snmp.table.field]]
    name = "value"
    oid = ".1.3.6.1.4.1.14988.1.1.3.100.1.3" # mtxrHlBaseValue
```

---

## 4. Troubleshooting Table
| Gejala | Penyebab | Solusi |
| :--- | :--- | :--- |
| `No Such Object` | Index OID tidak ada di model hardware tersebut (misal: OID Board Temp di CRS312). | Gunakan metode Table (Poin 3) atau cek index manual via `snmpwalk`. |
| `Timeout` | Perangkat down, IP salah, atau port 161 diblokir firewall (Input Chain). | Pastikan `/snmp set enabled=yes` dan cek access-list. |
| `Nilai 0` | Sensor mungkin tidak aktif atau hardware tidak mendukung pembacaan real-time. | Cek `/system health print` di CLI. |

---
*Terakhir diupdate: 2026-04-16*
