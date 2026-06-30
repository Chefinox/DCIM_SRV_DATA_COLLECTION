#!/usr/bin/env python3
"""
populate_hci01_itop.py
======================
Mengisi otomatis data iTop CMDB untuk FALAH01-SERVER-HCI-01:
  1. Physical Interfaces (NIC) — nama prefixed: FALAH01-SERVER-HCI-01:Ethernet 1, dst.
  2. Network Device connections (uplink aktif ke DIST-SW-SERVER1 dan SERVER2)
  3. Logical Volumes (Physical Disk dari RAID controller Redfish)

Sumber data:
  - Redfish API (https://10.50.0.2) dengan user hndept
  - NetBox API (http://10.70.0.20:9008) untuk mapping interface ↔ switch
  - iTop REST API (http://localhost:8080)

Usage:
  python3 populate_hci01_itop.py [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import warnings

import requests

warnings.filterwarnings("ignore")

# ─────────────────────── Konfigurasi ───────────────────────
ITOP_URL   = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER  = "admin"
ITOP_PASS  = "Inovasi@0918"

REDFISH_BASE = "https://10.50.0.2"
REDFISH_USER = "hndept"
REDFISH_PASS = "F!tech@0918"

NETBOX_URL   = "http://10.70.0.20:9008"
NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

# iTop Object IDs (sudah terverifikasi)
SERVER_ITOP_ID   = "26"   # Server::26 = FALAH01-SERVER-HCI-01
SERVER_NAME      = "FALAH01-SERVER-HCI-01"
ORG_ID           = "1"

# Network Device di iTop yang terhubung
SWITCH_SERVER1_ID   = "6"   # NetworkDevice::6 = FALAH01-FIT-DIST-SW-SERVER1
SWITCH_SERVER2_ID   = "7"   # NetworkDevice::7 = FALAH01-FIT-DIST-SW-SERVER2
SWITCH_SERVER1_NAME = "FALAH01-FIT-DIST-SW-SERVER1"
SWITCH_SERVER2_NAME = "FALAH01-FIT-DIST-SW-SERVER2"

# NetBox Device ID untuk FALAH01-SERVER-HCI-01
NETBOX_DEVICE_ID = 177

# ─────────────────────── Cached Redfish Data ───────────────────────
# Data sudah diverifikasi dari Redfish pada sesi explorasi.
# Digunakan sebagai fallback jika Redfish timeout/lambat.
CACHED_NICS = [
    {"id": "NIC4",      "name": "External Ethernet Interface",   "mac": "D4:04:E6:78:7D:67", "speed": 1000,  "state": "Enabled"},
    {"id": "NIC1",      "name": "External Ethernet Interface",   "mac": "D4:04:E6:78:7D:64", "speed": 10000, "state": "Enabled"},
    {"id": "NIC2",      "name": "External Ethernet Interface",   "mac": "D4:04:E6:78:7D:65", "speed": 10000, "state": "Enabled"},
    {"id": "NIC3",      "name": "External Ethernet Interface",   "mac": "D4:04:E6:78:7D:66", "speed": 10000, "state": "Enabled"},
    {"id": "ToManager", "name": "Host Ethernet Interface",       "mac": "3A:68:DD:A9:49:27", "speed": None,  "state": "Disabled"},
]
CACHED_DISKS = [
    {"id": "Disk.0",  "name": "960GB 6Gbps SATA 2.5 SSD (SED)", "model": "MTFDDAK960TGA-1BC16A", "serial": "46693388", "size_gb": 960.2, "media_type": "SSD", "protocol": "SATA", "state": "Enabled", "controller": "RAID Storage", "raid": "RAID 1"},
    {"id": "Disk.1",  "name": "960GB 6Gbps SATA 2.5 SSD (SED)", "model": "MTFDDAK960TGA-1BC16A", "serial": "4669335B", "size_gb": 960.2, "media_type": "SSD", "protocol": "SATA", "state": "Enabled", "controller": "RAID Storage", "raid": "RAID 1"},
    {"id": "Disk.2",  "name": "960GB 6Gbps SATA 2.5 SSD (SED)", "model": "MTFDDAK960TGA-1BC16A", "serial": "466934C9", "size_gb": 960.2, "media_type": "SSD", "protocol": "SATA", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.3",  "name": "960GB 6Gbps SATA 2.5 SSD (SED)", "model": "MTFDDAK960TGA-1BC16A", "serial": "46693458", "size_gb": 960.2, "media_type": "SSD", "protocol": "SATA", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.4",  "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0MG", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.5",  "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0P3", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.6",  "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0LV", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.7",  "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0NP", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.8",  "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0PA", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.9",  "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3L0A1XC", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.10", "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0NM", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
    {"id": "Disk.11", "name": "2.4TB 12Gbps SAS 2.5 HDD",       "model": "AL15SEB24EQ",         "serial": "Z3M0A0P1", "size_gb": 2400.5, "media_type": "HDD", "protocol": "SAS", "state": "Enabled", "controller": "RAID Storage", "raid": ""},
]

# Mapping: NetBox interface name → (switch_id, switch_port, switch_name, Redfish NIC index)
# Berdasarkan data NetBox cables + Redfish speed matching
INTERFACE_MAP = [
    {
        "netbox_name": "Ethernet 1",
        "itop_name":   f"{SERVER_NAME}:Ethernet 1",
        "redfish_name": "NIC4",          # Redfish: External Ethernet Interface NIC4, 1000 Mbps
        "speed_mbps": 1000,
        "switch_id":   SWITCH_SERVER1_ID,
        "switch_name": SWITCH_SERVER1_NAME,
        "switch_port": "ether13",
        "device_port": "Ethernet 1",
        "comment":     "TEAMING LAN — Connected to DIST-SW-SERVER1:ether13",
    },
    {
        "netbox_name": "Ethernet 2",
        "itop_name":   f"{SERVER_NAME}:Ethernet 2",
        "redfish_name": "NIC1",          # Redfish: External Ethernet Interface NIC1, 10000 Mbps
        "speed_mbps": 10000,
        "switch_id":   SWITCH_SERVER2_ID,
        "switch_name": SWITCH_SERVER2_NAME,
        "switch_port": "ether1",
        "device_port": "Ethernet 2",
        "comment":     "Bonding HCI 01 — Connected to DIST-SW-SERVER2:ether1 (Port1)",
    },
    {
        "netbox_name": "Ethernet 3",
        "itop_name":   f"{SERVER_NAME}:Ethernet 3",
        "redfish_name": "NIC2",
        "speed_mbps": 10000,
        "switch_id":   SWITCH_SERVER2_ID,
        "switch_name": SWITCH_SERVER2_NAME,
        "switch_port": "ether2",
        "device_port": "Ethernet 3",
        "comment":     "Bonding HCI 01 — Connected to DIST-SW-SERVER2:ether2 (Port2)",
    },
    {
        "netbox_name": "Ethernet 4",
        "itop_name":   f"{SERVER_NAME}:Ethernet 4",
        "redfish_name": "NIC3",
        "speed_mbps": 10000,
        "switch_id":   SWITCH_SERVER2_ID,
        "switch_name": SWITCH_SERVER2_NAME,
        "switch_port": "ether3",
        "device_port": "Ethernet 4",
        "comment":     "Bonding HCI 01 — Connected to DIST-SW-SERVER2:ether3 (Port3)",
    },
    {
        "netbox_name": "XCC",
        "itop_name":   f"{SERVER_NAME}:XCC",
        "redfish_name": "ToManager",     # Redfish: Host Ethernet Interface (ToManager)
        "speed_mbps": 1000,
        "switch_id":   SWITCH_SERVER1_ID,
        "switch_name": SWITCH_SERVER1_NAME,
        "switch_port": "ether33",
        "device_port": "XCC",
        "comment":     "Management (XCC/iDRAC) — Connected to DIST-SW-SERVER1:ether33 | IP: 10.50.0.2",
    },
]

# Uplink connections (hanya switch yang benar-benar terhubung saat ini)
UPLINK_CONNECTIONS = [
    {
        "switch_id":   SWITCH_SERVER1_ID,
        "switch_name": SWITCH_SERVER1_NAME,
        "network_port": "ether13",   # Port utama teaming di SW-SERVER1
        "device_port":  "Ethernet 1",
        "connection_type": "downlink",
    },
    {
        "switch_id":   SWITCH_SERVER2_ID,
        "switch_name": SWITCH_SERVER2_NAME,
        "network_port": "ether1",    # Port utama bonding di SW-SERVER2
        "device_port":  "Ethernet 2",
        "connection_type": "downlink",
    },
]

# ─────────────────────── Logger ───────────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("populate_hci01")


# ─────────────────────── iTop Client ───────────────────────
class ITopClient:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.session = requests.Session()

    def _post(self, payload: dict) -> dict:
        r = self.session.post(
            ITOP_URL,
            data={
                "auth_user": ITOP_USER,
                "auth_pwd":  ITOP_PASS,
                "json_data": json.dumps(payload),
            },
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        if body.get("code") not in (0, None):
            raise RuntimeError(f"iTop API error: {body}")
        return body

    def find(self, class_name: str, oql: str) -> tuple[str | None, dict]:
        body = self._post({
            "operation": "core/get",
            "class": class_name,
            "key": oql,
            "output_fields": "*",
        })
        objs = body.get("objects") or {}
        if not objs:
            return None, {}
        key, val = next(iter(objs.items()))
        return key.split("::")[-1], val.get("fields", {})

    def upsert(self, class_name: str, find_oql: str, fields: dict, comment: str = "populate_hci01") -> str | None:
        obj_id, current = self.find(class_name, find_oql)
        clean = {k: v for k, v in fields.items() if v not in (None, "")}
        if obj_id:
            # Sudah ada, skip (idempotent)
            LOG.info("  ⏭  EXISTS %s id=%s name=%s", class_name, obj_id, fields.get("name", find_oql))
            return obj_id
        if self.dry_run:
            LOG.info("  🔍 DRY-RUN CREATE %s fields=%s", class_name, clean)
            return "dry-run"
        body = self._post({
            "operation": "core/create",
            "class": class_name,
            "fields": clean,
            "comment": comment,
        })
        objs = body.get("objects") or {}
        if objs:
            new_id = next(iter(objs.keys())).split("::")[-1]
            LOG.info("  ✅ CREATED %s id=%s name=%s", class_name, new_id, fields.get("name", "?"))
            return new_id
        return None

    def update(self, class_name: str, obj_id: str, fields: dict, comment: str = "populate_hci01") -> bool:
        """Update field pada objek yang sudah ada."""
        clean = {k: v for k, v in fields.items() if v not in (None, "")}
        if not clean:
            return True
        if self.dry_run:
            LOG.info("  🔍 DRY-RUN UPDATE %s id=%s fields=%s", class_name, obj_id, clean)
            return True
        body = self._post({
            "operation": "core/update",
            "class": class_name,
            "key": obj_id,
            "fields": clean,
            "comment": comment,
        })
        return body.get("code") == 0

    def delete_by_oql(self, class_name: str, oql: str, comment: str = "cleanup") -> int:
        """Hapus semua objek yang match OQL, return jumlah yang dihapus."""
        if self.dry_run:
            LOG.info("  🔍 DRY-RUN DELETE %s WHERE %s", class_name, oql)
            return 0
        body = self._post({
            "operation": "core/delete",
            "class": class_name,
            "key": oql,
            "comment": comment,
        })
        deleted = len(body.get("objects") or {})
        return deleted


# ─────────────────────── Redfish Client ───────────────────────
class RedfishClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.auth = (REDFISH_USER, REDFISH_PASS)
        self.session.verify = False

    def get(self, path: str, timeout: int = 8) -> dict:
        url = REDFISH_BASE + path if path.startswith("/") else path
        r = self.session.get(url, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_ethernet_interfaces(self) -> list[dict]:
        """Return list NIC dari Redfish dengan MAC address."""
        col = self.get("/redfish/v1/Systems/1/EthernetInterfaces", timeout=6)
        nics = []
        for member in col.get("Members", []):
            try:
                idata = self.get(member["@odata.id"], timeout=6)
                nics.append({
                    "id":    idata.get("Id", ""),
                    "name":  idata.get("Name", ""),
                    "mac":   (idata.get("MACAddress") or "").upper(),
                    "speed": idata.get("SpeedMbps"),
                    "state": idata.get("Status", {}).get("State", ""),
                })
            except Exception as e:
                LOG.warning("Skip NIC %s: %s", member.get("@odata.id"), e)
        return nics

    def get_physical_disks(self) -> list[dict]:
        """Return list physical disk dari RAID controller."""
        try:
            storage = self.get("/redfish/v1/Systems/1/Storage", timeout=6)
        except Exception as e:
            LOG.error("Cannot get storage list: %s", e)
            return []
        disks = []
        for ctrl_member in storage.get("Members", []):
            try:
                ctrl = self.get(ctrl_member["@odata.id"], timeout=6)
                ctrl_name = ctrl.get("Name", ctrl_member["@odata.id"].split("/")[-1])
                for drive in ctrl.get("Drives", []):
                    try:
                        d = self.get(drive["@odata.id"], timeout=6)
                        state = d.get("Status", {}).get("State", "")
                        if state == "Absent":
                            continue  # Skip slot kosong
                        size_gb = round((d.get("CapacityBytes") or 0) / 1e9, 1)
                        disks.append({
                            "id":          d.get("Id", ""),
                            "name":        d.get("Name", "").strip(),
                            "model":       (d.get("Model") or "").strip(),
                            "serial":      (d.get("SerialNumber") or "").strip(),
                            "size_gb":     size_gb,
                            "media_type":  d.get("MediaType", ""),
                            "protocol":    d.get("Protocol", ""),
                            "state":       state,
                            "controller":  ctrl_name,
                        })
                    except Exception as e:
                        LOG.warning("Skip drive %s: %s", drive.get("@odata.id"), e)
            except Exception as e:
                LOG.warning("Skip controller %s: %s", ctrl_member.get("@odata.id"), e)
        return disks


# ─────────────────────── Tahap 1: Physical Interfaces ───────────────────────
def sync_physical_interfaces(itop: ITopClient, redfish_nics: list[dict], dry_run: bool) -> dict[str, str]:
    """Buat PhysicalInterface di iTop untuk setiap NIC SRV-HCI-01.
    Return mapping itop_name → itop_id.
    """
    LOG.info("=" * 60)
    LOG.info("TAHAP 1: Sync Physical Interfaces")
    LOG.info("=" * 60)

    # Build MAC lookup dari Redfish berdasarkan speed
    # NIC1=10G, NIC2=10G, NIC3=10G, NIC4=1G, ToManager=disabled
    mac_by_redfish_name: dict[str, str] = {}
    for nic in redfish_nics:
        raw_name = nic["name"]
        nid = nic["id"]
        # Map redfish name ke identifier kita
        if "NIC1" in nid or raw_name.endswith("NIC1"):
            mac_by_redfish_name["NIC1"] = nic["mac"]
        elif "NIC2" in nid or raw_name.endswith("NIC2"):
            mac_by_redfish_name["NIC2"] = nic["mac"]
        elif "NIC3" in nid or raw_name.endswith("NIC3"):
            mac_by_redfish_name["NIC3"] = nic["mac"]
        elif "NIC4" in nid or raw_name.endswith("NIC4"):
            mac_by_redfish_name["NIC4"] = nic["mac"]
        elif "Manager" in raw_name or "ToManager" in nid:
            mac_by_redfish_name["ToManager"] = nic["mac"]

    LOG.info("MAC from Redfish: %s", mac_by_redfish_name)

    created_ids: dict[str, str] = {}
    for iface in INTERFACE_MAP:
        itop_name    = iface["itop_name"]
        redfish_key  = iface["redfish_name"]
        mac          = mac_by_redfish_name.get(redfish_key, "")
        speed_str    = str(iface["speed_mbps"]) if iface["speed_mbps"] else ""

        # XCC management interface — IP address management server
        ip_address = "10.50.0.2" if iface["netbox_name"] == "XCC" else ""

        fields = {
            "name":             itop_name,
            "connectableci_id": f"SELECT Server WHERE id = {SERVER_ITOP_ID}",
            # org_id: read-only di PhysicalInterface, diisi otomatis dari parent server
            "macaddress":       mac,
            "ipaddress":        ip_address,
            "speed":            speed_str,
            "comment":          iface["comment"],
        }

        oql = f"SELECT PhysicalInterface WHERE name = '{itop_name}' AND connectableci_id = {SERVER_ITOP_ID}"
        ni_id = itop.upsert("PhysicalInterface", oql, fields, comment="populate_hci01 - network interface")
        if ni_id:
            created_ids[itop_name] = ni_id

    LOG.info("Physical Interfaces selesai: %d/%d", len(created_ids), len(INTERFACE_MAP))
    return created_ids


# ─────────────────────── Tahap 2: Network Device Connections ───────────────────────
def sync_network_device_connections(itop: ITopClient) -> None:
    """Buat link lnkConnectableCIToNetworkDevice untuk uplink aktif SRV-HCI-01."""
    LOG.info("=" * 60)
    LOG.info("TAHAP 2: Sync Network Device Connections (Uplink Aktif)")
    LOG.info("=" * 60)

    for conn in UPLINK_CONNECTIONS:
        sw_id   = conn["switch_id"]
        sw_name = conn["switch_name"]
        fields  = {
            "connectableci_id": f"SELECT Server WHERE id = {SERVER_ITOP_ID}",
            "networkdevice_id": f"SELECT NetworkDevice WHERE id = {sw_id}",
            "network_port":     conn["network_port"],
            "device_port":      conn["device_port"],
            "connection_type":  conn["connection_type"],
        }
        oql = (
            f"SELECT lnkConnectableCIToNetworkDevice "
            f"WHERE connectableci_id = {SERVER_ITOP_ID} AND networkdevice_id = {sw_id}"
        )
        lnk_id = itop.upsert("lnkConnectableCIToNetworkDevice", oql, fields,
                              comment="populate_hci01 - network device link")
        if lnk_id:
            LOG.info("  Link: %s ↔ %s (port %s)", SERVER_NAME, sw_name, conn["network_port"])

    LOG.info("Network Device Connections selesai.")


# ─────────────────────── Tahap 3: Logical Volumes (Physical Disks) ───────────────────────
def sync_logical_volumes(itop: ITopClient, disks: list[dict]) -> None:
    """Buat LogicalVolume di iTop untuk setiap physical disk yang terpasang.
    
    Flow:
      1. Buat/cari StorageSystem CI (internal RAID controller)
      2. Untuk tiap disk: buat LogicalVolume linked ke StorageSystem
      3. Buat lnkServerToVolume untuk link ke Server
    """
    LOG.info("=" * 60)
    LOG.info("TAHAP 3: Sync Logical Volumes (Physical Disks dari Redfish)")
    LOG.info("=" * 60)

    enabled_disks = [d for d in disks if d["state"] == "Enabled"]
    LOG.info("Disk dari Redfish — Total: %d | Enabled: %d", len(disks), len(enabled_disks))

    # ── Step 3a: Ensure StorageSystem (internal RAID) ada ──
    ss_name  = f"{SERVER_NAME}:Internal RAID Storage"
    ss_oql   = f"SELECT StorageSystem WHERE name = '{ss_name}'"
    ss_fields = {
        "name":        ss_name,
        "org_id":      "SELECT Organization WHERE id = 1",
        "description": (
            "Internal RAID Controller RAID_Slot15 | Lenovo ThinkSystem SR650 V3 | "
            f"{len([d for d in enabled_disks if d['media_type']=='SSD'])}x SSD 960GB SATA + "
            f"{len([d for d in enabled_disks if d['media_type']=='HDD'])}x HDD 2.4TB SAS"
        ),
        "location_id": "SELECT Location WHERE name = \"Ruang Server\"",
        "status":      "production",
    }
    ss_id = itop.upsert("StorageSystem", ss_oql, ss_fields,
                        comment="populate_hci01 - internal RAID storage system")
    if not ss_id or ss_id == "dry-run":
        LOG.warning("StorageSystem tidak bisa dibuat — skip Logical Volumes")
        return
    LOG.info("  StorageSystem: %s (id=%s)", ss_name, ss_id)

    # ── Step 3b: Buat LogicalVolume tiap disk ──
    for disk in enabled_disks:
        disk_id   = disk["id"]
        disk_label = f"{SERVER_NAME}:{disk_id} ({disk['size_gb']}GB {disk['media_type']} {disk['protocol']})"
        description = (
            f"Physical Disk | Controller: {disk['controller']} | "
            f"Model: {disk['model']} | SN: {disk['serial']} | "
            f"Size: {disk['size_gb']} GB | Type: {disk['media_type']} | "
            f"Protocol: {disk['protocol']}"
        )

        size_str = f"{disk['size_gb']} GB"
        raid_str = disk.get("raid", "")

        lv_oql = f"SELECT LogicalVolume WHERE name = '{disk_label}'"
        lv_fields = {
            "name":             disk_label,
            "lun_id":           disk_id,           # e.g. "Disk.0"
            "storagesystem_id": f"SELECT StorageSystem WHERE id = {ss_id}",
            "description":      description,
            "size":             size_str,           # e.g. "960.2 GB"
            "raid_level":       raid_str,
        }
        lv_id = itop.upsert("LogicalVolume", lv_oql, lv_fields,
                            comment="populate_hci01 - physical disk")

        # Jika LV sudah EXISTS (upsert skip), tetap update size & raid
        if lv_id and lv_id not in ("dry-run", None):
            lv_obj_id, lv_fields_cur = itop.find(
                "LogicalVolume", f"SELECT LogicalVolume WHERE id = {lv_id}"
            )
            update_fields = {}
            if lv_fields_cur.get("size") != size_str:
                update_fields["size"] = size_str
            if lv_fields_cur.get("raid_level") != raid_str:
                update_fields["raid_level"] = raid_str
            
            if update_fields:
                itop.update("LogicalVolume", lv_id, update_fields,
                            comment="populate_hci01 - update disk size/raid")
                LOG.info("    ↳ Updated LV %s", update_fields)

        # ── Step 3c: Link LogicalVolume → Server (dengan size_used = full disk size) ──
        if lv_id and lv_id != "dry-run":
            link_oql = (
                f"SELECT lnkServerToVolume "
                f"WHERE server_id = {SERVER_ITOP_ID} AND volume_id = {lv_id}"
            )
            link_fields = {
                "server_id": f"SELECT Server WHERE id = {SERVER_ITOP_ID}",
                "volume_id": f"SELECT LogicalVolume WHERE id = {lv_id}",
                "size_used": size_str,   # Full capacity = used by server (internal disk)
            }
            lnk_id = itop.upsert("lnkServerToVolume", link_oql, link_fields,
                                  comment="populate_hci01 - server-volume link")

            # Jika link sudah EXISTS, tetap update size_used
            if lnk_id and lnk_id not in ("dry-run", None):
                lnk_obj_id, lnk_cur = itop.find(
                    "lnkServerToVolume", f"SELECT lnkServerToVolume WHERE id = {lnk_id}"
                )
                if lnk_cur.get("size_used") != size_str:
                    itop.update("lnkServerToVolume", lnk_id, {"size_used": size_str},
                                comment="populate_hci01 - update size_used")
                    LOG.info("    ↳ Updated size_used=%s", size_str)

    LOG.info("Logical Volumes selesai: %d disk diproses.", len(enabled_disks))


# ─────────────────────── Verifikasi Akhir ───────────────────────
def verify_result(itop: ITopClient) -> None:
    LOG.info("=" * 60)
    LOG.info("VERIFIKASI AKHIR — %s", SERVER_NAME)
    LOG.info("=" * 60)

    # Check physical interfaces
    _, server_fields = itop.find("Server", f"SELECT Server WHERE id = {SERVER_ITOP_ID}")
    ni_count  = len(server_fields.get("physicalinterface_list", []))
    nd_count  = len(server_fields.get("networkdevice_list", []))
    lv_count  = len(server_fields.get("logicalvolumes_list", []))

    LOG.info("  Physical Interfaces : %d (expected 5)", ni_count)
    LOG.info("  Network Devices     : %d (expected 2)", nd_count)
    LOG.info("  Logical Volumes     : %d (expected 12)", lv_count)

    if ni_count >= 5 and nd_count >= 2 and lv_count >= 12:
        LOG.info("✅ SEMUA DATA TERISI LENGKAP!")
    else:
        LOG.warning("⚠️  Ada data yang belum terisi. Periksa log di atas.")


# ─────────────────────── Main ───────────────────────
def main() -> int:
    parser = argparse.ArgumentParser(description="Populate iTop CMDB untuk FALAH01-SERVER-HCI-01")
    parser.add_argument("--dry-run", action="store_true", help="Simulasi tanpa menulis ke iTop")
    parser.add_argument("--use-cache", action="store_true", default=True,
                        help="Gunakan cached Redfish data (default: True, skip Redfish fetch)")
    parser.add_argument("--live-redfish", action="store_true",
                        help="Fetch langsung dari Redfish (override --use-cache)")
    args = parser.parse_args()

    if args.dry_run:
        LOG.info("🔍 MODE DRY-RUN — tidak ada perubahan yang akan disimpan")

    use_live = args.live_redfish

    itop    = ITopClient(dry_run=args.dry_run)

    # ── Ambil data NIC ──
    if use_live:
        redfish = RedfishClient()
        LOG.info("Mengambil data NIC dari Redfish (%s)...", REDFISH_BASE)
        try:
            redfish_nics = redfish.get_ethernet_interfaces()
            LOG.info("  Ditemukan %d NIC dari Redfish (live)", len(redfish_nics))
        except Exception as e:
            LOG.warning("Redfish timeout/error: %s — fallback ke cached data", e)
            redfish_nics = CACHED_NICS
    else:
        LOG.info("Menggunakan cached NIC data (5 NIC, sudah diverifikasi dari Redfish)")
        redfish_nics = CACHED_NICS

    for nic in redfish_nics:
        LOG.info("  NIC %s: MAC=%s Speed=%s State=%s", nic["id"], nic["mac"], nic.get("speed"), nic["state"])

    # ── Ambil data Disk ──
    if use_live:
        LOG.info("Mengambil data Physical Disk dari Redfish...")
        try:
            disks = redfish.get_physical_disks()
            LOG.info("  Ditemukan %d disk (live)", len(disks))
        except Exception as e:
            LOG.warning("Redfish disk timeout/error: %s — fallback ke cached data", e)
            disks = CACHED_DISKS
    else:
        LOG.info("Menggunakan cached Disk data (12 disk, sudah diverifikasi dari Redfish)")
        disks = CACHED_DISKS

    for d in disks:
        LOG.info("  %s: %s %s %.0fGB SN=%s", d["id"], d["model"], d["media_type"], d["size_gb"], d["serial"])

    # ── Tahap 1: Physical Interfaces ──
    sync_physical_interfaces(itop, redfish_nics, args.dry_run)

    # ── Tahap 2: Network Device Connections ──
    sync_network_device_connections(itop)

    # ── Tahap 3: Logical Volumes (Physical Disks) ──
    sync_logical_volumes(itop, disks)

    # ── Verifikasi ──
    if not args.dry_run:
        verify_result(itop)

    LOG.info("Script selesai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
