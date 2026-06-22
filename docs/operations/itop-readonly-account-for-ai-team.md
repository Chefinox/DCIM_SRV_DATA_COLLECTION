# Membuat Akun iTop Read-Only untuk Tim AI

> **Versi**: 1.0 · **Tanggal**: 2026-06-17
> **Tujuan**: Menyediakan akun iTop berhak **baca-saja** untuk tim AI, agar mereka bisa menelusuri relasi CMDB (impact analysis, contact, koneksi antar-CI) **tanpa** memakai akun `admin` yang berhak tulis penuh.
> **Selaras**: `docs/development/itop-api-baseline-for-agents.md` · `docs/architecture/v4.2-pipeline-architecture.md` §16 (L14).

---

## Konsep singkat (model izin iTop)

iTop memisahkan **login** (`UserLocal`) dari **identitas orang** (`Person`), dan hak akses ditentukan oleh **Profile** yang dilekatkan ke user. Untuk baca-saja, gunakan profil bawaan:

| Profile bawaan | Akses |
|---|---|
| **Portal user** | terlalu sempit (hanya portal tiket) — JANGAN |
| **Configuration Manager** | baca + tulis CI — terlalu luas |
| **Service Desk Agent** | baca luas + tulis tiket — terlalu luas |
| ✅ **REST Services User** | khusus untuk akses REST API (read via `core/get`) |

> **Rekomendasi**: kombinasikan **REST Services User** (agar bisa pakai API) dengan profil baca seperlunya. Untuk benar-benar read-only, **jangan** beri profil yang mengandung hak tulis (Configuration Manager/Administrator). Bila perlu cakupan baca lebih luas dari sekadar REST, buat **Profile kustom read-only** (Opsi B).

---

## Opsi A — Lewat UI iTop (disarankan, paling aman)

Langkah ini dilakukan oleh **admin infra** di `http://10.70.0.56:8080`.

### 1. (Opsional) Buat Person untuk tim AI
`Data administration ▸ Persons ▸ New`:
- **Name / First Name**: `AI` / `Team`
- **Organization**: `PT. Falah Inovasi Teknologi`
- **Email**: email tim AI

### 2. Buat User Login
`Administration ▸ User Accounts ▸ New`:
- **Login**: `ai_readonly`
- **Type**: `Local User` (UserLocal)
- **Password**: buat password kuat (acak ≥20 char)
- **Contact (Person)**: pilih Person dari langkah 1 (atau biarkan kosong bila tidak perlu)
- **Status**: `enabled`
- **Profiles**: tambahkan **`REST Services User`** (wajib agar API jalan). Bila tim AI juga perlu menjelajah relasi luas via API, tambahkan profil baca kustom dari Opsi B. **Jangan** tambahkan profil bertulis.

### 3. Simpan & catat kredensial
Simpan login/password di secret store, lalu serahkan ke tim AI lewat kanal aman (bukan chat biasa/Git).

---

## Opsi B — Profile kustom "AI Read-Only" (bila butuh baca luas)

`REST Services User` saja kadang membatasi class yang bisa dibaca. Untuk baca **semua class CMDB** tanpa hak tulis:

`Administration ▸ Profiles ▸ New`:
- **Name**: `AI Read-Only`
- **Description**: `Read-only access for AI team (CMDB relations)`
- Pada matriks **Grant**, untuk class-class yang relevan (`Server`, `NetworkDevice`, `StorageSystem`, `Peripheral`, `PowerSource`, `Location`, `Rack`, `Contact`, dan link class relasi), centang **hanya** kolom **Read**. Biarkan **Create/Modify/Delete/Bulk** kosong.

Lalu lekatkan profil ini + `REST Services User` ke user `ai_readonly` (langkah 2 di atas).

> Selalu sertakan **`REST Services User`**; tanpa itu, login apa pun ditolak saat memanggil `rest.php`.

---

## Verifikasi (uji baca BOLEH, tulis DITOLAK)

Ganti `<PWD>` dengan password akun, jalankan di host:

```bash
ITOP_URL="http://10.70.0.56:8080/webservices/rest.php?version=1.3"

# T1 — READ harus BERHASIL (code 0, ada objects)
curl -s "$ITOP_URL" \
  --data-urlencode "auth_user=ai_readonly" \
  --data-urlencode "auth_pwd=<PWD>" \
  --data-urlencode 'json_data={"operation":"core/get","class":"Server","key":"SELECT Server","output_fields":"name,serialnumber,status"}' \
  | python3 -m json.tool | head -20

# T2 — WRITE harus DITOLAK (code != 0 / "not allowed")
curl -s "$ITOP_URL" \
  --data-urlencode "auth_user=ai_readonly" \
  --data-urlencode "auth_pwd=<PWD>" \
  --data-urlencode 'json_data={"operation":"core/update","class":"Server","key":1,"comment":"selftest readonly","fields":{"status":"production"}}' \
  | python3 -m json.tool | head -20
```

**Hasil yang benar**:
- T1 → `"code": 0` dan daftar server muncul.
- T2 → `"code"` non-nol atau pesan izin ditolak (mis. *"not allowed"*/*"Security issue"*). Jika T2 berhasil meng-update, profil masih terlalu luas — cabut profil bertulis.

---

## Setelah akun jadi

1. Berikan login + password ke tim AI lewat kanal aman.
2. Tim AI mengisi env `ITOP_API_USER=ai_readonly` dan `ITOP_API_PASS=<PWD>` (lihat `docs/development/itop-api-baseline-for-agents.md`).
3. Akun `admin` tetap hanya untuk service internal pipeline (sync), tidak dibagikan keluar.
