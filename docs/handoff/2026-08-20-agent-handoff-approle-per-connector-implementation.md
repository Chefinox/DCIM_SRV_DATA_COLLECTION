# Handoff Report: AppRole Scoped Per-Connector Implementation

**Date:** 2026-08-20
**Author:** GitHub Copilot

---

## 1. Status Akses Vault (Tugas 0)

| Aspek | Hasil |
|-------|-------|
| Container Vault | ✅ Running, uptime 9 hari |
| Vault Status | Initialized, Unsealed, HA disabled, v1.15.6 |
| Vault UI | ✅ Aktif di `http://localhost:8200/ui/` (HTTP 200) — owner belum pernah mengaksesnya |
| Root Token (dari task sebelumnya) | ✅ Valid, policies=[root], type=service |
| Credential Files | `init.txt`, `role_id`, `secret_id` tersedia di `vault/config/` |
| **Stop?** | ❌ Tidak — akses admin tersedia, lanjut eksekusi |

---

## 2. Konfirmasi Konvensi Wiki (Tugas 1)

Sumber yang dibaca:

| File | Prinsip Relevan |
|------|-----------------|
| `concepts/secret-management-strategy.md` | AppRole auth untuk aplikasi, audit semua akses |
| `entities/vault.md` | KV engine untuk static secrets, AppRole + K8s auth |
| `product-description/...product-description.md` §2.8 | **"Service account per connector dengan izin minimum"** — mandate utama |
| `technical-requirements/v4.2-goal-prompt.md` | **Stop-if: Vault setup memerlukan root token yang tidak bisa di-rollback** |
| `reference-designs/block1-...provisioning.md` §9, §13 | Path structure `secret/dcim/{component}/`, TTL default 1h/max 24h, policy `dcim-app` monolitik |

**Temuan gap:** Wiki mandatkan per-connector isolation, tapi reference design masih punya policy monolitik (`dcim-app` reads all `secret/dcim/*`). Task ini menutup gap tersebut.

**File baru sejak terakhir dicek:** Tidak ada file baru tentang AppRole/TTL/rotation.

---

## 3. Tabel Inventarisasi Connector → AppRole (Tugas 2)

### Secret Paths yang Ada di Vault

```
secret/dcim/
├── elastic_pass     (ES password)
├── kibana_pass      (Kibana password)
├── postgres         (PostgreSQL password)
├── sot_db_pass      (SoT DB password)
├── ralph            (Ralph API token)
├── ralph_new        (Ralph new API token)
├── jwt_verifier     (JWT key — tidak ada consumer aktif)
└── redfish_pass     (Redfish/IPMI password — baru di-seed)
```

### Mapping Connector → AppRole

| Connector | Files yang Menggunakan | Secret Dibutuhkan | AppRole | Policy |
|-----------|----------------------|-------------------|---------|--------|
| **ES Consumers** | `siem_es_consumer/app.py`, `es_logger/executor.py` | `elastic_pass`, `kibana_pass` | `approle-elasticsearch` | `policy-elasticsearch-readonly` |
| **PostgreSQL/Lineage** | `utils/lineage.py`, `configs/loader.py` | `postgres`, `sot_db_pass` | `approle-postgres` | `policy-postgres-readonly` |
| **Redfish/Hardware** | `scripts/redfish_poller.py`, `scripts/server_inventory_collector.py` | `redfish_pass` | `approle-redfish` | `policy-redfish-readonly` |
| **Ralph/CMDB** | `configs/loader.py` (via ralph key) | `ralph`, `ralph_new` | `approle-ralph` | `policy-ralph-readonly` |

---

## 4. Bukti Implementasi & Uji Per AppRole (Tugas 3)

### Config Per AppRole

| AppRole | `token_ttl` | `token_max_ttl` | `secret_id_ttl` | Policy |
|---------|-------------|-----------------|-----------------|--------|
| `approle-elasticsearch` | 3600s (1h) | 86400s (24h) | 2592000s (30d) | `policy-elasticsearch-readonly` |
| `approle-postgres` | 3600s (1h) | 86400s (24h) | 2592000s (30d) | `policy-postgres-readonly` |
| `approle-redfish` | 3600s (1h) | 86400s (24h) | 2592000s (30d) | `policy-redfish-readonly` |
| `approle-ralph` | 3600s (1h) | 86400s (24h) | 2592000s (30d) | `policy-ralph-readonly` |

### Hasil Test Positif + Negatif (ALL PASSED)

```
=== approle-elasticsearch ===
  Login: OK
  [✓] [POSITIVE] elastic_pass: PASS
  [✓] [NEGATIVE] postgres: PASS (403 denied)
  [✓] [NEGATIVE] ralph: PASS (403 denied)
  [✓] [NEGATIVE] redfish_pass: PASS (403 denied)

=== approle-postgres ===
  Login: OK
  [✓] [POSITIVE] postgres: PASS
  [✓] [POSITIVE] sot_db_pass: PASS
  [✓] [NEGATIVE] elastic_pass: PASS (403 denied)
  [✓] [NEGATIVE] ralph: PASS (403 denied)
  [✓] [NEGATIVE] redfish_pass: PASS (403 denied)

=== approle-redfish ===
  Login: OK
  [✓] [POSITIVE] redfish_pass: PASS
  [✓] [NEGATIVE] elastic_pass: PASS (403 denied)
  [✓] [NEGATIVE] postgres: PASS (403 denied)
  [✓] [NEGATIVE] ralph: PASS (403 denied)

=== approle-ralph ===
  Login: OK
  [✓] [POSITIVE] ralph: PASS
  [✓] [POSITIVE] ralph_new: PASS
  [✓] [NEGATIVE] elastic_pass: PASS (403 denied)
  [✓] [NEGATIVE] postgres: PASS (403 denied)
  [✓] [NEGATIVE] redfish_pass: PASS (403 denied)

Overall: ALL TESTS PASSED
```

Setiap AppRole **hanya** bisa membaca secret yang di-assign — akses ke path di luar scope-nya ditolak (403).

---

## 5. Status Migrasi Config Connector (Tugas 4)

### Perubahan di `src/utils/secrets.py`

`get_secret()` sekarang **otomatis memilih AppRole yang tepat** berdasarkan secret name:

```
elastic_pass  → role_id_elasticsearch / secret_id_elasticsearch
postgres      → role_id_postgres / secret_id_postgres
redfish_pass  → role_id_redfish / secret_id_redfish
ralph         → role_id_ralph / secret_id_ralph
(unknown)     → role_id / secret_id (fallback ke dcim-role generik)
```

**Backward compatible:** Jika per-connector files tidak ditemukan, fallback ke `role_id`/`secret_id` generik (dcim-role lama).

### Verifikasi Fungsional

```
get_secret("elastic_pass"): OK (len=20) — via approle-elasticsearch
get_secret("postgres"):     OK (len=12) — via approle-postgres
```

### Status Per Connector

| Connector | Migrasi ke AppRole Baru | Status |
|-----------|------------------------|--------|
| ES Consumers | ✅ Otomatis via `secrets.py` | Ready |
| PostgreSQL/Lineage | ✅ Otomatis via `secrets.py` | Ready |
| Redfish/Hardware | ⚠️ `scripts/redfish_poller.py` punya `get_secret()` lokal, bukan dari `src.utils.secrets` | Partial — script menggunakan Docker secret / env var fallback, bukan Vault AppRole |
| Ralph/CMDB | ✅ Otomatis via `configs/loader.py` → `secrets.py` | Ready |

**Catatan:** `scripts/redfish_poller.py` dan `scripts/server_inventory_collector.py` memiliki fungsi `get_secret()` sendiri yang hanya membaca dari Docker secrets/env var, BUKAN dari Vault. Migrasi script ini ke `src.utils.secrets` adalah task terpisah yang memerlukan testing lebih lanjut.

### `dcim-role` Lama

**Tidak dihapus/dinonaktifkan** — tetap aktif sebagai fallback. TTL sudah diperbaiki (1h/24h) dari task sebelumnya.

---

## 6. Rekomendasi Next Step

### Siap untuk Revoke Root Token?

**Ya, kondisional.** AppRole per-connector sudah teruji dan fungsional. Root token bisa di-revoke **setelah** owner mengkonfirmasi:
1. Tidak ada operasi admin Vault lain yang pending dalam waktu dekat.
2. Proses `vault operator generate-root` dipahami untuk recovery jika butuh admin access lagi nanti.

### Next Steps di Luar Scope Task Ini

| Item | Prioritas | Alasan |
|------|-----------|--------|
| Revoke root token aktif | HIGH | Setelah konfirmasi owner |
| Migrasi `scripts/redfish_poller.py` dan `server_inventory_collector.py` ke `src.utils.secrets` | MEDIUM | Script masih pakai Docker secret/env var, belum via Vault |
| Deprecate `dcim-role` generik | LOW | Setelah semua connector terverifikasi stabil pada AppRole baru |
| Migrasi credential ES ke Vault | MEDIUM | Out of scope — butuh izin terpisah |
| Fix DLQ error isolation (`mikrotik_poller.py`, `cctv_poller.py`) | MEDIUM | Out of scope — butuh izin terpisah |
| Review `secret_id_ttl=30d` — apakah perlu auto-rotation mechanism | LOW | Saat ini manual rotation setiap 30 hari |

### File & Commit

- **Commit:** `392c51e` — `feat: implement per-connector AppRole isolation in Vault`
- **Policy HCL files:** Tersimpan di Vault (bukan file lokal)
- **Credential files:** `vault/config/role_id_*`, `vault/config/secret_id_*` — semua di `.gitignore`
