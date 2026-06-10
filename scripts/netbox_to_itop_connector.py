#!/usr/bin/env python3
"""
Netbox → iTop Connector v1
Syncs interfaces and cable connections from Netbox to iTop CMDB.

Strategy:
  - Only ADDS interfaces/cables that don't exist yet (idempotent, non-destructive)
  - Does NOT overwrite data created by the Kafka pipeline (dcim-itop-unified)
  - Stores cable info in PhysicalInterface.comment field
  - Stores raw cable data in PostgreSQL netbox_cables table

Usage:
  python3 netbox_to_itop_connector.py              # One-shot sync
  python3 netbox_to_itop_connector.py --daemon      # Run as daemon (every 3600s)
  python3 netbox_to_itop_connector.py --dry-run     # Preview changes without writing
"""

import json
import logging
import os
import signal
import sys
import time
from datetime import datetime, timezone

import psycopg2
import requests

# ─── Configuration ────────────────────────────────────────────────────────────
ITOP_URL      = "http://localhost:8080/webservices/rest.php?version=1.3"
ITOP_USER     = "admin"
ITOP_PASS     = "Inovasi@0918"

NETBOX_URL    = "http://10.70.0.20:9008"
NETBOX_TOKEN  = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

DB_HOST       = "localhost"
DB_NAME       = "dcim_sot"
DB_USER       = "sot_admin"
DB_PASS       = "Inovasi@0918"

ORG_ID        = "1"
SYNC_INTERVAL = 3600  # seconds between syncs in daemon mode

# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s %(levelname)-8s [netbox-connector] %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("netbox_connector")

# ─── Signal handling ──────────────────────────────────────────────────────────
_STOP = False

def _handle_signal(signum, frame):
    global _STOP
    logger.info("Received signal %s, shutting down...", signum)
    _STOP = True

signal.signal(signal.SIGTERM, _handle_signal)
signal.signal(signal.SIGINT, _handle_signal)

# ─── Name Mapping: Netbox → iTop ─────────────────────────────────────────────
# Netbox uses "FALAH01-" prefix; iTop uses shorter names.
# Most devices follow pattern: strip prefix + fix case.
# NAS and some special devices need explicit mapping.

# Explicit overrides for devices that don't follow the simple pattern
NAME_MAP = {
    "FALAH01-NAS-01": "NAS-INFRA",
    "FALAH01-NAS-02": "NAS-FAT",
    "FALAH01-NAS-03": "NAS-SD01",
    "FALAH01-NAS-04": "NAS-CD01",
    "FALAH01-NAS-05": "NAS-CD02",
    "FALAH01-NAS-06": "NAS-FIT",
    "FALAH01-UPS-3PHASE-30kVA": "UPS-FIT",
    "FALAH01-NVR-HIKVISION": "NVR-FIT",
    "FALAH01-PC-RENDER-01": "PC-Render-01",
    "FALAH01-PC-RENDER-02": "PC-Render-02",
    "FALAH01-PC-RENDER-03": "PC-Render-03",
    "FALAH01-PC-RENDER-04": "PC-Render-04",
    "FALAH01-SERVER-RENDER-01": "SERVER-Render-01",
    "FALAH01-SERVER-RENDER-02": "SERVER-Render-02",
}


def nb_to_itop_name(nb_name: str) -> str:
    """Convert Netbox device name to iTop device name."""
    if nb_name in NAME_MAP:
        return NAME_MAP[nb_name]
    # Generic pattern: strip FALAH01- prefix
    if nb_name.startswith("FALAH01-"):
        return nb_name[len("FALAH01-"):]
    return nb_name


# ─── Interface Name Mapping: Netbox → iTop ───────────────────────────────────
# Netbox uses "Ethernet 1", "Ethernet 2", etc.
# Kafka pipeline (Redfish) uses "NIC1", "NIC2", etc.
# This mapping is for Lenovo servers where Redfish reports NICs differently.
# Also includes management interface variants (mgmt0, Management, BMC, IPMI → XCC)
IFACE_NAME_MAP = {
    "Ethernet 1": "NIC1",
    "Ethernet 2": "NIC2",
    "Ethernet 3": "NIC3",
    "Ethernet 4": "NIC4",
    "XCC": "XCC",
    "mgmt0": "XCC",
    "Management": "XCC",
    "BMC": "XCC",
    "IPMI": "XCC",
}

# Reverse lookup: iTop → Netbox (for cable matching)
ITOP_TO_NETBOX_IFACE_MAP = {v: k for k, v in IFACE_NAME_MAP.items()}

def nb_to_itop_iface_name(nb_iface_name: str) -> str:
    """Convert Netbox interface name to iTop interface name."""
    return IFACE_NAME_MAP.get(nb_iface_name, nb_iface_name)

def itop_to_nb_iface_name(itop_iface_name: str) -> str:
    """Convert iTop interface name to Netbox interface name (reverse lookup)."""
    return ITOP_TO_NETBOX_IFACE_MAP.get(itop_iface_name, itop_iface_name)


# ─── Netbox Client ────────────────────────────────────────────────────────────
class NetboxClient:
    def __init__(self):
        self.base = NETBOX_URL.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Token {NETBOX_TOKEN}",
            "Accept": "application/json",
        })

    def _get_page(self, url: str, params: dict = None) -> dict:
        resp = self.session.get(url, params=params, timeout=30)
        resp.raise_for_status()
        return resp.json()

    def list_all(self, path: str) -> list:
        """Fetch all pages from a Netbox API endpoint."""
        url = f"{self.base}{path}" if not path.startswith("http") else path
        results = []
        data = self._get_page(url, {"limit": 200})
        results.extend(data.get("results", []))
        while data.get("next"):
            data = self._get_page(data["next"])
            results.extend(data.get("results", []))
        return results

    def get_devices(self) -> list:
        return self.list_all("/api/dcim/devices/")

    def get_interfaces(self, device_id: int = None) -> list:
        path = "/api/dcim/interfaces/"
        if device_id:
            return self.list_all(f"{path}?device_id={device_id}")
        return self.list_all(path)

    def get_cables(self) -> list:
        return self.list_all("/api/dcim/cables/")


# ─── iTop Client ──────────────────────────────────────────────────────────────
class ITopClient:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.session = requests.Session()

    def _post(self, payload: dict) -> dict:
        resp = self.session.post(
            ITOP_URL,
            data={
                "auth_user": ITOP_USER,
                "auth_pwd":  ITOP_PASS,
                "json_data": json.dumps(payload),
            },
            timeout=60,
        )
        resp.raise_for_status()
        body = resp.json()
        if body.get("code") not in (0, None):
            raise RuntimeError(f"iTop API error: {body}")
        return body

    def find(self, class_name: str, oql: str) -> tuple:
        """Returns (object_id_str, fields_dict) or (None, None)."""
        body = self._post({
            "operation": "core/get",
            "class": class_name,
            "key": oql,
            "output_fields": "*",
        })
        objs = body.get("objects") or {}
        if not objs:
            return None, None
        first_key = next(iter(objs.keys()))
        first_id = first_key.split("::")[-1]
        return first_id, objs[first_key]["fields"]

    def find_all(self, class_name: str, oql: str) -> dict:
        """Returns {object_id_str: fields_dict} for all matches."""
        body = self._post({
            "operation": "core/get",
            "class": class_name,
            "key": oql,
            "output_fields": "*",
        })
        objs = body.get("objects") or {}
        result = {}
        for k, v in objs.items():
            oid = k.split("::")[-1]
            result[oid] = v.get("fields", {})
        return result

    def create(self, class_name: str, fields: dict, comment: str = "netbox-connector") -> str:
        if self.dry_run:
            logger.info("  [DRY-RUN] CREATE %s fields=%s", class_name, {k: v for k, v in fields.items() if v})
            return "dry-run"
        body = self._post({
            "operation": "core/create",
            "class": class_name,
            "fields": {k: v for k, v in fields.items() if v not in (None, "")},
            "comment": comment,
        })
        objs = body.get("objects") or {}
        if objs:
            new_id = next(iter(objs.keys())).split("::")[-1]
            return new_id
        return None

    def update(self, class_name: str, obj_id: str, fields: dict, comment: str = "netbox-connector") -> bool:
        clean = {k: v for k, v in fields.items() if v not in (None, "")}
        if not clean:
            return True
        if self.dry_run:
            logger.info("  [DRY-RUN] UPDATE %s id=%s fields=%s", class_name, obj_id, clean)
            return True
        body = self._post({
            "operation": "core/update",
            "class": class_name,
            "key": obj_id,
            "fields": clean,
            "comment": comment,
        })
        return body.get("code") == 0

    def get_devices_by_class(self, class_name: str) -> dict:
        """Get all devices of a given class. Returns {name: (id, fields)}."""
        result = self.find_all(class_name, f"SELECT {class_name}")
        return {v.get("name", ""): (k, v) for k, v in result.items()}

    def get_interfaces_for_device(self, device_id: str) -> dict:
        """Get all PhysicalInterface objects for a device. Returns {name: (id, fields)}."""
        result = self.find_all(
            "PhysicalInterface",
            f"SELECT PhysicalInterface WHERE connectableci_id = {device_id}",
        )
        return {v.get("name", ""): (k, v) for k, v in result.items()}


# ─── PostgreSQL ───────────────────────────────────────────────────────────────
def get_db_conn():
    return psycopg2.connect(
        host=DB_HOST, dbname=DB_NAME, user=DB_USER, password=DB_PASS
    )


def upsert_cable(conn, cable: dict, a_dev: str, a_iface: str, b_dev: str, b_iface: str):
    """Insert or update cable record in netbox_cables table."""
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO netbox_cables (nb_cable_id, cable_type, cable_status, label,
                                       a_device, a_interface, b_device, b_interface, last_synced)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (nb_cable_id) DO UPDATE SET
                cable_type = EXCLUDED.cable_type,
                cable_status = EXCLUDED.cable_status,
                label = EXCLUDED.label,
                a_device = EXCLUDED.a_device,
                a_interface = EXCLUDED.a_interface,
                b_device = EXCLUDED.b_device,
                b_interface = EXCLUDED.b_interface,
                last_synced = NOW()
        """, (
            cable.get("id"),
            (cable.get("type") or {}).get("value") if isinstance(cable.get("type"), dict) else cable.get("type"),
            (cable.get("status") or {}).get("value") if isinstance(cable.get("status"), dict) else cable.get("status"),
            cable.get("label") or cable.get("display") or "",
            a_dev, a_iface, b_dev, b_iface,
        ))


# ─── Main Sync Logic ─────────────────────────────────────────────────────────
class NetboxConnector:
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.nb = NetboxClient()
        self.itop = ITopClient(dry_run)
        self.stats = {
            "interfaces_created": 0,
            "interfaces_skipped": 0,
            "interfaces_updated": 0,
            "cables_synced": 0,
            "devices_matched": 0,
            "devices_not_found": 0,
            "links_created": 0,
        }

    def run(self):
        logger.info("=" * 60)
        logger.info("Netbox → iTop Connector sync started (dry_run=%s)", self.dry_run)

        # 1. Build device mapping: Netbox name → iTop name → iTop device info
        logger.info("Step 1: Building device mapping...")
        nb_devices = self.nb.get_devices()
        logger.info("  Found %d devices in Netbox", len(nb_devices))

        # Gather all iTop devices across classes that support PhysicalInterface
        # Only ConnectableCI subclasses can have interfaces (Server, NAS, NetworkDevice)
        CONNECTABLE_CLASSES = ["Server", "NAS", "NetworkDevice"]
        itop_devices = {}  # itop_name → (itop_class, itop_id, itop_fields)
        itop_devices_lower = {}  # lowercase name → (itop_class, itop_id, itop_fields)
        for cls in CONNECTABLE_CLASSES:
            for name, (oid, fields) in self.itop.get_devices_by_class(cls).items():
                itop_devices[name] = (cls, oid, fields)
                itop_devices_lower[name.lower()] = (cls, oid, fields)
        logger.info("  Found %d devices in iTop", len(itop_devices))

        # Build Netbox→iTop mapping (case-insensitive lookup)
        device_map = {}  # nb_device_id → {itop_name, itop_class, itop_id, nb_name}
        for nb_dev in nb_devices:
            nb_name = nb_dev["name"]
            itop_name = nb_to_itop_name(nb_name)
            # Try exact match first, then case-insensitive
            matched = itop_devices.get(itop_name) or itop_devices_lower.get(itop_name.lower())
            if matched:
                cls, oid, _ = matched
                device_map[nb_dev["id"]] = {
                    "itop_name": itop_name,
                    "itop_class": cls,
                    "itop_id": oid,
                    "nb_name": nb_name,
                }
                self.stats["devices_matched"] += 1
            else:
                self.stats["devices_not_found"] += 1
                logger.debug("  Netbox device '%s' (→ '%s') not found in iTop", nb_name, itop_name)

        logger.info("  Matched %d devices, %d not found in iTop",
                     self.stats["devices_matched"], self.stats["devices_not_found"])

        # 2. Sync Cables → PostgreSQL (raw data)
        logger.info("Step 2: Syncing cables to PostgreSQL...")
        self._sync_cables_to_db()

        # 3. Sync Interfaces → iTop PhysicalInterface
        logger.info("Step 3: Syncing interfaces to iTop...")
        self._sync_interfaces(device_map)

        # 4. Enrich interfaces with cable connection info
        logger.info("Step 4: Enriching interfaces with cable connection info...")
        self._enrich_interfaces_with_cables(device_map)

        # 5. Cleanup duplicate/stale device-to-device links
        logger.info("Step 5: Cleaning up duplicate links...")
        self._cleanup_duplicate_links(device_map)

        # 6. Create device-to-device links (Server/NAS → NetworkDevice)
        logger.info("Step 6: Creating device-to-device links...")
        self._sync_device_links(device_map)

        logger.info("Sync complete. Stats: %s", self.stats)
        return self.stats

    def _sync_cables_to_db(self):
        """Fetch all cables from Netbox and store in PostgreSQL."""
        cables = self.nb.get_cables()
        logger.info("  Found %d cables in Netbox", len(cables))

        conn = get_db_conn()
        try:
            for cable in cables:
                a_terminations = cable.get("a_terminations") or []
                b_terminations = cable.get("b_terminations") or []

                a_dev = ""
                a_iface = ""
                b_dev = ""
                b_iface = ""

                if a_terminations:
                    a_term = a_terminations[0]
                    a_obj = a_term.get("object") or {}
                    a_dev = (a_obj.get("device") or {}).get("name", "")
                    a_iface = a_obj.get("name", "")

                if b_terminations:
                    b_term = b_terminations[0]
                    b_obj = b_term.get("object") or {}
                    b_dev = (b_obj.get("device") or {}).get("name", "")
                    b_iface = b_obj.get("name", "")

                upsert_cable(conn, cable, a_dev, a_iface, b_dev, b_iface)
                self.stats["cables_synced"] += 1

            conn.commit()
            logger.info("  Synced %d cables to netbox_cables table", self.stats["cables_synced"])
        except Exception as e:
            conn.rollback()
            logger.error("  Error syncing cables to DB: %s", e)
            raise
        finally:
            conn.close()

    def _sync_interfaces(self, device_map: dict):
        """Sync Netbox interfaces to iTop PhysicalInterface (only add missing)."""
        # Build cable lookup: (device_name, interface_name) → cable info
        cable_lookup = self._build_cable_lookup()

        for nb_dev_id, mapping in device_map.items():
            itop_name = mapping["itop_name"]
            itop_id = mapping["itop_id"]
            nb_name = mapping["nb_name"]

            # Get interfaces from Netbox for this device
            try:
                nb_interfaces = self.nb.get_interfaces(nb_dev_id)
            except Exception as e:
                logger.warning("  Failed to fetch Netbox interfaces for %s: %s", nb_name, e)
                continue

            if not nb_interfaces:
                continue

            # Get existing interfaces in iTop for this device
            existing_ifaces = self.itop.get_interfaces_for_device(itop_id)
            existing_names = set(existing_ifaces.keys())

            # Build a set of existing names for fuzzy matching
            # e.g., "NIC1" should match "Ethernet 1" for Lenovo servers
            existing_names_lower = {n.lower(): n for n in existing_names}

            for nb_iface in nb_interfaces:
                iface_name = nb_iface.get("name", "")
                if not iface_name:
                    continue

                # Build comment with connection info
                comment = self._build_interface_comment(nb_name, iface_name, cable_lookup)

                # Build speed from Netbox
                speed_mbps = self._get_speed_mbps(nb_iface)

                # Check if this Netbox interface already exists in iTop
                # Try: exact match, case-insensitive, IFACE_NAME_MAP, and MAC-based matching
                matched_name = None
                if iface_name in existing_names:
                    matched_name = iface_name
                elif iface_name.lower() in existing_names_lower:
                    matched_name = existing_names_lower[iface_name.lower()]
                else:
                    # Try mapped name (Ethernet 1 → NIC1)
                    mapped = nb_to_itop_iface_name(iface_name)
                    if mapped != iface_name:
                        if mapped in existing_names:
                            matched_name = mapped
                        elif mapped.lower() in existing_names_lower:
                            matched_name = existing_names_lower[mapped.lower()]
                
                # Fallback: MAC-based matching (when naming conventions differ)
                if not matched_name:
                    nb_mac = (nb_iface.get("mac_address") or "").strip().lower()
                    if nb_mac:
                        for itop_iface_name, (itop_iface_id, itop_iface_fields) in existing_ifaces.items():
                            itop_mac = (itop_iface_fields.get("macaddress") or "").strip().lower()
                            if itop_mac and itop_mac == nb_mac:
                                matched_name = itop_iface_name
                                logger.debug("  MAC match: %s/%s → %s (MAC: %s)", itop_name, iface_name, itop_iface_name, nb_mac)
                                break

                if matched_name:
                    # Interface already exists — only update comment if it has cable info
                    # and the existing comment doesn't already have it
                    iface_id, iface_fields = existing_ifaces[matched_name]
                    existing_comment = iface_fields.get("comment", "")
                    if comment and "Connected to:" in comment and "Connected to:" not in existing_comment:
                        logger.info("  ↺ Updating comment for %s/%s", itop_name, matched_name)
                        self.itop.update("PhysicalInterface", iface_id, {"comment": comment})
                        self.stats["interfaces_updated"] += 1
                    else:
                        self.stats["interfaces_skipped"] += 1
                    continue

                # Interface doesn't exist in iTop — create it from Netbox data
                # (matching above already handles exact/case/mapped/MAC dedup)
                mac = (nb_iface.get("mac_address") or "").strip()
                ip_addr = ""
                # Try to get IP from primary_ip4
                primary_ip = nb_iface.get("primary_ip4") or nb_iface.get("ip_addresses")
                if isinstance(primary_ip, dict):
                    ip_addr = primary_ip.get("address", "").split("/")[0]
                elif isinstance(primary_ip, list) and primary_ip:
                    ip_addr = primary_ip[0].get("address", "").split("/")[0]

                fields = {
                    "name": iface_name,
                    "connectableci_id": itop_id,
                    "macaddress": mac,
                    "ipaddress": ip_addr,
                    "speed": str(speed_mbps) if speed_mbps else "",
                    "comment": comment or f"Netbox interface {nb_iface.get('id')}",
                }

                logger.info("  + Creating interface %s/%s (mac=%s)", itop_name, iface_name, mac or "none")
                self.itop.create("PhysicalInterface", fields)
                self.stats["interfaces_created"] += 1

            # Phase 4: Create XCC (management interface) from Netbox if missing
            # Redfish doesn't report BMC/XCC, so we need to create it from Netbox
            xcc_variants = ["XCC", "mgmt0", "Management", "BMC", "IPMI"]
            has_xcc = any(name in existing_names for name in xcc_variants)
            
            if not has_xcc:
                # Look for XCC interface in Netbox
                for nb_iface in nb_interfaces:
                    iface_name = nb_iface.get("name", "")
                    if iface_name in xcc_variants:
                        # Found XCC in Netbox, create it in iTop
                        mac = (nb_iface.get("mac_address") or "").strip()
                        ip_addr = ""
                        primary_ip = nb_iface.get("primary_ip4") or nb_iface.get("ip_addresses")
                        if isinstance(primary_ip, dict):
                            ip_addr = primary_ip.get("address", "").split("/")[0]
                        elif isinstance(primary_ip, list) and primary_ip:
                            ip_addr = primary_ip[0].get("address", "").split("/")[0]
                        
                        speed_mbps = self._get_speed_mbps(nb_iface)
                        comment = self._build_interface_comment(nb_name, iface_name, cable_lookup)
                        
                        fields = {
                            "name": "XCC",  # Standardize to XCC
                            "connectableci_id": itop_id,
                            "macaddress": mac,
                            "ipaddress": ip_addr,
                            "speed": str(speed_mbps) if speed_mbps else "",
                            "comment": comment or f"Management interface from Netbox",
                        }
                        
                        logger.info("  + Creating XCC interface %s/XCC (mac=%s, from Netbox %s)", itop_name, mac or "none", iface_name)
                        self.itop.create("PhysicalInterface", fields)
                        self.stats["interfaces_created"] += 1
                        break  # Only create one XCC interface

    def _build_cable_lookup(self) -> dict:
        """Build lookup: (device_name, interface_name) → {peer_device, peer_interface, cable_type, cable_status}.
        Also adds mapped interface names (Ethernet 1 → NIC1) for Lenovo servers.
        Supports bonding/LACP with position-based termination matching."""
        cables = self.nb.get_cables()
        lookup = {}

        for cable in cables:
            a_terminations = cable.get("a_terminations") or []
            b_terminations = cable.get("b_terminations") or []

            if not a_terminations or not b_terminations:
                continue

            cable_type = ""
            if isinstance(cable.get("type"), dict):
                cable_type = cable["type"].get("label", cable["type"].get("value", ""))
            elif cable.get("type"):
                cable_type = str(cable["type"])

            cable_status = ""
            if isinstance(cable.get("status"), dict):
                cable_status = cable["status"].get("label", cable["status"].get("value", ""))

            # Match terminations by index (position-based pairing for bonding)
            max_len = max(len(a_terminations), len(b_terminations))
            for i in range(max_len):
                a_term = a_terminations[i].get("object") if i < len(a_terminations) else None
                b_term = b_terminations[i].get("object") if i < len(b_terminations) else None

                if not a_term or not b_term:
                    continue

                a_dev = (a_term.get("device") or {}).get("name", "")
                a_iface = a_term.get("name", "")
                b_dev = (b_term.get("device") or {}).get("name", "")
                b_iface = b_term.get("name", "")

                info = {
                    "cable_id": cable.get("id"),
                    "cable_type": cable_type,
                    "cable_status": cable_status,
                    "cable_label": cable.get("label", ""),
                    "termination_count": max(len(a_terminations), len(b_terminations)),
                }

                # A-end sees B-end as peer
                lookup[(a_dev, a_iface)] = {**info, "peer_device": b_dev, "peer_interface": b_iface}
                # B-end sees A-end as peer
                lookup[(b_dev, b_iface)] = {**info, "peer_device": a_dev, "peer_interface": a_iface}

                # Also add mapped interface names (Ethernet 1 → NIC1) for Lenovo servers
                a_mapped = nb_to_itop_iface_name(a_iface)
                b_mapped = nb_to_itop_iface_name(b_iface)
                if a_mapped != a_iface:
                    lookup[(a_dev, a_mapped)] = {**info, "peer_device": b_dev, "peer_interface": b_iface}
                if b_mapped != b_iface:
                    lookup[(b_dev, b_mapped)] = {**info, "peer_device": a_dev, "peer_interface": a_iface}

                # Add lowercase variants for case-insensitive matching
                lookup[(a_dev, a_iface.lower())] = {**info, "peer_device": b_dev, "peer_interface": b_iface}
                lookup[(b_dev, b_iface.lower())] = {**info, "peer_device": a_dev, "peer_interface": a_iface}
                if a_mapped != a_iface:
                    lookup[(a_dev, a_mapped.lower())] = {**info, "peer_device": b_dev, "peer_interface": b_iface}
                if b_mapped != b_iface:
                    lookup[(b_dev, b_mapped.lower())] = {**info, "peer_device": a_dev, "peer_interface": a_iface}

        return lookup

    def _build_interface_comment(self, nb_device: str, iface_name: str, cable_lookup: dict) -> str:
        """Build a comment string with cable connection info."""
        key = (nb_device, iface_name)
        if key not in cable_lookup:
            return ""

        info = cable_lookup[key]
        parts = [f"Connected to: {info['peer_device']}/{info['peer_interface']}"]
        
        # Add bonding/LACP info from cable label
        cable_label = info.get("cable_label", "")
        term_count = info.get("termination_count", 1)
        if term_count > 1:
            # Multi-termination = bonding/LACP/teaming
            bonding_type = "Bonding/LACP" if "bond" in cable_label.lower() else "Team"
            if "teaming" in cable_label.lower() or "team" in cable_label.lower():
                bonding_type = "Teaming"
            parts.append(f"{bonding_type} ({term_count} links): {cable_label}")
        elif cable_label:
            parts.append(f"Cable: {cable_label}")
            
        if info.get("cable_type") and not cable_label:
            parts.append(f"Cable: {info['cable_type']}")
        if info.get("cable_status"):
            parts.append(f"Status: {info['cable_status']}")
        return " | ".join(parts)

    def _enrich_interfaces_with_cables(self, device_map: dict):
        """Update existing iTop interfaces with cable connection info from Netbox."""
        # This is already handled in _sync_interfaces via comment updates
        pass

    def _cleanup_duplicate_links(self, device_map: dict):
        """Remove duplicate/stale lnkConnectableCIToNetworkDevice links.
        
        Strategy: For each Server/NAS device that has Netbox cable data,
        remove ALL existing links so they can be recreated correctly.
        This handles old duplicates from previous buggy runs.
        """
        # Determine which devices have Netbox cable data
        devices_with_cables = set()
        cables = self.nb.get_cables()
        for cable in cables:
            for term_list in [cable.get("a_terminations", []), cable.get("b_terminations", [])]:
                for t in term_list:
                    obj = t.get("object", {})
                    dev_name = (obj.get("device") or {}).get("name", "")
                    if dev_name:
                        devices_with_cables.add(dev_name.upper())

        # Get all existing links
        existing_links = self.itop.find_all(
            "lnkConnectableCIToNetworkDevice",
            "SELECT lnkConnectableCIToNetworkDevice"
        )

        # Get device info for matching
        for nb_dev_id, mapping in device_map.items():
            if mapping["itop_class"] not in ("Server", "NAS"):
                continue
            nb_upper = mapping["nb_name"].upper()
            if nb_upper not in devices_with_cables:
                continue

            itop_id = mapping["itop_id"]
            # Find all existing links for this device
            links_to_delete = []
            for link_id, fields in existing_links.items():
                if str(fields.get("connectableci_id")) == str(itop_id):
                    link_oid = link_id.split("::")[-1] if "::" in link_id else link_id
                    links_to_delete.append(link_oid)

            if links_to_delete:
                logger.info("  🗑 Removing %d stale links for %s", len(links_to_delete), mapping["itop_name"])
                for link_oid in links_to_delete:
                    try:
                        self.itop._post({
                            "operation": "core/delete",
                            "class": "lnkConnectableCIToNetworkDevice",
                            "key": link_oid,
                            "comment": "netbox-connector: cleanup stale/duplicate links",
                        })
                    except Exception as e:
                        logger.warning("  Failed to delete link %s: %s", link_oid, e)

    def _sync_device_links(self, device_map: dict):
        """Create lnkConnectableCIToNetworkDevice links for Server/NAS → NetworkDevice connections.
        
        Handles bonding/LACP where one cable has multiple terminations on each side.
        Fetches directly from Netbox API to get all terminations.
        """
        import requests
        NETBOX_URL = "http://10.70.0.20:9008/api/dcim/cables/?limit=500"
        NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"
        
        headers = {'Authorization': f'Token {NETBOX_TOKEN}'}
        resp = requests.get(NETBOX_URL, headers=headers, timeout=30)
        cables_data = resp.json().get('results', [])
        
        # Build cable lookup with ALL terminations (for bonding/LACP support)
        # Match terminations by index/position, not all combinations
        cable_lookup = {}
        for cable in cables_data:
            a_terminations = cable.get('a_terminations', [])
            b_terminations = cable.get('b_terminations', [])
            
            cable_type = cable.get('type', {}).get('label', '') if isinstance(cable.get('type'), dict) else str(cable.get('type', ''))
            
            # Match terminations by index (position-based pairing for bonding)
            max_len = max(len(a_terminations), len(b_terminations))
            for i in range(max_len):
                a_term = a_terminations[i] if i < len(a_terminations) else None
                b_term = b_terminations[i] if i < len(b_terminations) else None
                
                if a_term and b_term:
                    a_obj = a_term.get('object', {}) if isinstance(a_term, dict) and 'object' in a_term else a_term
                    b_obj = b_term.get('object', {}) if isinstance(b_term, dict) and 'object' in b_term else b_term
                    
                    a_dev = (a_obj.get('device') or {}).get('name', '') if isinstance(a_obj, dict) else ''
                    a_iface = a_obj.get('name', '') if isinstance(a_obj, dict) else ''
                    b_dev = (b_obj.get('device') or {}).get('name', '') if isinstance(b_obj, dict) else ''
                    b_iface = b_obj.get('name', '') if isinstance(b_obj, dict) else ''
                    
                    # Store both directions
                    cable_lookup[(a_dev.upper(), a_iface)] = (b_dev, b_iface, cable_type)
                    cable_lookup[(b_dev.upper(), b_iface)] = (a_dev, a_iface, cable_type)
                    
                    # Add mapped interface names
                    a_mapped = nb_to_itop_iface_name(a_iface)
                    b_mapped = nb_to_itop_iface_name(b_iface)
                    if a_mapped != a_iface:
                        cable_lookup[(a_dev.upper(), a_mapped)] = (b_dev, b_iface, cable_type)
                    if b_mapped != b_iface:
                        cable_lookup[(b_dev.upper(), b_mapped)] = (a_dev, a_iface, cable_type)
        
        # Get existing links
        existing_links = self.itop.find_all(
            "lnkConnectableCIToNetworkDevice",
            "SELECT lnkConnectableCIToNetworkDevice"
        )
        existing_pairs = set()
        for _, fields in existing_links.items():
            existing_pairs.add((
                fields.get("connectableci_id"),
                fields.get("networkdevice_id"),
                fields.get("device_port"),
                fields.get("network_port")
            ))

        # Get all NetworkDevice IDs in iTop (case-insensitive lookup)
        ndevs = self.itop.get_devices_by_class("NetworkDevice")
        ndev_name_to_id = {name: oid for name, (oid, _) in ndevs.items()}
        ndev_name_to_id_lower = {name.lower(): oid for name, (oid, _) in ndevs.items()}

        # Process each matched device
        for nb_dev_id, mapping in device_map.items():
            itop_name = mapping["itop_name"]
            itop_id = mapping["itop_id"]
            nb_name = mapping["nb_name"]
            itop_class = mapping["itop_class"]

            # Only process Server and NAS
            if itop_class not in ("Server", "NAS"):
                continue

            nb_upper = nb_name.upper()

            # Find all NetworkDevice connections from cable data
            # Use set to avoid duplicates from cable_lookup variants
            connected_cables = set()  # set of (ndev_itop_name, device_port, network_port)
            for (cable_dev, cable_iface), (peer_dev, peer_iface, ctype) in cable_lookup.items():
                if cable_dev == nb_upper:
                    peer_itop = nb_to_itop_name(peer_dev)
                    # Case-insensitive NetworkDevice lookup
                    if peer_itop in ndev_name_to_id or peer_itop.lower() in ndev_name_to_id_lower:
                        # Map device_port to iTop naming convention (Ethernet 1 → NIC1)
                        itop_device_port = nb_to_itop_iface_name(cable_iface)
                        # Normalize peer name to actual iTop name for link creation
                        actual_peer = peer_itop
                        if peer_itop not in ndev_name_to_id and peer_itop.lower() in ndev_name_to_id_lower:
                            # Find actual iTop name from lowercase match
                            for nd_name in ndev_name_to_id:
                                if nd_name.lower() == peer_itop.lower():
                                    actual_peer = nd_name
                                    break
                        connected_cables.add((actual_peer, itop_device_port, peer_iface))

            # Create links
            for ndev_name, device_port, network_port in connected_cables:
                ndev_id = ndev_name_to_id.get(ndev_name) or ndev_name_to_id_lower.get(ndev_name.lower())
                if not ndev_id:
                    continue
                # Check 4-tuple: (server_id, switch_id, device_port, network_port)
                if (itop_id, ndev_id, device_port, network_port) in existing_pairs:
                    continue

                self.itop.create("lnkConnectableCIToNetworkDevice", {
                    "connectableci_id": itop_id,
                    "networkdevice_id": ndev_id,
                    "network_port": network_port,
                    "device_port": device_port,
                    "connection_type": "uplink",
                })
                self.stats["links_created"] = self.stats.get("links_created", 0) + 1
                logger.info("  ✓ %s → %s (%s→%s)", itop_name, ndev_name, device_port, network_port)

    def _get_speed_mbps(self, iface: dict) -> int:
        """Extract interface speed in Mbps from Netbox interface data."""
        # Netbox may have 'speed' directly or in type
        speed = iface.get("speed")
        if speed:
            return int(speed)

        # Try to infer from type label
        type_info = iface.get("type") or {}
        type_label = ""
        if isinstance(type_info, dict):
            type_label = type_info.get("label", type_info.get("value", "")).lower()
        elif isinstance(type_info, str):
            type_label = type_info.lower()

        speed_map = {
            "100base-tx": 100,
            "1000base-t": 1000,
            "1000base-x": 1000,
            "10gbase-t": 10000,
            "10gbase-x": 10000,
            "25gbase-x": 25000,
            "40gbase-x": 40000,
            "100gbase-x": 100000,
            "sfp+": 10000,
            "sfp": 1000,
            "qsfp+": 40000,
            "qsfp28": 100000,
        }
        for key, val in speed_map.items():
            if key in type_label:
                return val

        return 0


# ─── Entry Point ──────────────────────────────────────────────────────────────
def main():
    dry_run = "--dry-run" in sys.argv
    daemon = "--daemon" in sys.argv

    if dry_run:
        logger.info("Running in DRY-RUN mode — no changes will be made")

    while not _STOP:
        try:
            connector = NetboxConnector(dry_run=dry_run)
            connector.run()
        except Exception as e:
            logger.exception("Sync failed: %s", e)

        if not daemon:
            break

        logger.info("Next sync in %d seconds...", SYNC_INTERVAL)
        for _ in range(SYNC_INTERVAL):
            if _STOP:
                break
            time.sleep(1)

    logger.info("Connector stopped.")


if __name__ == "__main__":
    main()
