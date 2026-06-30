#!/usr/bin/env python3
import json
import logging
import requests
import sys
import argparse
import os

sys.path.append("/home/infra/dcim_metrics_project")
from scripts.dcim_inventory_poller import poll_nas, poll_ups, poll_hikvision, HIKVISION_NVR, HIKVISION_CAM_USER, HIKVISION_CAM_PASS

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ITOP_URL = 'http://localhost:8080/webservices/rest.php?version=1.3'
ITOP_USER = 'admin'
ITOP_PASS = 'Inovasi@0918'

NETBOX_URL = "http://10.70.0.20:9008"
NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("sync_endpoints")

# Mapping NAS NetBox name to New iTop name and IP
NAS_MAPPING = {
    "FALAH01-NAS-01": {"new_name": "FALAH01-NAS-INFRA", "ip": "10.50.0.106"},
    "FALAH01-NAS-02": {"new_name": "FALAH01-NAS-FAT",   "ip": "10.50.0.107"},
    "FALAH01-NAS-03": {"new_name": "FALAH01-NAS-SD01",  "ip": "10.50.0.108"},
    "FALAH01-NAS-04": {"new_name": "FALAH01-NAS-CD01",  "ip": "10.50.0.109"},
    "FALAH01-NAS-05": {"new_name": "FALAH01-NAS-CD02",  "ip": "10.50.0.110"},
    "FALAH01-NAS-06": {"new_name": "FALAH01-NAS-FIR",   "ip": "10.50.0.105"},
}

UPS_HOSTS = [
    {"nb_name": "FALAH01-UPS-3PHASE-30kVA", "ip": "192.168.100.140", "name": "UPS-APC-30K"},
]

NVR_HOSTS = [
    {"nb_name": "FALAH01-NVR-HIKVISION", "ip": "192.168.1.254"},
]


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
        objs = body.get("objects")
        if not objs:
            return None, {}
        first_key = next(iter(objs.keys()))
        first_id = first_key.split("::")[-1]
        return first_id, objs[first_key]["fields"]

    def upsert(self, class_name: str, find_oql: str, fields: dict, comment: str = "sync_endpoints") -> str | None:
        obj_id, current = self.find(class_name, find_oql)
        clean = {k: v for k, v in fields.items() if v not in (None, "")}
        if obj_id:
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

    def update(self, class_name: str, obj_id: str, fields: dict, comment: str = "sync_endpoints") -> bool:
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
        if body.get("code") == 0:
            LOG.info("  ✅ UPDATED %s id=%s", class_name, obj_id)
            return True
        return False


class NetboxClient:
    def __init__(self):
        self.headers = {"Authorization": f"Token {NETBOX_TOKEN}"}

    def get_device(self, name: str) -> dict:
        r = requests.get(f"{NETBOX_URL}/api/dcim/devices/?name={name}", headers=self.headers)
        res = r.json().get('results', [])
        return res[0] if res else None

    def get_interfaces(self, device_id: int) -> list[dict]:
        r = requests.get(f"{NETBOX_URL}/api/dcim/interfaces/?device_id={device_id}&limit=200", headers=self.headers)
        return r.json().get('results', [])


def sync_device(nb_name: str, itop_class: str, itop_name: str, ip: str, device_type: str, dry_run: bool):
    LOG.info("=" * 60)
    LOG.info(f"Mulai sinkronisasi: NetBox({nb_name}) -> iTop({itop_name}) [{itop_class}]")

    itop = ITopClient(dry_run)
    netbox = NetboxClient()

    # 1. Rename in iTop if nb_name != itop_name (for NAS)
    if nb_name != itop_name:
        old_id, _ = itop.find(itop_class, f"SELECT {itop_class} WHERE name = '{nb_name}'")
        if old_id:
            LOG.info(f"Renaming {nb_name} -> {itop_name} di iTop")
            itop.update(itop_class, old_id, {"name": itop_name})

    # 2. Get NetBox Device and Interfaces
    nb_dev = netbox.get_device(nb_name)
    if not nb_dev:
        LOG.warning(f"Device {nb_name} tidak ditemukan di NetBox! Melanjutkan ke iTop device.")
    
    # Check rack units
    rack_units = ""
    if nb_dev:
        dt_url = nb_dev.get("device_type", {}).get("url")
        if dt_url:
            try:
                r = requests.get(dt_url, headers=netbox.headers)
                u_height = r.json().get("u_height")
                if u_height is not None:
                    rack_units = str(int(u_height))
            except:
                pass

    # 3. Pull from Device API using poller
    polled_data = {}
    if device_type == "nas":
        polled_data = poll_nas({"hostname": itop_name, "ip": ip, "method": "snmp"})
    elif device_type == "ups":
        polled_data = poll_ups({"name": "UPS-APC-30K", "ip": ip})
    elif device_type == "nvr":
        polled_data = poll_hikvision(ip, HIKVISION_NVR["user"], HIKVISION_NVR["password"], "nvr")
    elif device_type == "cctv":
        polled_data = poll_hikvision(ip, HIKVISION_CAM_USER, HIKVISION_CAM_PASS, "cctv")
    
    # 4. Map API properties to iTop fields
    brand_id = None
    brand_name = polled_data.get("manufacturer", "")
    if brand_name:
        b_id, _ = itop.find("Brand", f"SELECT Brand WHERE name='{brand_name}'")
        if not b_id:
            b_id = itop.upsert("Brand", f"SELECT Brand WHERE name='{brand_name}'", {"name": brand_name})
        brand_id = b_id

    model_id = None
    model_name = polled_data.get("model", "")
    if model_name and brand_id:
        # Note: Model in iTop uses `name` and `brand_id`
        m_id, _ = itop.find("Model", f"SELECT Model WHERE name='{model_name}'")
        if not m_id:
            m_id = itop.upsert("Model", f"SELECT Model WHERE name='{model_name}'", {"name": model_name, "brand_id": brand_id, "type": "NetworkDevice"}) # using NetworkDevice as general type
        model_id = m_id

    osversion_id = None
    fw_ver = polled_data.get("firmware_version", "")
    if fw_ver:
        o_id, _ = itop.find("IOSVersion", f"SELECT IOSVersion WHERE name='{fw_ver}'")
        if not o_id:
            o_id = itop.upsert("IOSVersion", f"SELECT IOSVersion WHERE name='{fw_ver}'", {"name": fw_ver, "brand_id": brand_id})
        osversion_id = o_id

    # 5. Update iTop Device
    itop_id, _ = itop.find(itop_class, f"SELECT {itop_class} WHERE name = '{itop_name}'")
    if not itop_id:
        LOG.warning(f"Device {itop_name} tidak ada di iTop! Membuat baru...")
        itop_id = itop.upsert(itop_class, f"SELECT {itop_class} WHERE name = '{itop_name}'", {"name": itop_name, "org_id": "1"})
        
    update_fields = {}
    if brand_id: update_fields["brand_id"] = brand_id
    if model_id: update_fields["model_id"] = model_id
    if polled_data.get("serial_number"): update_fields["serialnumber"] = polled_data["serial_number"]
    
    # Specific fields based on class
    if itop_class == "NAS":
        if ip: update_fields["managementip"] = ip
        if rack_units: update_fields["nb_u"] = rack_units
    elif itop_class == "NetworkDevice":
        if osversion_id: update_fields["iosversion_id"] = osversion_id
        if ip: update_fields["managementip"] = ip
        if rack_units: update_fields["nb_u"] = rack_units
    elif itop_class == "PowerSource":
        # PowerSource does not have managementip, nb_u, or iosversion_id in default iTop
        pass

    if update_fields:
        LOG.info(f"Mengupdate properti {itop_name}: {update_fields}")
        itop.update(itop_class, itop_id, update_fields)

    # 6. Process Interfaces & Links from NetBox
    if itop_class == "PowerSource":
        LOG.info(f"Skipping interface sync for {itop_name} (PowerSource is not a ConnectableCI in iTop)")
    elif nb_dev:
        nb_intfs = netbox.get_interfaces(nb_dev["id"])
        LOG.info(f"Ditemukan {len(nb_intfs)} antarmuka di NetBox untuk {nb_name}")

        for intf in nb_intfs:
            i_name = intf["name"]
            mac = intf.get("mac_address") or ""
            
            # Upsert interface to iTop
            i_oql = f"SELECT PhysicalInterface WHERE name='{i_name}' AND connectableci_id='{itop_id}'"
            i_id = itop.upsert("PhysicalInterface", i_oql, {
                "name": i_name,
                "connectableci_id": itop_id,
                "macaddress": mac
            })

            # Check peer and create link
            peers = intf.get("link_peers", [])
            if peers and peers[0].get("device"):
                peer_dev_name = peers[0]["device"]["name"]
                peer_intf_name = peers[0]["name"]
                
                # Find peer in iTop
                peer_id, _ = itop.find("NetworkDevice", f"SELECT NetworkDevice WHERE name='{peer_dev_name}'")
                if peer_id:
                    # Coba cari tanpa prefix dulu
                    peer_i_id, _ = itop.find("PhysicalInterface", f"SELECT PhysicalInterface WHERE name='{peer_intf_name}' AND connectableci_id='{peer_id}'")
                    if not peer_i_id:
                        # Coba cari dengan format prefix (seperti standar skrip sinkronisasi Mikrotik kita: DeviceName:InterfaceName)
                        peer_i_id, _ = itop.find("PhysicalInterface", f"SELECT PhysicalInterface WHERE name='{peer_dev_name}:{peer_intf_name}' AND connectableci_id='{peer_id}'")
                        
                    if peer_i_id:
                        # Link them
                        link_oql = f"SELECT lnkConnectableCIToNetworkDevice WHERE networkdevice_id='{peer_id}' AND connectableci_id='{itop_id}'"
                        link_id, _ = itop.find("lnkConnectableCIToNetworkDevice", link_oql)
                        if not link_id:
                            LOG.info(f"Menyambungkan {itop_name}:{i_name} -> {peer_dev_name}:{peer_intf_name}")
                            itop.upsert("lnkConnectableCIToNetworkDevice", link_oql, {
                                "networkdevice_id": peer_id,
                                "connectableci_id": itop_id,
                                "networkdeviceport_id": peer_i_id,
                                "connectableciport_id": i_id,
                                "connection_type": "uplink"
                            })
                    else:
                        LOG.warning(f"Interface peer {peer_intf_name} di device {peer_dev_name} tidak ditemukan di iTop!")
                else:
                    LOG.warning(f"Device peer {peer_dev_name} tidak ditemukan di iTop!")


def main():
    parser = argparse.ArgumentParser(description="Sync NAS, UPS, NVR, CCTV properties and relations")
    parser.add_argument("--dry-run", action="store_true", help="Do not make actual changes")
    args = parser.parse_args()

    # 1. Sync NAS
    for nb_name, mapping in NAS_MAPPING.items():
        sync_device(nb_name, "NAS", mapping["new_name"], mapping["ip"], "nas", args.dry_run)

    # 2. Sync UPS
    for ups in UPS_HOSTS:
        sync_device(ups["nb_name"], "PowerSource", ups["nb_name"], ups["ip"], "ups", args.dry_run)

    # 3. Sync NVR
    for nvr in NVR_HOSTS:
        sync_device(nvr["nb_name"], "NetworkDevice", nvr["nb_name"], nvr["ip"], "nvr", args.dry_run)

    # 4. Sync CCTV
    # Wait, we need to fetch all CCTVs from NetBox first, then sync them
    LOG.info("Fetching CCTVs from NetBox...")
    netbox = NetboxClient()
    r = requests.get(f"{NETBOX_URL}/api/dcim/devices/?limit=1000", headers=netbox.headers)
    for d in r.json().get("results", []):
        name = d.get("name", "")
        if "CCTV" in name or "CAM" in name:
            ip = d.get("primary_ip", {}).get("address", "")
            if ip:
                ip = ip.split("/")[0] # remove subnet mask
                sync_device(name, "NetworkDevice", name, ip, "cctv", args.dry_run)

    LOG.info("Semua sinkronisasi selesai!")

if __name__ == "__main__":
    main()
