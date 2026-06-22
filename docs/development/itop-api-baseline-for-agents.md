# iTop API Baseline for AI Agents

**Version**: 1.2  
**Date**: 2026-06-17  
**Purpose**: Referensi untuk AI agent/tim AI yang perlu query relasi aset mendalam (impact analysis, contact, koneksi antar-CI) di iTop CMDB.
**Selaras**: `docs/architecture/v4.2-pipeline-architecture.md` §16 (L14 — Data Interface for AI).

> **Peran iTop untuk AI (v4.2)**: iTop = sumber **relasi antar-perangkat** (CMDB), pelengkap data time-series di PostgreSQL. Untuk fitur dasar (`site`, `rack_name`) cukup pakai `v_train_*` di PostgreSQL; query langsung ke iTop hanya untuk relasi mendalam (lihat §8).
>
> ⚠️ **Keamanan kredensial**: iTop **belum punya role read-only** seperti `dcim_ai_reader` di PostgreSQL. Akun `admin` punya akses tulis penuh. **Jangan tanam password di kode/repo.** Ambil dari environment (`ITOP_API_USER` / `ITOP_API_PASS`) yang diisi dari secret store. Bila tim AI hanya perlu **baca relasi**, mintakan akun iTop dengan profil read-only ke admin infra (rekomendasi), bukan memakai `admin`.

---

## 1. Endpoint dan Autentikasi

**Base URL**: `http://10.70.0.56:8080/webservices/rest.php`  
**Method**: `POST`  
**Content-Type**: `application/x-www-form-urlencoded`  
**API Version**: 1.3 (ditambahkan sebagai query parameter `?version=1.3`)

### Autentikasi

| Parameter | Description | Sumber nilai |
|---|---|---|
| `auth_user` | Username iTop | env `ITOP_API_USER` (mis. `admin`) |
| `auth_pwd` | Password iTop | env `ITOP_API_PASS` (dari secret store — **jangan hardcode**) |

### Payload Format

Setiap request dikirim sebagai form-encoded dengan parameter `json_data` berisi JSON string:

```python
import os, requests, json

ITOP_URL = "http://10.70.0.56:8080/webservices/rest.php?version=1.3"
ITOP_USER = os.environ["ITOP_API_USER"]   # mis. "admin"
ITOP_PASS = os.environ["ITOP_API_PASS"]   # dari secret store, jangan hardcode

def itop_post(payload: dict) -> dict:
    data = {
        "auth_user": ITOP_USER,
        "auth_pwd": ITOP_PASS,
        "json_data": json.dumps(payload),
    }
    r = requests.post(ITOP_URL, data=data, timeout=15)
    r.raise_for_status()
    return r.json()
```

---

## 2. Operasi Dasar

### 2.1 `core/get` — Membaca CI

```python
payload = {
    "operation": "core/get",
    "class": "Server",
    "key": "SELECT Server WHERE status = 'production'",
    "output_fields": "name,serialnumber,location_name,rack_name,brand_name,model_name,status"
}
result = itop_post(payload)
# result["objects"] → dict { "Server::3125": { "fields": {...}, "class": "Server", "key": "3125" } }
```

**Parameter opsional**:
- `"limit": 100` — Batasi jumlah hasil
- `"page": 1` — Pagination (mulai dari 1)

### 2.2 `core/create` — Membuat CI Baru

```python
payload = {
    "operation": "core/create",
    "class": "Server",
    "comment": "Auto-sync from DCIM pipeline",
    "fields": {
        "name": "SERVER-NEW-01",
        "serialnumber": "ABC123XYZ",
        "org_id": 1,                    # FK ke Organization (default: 1 = PT. Falah Inovasi Teknologi)
        "status": "production",
        "managementip": "10.50.0.10",
        "brand_id": "SELECT Brand WHERE name = 'Lenovo'",
        "model_id": "SELECT Model WHERE name = '7D76CTO1WW'",
        "location_id": "SELECT Location WHERE name = 'Ruang Server'",
        "rack_id": "SELECT Rack WHERE name = 'Rack Server 1'"
    }
}
result = itop_post(payload)
# result["objects"]["Server::NEW::1234"] → object dengan key baru
```

**Catatan**:
- FK fields (`brand_id`, `model_id`, `location_id`, `rack_id`) bisa berupa OQL sub-query atau numeric ID
- `org_id` wajib diisi (default: `1`)
- `comment` wajib untuk operasi create/update/delete

### 2.3 `core/update` — Update Atribut CI

```python
# Penting: "key" harus berupa numeric object ID (bukan nama/OQL)
payload = {
    "operation": "core/update",
    "class": "Server",
    "key": 3125,                        # Numeric ID dari core/get response
    "comment": "Auto-update from DCIM pipeline",
    "fields": {
        "managementip": "10.50.0.99",
        "status": "production"
    }
}
result = itop_post(payload)
# result["objects"]["Server::3125"]["code"] → 0 jika sukses
```

**Mendapatkan ID**:
```python
# Dari core/get response:
# "Server::3125" → key = 3125
key_str = list(result["objects"].keys())[0]  # "Server::3125"
numeric_id = key_str.split("::")[1]          # "3125"
```

### 2.4 `core/apply_stimulus` — Mengubah Lifecycle State

```python
payload = {
    "operation": "core/apply_stimulus",
    "class": "Server",
    "key": 3125,
    "comment": "Moving to production",
    "stimulus": "ev_production"         # Stimulus name (lihat tabel di bawah)
}
result = itop_post(payload)
```

**Stimulus yang umum**:

| Stimulus | Dari | Ke | Deskripsi |
|---|---|---|---|
| `ev_stock` | (any) | stock | Pindah ke gudang |
| `ev_production` | stock / implementation | production | Aktifkan ke produksi |
| `ev_obsolescence` | production | obsolete | Tandai obsolete |

---

## 3. OQL Query Examples

OQL (Object Query Language) adalah query language iTop untuk mencari CI.

### 3.1 Server

```sql
-- Semua server di production
SELECT Server WHERE status = 'production'

-- Server berdasarkan serial number
SELECT Server WHERE serialnumber = 'J901GKXY'

-- Server berdasarkan nama
SELECT Server WHERE name = 'SERVER-HCI-01'

-- Server di rack tertentu
SELECT Server WHERE rack_name = 'Rack Server 1'

-- Server berdasarkan management IP
SELECT Server WHERE managementip LIKE '10.50.0.%'
```

### 3.2 NetworkDevice

```sql
-- Semua network device
SELECT NetworkDevice

-- Switch berdasarkan tipe
SELECT NetworkDevice WHERE networkdevicetype_name = 'Switch'

-- Router berdasarkan IP
SELECT NetworkDevice WHERE managementip = '172.16.35.1'

-- NVR (terdaftar sebagai NetworkDevice)
SELECT NetworkDevice WHERE name LIKE 'NVR%'
```

### 3.3 StorageSystem (NAS)

```sql
-- Semua storage system
SELECT StorageSystem

-- NAS berdasarkan nama
SELECT StorageSystem WHERE name LIKE 'NAS%'
```

### 3.4 Peripheral (CCTV Camera)

```sql
-- Semua peripheral
SELECT Peripheral

-- CCTV berdasarkan serial number
SELECT Peripheral WHERE serialnumber LIKE 'DS-%'

-- CCTV berdasarkan nama
SELECT Peripheral WHERE name LIKE 'CAMERA%'
```

### 3.5 PowerSource (UPS/PDU)

```sql
-- Semua power source
SELECT PowerSource

-- UPS berdasarkan nama
SELECT PowerSource WHERE name LIKE 'UPS%'
```

### 3.6 Lokasi dan Rack

```sql
-- Semua lokasi
SELECT Location

-- Rack di lokasi tertentu
SELECT Rack WHERE location_name = 'Ruang Server'

-- DataCenter
SELECT DataCenter
```

### 3.7 Reference Data

```sql
-- Brand
SELECT Brand WHERE name = 'Lenovo'

-- Model
SELECT Model WHERE name = '7D76CTO1WW'

-- IOS Version (firmware)
SELECT IOSVersion WHERE name = 'RouterOS 7.12'
```

---

## 4. Field Reference per Class

### 4.1 Server

| Field | Type | Description | Contoh |
|---|---|---|---|
| `name` | string | Hostname | `SERVER-HCI-01` |
| `serialnumber` | string | Serial number | `J901GKXY` |
| `status` | enum | Lifecycle status | `production`, `stock` |
| `managementip` | string | Management IP | `10.50.0.2` |
| `location_name` | string (FK → Location) | Lokasi fisik | `Ruang Server` |
| `rack_name` | string (FK → Rack) | Nama rack | `Rack Server 2` |
| `brand_name` | string (FK → Brand) | Manufacturer | `Lenovo` |
| `model_name` | string (FK → Model) | Model name | `7D76CTO1WW` |
| `org_id` | integer (FK → Organization) | Organization | `1` |
| `cpu` | string | CPU description | `2x Intel Xeon Gold 5416S 16C/32T` |
| `ram` | string | Total RAM | `256 GB` |
| `nb_u` | integer | Rack units | `2` |
| `osfamily` | string | OS family | `Linux` |
| `osversion` | string | OS version | `Ubuntu 24.04` |
| `asset_tag` | string | Asset tag | `FIT-SRV-001` |

### 4.2 NetworkDevice

| Field | Type | Description | Contoh |
|---|---|---|---|
| `name` | string | Device hostname | `FIT-Core-RTR` |
| `serialnumber` | string | Serial number | `HC707RR1T60` |
| `status` | enum | Lifecycle status | `production` |
| `managementip` | string | Management IP | `172.16.35.1` |
| `location_name` | string (FK → Location) | Lokasi | `Ruang Server` |
| `rack_name` | string (FK → Rack) | Rack | `Rack Server 1` |
| `brand_name` | string (FK → Brand) | Manufacturer | `MikroTik` |
| `model_name` | string (FK → Model) | Model | `RouterOS CCR2004-16G-2S+` |
| `iosversion_name` | string (FK → IOSVersion) | Firmware version | `RouterOS 7.12` |
| `networkdevicetype_name` | string (FK → NetworkDeviceType) | Tipe device | `Switch`, `Router`, `NVR` |
| `nb_u` | integer | Rack units | `1` |
| `ram` | string | RAM | `4096 MB` |
| `org_id` | integer (FK → Organization) | Organization | `1` |

### 4.3 StorageSystem (NAS)

| Field | Type | Description | Contoh |
|---|---|---|---|
| `name` | string | Nama storage | `NAS-FIT` |
| `serialnumber` | string | Serial number | `2050PDN123456` |
| `status` | enum | Lifecycle status | `production` |
| `location_name` | string (FK → Location) | Lokasi | `Ruang Server` |
| `brand_name` | string (FK → Brand) | Manufacturer | `Synology` |
| `model_name` | string (FK → Model) | Model | `RS2423RP+` |
| `org_id` | integer (FK → Organization) | Organization | `1` |

### 4.4 Peripheral (CCTV Camera)

| Field | Type | Description | Contoh |
|---|---|---|---|
| `name` | string | Nama camera | `CAMERA-10` |
| `serialnumber` | string | Serial number | `DS-2CD1143G0E-I20210227AAWRF58406296` |
| `status` | enum | Lifecycle status | `production` |
| `location_name` | string (FK → Location) | Lokasi | (sering kosong) |
| `brand_name` | string (FK → Brand) | Manufacturer | `Hikvision` |
| `model_name` | string (FK → Model) | Model | `DS-2CD1143G0E-I` |
| `org_id` | integer (FK → Organization) | Organization | `1` |

### 4.5 PowerSource (UPS/PDU)

| Field | Type | Description | Contoh |
|---|---|---|---|
| `name` | string | Nama UPS/PDU | `FALAH01-MDP-RUANG-SERVER-FIT` |
| `serialnumber` | string | Serial number | (sering kosong) |
| `status` | enum | Lifecycle status | `production` |
| `location_name` | string (FK → Location) | Lokasi | `Ruang Server` |
| `brand_name` | string (FK → Brand) | Manufacturer | `APC` |
| `model_name` | string (FK → Model) | Model | `Easy UPS 3S` |
| `org_id` | integer (FK → Organization) | Organization | `1` |

---

## 5. Python Snippet: Get dan Update CI

### 5.1 Mengambil Semua CI dari Satu Class

```python
def get_all_cis(itop_class: str, output_fields: str, limit: int = 200) -> list:
    """Ambil semua CI dari satu class iTop. Handle pagination."""
    all_objects = []
    page = 1
    while True:
        payload = {
            "operation": "core/get",
            "class": itop_class,
            "key": f"SELECT {itop_class}",
            "output_fields": output_fields,
            "limit": limit,
            "page": page
        }
        result = itop_post(payload)
        objects = result.get("objects", {})
        if not objects:
            break
        for key, ci in objects.items():
            all_objects.append({
                "id": key.split("::")[1] if "::" in key else key,
                "class": ci.get("class"),
                "fields": ci.get("fields", {})
            })
        page += 1
    return all_objects
```

### 5.2 Update CI berdasarkan Serial Number

```python
def update_ci_by_sn(itop_class: str, serial_number: str, fields_to_update: dict) -> bool:
    """Cari CI berdasarkan serial number, lalu update fields-nya."""
    # 1. Cari CI
    payload = {
        "operation": "core/get",
        "class": itop_class,
        "key": f"SELECT {itop_class} WHERE serialnumber = '{serial_number}'",
        "output_fields": "name,serialnumber"
    }
    result = itop_post(payload)
    objects = result.get("objects", {})
    
    if not objects:
        print(f"CI not found: {itop_class} SN={serial_number}")
        return False
    
    # 2. Ambil numeric ID
    key_str = list(objects.keys())[0]
    numeric_id = key_str.split("::")[1] if "::" in key_str else key_str
    
    # 3. Update
    update_payload = {
        "operation": "core/update",
        "class": itop_class,
        "key": int(numeric_id),
        "comment": "Auto-update from DCIM pipeline",
        "fields": fields_to_update
    }
    update_result = itop_post(update_payload)
    ci_key = list(update_result.get("objects", {}).keys())[0] if update_result.get("objects") else None
    code = update_result.get("objects", {}).get(ci_key, {}).get("code", -1) if ci_key else -1
    
    return code == 0
```

### 5.3 Membuat CI Baru (dengan Referensi FK via OQL)

```python
def create_server(name: str, serial_number: str, ip: str, brand: str, model: str) -> dict:
    """Buat server baru di iTop dengan FK references via OQL sub-query."""
    payload = {
        "operation": "core/create",
        "class": "Server",
        "comment": "Auto-created from DCIM pipeline",
        "fields": {
            "name": name,
            "serialnumber": serial_number,
            "org_id": 1,
            "status": "production",
            "managementip": ip,
            "brand_id": f"SELECT Brand WHERE name = '{brand}'",
            "model_id": f"SELECT Model WHERE name = '{model}'",
            "nb_u": 2
        }
    }
    result = itop_post(payload)
    objects = result.get("objects", {})
    if objects:
        key = list(objects.keys())[0]
        ci = objects[key]
        if ci.get("code") == 0:
            print(f"Created: {name} → {key}")
            return ci
        else:
            print(f"Create failed: {ci.get('message')}")
    return {}
```

---

## 6. Error Handling

### 6.1 Response Structure

```json
{
    "code": 0,
    "message": "Found: 5",
    "objects": {
        "Server::3125": {
            "code": 0,
            "message": "",
            "class": "Server",
            "key": "3125",
            "fields": { ... }
        }
    }
}
```

### 6.2 Kode Status

| Code | Meaning | Tindakan |
|---|---|---|
| `0` | OK / Success | Lanjutkan |
| `1` | Error pada satu CI | Cek `message` field di object level |
| `100` | API Error (global) | Cek top-level `message`, biasanya invalid attribute/OQL |

### 6.3 Error Patterns yang Umum

**Invalid attribute code**:
```json
{
    "code": 100,
    "message": "Error: output_fields: invalid attribute code 'osfamily'"
}
```
→ Field name salah atau tidak ada di class tersebut. Cek field reference di Section 4.

**Authentication failed**:
```json
{
    "code": 100,
    "message": "Error: ..."
}
```
→ Cek `auth_user` dan `auth_pwd` parameters.

**Object not found (core/update)**:
```json
{
    "objects": {
        "Server::99999": {
            "code": 1,
            "message": "Object not found"
        }
    }
}
```
→ ID tidak valid atau object sudah dihapus.

### 6.4 Best Practice Error Handling

```python
def safe_itop_call(payload: dict) -> tuple[bool, dict]:
    """Safe wrapper untuk iTop API call."""
    try:
        result = itop_post(payload)
    except requests.exceptions.RequestException as e:
        return False, {"error": f"HTTP error: {e}"}
    
    # Global error
    if result.get("code", 0) != 0:
        return False, {"error": result.get("message", "Unknown error")}
    
    # Per-object error
    objects = result.get("objects", {})
    errors = {}
    for key, ci in objects.items():
        if ci.get("code", 0) != 0:
            errors[key] = ci.get("message", "Unknown error")
    
    if errors:
        return False, {"errors": errors, "objects": objects}
    
    return True, {"objects": objects}
```

---

## 7. Deployment Info

| Item | Value |
|---|---|
| iTop URL | `http://10.70.0.56:8080` |
| API Endpoint | `/webservices/rest.php?version=1.3` |
| Auth User | via env `ITOP_API_USER` (mis. `admin`) |
| Auth Password | via env `ITOP_API_PASS` (secret store — tidak dicantumkan di dokumen) |
| Organization ID | `1` (PT. Falah Inovasi Teknologi) |
| Database | MariaDB (internal Docker network) |
| iTop Version | 3.1.1 (container `vbkunin/itop:3.1.1`) |
| Total CI Count | ~79 (5 Server, 6 NetworkDevice, 5 StorageSystem, 61 Peripheral, 2 PowerSource) |

---

## 8. Pencarian Relasi Perangkat Mendalam (Untuk AI)

Dalam proses persiapan data (*AI Readiness* v4.2), sebagian besar lokasi dasar (`site`, `rack_name`) sudah disertakan di PostgreSQL `v_train_*` sehingga AI bisa langsung menggunakannya. Namun, jika AI membutuhkan relasi CMDB yang lebih mendalam (contoh: Mengetahui nama *Contact Person* atau menelusuri dampak (*Impact Analysis*) jika sebuah Switch mati terhadap Server yang terhubung dengannya), AI harus melakukan query langsung ke iTop.

Gunakan **OQL** dengan kunci `serialnumber` untuk mendapatkan relasi utuh tersebut:

```python
# Contoh: Mencari relasi dan kontak dari Server
payload = {
    "operation": "core/get",
    "class": "Server",
    "key": f"SELECT Server WHERE serialnumber = '{serial_number}'",
    "output_fields": "contacts_list,documents_list,physicalinterface_list"
}
result = itop_post(payload)
```
