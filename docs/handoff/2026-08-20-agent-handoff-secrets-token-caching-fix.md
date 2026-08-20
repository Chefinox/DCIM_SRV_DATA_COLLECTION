# Handoff Report: Vault Token Caching Fix & Policy HCL Infrastructure-as-Code

**Date:** 2026-08-20
**Author:** GitHub Copilot

---

## 1. Analisis Pola Pemanggilan & Solusi Caching

### Analisis Skenario Eksekusi

| Tipe Komponen | Contoh Service | Perilaku Eksekusi | Kebutuhan Caching |
|---------------|----------------|-------------------|-------------------|
| **Long-running daemons** | `dcim_dlq_consumer.py`, `dcim_itop_unified_consumer.py`, normalizers | Berjalan terus-menerus sebagai satu proses Python | **In-memory cache** (`dict` module-level) |
| **NiFi / Scheduled processes** | `redfish_poller.py`, `virtualization_poller_nifi.py`, cron jobs | Proses Python baru di-spawn per siklus / per eksekusi | **File-based cache** (`vault/config/cache/token_<connector>.json`) |

### Arsitektur Caching Dual-Layer

Mekanisme caching dual-layer diimplementasikan di `src/utils/secrets.py`:

```
get_secret(name)
  ├── 1. In-Memory Cache Check (_token_cache)
  │      └── Valid? → Use token directly (0 HTTP logins)
  ├── 2. File Cache Check (vault/config/cache/token_<connector>.json)
  │      └── Valid? → Populate in-memory + Use token (0 HTTP logins)
  ├── 3. Fresh AppRole Login (via hvac)
  │      └── Save token & expiry to both In-Memory and File Cache
  └── 4. Automatic 403 Retry
         └── If cached token rejected (revoked/expired server-side):
             Invalidate cache → Fresh login → Retry secret read once
```

**Konfigurasi Cache:**
- Buffer expiry: `60 detik` sebelum TTL aktual (mencegah race condition dekat expiry)
- Default TTL: `3600 detik` (1 jam)
- Cache file path: `vault/config/cache/token_<connector>.json` (ditambahkan ke `.gitignore`)

---

## 2. Bukti Reuse Token Bekerja (Tugas 2)

### Test 1: Multiple Calls vs Lease Creation

Simulasi 15 pemanggilan `get_secret()` beruntun:
- 10x `get_secret('elastic_pass')` (connector: `elasticsearch`)
- 5x `get_secret('postgres')` (connector: `postgres`)

**Hasil Output:**

```
=== LEASES BEFORE TEST: 7 ===

--- Calling get_secret('elastic_pass') 10 times ---
vault: fresh login for connector 'elasticsearch' (ttl=3600s)
  Call 1: value_len=20
vault: reusing in-memory cached token for 'elasticsearch'
  Call 2: value_len=20
vault: reusing in-memory cached token for 'elasticsearch'
  Call 3..10: value_len=20

--- Calling get_secret('postgres') 5 times ---
vault: fresh login for connector 'postgres' (ttl=3600s)
  Call 1: value_len=12
vault: reusing in-memory cached token for 'postgres'
  Call 2..5: value_len=12

=== LEASES AFTER TEST: 9 ===
=== NEW LEASES CREATED: 2 (for 15 get_secret calls) ===
```

**Hasil:** Dari 15 pemanggilan, **hanya 2 lease baru** yang dibuat di Vault (1 per connector). Penurunan **86.7%** pembuatan lease.

---

### Test 2: Edge Cases & Fallback (ALL PASSED)

| Skenario Test | Expektasi | Hasil | Status |
|---------------|-----------|-------|--------|
| **File cache corrupt** (JSON syntax error) | Abaikan file corrupt, fallback ke login baru | `vault: ignoring corrupt cache file... fresh login` | ✅ **PASS** |
| **Token revoked/expired (403)** | Tangkap 403, invalidate cache, auto re-login, retry | `vault: cached token rejected (403)... fresh login` | ✅ **PASS** |
| **File cache reuse (proses baru)** | In-memory kosong (proses baru), baca token valid dari file | `vault: reusing file-cached token for 'elasticsearch'` | ✅ **PASS** |

---

## 3. Status Policy HCL (Infrastructure-as-Code)

Definisi 4 policy HCL di-export dari Vault dan di-commit ke repository sebagai source of truth:

| Policy File | Direct Access Scope | Audit Security |
|-------------|---------------------|----------------|
| `vault/policies/policy-elasticsearch-readonly.hcl` | `secret/data/dcim/elastic_pass`, `secret/data/dcim/kibana_pass` | ✅ Clean (path + read only) |
| `vault/policies/policy-postgres-readonly.hcl` | `secret/data/dcim/postgres`, `secret/data/dcim/sot_db_pass` | ✅ Clean (path + read only) |
| `vault/policies/policy-redfish-readonly.hcl` | `secret/data/dcim/redfish_pass` | ✅ Clean (path + read only) |
| `vault/policies/policy-ralph-readonly.hcl` | `secret/data/dcim/ralph`, `secret/data/dcim/ralph_new` | ✅ Clean (path + read only) |

**Keamanan File:** `grep` audit mengonfirmasi **0 secret, password, atau token** tertulis di dalam file-file HCL ini (exit code 1 / clean).

---

## 4. Perubahan File & Commit

- **`src/utils/secrets.py`**: dual-layer caching (`_read_cached_token`, `_store_cached_token`, `_invalidate_cache`), auto 403-retry.
- **`.gitignore`**: ditambahkan `vault/config/cache/`.
- **`vault/policies/policy-*.hcl`**: 4 file HCL baru (Infrastructure-as-Code).
- **Commit:** `ba3bd67` — `fix(security): implement Vault token caching in secrets.py & commit policy HCLs`

---

## 5. Kesimpulan

 Root cause pembuatan lease berlebihan (**re-login pada setiap pemanggilan `get_secret()`**) telah **sepenuhnya teratasi** di level kode:
1. Token di-reuse untuk seluruh pemanggilan berturut-turut dalam window 1 jam (TTL).
2. long-running daemons menggunakan in-memory cache (0 I/O disk, 0 HTTP logins ekstra).
3. Short-lived script (ExecuteProcess / cron) menggunakan file-based cache (`vault/config/cache/`).
4. Jika token di-revoke manual / expired, sistem secara otomatis recover via 403-retry tanpa melempar exception.
5. Definisi policy Vault telah di-commit sebagai Infrastructure-as-Code yang aman dan auditable.
