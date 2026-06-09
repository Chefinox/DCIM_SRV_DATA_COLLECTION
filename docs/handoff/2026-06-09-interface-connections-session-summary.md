# SESSION SUMMARY — iTop Interface Connections & Naming Alignment

## 1. Session Metadata

- **Session Title:** Fix iTop Interface Connections, Bonding/LACP Support, Naming Alignment
- **Date/Time:** 2026-06-09 (WIB)
- **User:** Infra team (bahasa Indonesia)
- **Main Topic:** Memperbaiki relasi interface connections antar CI di iTop — hanya NIC1 & NIC2 yang ter-link ke NetworkDevice, NIC3/NIC4/XCC hilang. Plus penyelarasan penamaan antara Netbox dan iTop.
- **Session Type:** Debugging + Coding + Integration
- **Current Status:** In Progress — server links sudah benar, NAS links masih perlu perbaikan

---

## 2. High-Level Summary

Sesi ini berfokus pada perbaikan relasi interface connections di iTop CMDB. User melaporkan bahwa hanya NIC1 & NIC2 yang ter-link ke NetworkDevice, padahal di Netbox semua 4 NIC + XCC terkoneksi ke switch/router. Investigasi menemukan 2 root cause: (1) `_sync_device_links()` menggunakan dict yang di-key oleh nama switch sehingga multiple kabel ke switch yang sama saling menimpa, dan (2) Netbox menggunakan bonding/LACP dimana satu cable memiliki multiple terminations (position-based pairing). Fix meliputi: perbaikan dict→set, index-based termination matching untuk bonding, MAC-based interface matching, auto-create XCC dari Netbox, dan expand IFACE_NAME_MAP. Server links sekarang sudah benar (17 links untuk 5 servers). NAS links masih memiliki duplikat yang perlu diperbaiki.

---

## 3. User Goal

- **Primary Goal:** Semua interface (NIC1-4 + XCC) pada setiap server harus ter-link ke NetworkDevice yang sesuai di iTop, sesuai dengan data koneksi di Netbox
- **Secondary Goals:**
  - Penamaan interface harus konsisten antara Netbox dan iTop — mengutamakan nama dari pipeline (perangkat langsung)
  - Interface NAS harus diambil dari perangkat langsung (SNMP), bukan dari Netbox
  - Interface Switch/Router harus dari pipeline (Telegraf SNMP), bukan dari Netbox
- **Expected Output:** Semua perangkat di iTop punya interface connections yang lengkap dan benar
- **Success Criteria:** User verifikasi di UI iTop — setiap server menunjukkan semua NetworkDevice yang terhubung sesuai Netbox

---

## 4. Important Context

- **Background:** Server Ubuntu, stack Kafka → Python consumer → iTop REST API. Data koneksi dari Netbox API (`http://10.70.0.20:9008`). Pipeline data dari Redfish (server), SNMP (NAS/Network/UPS), ISAPI (CCTV/NVR).
- **Current Environment:**
  - Service: `netbox-itop-connector.service` (daemon, sync setiap 1 jam)
  - Connector: `/home/infra/dcim_metrics_project/scripts/netbox_to_itop_connector.py`
  - Consumer: `/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py`
  - iTop: `http://localhost:8080` (admin/Inovasi@0918)
  - Netbox: `http://10.70.0.20:9008`
  - PostgreSQL: `dcim_sot` di localhost:5432
- **Known Constraints:**
  - iTop Community edition tidak punya kelas PhysicalLink/Cable
  - `lnkConnectableCIToNetworkDevice` adalah link table untuk Server/NAS → NetworkDevice
  - Redfish tidak melaporkan BMC/XCC interface
  - NAS tidak punya Redfish data — interface harus dari SNMP
  - Netbox bonding cable memiliki multiple terminations dengan **position-based pairing** (A[0]↔B[0], A[1]↔B[1], dst)
  - `powerA_id`/`powerB_id` field names case-sensitive
  - Netbox API response untuk cable hanya menampilkan satu termination per side dalam `_build_cable_lookup()` tapi `_sync_device_links()` sudah di-fix untuk fetch langsung dari API
- **User Preferences:**
  - Langsung ke inti, teknis
  - Data harus dari perangkat langsung (pipeline), bukan dari Netbox untuk atribut perangkat
  - Netbox hanya untuk relasi/koneksi
  - Penamaan interface mengikuti nama dari perangkat (Redfish NIC1-4, SNMP ifName)
  - Konfirmasi sebelum perubahan besar
  - Bahasa Indonesia

---

## 5. Key Decisions Made

| Decision | Reason | Impact |
|---|---|---|
| Pipeline names are authoritative | Redfish NIC1-4 dari hardware langsung, SNMP ifName dari perangkat | iTop menggunakan NIC1-4, bukan Ethernet 1-4 dari Netbox |
| Bonding cable: position-based pairing | A[0]↔B[0], A[1]↔B[1] — bukan all combinations (A×B) | NIC2→ether1, NIC3→ether2, NIC4→ether3 (bukan semua ke ether1) |
| Fetch cables langsung dari Netbox API di `_sync_device_links()` | DB `netbox_cables` table hanya menyimpan satu pasangan per cable | Mendukung bonding/LACP dengan multiple terminations |
| `_build_cable_lookup()` masih dari DB | Untuk comment enrichment, satu pasangan sudah cukup | Comment hanya menampilkan satu peer, bukan semua bonding peers |
| Auto-create XCC dari Netbox | Redfish tidak report BMC/XCC | XCC interface otomatis dibuat dari Netbox jika belum ada di iTop |
| MAC-based matching sebagai fallback | Handles edge cases dimana naming convention berbeda | Interface dengan MAC sama akan match meskipun nama berbeda |

---

## 6. Work Completed

- [x] **Investigasi root cause** — dict overwrite di `_sync_device_links()` + bonding cable multiple terminations
- [x] **Backup scripts** — `netbox_to_itop_connector.py.bak.20260609` dan `dcim_itop_unified_consumer.py.bak.20260609`
- [x] **Phase 1: Fix dict overwrite** — Ganti `connected_ndevs = {}` dengan `connected_cables = set()` dan 4-tuple dedup key
- [x] **Phase 2: Expand IFACE_NAME_MAP** — Tambah `mgmt0`, `Management`, `BMC`, `IPMI` → `XCC` dan reverse lookup
- [x] **Phase 3: MAC-based matching** — Fallback pencocokan berbasis MAC address di `_sync_interfaces()`
- [x] **Phase 4: Auto-create XCC dari Netbox** — Membuat interface XCC dari Netbox jika Redfish tidak report
- [x] **Phase 5: NAS consumer support** — Update consumer untuk memproses interface NAS (`class_name in ("Server", "NAS")`)
- [x] **Phase 6: Bonding/LACP fix** — `_sync_device_links()` fetch langsung dari Netbox API dengan position-based termination matching
- [x] **Cleanup duplikat links** — Hapus duplikat NIC2, NIC3, NIC4 yang salah mapping
- [x] **Server links verified** — Semua 5 servers punya links yang benar (17 total server links)

---

## 7. Current Progress / State

```text
Current state:
- Server links: ✅ SUDAH BENAR
  - HCI-01: NIC1→SW1/ether13, NIC2→SW2/ether1, NIC3→SW2/ether2, NIC4→SW2/ether3, XCC→SW1/ether33
  - HCI-02: NIC1→SW1/ether17, NIC2→SW2/ether4, NIC3→SW2/ether5, NIC4→SW2/ether6, XCC→SW1/ether34
  - HCI-03: NIC1→SW1/ether21, NIC2→SW2/combo3, NIC3→SW2/ether7, NIC4→SW2/ether8, XCC→SW1/ether35
  - Render-01: NIC1→SW1/ether25
  - Render-02: NIC1→SW1/ether29

- NAS links: ❌ MASIH ADA DUPLIKAT (bonding issue yang sama)
  - NAS-CD01: LAN 1→ether7, LAN 1→ether8, LAN 2→ether8 (duplikat!)
  - NAS-FIT: LAN 1→ether5, LAN 1→ether6, LAN 2→ether6 (duplikat!)
  - NAS-SD01: LAN 1→ether3, LAN 1→ether4, LAN 2→ether4 (duplikat!)
  - NAS-INFRA: NIC3→sfp-sfpplus4 (hanya 1 link, seharusnya lebih)

- `_build_cable_lookup()` (line ~540): MASIH MENGGUNAKAN LOGIKA LAMA
  - Hanya mengambil a_terminations[0] dan b_terminations[0]
  - Tidak menangani bonding cable dengan multiple terminations
  - Digunakan oleh `_sync_interfaces()` dan `_build_interface_comment()`

- Service: netbox-itop-connector.service RUNNING (sync setiap 1 jam)
- Consumer: dcim-itop-unified.service RUNNING (interface NAS sudah diproses)

- Uncommitted changes: Banyak perubahan di scripts/ dan docs/ belum di-commit
```

---

## 8. Open Issues / Unresolved Questions

| Issue / Question | Status | Recommended Action |
|---|---|---|
| NAS links duplikat (bonding issue) | **Open** | Fix `_build_cable_lookup()` untuk handle multiple terminations (position-based), atau hapus duplikat NAS links secara manual dan pastikan connector tidak membuat ulang |
| NAS-INFRA hanya punya 1 link | **Open** | Cek apakah NAS-INFRA punya cable di Netbox untuk interface lain selain NIC3 |
| `_build_cable_lookup()` masih old logic | **Open** | Update untuk position-based termination matching seperti `_sync_device_links()` |
| Render servers hanya punya 1 link (NIC1) | **Pending verification** | Render servers di Netbox punya 5 cables (Ethernet 1-4 + XCC), tapi hanya NIC1 yang ter-link. Kemungkinan karena `has_pipeline_ifaces` check di `_sync_interfaces()` |
| Uncommitted changes | **Open** | Commit semua perubahan ke git |
| NAS interface naming | **Pending user confirmation** | NAS dari Netbox pakai "Ethernet 1", "LAN 1". Apakah perlu di-mapping ke format NIC? |

---

## 9. Next Recommended Actions

1. **Fix `_build_cable_lookup()`** — Update untuk position-based termination matching (sama seperti fix di `_sync_device_links()`) agar comment enrichment dan interface matching juga mendukung bonding
2. **Cleanup NAS duplikat links** — Hapus link NAS yang duplikat (LAN 1→ether8, LAN 2→ether8, dst) dan pastikan connector membuat ulang dengan benar
3. **Verify Render server links** — Cek apakah Render-01/02 seharusnya punya lebih dari 1 link (NIC2-4 + XCC)
4. **Commit changes** — `git add` dan `git commit` untuk semua perubahan
5. **Restart service** — `sudo systemctl restart netbox-itop-connector.service` setelah fix
6. **User verification** — Minta user cek UI iTop untuk memastikan semua link benar

---

## 10. Files, Links, Artifacts, and References

| Item | Type | Purpose | Status |
|---|---|---|---|
| `/home/infra/dcim_metrics_project/scripts/netbox_to_itop_connector.py` | File (Python) | Netbox → iTop connector daemon | Modified |
| `/home/infra/dcim_metrics_project/scripts/netbox_to_itop_connector.py.bak.20260609` | File (Python) | Backup sebelum perubahan | Created |
| `/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py` | File (Python) | Kafka → iTop consumer v8 | Modified (NAS interface support) |
| `/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py.bak.20260609` | File (Python) | Backup sebelum perubahan | Created |
| `/etc/telegraf/telegraf.d/nas-snmp.conf` | File (Telegraf) | NAS SNMP polling (termasuk interface) | Already existed |
| `/home/infra/dcim_metrics_project/docs/handoff/2026-06-09-server-fixes-session-summary.md` | File (Doc) | Handoff dari sesi sebelumnya | Reference |
| `netbox-itop-connector.service` | Systemd service | Netbox connector daemon (1hr interval) | Running |

---

## 11. Technical Details

### Bonding/LACP Cable Structure (dari Netbox API)

```
Cable 59: "Bonding HCI 01"
  A Terminations:                    B Terminations:
  [0] SW-SERVER2 / ether1      ↔    [0] HCI-01 / Ethernet 2  → NIC2
  [1] SW-SERVER2 / ether2      ↔    [1] HCI-01 / Ethernet 3  → NIC3
  [2] SW-SERVER2 / ether3      ↔    [2] HCI-01 / Ethernet 4  → NIC4

Cable 60: "Bonding HCI 02"
  A Terminations:                    B Terminations:
  [0] SW-SERVER2 / ether4      ↔    [0] HCI-02 / Ethernet 2  → NIC2
  [1] SW-SERVER2 / ether5      ↔    [1] HCI-02 / Ethernet 3  → NIC3
  [2] SW-SERVER2 / ether6      ↔    [2] HCI-02 / Ethernet 4  → NIC4

Cable 61: "Bonding HCI 03"
  A Terminations:                    B Terminations:
  [0] SW-SERVER2 / combo3      ↔    [0] HCI-03 / Ethernet 2  → NIC2
  [1] SW-SERVER2 / ether7      ↔    [1] HCI-03 / Ethernet 3  → NIC3
  [2] SW-SERVER2 / ether8      ↔    [2] HCI-03 / Ethernet 4  → NIC4
```

### Key Code Changes in `netbox_to_itop_connector.py`

1. **`IFACE_NAME_MAP` (line ~100)** — Ditambah: `mgmt0`, `Management`, `BMC`, `IPMI` → `XCC`; plus `ITOP_TO_NETBOX_IFACE_MAP` (reverse lookup)
2. **`_sync_interfaces()` (line ~430)** — Ditambah MAC-based matching sebagai fallback
3. **`_sync_interfaces()` (line ~500)** — Ditambah auto-create XCC dari Netbox
4. **`_sync_device_links()` (line ~638)** — Diubah dari `cable_lookup = {}` (DB-based, single termination) ke fetch langsung dari Netbox API dengan **position-based termination matching**
5. **Dedup key** — Diubah dari `(connectableci_id, networkdevice_id)` ke `(connectableci_id, networkdevice_id, device_port, network_port)`

### Key Code Changes in `dcim_itop_unified_consumer.py`

1. **Line ~1145** — Diubah dari `if measurement == "interface" and obj_id:` menjadi `if measurement == "interface" and obj_id:` + `if class_name in ("NetworkDevice", "NAS"):` untuk mendukung interface NAS

### `_build_cable_lookup()` — BELUM DI-UPDATE (BUG MASIH ADA)

```python
# Line ~540 — MASIH MENGGUNAKAN LOGIKA LAMA:
a_term = a_terminations[0].get("object") or {}  # Hanya [0]!
b_term = b_terminations[0].get("object") or {}  # Hanya [0]!
```

Perlu diupdate untuk position-based matching seperti `_sync_device_links()`.

### iTop Object IDs (Current State)

```
Servers:
  SERVER-HCI-01    = 2954    5 links (NIC1-4 + XCC) ✅
  SERVER-HCI-02    = 2956    5 links (NIC1-4 + XCC) ✅
  SERVER-HCI-03    = 2955    5 links (NIC1-4 + XCC) ✅
  SERVER-Render-01 = 3102    1 link  (NIC1 only)    ⚠️
  SERVER-Render-02 = 3096    1 link  (NIC1 only)    ⚠️

NetworkDevices:
  FIT-Core-RTR        = 3097
  FIT-Core-SW         = 3002
  FIT-DIST-SW-LAN1    = 3003
  FIT-DIST-SW-SERVER1 = 3001
  FIT-DIST-SW-SERVER2 = 3000
  NVR-FIT             = 3099
```

### Cable Connection Map (Verified from Netbox + iTop)

```
HCI-01: NIC1→SW1/ether13, NIC2→SW2/ether1, NIC3→SW2/ether2, NIC4→SW2/ether3, XCC→SW1/ether33
HCI-02: NIC1→SW1/ether17, NIC2→SW2/ether4, NIC3→SW2/ether5, NIC4→SW2/ether6, XCC→SW1/ether34
HCI-03: NIC1→SW1/ether21, NIC2→SW2/combo3, NIC3→SW2/ether7, NIC4→SW2/ether8, XCC→SW1/ether35
Render-01: NIC1→SW1/ether25, NIC2→SW1/ether26, NIC3→SW1/ether27, NIC4→SW1/ether28, XCC→SW1/ether36
Render-02: NIC1→SW1/ether29, NIC2→SW1/ether30, NIC3→SW1/ether31, NIC4→SW1/ether32, XCC→SW1/ether37
```

### NAS Link Status (MASIH BERMASALAH)

```
NAS-INFRA: NIC3→sfp-sfpplus4 (1 link, seharusnya lebih)
NAS-CD01:  LAN1→ether7, LAN1→ether8, LAN2→ether8 (duplikat!)
NAS-FIT:   LAN1→ether5, LAN1→ether6, LAN2→ether6 (duplikat!)
NAS-SD01:  LAN1→ether3, LAN1→ether4, LAN2→ether4 (duplikat!)
NAS-CD02:  (belum dicek)
```

---

## 12. User Preferences and Working Style

- **Tone Preference:** Langsung ke inti, teknis, tidak perlu basa-basi
- **Detail Level:** Tinggi — user memahami bonding/LACP, Netbox API, iTop REST API
- **Output Format Preference:** Tabel untuk data, command siap copy-paste, verifikasi di setiap langkah
- **Important Style Notes:**
  - User mengoreksi langsung ketika ada kesalahan mapping (NIC3→ether3 seharusnya NIC3→ether2)
  - User sangat detail — memverifikasi setiap link di UI iTop
  - User menginginkan penamaan interface mengikuti perangkat langsung, bukan konvensi Netbox
  - Data inventory dari perangkat langsung (Redfish/SNMP) diprioritaskan; Netbox hanya untuk relasi

---

## 13. Assumptions and Boundaries

### Confirmed Facts
- Bonding cable di Netbox menggunakan **position-based pairing** (A[0]↔B[0], bukan all combinations)
- `_sync_device_links()` sudah di-fix untuk handle bonding
- `_build_cable_lookup()` **belum** di-fix untuk handle bonding
- Server links sudah benar (17 links)
- NAS links masih memiliki duplikat
- NAS interface data dari SNMP pipeline (sudah ada di `/etc/telegraf/telegraf.d/nas-snmp.conf`)

### Assumptions
- Render servers seharusnya punya 5 links (NIC1-4 + XCC) — perlu verifikasi
- NAS bonding cable juga menggunakan position-based pairing — perlu verifikasi

### Do Not Assume
- Jangan asumsikan semua cable menggunakan position-based pairing — verifikasi di Netbox API
- Jangan asumsikan Render server links sudah benar — hanya NIC1 yang ter-link saat ini
- Jangan asumsikan NAS interface naming sudah benar — perlu konfirmasi user

---

## 14. Memory Candidates

| Memory Candidate | Reason |
|---|---|
| Netbox bonding cable: position-based pairing, bukan all combinations | Critical untuk semua bonding cable handling di connector |
| `_build_cable_lookup()` perlu update untuk multi-termination | Masih menggunakan old logic, menyebabkan NAS duplikat links |
| `has_pipeline_ifaces` check di `_sync_interfaces()` bisa mencegah pembuatan interface Render NIC2-4 | Perlu investigasi apakah ini penyebab Render hanya punya 1 link |

---

## 15. Final Handoff Brief

```markdown
The previous session focused on fixing interface connections in iTop CMDB — 
only NIC1 & NIC2 had device links while NIC3, NIC4, and XCC were missing.

Root causes were: (1) dict overwrite in _sync_device_links(), and (2) bonding/LACP 
cables with position-based multiple terminations not handled correctly.

We completed: fixing _sync_device_links() to use set-based dedup and position-based 
termination matching from Netbox API, expanding IFACE_NAME_MAP with management interface 
variants, adding MAC-based interface matching, auto-creating XCC from Netbox, and adding 
NAS interface support in the consumer.

Server links are now CORRECT (17 links for 5 servers). However, NAS links still have 
duplicates due to _build_cable_lookup() not being updated for multi-termination support. 
Render servers also only have 1 link each (NIC1) instead of 5 — needs investigation.

The next agent should:
1. Fix _build_cable_lookup() for position-based termination matching (same as _sync_device_links fix)
2. Cleanup NAS duplicate links
3. Investigate why Render servers only have 1 link
4. Commit all changes to git
5. Verify everything with user

Important: bonding cables use position-based pairing (A[0]↔B[0]), NOT all combinations.
Pipeline names (NIC1-4 from Redfish, ifName from SNMP) are authoritative over Netbox naming.
User communicates in Indonesian and verifies every link in iTop UI.
```
