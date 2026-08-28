# SESSION SUMMARY DOCUMENT

## 1. Session Metadata

- **Session Title:** Deploy iTop & Sync NetBox CMDB
- **Date/Time:** May 26, 2026
- **User:** Not specified
- **Main Topic:** iTop Community Edition deployment and NetBox-to-iTop CMDB synchronization
- **Session Type:** Coding / Debugging / Deployment / Data Integration
- **Current Status:** Completed for devices, locations, models, and VMs; follow-up needed for interfaces/IPs/clusters if desired.

---

## 2. High-Level Summary

User wanted iTop Community Edition deployed with Docker Compose and populated from NetBox at `http://10.70.0.20:9008/`. Deployment stack was created under `/home/infra/dcim_metrics_project/itop` using MariaDB, iTop web, and a Python NetBox-to-iTop sync service. Several deployment and sync blockers were resolved: web access, filesystem permissions, NetBox token, iTop REST profile, class mapping, required fields, duplicate objects, location/model population, NAS classification, and VM import. Final state: all 80 NetBox devices are imported into iTop with correct location/model fields, and all 41 NetBox VMs are imported into iTop under Hypervisor hosts mapped from NetBox clusters.

---

## 3. User Goal

- **Primary Goal:** Deploy iTop and populate CMDB data from NetBox.
- **Secondary Goals:**
  - Make iTop accessible from other devices.
  - Import all NetBox devices into correct iTop CI classes.
  - Populate location and model fields from NetBox.
  - Import NetBox Virtual Machines into iTop.
  - Preserve relationship integrity and avoid duplicates.
- **Expected Output:** Working iTop deployment plus idempotent sync from NetBox to iTop.
- **Success Criteria:**
  - iTop web accessible.
  - NetBox API reachable and authorized.
  - iTop REST API usable.
  - Devices imported without missing items.
  - Locations/models populated.
  - VMs imported with valid `virtualhost_id`.
  - No known duplicate device objects.

---

## 4. Important Context

- **Background:**  
  User requested iTop Community Edition deployment and CMDB population from NetBox. Work was done in `/home/infra/dcim_metrics_project/itop`.

- **Current Environment:**
  - OS: Linux
  - Workspace root: `/home/infra`
  - Project: `/home/infra/dcim_metrics_project`
  - iTop folder: `/home/infra/dcim_metrics_project/itop`
  - NetBox URL: `http://10.70.0.20:9008/`
  - iTop external URL: `http://10.70.0.56:8080/`
  - iTop REST endpoint: `/webservices/rest.php?version=1.3`
  - Docker Compose services:
    - `itop-db`
    - `itop-web`
    - `netbox-itop-sync`

- **Known Constraints:**
  - Do not redesign infrastructure architecture.
  - Do not add Kafka, Elastic, Redis, or unrelated systems.
  - Only deploy and populate iTop.
  - Sync must be idempotent.
  - Avoid duplicates.
  - Preserve relationship integrity.
  - `.env` contains secrets; do not print full content.

- **User Preferences:**
  - Wants practical execution, not only explanation.
  - Indonesian language preferred.
  - Direct, concise updates useful.
  - Wants real verification from system state.

- **Important Notes:**
  - `netbox-itop-sync` uses `network_mode: host` because Docker bridge could not reach NetBox.
  - iTop REST account must have `REST Services User` profile.
  - Installed iTop model differs from assumed mapping: some classes invalid or abstract.

---

## 5. Key Decisions Made

| Decision | Reason | Impact |
|---|---|---|
| Use `network_mode: host` for sync container | Docker internal network could not reach NetBox `10.70.0.20:9008` | Sync can access both NetBox and local iTop URL |
| Disable `interfaces` and `ip_addresses` sync | `NetworkInterface` and `IPAddress` mapping/classes not safe in current iTop install | Device/VM sync stable; interfaces/IPs remain future work |
| Avoid `PhysicalDevice` as create target | iTop rejects abstract/base class with HTTP 500 | All roles mapped to concrete iTop classes |
| Map NetBox `Storage` role to iTop `NAS` | Synology NAS was incorrectly imported as Server | Six NAS devices moved to `NAS`; future sync keeps them there |
| Create iTop `Location` objects from NetBox device location/site | iTop device `location_name` was undefined | All imported devices now have location where NetBox has location/site |
| Create iTop `Model` objects from NetBox device types | iTop device `model_name` was undefined | All imported devices now have model |
| Map NetBox clusters to iTop `Hypervisor` objects | NetBox VMs had no direct `device`; iTop VMs require `virtualhost_id` | All 41 VMs imported under `Hyper-V` or `Proxmox-FIT` |
| Disable `clusters` sync to `LogicalVolume` | `LogicalVolume.org_id` is read-only | Cluster objects not imported as LogicalVolume; cluster hosts represented as Hypervisor |

---

## 6. Work Completed

- [x] Created iTop deployment artifacts under `/home/infra/dcim_metrics_project/itop`.
- [x] Created Docker Compose stack with MariaDB, iTop web, and sync service.
- [x] Created `.env.example`, docs, runbook, sync documentation, mapping config, Python sync service.
- [x] Started iTop and MariaDB stack.
- [x] Exposed iTop externally on `0.0.0.0:8080`.
- [x] Opened/verified port `8080`.
- [x] Fixed iTop installer writable paths:
  - `/var/www/html/log`
  - `/var/www/html/conf`
- [x] User completed iTop installer.
- [x] User updated NetBox token.
- [x] User added iTop `REST Services User` profile.
- [x] Fixed sync logging crash caused by `extra={"name": ...}`.
- [x] Added required `org_id` and `networkdevicetype_id`.
- [x] Replaced invalid `Firewall` mapping with `NetworkDevice`.
- [x] Disabled unsupported interface/IP sync.
- [x] Audited all NetBox device roles.
- [x] Mapped all 80 NetBox devices to concrete iTop classes.
- [x] Cleaned duplicate `Peripheral` and `PC` objects created during failed attempts.
- [x] Moved six Synology devices from `Server` to `NAS`.
- [x] Populated `location_id` and `model_id` for all devices.
- [x] Imported all 41 NetBox VMs into iTop `VirtualMachine`.
- [x] Created iTop `Hypervisor` objects for:
  - `Hyper-V`
  - `Proxmox-FIT`
- [x] Verified final import coverage.

---

## 7. Current Progress / State

~~~text
Current state:
iTop deployment is running. NetBox-to-iTop sync is operational for devices, locations, models, brands, racks, NAS, hypervisors, and virtual machines.

All 80 NetBox devices are present in iTop across concrete CI classes:
Server, NAS, NetworkDevice, PowerSource, Printer, Peripheral, PC.

All device locations and models are populated from NetBox. All 41 NetBox VMs are imported into iTop VirtualMachine and assigned to iTop Hypervisor hosts based on NetBox cluster:
Hyper-V = 33 VMs
Proxmox-FIT = 8 VMs

Remaining disabled areas:
interfaces: false
ip_addresses: false
clusters: false
~~~

---

## 8. Open Issues / Unresolved Questions

| Issue / Question | Status | Recommended Action |
|---|---|---|
| Interface sync disabled | Open | Probe iTop `NetworkInterface` required fields, then enable with parent CI validation |
| IP address sync disabled | Open | Check if iTop IPAM module/classes exist, likely `IPv4Address`/`IPv6Address`; map accordingly |
| Cluster sync disabled | Open | Decide whether NetBox clusters should stay represented as `Hypervisor` hosts or also be modeled separately |
| VM host mapping uses cluster-level Hypervisor, not physical host | Known limitation | If NetBox later provides VM `device`, update sync to map to physical Hypervisor/Server |
| Some previous test objects may still exist | Pending | Optional cleanup for `NetBox Test Location`, `NetBox Test Rack`, `NetBox Test Server` if present |

---

## 9. Next Recommended Actions

1. Leave current device/VM sync active and monitor next scheduled run.
2. Add a lightweight verification command/script to validate:
   - NetBox devices vs iTop devices
   - NetBox VMs vs iTop VMs
   - missing location/model
3. If needed, clean old test objects:
   - `NetBox Test Location`
   - `NetBox Test Rack`
   - `NetBox Test Server`
4. For interface sync:
   - Probe iTop `NetworkInterface` schema.
   - Create one test interface with valid `connectableci_id`.
   - Add skip logic when parent CI missing.
   - Enable `interfaces: true`.
5. For IP sync:
   - Probe available classes:
     - `IPv4Address`
     - `IPv6Address`
     - `IPInterface`
     - `IPv4Subnet`
   - Enable only after valid class and relation mapping confirmed.
6. Update `SYNC.md` and `RUNBOOK.md` to reflect current flags and class mappings.

---

## 10. Files, Links, Artifacts, and References

| Item | Type | Purpose | Status |
|---|---|---|---|
| `/home/infra/dcim_metrics_project/itop/docker-compose.yml` | File | iTop/MariaDB/sync deployment | Used / Modified |
| `/home/infra/dcim_metrics_project/itop/.env` | File | Runtime secrets and config | Used; contains secrets, do not print |
| `/home/infra/dcim_metrics_project/itop/.env.example` | File | Safe env template | Created |
| `/home/infra/dcim_metrics_project/itop/sync/sync_netbox_to_itop.py` | File | Main Python sync service | Modified |
| `/home/infra/dcim_metrics_project/itop/sync/mapping.yaml` | File | NetBox-to-iTop class/field mapping | Modified |
| `/home/infra/dcim_metrics_project/itop/sync/Dockerfile` | File | Sync container image | Created |
| `/home/infra/dcim_metrics_project/itop/sync/requirements.txt` | File | Python dependencies | Created |
| `/home/infra/dcim_metrics_project/itop/mariadb/conf.d/itop.cnf` | File | MariaDB tuning | Created |
| `/home/infra/dcim_metrics_project/itop/DEPLOYMENT.md` | Doc | Deployment guide | Created |
| `/home/infra/dcim_metrics_project/itop/SYNC.md` | Doc | Sync documentation | Created; may need update |
| `/home/infra/dcim_metrics_project/itop/RUNBOOK.md` | Doc | Operational runbook | Created; may need update |
| `http://10.70.0.20:9008/` | URL | NetBox source | Used |
| `http://10.70.0.56:8080/` | URL | iTop UI | Used |
| `/home/infra/dcim_metrics_project/docs/standar_dcim/collecting-session-summary-template.md` | Doc | Template used for this summary | Used |

---

## 11. Technical Details

### Commands Mentioned

~~~bash
cd /home/infra/dcim_metrics_project/itop

docker compose build netbox-itop-sync
docker compose up -d --force-recreate netbox-itop-sync
docker compose exec -T netbox-itop-sync python /app/sync_netbox_to_itop.py --mapping /app/mapping.yaml

python3 -m py_compile sync/sync_netbox_to_itop.py
docker compose ps
docker compose logs --tail=120 netbox-itop-sync
~~~

### Config / Settings

~~~yaml
sync:
  virtual_machines: true
  vm_cluster_hosts: true
  clusters: false
  interfaces: false
  ip_addresses: false

role_to_itop_class:
  access point: NetworkDevice
  access switch: NetworkDevice
  server: Server
  hypervisor: Hypervisor
  switch: NetworkDevice
  firewall: NetworkDevice
  ups: PowerSource
  pdu: PowerSource
  storage: NAS
  router: NetworkDevice
  printer: Printer
  cable management: Peripheral
  fiber otb: Peripheral
  nvr: NetworkDevice
  pc render: PC
  patch panel: Peripheral
  rack shelf: Peripheral
  link-balancer: NetworkDevice
  default: Peripheral
~~~

### Errors / Logs

~~~text
Initial blockers:
- NetBox token returned 403 Forbidden.
- iTop REST user missing REST Services User profile.
- iTop web only bound to 127.0.0.1:8080.
- /var/www/html/log not writable.
- /var/www/html/conf not writable.
- Container network could not reach NetBox: Network is unreachable.
- PhysicalDevice create returned HTTP 500.
- Firewall class invalid.
- IPAddress class invalid.
- VirtualMachine rejected missing virtualhost_id.
- LogicalVolume org_id read-only.
- Location description unknown attribute.
- rack_id unknown on several non-rackable classes.
- Duplicates created during failed sync attempts.
~~~

### Architecture / Structure

~~~text
Deployment:
- iTop web: vbkunin/itop:3.1.1
- Database: mariadb:10.11
- Sync service: Python 3.12 custom container
- Sync network: host mode
- Persistent volumes:
  - MariaDB data
  - iTop data/config/logs
  - sync state

Sync flow:
1. Fetch NetBox endpoints.
2. Ensure reference data.
3. Sync manufacturers to Brand.
4. Sync sites and device locations to Location.
5. Sync racks.
6. Sync models to Model.
7. Sync devices to concrete iTop classes.
8. Sync cluster hosts to Hypervisor.
9. Sync VMs to VirtualMachine with virtualhost_id.
10. Skip disabled interfaces/IPs/clusters.
~~~

---

## 12. User Preferences and Working Style

- **Tone Preference:** Indonesian; concise; direct.
- **Detail Level:** Enough detail to operate/debug; avoid long generic theory.
- **Output Format Preference:** Structured summaries, checklists, tables, final counts.
- **Important Style Notes:**
  - Do not expose secrets from `.env`.
  - User prefers action and verification over explanation only.
  - Keep architecture unchanged unless explicitly asked.
  - Avoid inventing facts; verify through commands where possible.

---

## 13. Assumptions and Boundaries

### Confirmed Facts

- NetBox URL is `http://10.70.0.20:9008/`.
- iTop accessible on `http://10.70.0.56:8080/`.
- NetBox device total: 80.
- NetBox VM total: 41.
- iTop imported devices: 80 matched from NetBox.
- iTop imported VMs: 41 matched from NetBox.
- iTop Hypervisors:
  - `Hyper-V`: 33 VMs
  - `Proxmox-FIT`: 8 VMs
- Device locations missing in iTop: 0.
- Device models missing in iTop: 0.
- Interfaces/IPs/clusters remain disabled.

### Assumptions

- Mapping NetBox cluster to iTop `Hypervisor` is acceptable current representation because VMs have no direct NetBox `device`.
- `description` field can carry VM CPU/memory/disk details until exact iTop VM resource fields are mapped.

### Do Not Assume

- Do not assume IPAM classes exist in iTop.
- Do not assume `NetworkInterface` can be created without schema probing.
- Do not assume VMs are mapped to physical hosts; current mapping is cluster-level Hypervisor.
- Do not print real `.env` secrets.

---

## 14. Memory Candidates

| Memory Candidate | Reason |
|---|---|
| In this workspace, iTop sync lives at `/home/infra/dcim_metrics_project/itop` | Useful for future continuation |
| NetBox-to-iTop sync uses `network_mode: host` to reach NetBox | Prevents reverting working network fix |
| iTop `PhysicalDevice` should not be used as create target; use concrete classes | Prevents HTTP 500 errors |
| Current iTop model lacks safe `IPAddress` mapping; IP sync disabled | Prevents repeated failed imports |
| VMs use NetBox cluster to iTop Hypervisor mapping because NetBox VM `device` is null | Important relationship context |

---

## 15. Final Handoff Brief

~~~markdown
Previous session focused on deploying iTop Community Edition and synchronizing CMDB data from NetBox. User wanted iTop populated from NetBox without redesigning infrastructure or adding unrelated systems. Deployment under `/home/infra/dcim_metrics_project/itop` is running with MariaDB, iTop web, and Python sync service. All 80 NetBox devices are imported into concrete iTop classes with location and model populated; all 41 NetBox VMs are imported into iTop VirtualMachine using cluster-level Hypervisor hosts (`Hyper-V` = 33, `Proxmox-FIT` = 8). Current disabled sync areas are interfaces, IP addresses, and separate cluster objects. Next agent should only continue with interface/IP/cluster modeling if requested, and must avoid exposing `.env` secrets.
~~~
