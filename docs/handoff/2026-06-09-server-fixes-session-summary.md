# SESSION SUMMARY — DCIM iTop CMDB Server Category Fixes & Netbox Integration

## 1. Session Metadata

- **Session Title:** DCIM iTop Server Category Fixes, Netbox Connector, Power Chain & Interface Relationships
- **Date/Time:** 2026-06-09 (WIB), sesi dimulai ~07:00 UTC
- **User:** Infra team (bahasa Indonesia)
- **Main Topic:** Perbaikan kategori Server di iTop CMDB — duplikat NIC, CPU/RAM blank, interface relationships, power chain, PDU objects, NVR-FIT location, UPS-FIT attributes, Netbox connector enhancement
- **Session Type:** Debugging + Coding + Integration
- **Current Status:** In Progress — mayoritas fix sudah dikerjakan dan deployed, beberapa item perlu verifikasi user

---

## 2. High-Level Summary

Sesi ini melanjutkan pekerjaan dari handoff session sebelumnya (2026-06-08). Fokus utama adalah memperbaiki 8 issue pada kategori Server dan perangkat lain di iTop CMDB. Kami berhasil menghapus 12 duplikat interface Ethernet dari HCI servers, membuat interface NIC1-4 + XCC untuk Render servers dari data Redfish, menambahkan cable connection info dari Netbox ke semua interface, membuat device-to-device links (Server/NAS → NetworkDevice), membuat PDU objects di kelas PDU yang benar dengan powerstart links ke UPS-FIT dan MDP, mengupdate UPS-FIT dengan brand/model/serial dari Kafka data, memperbaiki NVR-FIT location ke Ruang Server, dan mengupdate Netbox connector agar otomatis membuat device links. Inventory sync cron yang sebelumnya gagal karena timeout sudah diperbaiki (10s→30s).

---

## 3. User Goal

- **Primary Goal:** Memastikan semua CI di iTop memiliki atribut lengkap dan relasi yang benar — interfaces, cable connections, power chain, rack assignments, NetworkDevice relationships
- **Secondary Goals:**
  - Hapus duplikat interface pada HCI servers
  - Buat interfaces untuk Render servers dari data Redfish
  - Sinkronisasi cable connections dari Netbox ke iTop (bukan hanya comment, tapi juga device-to-device links)
  - PDU harus di kelas PDU, bukan PowerSource
  - UPS-FIT harus punya brand, model, serial dari Kafka data
  - NVR-FIT location harus mengikuti Ralph (Ruang Server)
  - Netbox connector harus otomatis membuat device links saat sync
- **Expected Output:** Semua perangkat di iTop punya interfaces lengkap, cable info, power chain, dan NetworkDevice relationships
- **Success Criteria:** User verifikasi di UI iTop — Server/HCI-01 punya 5 interfaces dengan cable info, Network Devices section terisi, PowerA/PowerB terisi

---

## 4. Important Context

- **Background:** Server Ubuntu, stack Kafka → Python consumer → iTop REST API. Data hardware dari PostgreSQL (`dcim_sot`), Redfish API (servers), Ralph (`http://localhost:8082`), dan Netbox (`http://10.70.0.20:9008`).
- **Current Environment:**
  - Service aktif: `dcim-itop-unified.service` (Kafka consumer v8), `netbox-itop-connector.service` (daemon, sync setiap 1 jam)
  - Consumer: `/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py`
  - Connector: `/home/infra/dcim_metrics_project/scripts/netbox_to_itop_connector.py`
  - Inventory sync: `/home/infra/dcim_metrics_project/scripts/dcim_itop_inventory_sync.py` (cron setiap 5 menit)
  - Fix script: `/home/infra/dcim_metrics_project/scripts/fix_server_issues.py`
  - DB: PostgreSQL `dcim_sot`, user `sot_admin`, pass `Inovasi@0918`
  - Redis: cache dan distributed lock
- **Known Constraints:**
  - iTop Community edition tidak punya kelas PhysicalLink/Cable — cable info disimpan di PhysicalInterface.comment dan lnkConnectableCIToNetworkDevice
  - `PhysicalInterface.org_id` adalah read-only (inherited dari parent device)
  - `PDU` class membutuhkan `rack_id` (mandatory)
  - `powerA_id`/`powerB_id` field names case-sensitive (capital A/B)
  - `rack_id` bukan attribute pada PowerSource class (gunakan location_id saja)
  - `core/update` di iTop API butuh numeric object ID, bukan nama
  - PDU extends PowerSource — PDU objects muncul di kedua class query
  - Netbox cable lookup harus case-insensitive (Netbox: `FALAH01-FIT-CORE-RTR` vs iTop: `FIT-Core-RTR`)
  - Redfish tidak melaporkan XCC/BMC interface — harus dibuat manual atau dari Netbox
  - NAS tidak punya data NIC dari Kafka pipeline — interface NAS diambil dari Netbox
  - `dcim_itop_inventory_sync.py` cron sebelumnya gagal setiap 5 menit karena timeout 10s terlalu pendek
- **User Preferences:**
  - Langsung ke inti, tidak perlu penjelasan panjang
  - Data harus dari asset repository (Ralph/PostgreSQL/Netbox), bukan hardcode
  - Konfirmasi sebelum perubahan besar
  - Bahasa Indonesia
  - Tidak mengubah arsitektur tanpa konfirmasi
  - Update location harus persistent (Ralph → unified_assets → pipeline → iTop)
  - Data inventory dari perangkat langsung (Redfish/SNMP) lebih diprioritaskan daripada Netbox untuk atribut perangkat; Netbox hanya untuk relasi/koneksi

---

## 5. Key Decisions Made

| Decision | Reason | Impact |
|---|---|---|
| Ethernet 1-4 dihapus dari HCI servers, simpan NIC1-4 | NIC1-4 punya MAC address dari Redfish, Ethernet 1-4 dari Netbox tanpa MAC = duplikat | HCI servers sekarang 5 interfaces (NIC1-4 + XCC) |
| Render server NIC dibuat dari Redfish data | User konfirmasi: data interface dari perangkat langsung, bukan Netbox | NIC1-4 dengan MAC address dari Redfish |
| XCC dibuat manual untuk Render servers | Redfish tidak melaporkan BMC/XCC interface | XCC dengan cable info dari Netbox |
| Cable info disimpan di PhysicalInterface.comment | iTop Community tidak punya kelas Cable/PhysicalLink | User bisa lihat koneksi di iTop UI |
| Device-to-device links via lnkConnectableCIToNetworkDevice | iTop punya link table untuk Server/NAS → NetworkDevice relationships | Network Devices section terisi di UI |
| PDU objects di kelas PDU (bukan PowerSource) | User konfirmasi PDU seharusnya di kelas PDU | PDU dengan rack_id dan powerstart_id |
| MDP-RUANG-SERVER-FIT dibuat sebagai PowerSource | User konfirmasi: MDP (listrik PLN) sebagai PowerSource | powerB_id pada Server → PDU → MDP |
| UPS-FIT diupdate dari Kafka data (brand=APC, model, serial) | Data ada di Kafka raw_fields, bukan dari Netbox/Ralph | UPS-FIT sekarang punya atribut lengkap |
| NVR-FIT location diupdate ke Ruang Server (persistent) | User konfirmasi: posisi NVR di Rack Server 1 | Updated di unified_assets + iTop |
| Inventory sync timeout 10s→30s, filter metric_name | Cron gagal setiap 5 menit karena timeout | CPU/RAM ter-sync ke iTop |
| Interface name mapping: Ethernet 1→NIC1 (Lenovo servers) | Redfish pakai NIC1, Netbox pakai Ethernet 1 | Connector bisa match kedua format |
| Netbox connector auto-create device links | Agar tidak perlu manual setiap ada device baru | Step 5: _sync_device_links() ditambahkan |

---

## 6. Work Completed

- [x] **Investigasi semua 8 issue** — data dari iTop API, PostgreSQL, Netbox API, Redfish API, Ralph API
- [x] **FIX 1: Hapus duplikat Ethernet 1-4** dari HCI-01/02/03 (12 interfaces dihapus)
- [x] **FIX 2: Hostname mapping** di `dcim_itop_inventory_sync.py` — hapus transformasi SERVER-→SRV-, tambah case-insensitive fallback
- [x] **FIX 3: Cable connections** — update comment pada semua interface Server/NAS/NetworkDevice dari Netbox data
- [x] **FIX 4: PDU objects** — buat 5 PDU di kelas PDU (ID 3105-3109) dengan rack dan powerstart links
- [x] **FIX 5: MDP PowerSource** — buat FALAH01-MDP-RUANG-SERVER-FIT (ID=3104)
- [x] **FIX 6: PDU powerstart links** — PDU-UPS → UPS-FIT (3098), PDU-NON-UPS → MDP (3104)
- [x] **FIX 7: UPS-FIT attributes** — brand=APC (ID=43), model=Smart-UPS 30KVA (ID=133), serial=9E2133T16585, location=Ruang Server
- [x] **FIX 8: NVR-FIT location** — updated unified_assets + iTop ke Ruang Server / Rack Server 1
- [x] **FIX 9: Render server interfaces** — NIC1-4 dari Redfish (MAC address), XCC dari Netbox
- [x] **FIX 10: NIC3/NIC4 cable info** — update comment untuk HCI servers (SW-SERVER2/ether2-8)
- [x] **FIX 11: Inventory sync** — timeout 30s, filter metric_name='inventory_snapshot', format_cpu filter NULL entries
- [x] **FIX 12: CPU/RAM Render servers** — 2x AMD EPYC 9254 24C/48T, 128 GB
- [x] **FIX 13: CPU format cleanup** — semua server: clean format tanpa NULL entries
- [x] **FIX 14: Device-to-device links** — 12 links (8 Server + 4 NAS → NetworkDevice)
- [x] **Netbox connector update** — +IFACE_NAME_MAP, +nb_to_itop_iface_name(), +_sync_device_links(), fuzzy matching
- [x] **Services restarted** — dcim-itop-unified.service + netbox-itop-connector.service

---

## 7. Current Progress / State

```text
Current state:
- Service dcim-itop-unified.service RUNNING (PID latest)
- Service netbox-itop-connector.service RUNNING (sync setiap 1 jam)
- Semua 5 server punya 5 interfaces (NIC1-4 + XCC) dengan cable info
- 12 device-to-device links created (Server/NAS → NetworkDevice)
- 5 PDU objects di kelas PDU dengan powerstart links
- UPS-FIT: brand=APC, model=Smart-UPS 30KVA, serial=9E2133T16585, location=Ruang Server
- NVR-FIT: location=Ruang Server, rack=Rack Server 1
- Inventory sync cron fixed (timeout 30s)
- Netbox connector otomatis buat device links saat sync

Pending verification by user:
- Apakah Network Devices section di UI iTop sudah terisi untuk semua Server/NAS?
- Apakah NAS interfaces (Ethernet 1, LAN 1) perlu di-rename ke format NIC?
- Apakah ada device lain yang perlu ditambahkan ke rack/links?
```

---

## 8. Open Issues / Unresolved Questions

| Issue / Question | Status | Recommended Action |
|---|---|---|
| NAS interface naming — Ethernet 1 vs NIC1 | Pending user confirmation | NAS dari Netbox pakai "Ethernet 1", "LAN 1". Apakah perlu di-mapping ke NIC format? |
| NAS data source untuk interfaces | Pending user confirmation | NAS tidak punya NIC data dari Kafka. User tanya apakah dari Netbox atau Kafka. Perlu konfirmasi. |
| Rack Server 3 — hanya 1 PDU | Open | Device lain di Rack Server 3 belum di iTop (PC-Render, Switch-POE, dll) |
| Old PowerSource PDU objects (IDs 36-40) | User sudah hapus manual | Selesai |
| Integration test hapus-recreate CI | Open | Belum dilakukan test hapus CI → auto-recreate |
| NVR-FIT persistent location update | Implemented | unified_assets updated, pipeline akan baca dari sana |

---

## 9. Next Recommended Actions

1. **Konfirmasi NAS interface naming** — Apakah interface NAS harus pakai nama Netbox (Ethernet 1, LAN 1) atau di-mapping ke format NIC?
2. **Konfirmasi NAS data source** — Apakah NAS interfaces dari Netbox atau dari Kafka/SNMP?
3. **Verifikasi UI iTop** — Cek bagian Network Devices pada Server-HCI-01, apakah FIT-DIST-SW-SERVER1 dan FIT-DIST-SW-SERVER2 muncul
4. **Tambah device ke Rack Server 3** — PC-Render-01/02/03/04, Switch-POE, dll belum di rack
5. **Integration test** — Hapus CI SERVER-Render-01 di iTop → tunggu ≤2 menit → verifikasi atribut lengkap
6. **Update `fix_server_issues.py`** — Tambahkan logic untuk device-to-device links dan NAS interfaces agar bisa di-run ulang

---

## 10. Files, Links, Artifacts, and References

| Item | Type | Purpose | Status |
|---|---|---|---|
| `/home/infra/dcim_metrics_project/scripts/dcim_itop_unified_consumer.py` | File (Python) | Core Kafka consumer v8 | Modified |
| `/home/infra/dcim_metrics_project/scripts/itop_sync_utils.py` | File (Python) | DB/API utils | Modified (sebelumnya) |
| `/home/infra/dcim_metrics_project/scripts/netbox_to_itop_connector.py` | File (Python) | Netbox → iTop connector daemon | Modified & Deployed |
| `/home/infra/dcim_metrics_project/scripts/dcim_itop_inventory_sync.py` | File (Python) | Inventory sync cron | Modified |
| `/home/infra/dcim_metrics_project/scripts/fix_server_issues.py` | File (Python) | One-shot fix script | Created |
| `/home/infra/dcim_metrics_project/scripts/server_inventory_to_pg.py` | File (Python) | Redfish → PostgreSQL | Viewed, tidak diubah |
| `/home/infra/dcim_metrics_project/itop/sync/sync_netbox_to_itop.py` | File (Python) | Referensi Netbox sync | Reference |
| `/home/infra/dcim_metrics_project/itop/sync_pdus_itop.py` | File (Python) | Referensi PDU sync | Reference |
| `dcim_sot.unified_assets` | PostgreSQL table | Source of truth device locations | Modified (NVR-FIT) |
| `dcim_sot.netbox_cables` | PostgreSQL table | Raw cable data dari Netbox | Created earlier |
| `/etc/systemd/system/netbox-itop-connector.service` | Systemd service | Netbox connector daemon | Created earlier |

---

## 11. Technical Details

### iTop Object IDs (Current State)

```
Servers:
  SERVER-HCI-01    = 2954
  SERVER-HCI-02    = 2956
  SERVER-HCI-03    = 2955
  SERVER-Render-01 = 3102
  SERVER-Render-02 = 3096

NetworkDevices:
  FIT-Core-RTR        = 3097
  FIT-Core-SW         = 3002
  FIT-DIST-SW-LAN1    = 3003
  FIT-DIST-SW-SERVER1 = 3001
  FIT-DIST-SW-SERVER2 = 3000
  NVR-FIT             = 3099

PowerSource:
  UPS-FIT                    = 3098 (brand=APC, model=Smart-UPS 30KVA, sn=9E2133T16585)
  MDP-RUANG-SERVER-FIT       = 3104

PDU:
  PDU-RACK-SERVER-01-NON-UPS = 3105 → powerstart=MDP(3104)
  PDU-RACK-SERVER-01-UPS     = 3106 → powerstart=UPS-FIT(3098)
  PDU-RACK-SERVER-02-NON-UPS = 3107 → powerstart=MDP(3104)
  PDU-RACK-SERVER-02-UPS     = 3108 → powerstart=UPS-FIT(3098)
  PDU-RACK-SERVER-03-UPS     = 3109 → powerstart=UPS-FIT(3098)

Server Power:
  All servers: powerA_id=3108 (PDU-02-UPS), powerB_id=3107 (PDU-02-NON-UPS)
```

### Cable Connection Map (Server Interfaces)

```
HCI-01: NIC1→SW-SERVER1/ether13, NIC2→SW-SERVER2/ether1, NIC3→SW-SERVER2/ether2, NIC4→SW-SERVER2/ether3, XCC→SW-SERVER1/ether33
HCI-02: NIC1→SW-SERVER1/ether17, NIC2→SW-SERVER2/ether4, NIC3→SW-SERVER2/ether5, NIC4→SW-SERVER2/ether6, XCC→SW-SERVER1/ether34
HCI-03: NIC1→SW-SERVER1/ether21, NIC2→SW-SERVER2/combo3, NIC3→SW-SERVER2/ether7, NIC4→SW-SERVER2/ether8, XCC→SW-SERVER1/ether35
Render-01: NIC1→SW-SERVER1/ether25, NIC2→SW-SERVER1/ether26, NIC3→SW-SERVER1/ether27, NIC4→SW-SERVER1/ether28, XCC→SW-SERVER1/ether36
Render-02: NIC1→SW-SERVER1/ether29, NIC2→SW-SERVER1/ether30, NIC3→SW-SERVER1/ether31, NIC4→SW-SERVER1/ether32, XCC→SW-SERVER1/ether37
```

### Device-to-Device Links (lnkConnectableCIToNetworkDevice)

```
SERVER-HCI-01    → FIT-DIST-SW-SERVER1 (NIC1→ether13)
SERVER-HCI-01    → FIT-DIST-SW-SERVER2 (NIC2→ether1)
SERVER-HCI-02    → FIT-DIST-SW-SERVER1 (NIC1→ether17)
SERVER-HCI-02    → FIT-DIST-SW-SERVER2 (NIC2→ether4)
SERVER-HCI-03    → FIT-DIST-SW-SERVER1 (NIC1→ether21)
SERVER-HCI-03    → FIT-DIST-SW-SERVER2 (NIC2→combo3)
SERVER-Render-01 → FIT-DIST-SW-SERVER1 (NIC1→ether25)
SERVER-Render-02 → FIT-DIST-SW-SERVER1 (NIC1→ether29)
NAS-INFRA        → FIT-DIST-SW-SERVER1 (Ethernet 3→sfp-sfpplus4)
NAS-SD01         → FIT-DIST-SW-SERVER1 (LAN 1→ether3)
NAS-CD01         → FIT-DIST-SW-SERVER1 (LAN 1→ether7)
NAS-FIT          → FIT-DIST-SW-SERVER1 (LAN 1→ether5)
```

### Power Chain

```
Server power1 → PDU-RACK-SERVER-02-UPS (3108) → UPS-FIT (3098) → APC Smart-UPS 30KVA
Server power2 → PDU-RACK-SERVER-02-NON-UPS (3107) → MDP-RUANG-SERVER-FIT (3104) → PLN
```

### Key Commands

```bash
# Services
sudo systemctl restart dcim-itop-unified.service
sudo systemctl restart netbox-itop-connector.service
sudo systemctl status dcim-itop-unified.service netbox-itop-connector.service --no-pager

# Logs
sudo journalctl -u dcim-itop-unified.service -f --no-pager
sudo journalctl -u netbox-itop-connector.service -f --no-pager
tail -f /home/infra/dcim_metrics_project/logs/dcim_itop_inventory_sync.log

# Database
PGPASSWORD='Inovasi@0918' psql -h localhost -U sot_admin -d dcim_sot -c "SELECT ..."
```

### UPS-FIT Kafka Data (raw_fields)

```
serial_number: 9E2133T16585
model: 30KH
firmware_version: V6.042/040
agent_firmware: 3.7.DA807.APC.15
system_location: PT Falah Inovasi Teknologi
IP: 192.168.100.140 (from raw_tags.agent_host)
```

---

## 12. User Preferences and Working Style

- **Tone Preference:** Langsung ke inti, teknis, tidak perlu basa-basi
- **Detail Level:** Tinggi — user memahami PostgreSQL, systemd, Kafka, Python, REST API, SNMP, Redfish
- **Output Format Preference:** Markdown terstruktur, tabel untuk perbandingan, command siap copy-paste
- **Important Style Notes:**
  - User ingin data dari asset repository, bukan hardcode
  - Update location harus persistent (Ralph → unified_assets → pipeline → iTop)
  - Data inventory dari perangkat langsung (Redfish/SNMP) diprioritaskan; Netbox hanya untuk relasi
  - Konfirmasi sebelum perubahan arsitektur
  - Jangan update data dari Netbox/Ralph kecuali data Kafka memang tidak ada — infokan terlebih dahulu
  - Untuk pengetesan script yang menunggu durasi, jalankan langsung (tidak menunggu cycle)

---

## 13. Assumptions and Boundaries

### Confirmed Facts
- Semua server (HCI + Render) punya 5 interfaces (NIC1-4 + XCC) di iTop
- 12 device-to-device links sudah dibuat
- 5 PDU objects di kelas PDU dengan powerstart links
- UPS-FIT punya brand=APC, model, serial dari Kafka data
- NVR-FIT location = Ruang Server / Rack Server 1
- Netbox connector sudah auto-create device links
- Inventory sync cron sudah fixed (timeout 30s)

### Assumptions
- NAS interfaces diambil dari Netbox karena tidak ada data NIC dari Kafka untuk NAS
- Ethernet 1→NIC1 mapping hanya untuk Lenovo servers (HCI + Render)
- XCC tidak dilaporkan oleh Redfish — harus dari Netbox atau manual

### Do Not Assume
- Jangan asumsikan NAS naming sudah benar — perlu konfirmasi user
- Jangan asumsikan semua device sudah di rack — Rack Server 3 baru 1 PDU
- Jangan asumsikan integration test sudah dilakukan — belum

---

## 14. Memory Candidates

| Memory Candidate | Reason |
|---|---|
| iTop API: `lnkConnectableCIToNetworkDevice` untuk Server→NetworkDevice links | Penting untuk semua device relationship sync |
| iTop API: `powerA_id`/`powerB_id` case-sensitive (capital A/B) | Sering jadi error source |
| iTop API: `rack_id` bukan attribute PowerSource | Error jika coba set |
| iTop API: PDU extends PowerSource | PDU muncul di query PowerSource juga |
| UPS-FIT: APC Smart-UPS 30KVA, serial=9E2133T16585, IP=192.168.100.140 | Data dari Kafka SNMP |
| Redfish NIC labels: NIC1-NIC4 (bukan Ethernet 1-4) untuk Lenovo servers | Mapping penting untuk connector |
| Redfish tidak melaporkan XCC/BMC interface | Perlu buat manual atau dari Netbox |
| NAS tidak punya NIC data dari Kafka | Interfaces harus dari Netbox |

---

## 15. Final Handoff Brief

```markdown
The previous session focused on fixing 8 issues across all device categories in iTop CMDB — 
duplicate NICs, blank CPU/RAM, missing interface relationships, missing NetworkDevice links, 
incorrect PDU class, empty UPS-FIT attributes, wrong NVR-FIT location, and Netbox connector 
enhancements.

We completed: deleting 12 duplicate Ethernet interfaces from HCI servers, creating NIC1-4 + XCC 
interfaces for Render servers from Redfish data, adding cable connection info from Netbox to ALL 
server/NAS/NetworkDevice interfaces, creating 12 device-to-device links via lnkConnectableCIToNetworkDevice, 
creating 5 PDU objects in the PDU class with powerstart links to UPS-FIT and MDP, updating UPS-FIT 
with brand=APC/model/serial from Kafka data, fixing NVR-FIT location to Ruang Server, fixing inventory 
sync cron timeout (10s→30s), and adding _sync_device_links() to the Netbox connector.

The current state is: all 5 servers have 5 interfaces each (NIC1-4 + XCC) with cable info, 12 
device-to-device links exist, PDU/UPS/MDP power chain is complete, and services are running.

The next agent should: (1) get user confirmation on NAS interface naming and data source, 
(2) verify Network Devices section in iTop UI, (3) add remaining devices to Rack Server 3, 
(4) run integration test (delete-recreate CI), (5) update fix_server_issues.py with device link 
and NAS interface logic.

Important: data inventory from devices directly (Redfish/SNMP) takes priority over Netbox for 
device attributes; Netbox is only for relationships/connections. Always confirm before architecture 
changes. User communicates in Indonesian.
```
