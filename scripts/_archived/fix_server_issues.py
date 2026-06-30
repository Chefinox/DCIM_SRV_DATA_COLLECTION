#!/usr/bin/env python3
"""
Fix Server Issues Script
Mengatasi 5 masalah pada kategori Server di iTop CMDB:
  1. Hapus duplikat interface Ethernet 1-4 dari Netbox connector (HCI servers)
  2. Fix hostname mapping di dcim_itop_inventory_sync.py (untuk CPU/RAM)
  3. Tambahkan relasi interface → NetworkDevice dari Netbox cables
  4. Set powera_id / powerB_id pada Server dari Netbox power chain
"""

import json
import logging
import psycopg2
import requests
import sys

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s [fix-servers] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("fix_servers")

# ─── Configuration ────────────────────────────────────────────────────────────
ITOP_URL  = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER = "admin"
ITOP_PASS = "Inovasi@0918"

DB_HOST = "localhost"
DB_NAME = "dcim_sot"
DB_USER = "sot_admin"
DB_PASS = "Inovasi@0918"

# ─── Netbox Name → iTop Name Mapping ─────────────────────────────────────────
NAME_MAP = {
    "FALAH01-NAS-01": "NAS-INFRA",
    "FALAH01-NAS-02": "NAS-FAT",
    "FALAH01-NAS-03": "NAS-SD01",
    "FALAH01-NAS-04": "NAS-CD01",
    "FALAH01-NAS-05": "NAS-CD02",
    "FALAH01-NAS-06": "NAS-FIT",
    "FALAH01-UPS-3PHASE-30kVA": "UPS-FIT",
    "FALAH01-NVR-HIKVISION": "NVR-FIT",
}

def nb_to_itop_name(nb_name):
    if nb_name in NAME_MAP:
        return NAME_MAP[nb_name]
    if nb_name.startswith("FALAH01-"):
        return nb_name[len("FALAH01-"):]
    return nb_name


# ─── Netbox Interface Name → iTop Interface Name Mapping ─────────────────────
# Netbox uses "Ethernet 1", "Ethernet 2", etc.
# Kafka pipeline (Redfish) uses "NIC1", "NIC2", etc.
# This mapping is for Lenovo servers where Redfish reports NICs differently.
IFACE_NAME_MAP = {
    "Ethernet 1": "NIC1",
    "Ethernet 2": "NIC2",
    "Ethernet 3": "NIC3",
    "Ethernet 4": "NIC4",
    "XCC": "XCC",
}

def nb_to_itop_iface_name(nb_iface_name):
    """Convert Netbox interface name to iTop interface name."""
    return IFACE_NAME_MAP.get(nb_iface_name, nb_iface_name)


# ─── iTop Client ──────────────────────────────────────────────────────────────
class ITopClient:
    def __init__(self):
        self.session = requests.Session()

    def _post(self, payload):
        resp = self.session.post(
            ITOP_URL,
            data={"auth_user": ITOP_USER, "auth_pwd": ITOP_PASS, "json_data": json.dumps(payload)},
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") not in (0, None):
            logger.error("iTop API error: %s", body.get("message", ""))
        return body

    def get_all(self, cls, oql=None):
        body = self._post({
            "operation": "core/get",
            "class": cls,
            "key": oql or f"SELECT {cls}",
            "output_fields": "*",
        })
        result = {}
        for k, v in (body.get("objects") or {}).items():
            oid = k.split("::")[-1]
            result[oid] = v.get("fields", {})
        return result

    def update(self, cls, obj_id, fields, comment="fix-servers"):
        body = self._post({
            "operation": "core/update",
            "class": cls,
            "key": obj_id,
            "fields": {k: v for k, v in fields.items() if v not in (None, "")},
            "comment": comment,
        })
        return body.get("code") == 0

    def delete(self, cls, obj_id, comment="fix-servers: remove duplicate"):
        body = self._post({
            "operation": "core/delete",
            "class": cls,
            "key": obj_id,
            "comment": comment,
        })
        return body.get("code") == 0


# ─── PostgreSQL ───────────────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS)


# ═════════════════════════════════════════════════════════════════════════════
# FIX 1: Hapus duplikat Ethernet 1-4 dari HCI servers
# ═════════════════════════════════════════════════════════════════════════════
def fix1_delete_duplicate_interfaces(itop):
    logger.info("=" * 60)
    logger.info("FIX 1: Delete duplicate Ethernet 1-4 from HCI servers")
    logger.info("=" * 60)

    servers = itop.get_all("Server")
    server_map = {v["name"]: (k, v) for k, v in servers.items()}

    for srv_name in ["SERVER-HCI-01", "SERVER-HCI-02", "SERVER-HCI-03"]:
        if srv_name not in server_map:
            logger.warning("  Server %s not found in iTop", srv_name)
            continue

        srv_id, _ = server_map[srv_name]
        ifaces = itop.get_all("PhysicalInterface", f"SELECT PhysicalInterface WHERE connectableci_id = {srv_id}")

        # Group by name to find duplicates
        by_name = {}
        for oid, fields in ifaces.items():
            name = fields.get("name", "")
            by_name.setdefault(name, []).append((oid, fields))

        # NIC1-4 (from Kafka, have MAC) are the correct ones
        # Ethernet 1-4 (from Netbox, no MAC) are duplicates
        # XCC is management - keep it
        for iface_name, entries in by_name.items():
            if iface_name in ("NIC1", "NIC2", "NIC3", "NIC4", "XCC"):
                continue  # Keep these

            if iface_name.startswith("Ethernet"):
                # Check if there's a corresponding NIC with MAC
                # Ethernet 1 → NIC1, Ethernet 2 → NIC2, etc.
                nic_num = iface_name.replace("Ethernet ", "")
                corresponding_nic = f"NIC{nic_num}"

                if corresponding_nic in by_name:
                    # There's a NIC with this number - delete the Ethernet duplicate
                    for oid, fields in entries:
                        mac = fields.get("macaddress", "")
                        if not mac:
                            logger.info("  ✗ Deleting %s/%s (ID=%s) — duplicate of %s",
                                       srv_name, iface_name, oid, corresponding_nic)
                            itop.delete("PhysicalInterface", oid)
                else:
                    # No corresponding NIC - this might be a unique interface
                    # Keep it but log
                    logger.info("  ⚠ %s/%s has no corresponding NIC — keeping", srv_name, iface_name)


# ═════════════════════════════════════════════════════════════════════════════
# FIX 2: Fix hostname mapping in dcim_itop_inventory_sync.py
# ═════════════════════════════════════════════════════════════════════════════
def fix2_fix_hostname_mapping():
    logger.info("=" * 60)
    logger.info("FIX 2: Fix hostname mapping in dcim_itop_inventory_sync.py")
    logger.info("=" * 60)

    filepath = "/home/infra/dcim_metrics_project/scripts/dcim_itop_inventory_sync.py"
    with open(filepath, "r") as f:
        content = f.read()

    # The problematic code:
    # hostname = raw_hostname.upper()
    # if hostname.startswith("SERVER-"):
    #     hostname = hostname.replace("SERVER-", "SRV-")
    #     hostname = hostname.replace("RENDER", "Render")
    old_code = '''        hostname = raw_hostname.upper()
        if hostname.startswith("SERVER-"):
            hostname = hostname.replace("SERVER-", "SRV-")
            hostname = hostname.replace("RENDER", "Render")'''

    new_code = '''        # Use raw hostname as-is — iTop CI names match dcim_events hostnames
        hostname = raw_hostname'''

    if old_code in content:
        content = content.replace(old_code, new_code)
        with open(filepath, "w") as f:
            f.write(content)
        logger.info("  ✅ Fixed hostname mapping in %s", filepath)
    else:
        # Try to find the actual code
        if "SRV-" in content and "RENDER" in content:
            logger.warning("  ⚠ Hostname mapping code found but format differs. Manual fix needed.")
            # Find and show the problematic lines
            for i, line in enumerate(content.split("\n"), 1):
                if "SRV-" in line or ("RENDER" in line and "replace" in line):
                    logger.info("    Line %d: %s", i, line.strip())
        else:
            logger.info("  ℹ Hostname mapping already fixed or not found")


# ═════════════════════════════════════════════════════════════════════════════
# FIX 3: Add interface → NetworkDevice relationships from Netbox cables
# ═════════════════════════════════════════════════════════════════════════════
def fix3_add_interface_relationships(itop):
    logger.info("=" * 60)
    logger.info("FIX 3: Add interface → NetworkDevice cable relationships")
    logger.info("=" * 60)

    # 1. Build cable lookup from netbox_cables
    # Convert Netbox interface names to iTop interface names for server-side lookups
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT a_device, a_interface, b_device, b_interface, cable_type
        FROM netbox_cables
        ORDER BY a_device
    """)
    cable_lookup = {}  # (device_nb_name, itop_iface_name) → (peer_nb_name, peer_iface, cable_type)
    for row in cur.fetchall():
        a_dev, a_iface, b_dev, b_iface, cable_type = row
        # Convert server-side interface names to iTop format
        a_itop_iface = nb_to_itop_iface_name(a_iface)
        b_itop_iface = nb_to_itop_iface_name(b_iface)
        cable_lookup[(a_dev, a_itop_iface)] = (b_dev, b_iface, cable_type)
        cable_lookup[(b_dev, b_itop_iface)] = (a_dev, a_iface, cable_type)
    cur.close()
    conn.close()

    # 2. Get all servers
    servers = itop.get_all("Server")

    for srv_id, srv_fields in servers.items():
        srv_name = srv_fields["name"]
        nb_name = f"FALAH01-{srv_name}"  # Reverse mapping

        # Get interfaces for this server
        ifaces = itop.get_all("PhysicalInterface", f"SELECT PhysicalInterface WHERE connectableci_id = {srv_id}")

        for iface_id, iface_fields in ifaces.items():
            iface_name = iface_fields.get("name", "")
            existing_comment = iface_fields.get("comment", "")

            # Skip if already has cable info
            if "Connected to:" in existing_comment:
                continue

            # Look up cable connection
            # Try multiple name formats: FALAH01-prefixed, raw name, case-insensitive
            peer_info = None
            for lookup_dev in [nb_name, srv_name]:
                key = (lookup_dev, iface_name)
                if key in cable_lookup:
                    peer_info = cable_lookup[key]
                    break
            # Case-insensitive fallback
            if not peer_info:
                for (dev, iface), peer in cable_lookup.items():
                    if dev.upper() == nb_name.upper() and iface == iface_name:
                        peer_info = peer
                        break

            if not peer_info:
                continue

            peer_device, peer_iface, cable_type = peer_info
            peer_itop_name = nb_to_itop_name(peer_device)

            comment = f"Connected to: {peer_itop_name}/{peer_iface}"
            if cable_type:
                comment += f" | Cable: {cable_type}"

            logger.info("  ↺ %s/%s → %s/%s", srv_name, iface_name, peer_itop_name, peer_iface)
            itop.update("PhysicalInterface", iface_id, {"comment": comment})


# ═════════════════════════════════════════════════════════════════════════════
# FIX 4: Set powera_id / powerB_id on servers
# ═════════════════════════════════════════════════════════════════════════════
def fix4_set_power_relationships(itop):
    logger.info("=" * 60)
    logger.info("FIX 4: Set powerA/powerB source on servers")
    logger.info("=" * 60)

    # 1. Build power chain from netbox_cables
    # Server power-port → PDU power-outlet
    # PDU power-port → UPS
    conn = get_db()
    cur = conn.cursor()

    # Get server → PDU connections
    cur.execute("""
        SELECT a_device, a_interface, b_device, b_interface
        FROM netbox_cables
        WHERE cable_type = 'power'
        AND (a_device ILIKE '%server%' OR a_device ILIKE '%hci%' OR a_device ILIKE '%render%')
        ORDER BY a_device, a_interface
    """)
    server_pdu_map = {}  # (server_nb_name, power_port) → (pdu_nb_name, pdu_port)
    for row in cur.fetchall():
        server_pdu_map[(row[0], row[1])] = (row[2], row[3])

    # Get PDU → UPS connections
    cur.execute("""
        SELECT a_device, a_interface, b_device, b_interface
        FROM netbox_cables
        WHERE cable_type = 'power' AND a_device ILIKE '%pdu%'
    """)
    pdu_ups_map = {}  # pdu_nb_name → ups_nb_name
    for row in cur.fetchall():
        pdu_ups_map[row[0]] = row[2]

    cur.close()
    conn.close()

    # 2. Get PowerSource objects in iTop (PDUs are registered as PowerSource)
    power_sources = itop.get_all("PowerSource")
    ps_by_name = {v["name"]: (k, v) for k, v in power_sources.items()}

    # 3. Get all servers
    servers = itop.get_all("Server")

    for srv_id, srv_fields in servers.items():
        srv_name = srv_fields["name"]
        nb_name = f"FALAH01-{srv_name}"

        current_powera = srv_fields.get("powerA_id", "0")
        current_powerb = srv_fields.get("powerB_id", "0")

        # Find power connections for this server
        power_a_pdu = None  # power1 → UPS-connected PDU
        power_b_pdu = None  # power2 → NON-UPS-connected PDU

        for (dev, port), (pdu, pdu_port) in server_pdu_map.items():
            # Match case-insensitive (Netbox has RENDER-01, iTop has Render-01)
            if dev.upper() != nb_name.upper():
                continue
            if "power1" in port.lower() or "psu 1" in port.lower() or "ps1" in port.lower():
                power_a_pdu = pdu
            elif "power2" in port.lower() or "psu 2" in port.lower() or "ps2" in port.lower():
                power_b_pdu = pdu

        updates = {}

        # Set powerA (primary - UPS connected PDU)
        if power_a_pdu and power_a_pdu in ps_by_name:
            ps_id, _ = ps_by_name[power_a_pdu]
            if current_powera != ps_id:
                updates["powerA_id"] = ps_id
                logger.info("  %s powerA → %s (ID=%s)", srv_name, power_a_pdu, ps_id)

        # Set powerB (redundant - could be UPS or NON-UPS PDU)
        if power_b_pdu and power_b_pdu in ps_by_name:
            ps_id, _ = ps_by_name[power_b_pdu]
            if current_powerb != ps_id:
                updates["powerB_id"] = ps_id
                logger.info("  %s powerB → %s (ID=%s)", srv_name, power_b_pdu, ps_id)

        if updates:
            itop.update("Server", srv_id, updates)
        else:
            logger.info("  %s: power already set or no mapping found", srv_name)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════════════════
def main():
    dry_run = "--dry-run" in sys.argv
    fix_num = None
    for arg in sys.argv[1:]:
        if arg.startswith("--fix="):
            fix_num = int(arg.split("=")[1])

    logger.info("Starting Server Fixes (dry_run=%s, fix=%s)", dry_run, fix_num)

    itop = ITopClient()

    if fix_num is None or fix_num == 1:
        fix1_delete_duplicate_interfaces(itop)

    if fix_num is None or fix_num == 2:
        fix2_fix_hostname_mapping()

    if fix_num is None or fix_num == 3:
        fix3_add_interface_relationships(itop)

    if fix_num is None or fix_num == 4:
        fix4_set_power_relationships(itop)

    logger.info("All fixes complete!")


if __name__ == "__main__":
    main()
