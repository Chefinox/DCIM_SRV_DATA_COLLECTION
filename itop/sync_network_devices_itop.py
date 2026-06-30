#!/usr/bin/env python3
import json
import logging
import requests
import sys
import argparse
import routeros_api

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ITOP_URL = 'http://localhost:8080/webservices/rest.php?version=1.3'
ITOP_USER = 'admin'
ITOP_PASS = 'Inovasi@0918'

NETBOX_URL = "http://10.70.0.20:9008"
NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

MIKROTIK_USER = "netbox"
MIKROTIK_PASS = "netbox123"

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("sync_netdev")

# ==============================================================================
# ITOP CLIENT
# ==============================================================================
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

    def upsert(self, class_name: str, find_oql: str, fields: dict, comment: str = "sync_netdev") -> str | None:
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

    def update(self, class_name: str, obj_id: str, fields: dict, comment: str = "sync_netdev") -> bool:
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


# ==============================================================================
# NETBOX CLIENT
# ==============================================================================
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


def get_mikrotik_info_api(ip: str, mk_user: str, mk_pass: str) -> tuple[str, str, str, str, list]:
    """Connects to Mikrotik API to fetch version, ram, power status, and interfaces."""
    version = "RouterOS (MikroTik)"
    ram = ""
    powerA = "AC"
    powerB = "AC"
    interfaces = []
    
    if not ip:
        return version, ram, powerA, powerB, interfaces
        
    try:
        connection = routeros_api.RouterOsApiPool(
            ip, 
            username=mk_user, 
            password=mk_pass, 
            plaintext_login=True
        )
        api = connection.get_api()
        
        # 1. Fetch version and RAM
        res_info = api.get_resource('/system/resource').get()
        if res_info:
            version = f"RouterOS {res_info[0].get('version', '')}".strip()
            total_memory = res_info[0].get('total-memory')
            if total_memory:
                ram = str(int(total_memory) // 1048576) # Convert bytes to MB
            
        # 2. Fetch health (power status)
        try:
            health_info = api.get_resource('/system/health').get()
            if health_info:
                # Based on the hardware, check if PSU is failing. Defaults to AC unless explicitly failed.
                for h in health_info:
                    if h.get('name') == 'psu1-state' and h.get('value') != 'ok': powerA = 'Failed'
                    if h.get('name') == 'psu2-state' and h.get('value') != 'ok': powerB = 'Failed'
        except Exception as e:
            LOG.warning("Could not fetch /system/health: %s", e)
            
        # 3. Fetch interfaces
        intf_list = api.get_resource('/interface').get()
        interfaces = intf_list
        
        connection.disconnect()
    except Exception as e:
        LOG.warning(f"Gagal koneksi ke Mikrotik API {ip}: {e}")
        raise RuntimeError(f"API Connection Error: {e}")

    return version, ram, powerA, powerB, interfaces


def sync_device(dev_name: str, mk_user: str, mk_pass: str, dry_run: bool):
    LOG.info("=" * 60)
    LOG.info("Mulai sinkronisasi Network Device (dari API Mikrotik): %s", dev_name)

    itop = ITopClient(dry_run)
    netbox = NetboxClient()

    # 1. Cari perangkat di NetBox untuk mendapatkan IP Management
    nb_dev = netbox.get_device(dev_name)
    if not nb_dev:
        LOG.error("Device %s tidak ditemukan di NetBox!", dev_name)
        return

    # Fetch nb_u from NetBox device-type
    nb_u = ""
    dt_url = nb_dev.get("device_type", {}).get("url")
    if dt_url:
        try:
            r = requests.get(dt_url, headers=netbox.headers)
            u_height = r.json().get("u_height")
            if u_height is not None:
                nb_u = str(int(u_height))
        except Exception as e:
            LOG.warning("Could not fetch device-type from NetBox: %s", e)

    # 2. Cari perangkat di iTop
    itop_id, itop_data = itop.find("NetworkDevice", f"SELECT NetworkDevice WHERE name = '{dev_name}'")
    if not itop_id:
        LOG.error("Device %s tidak ditemukan di iTop! Buat dulu perangkat induknya.", dev_name)
        return

    # 3. Dapatkan IP dan konek ke Mikrotik API
    ip = ""
    if nb_dev.get("primary_ip"):
        ip = nb_dev["primary_ip"]["address"].split("/")[0]

    LOG.info("Menghubungi Mikrotik API di IP %s...", ip)
    try:
        ios_version, ram, pwr_a, pwr_b, interfaces = get_mikrotik_info_api(ip, mk_user, mk_pass)
    except Exception as e:
        LOG.error(f"ABORTING: {e}")
        raise

    LOG.info("Updating properties NetworkDevice di iTop...")
    updates = {}
    
    # Handle IOSVersion (needs an ID in iTop)
    if ios_version:
        ios_oql = f"SELECT IOSVersion WHERE name = '{ios_version}'"
        ios_fields = {"name": ios_version}
        if itop_data.get("brand_id"):
            ios_fields["brand_id"] = f"SELECT Brand WHERE id = {itop_data['brand_id']}"
        ios_id = itop.upsert("IOSVersion", ios_oql, ios_fields, comment="Auto-created during sync")
        if ios_id and str(itop_data.get("iosversion_id")) != str(ios_id):
            updates["iosversion_id"] = ios_id
            
    if "powera_source" in itop_data and itop_data.get("powera_source") != pwr_a: updates["powera_source"] = pwr_a
    if "powerb_source" in itop_data and itop_data.get("powerb_source") != pwr_b: updates["powerb_source"] = pwr_b
    if "ram" in itop_data and str(itop_data.get("ram")) != str(ram) and ram: updates["ram"] = ram
    if "nb_u" in itop_data and str(itop_data.get("nb_u")) != str(nb_u) and nb_u: updates["nb_u"] = nb_u
    
    if updates:
        itop.update("NetworkDevice", itop_id, updates)

    # 4. Sinkronisasi Interfaces dari Mikrotik API
    LOG.info("Ditemukan %d interfaces di Mikrotik untuk %s", len(interfaces), dev_name)

    for intf in interfaces:
        mk_name = intf.get("name")
        mac = intf.get("mac-address", "")
        
        # Upsert PhysicalInterface for the Switch
        pi_name = f"{dev_name}:{mk_name}"
        pi_oql = f"SELECT PhysicalInterface WHERE name = '{pi_name}' AND connectableci_id = {itop_id}"
        pi_fields = {
            "name": pi_name,
            "connectableci_id": f"SELECT NetworkDevice WHERE id = {itop_id}",
            "macaddress": mac,
        }
        itop.upsert("PhysicalInterface", pi_oql, pi_fields)

    # 5. Sinkronisasi Relasi Kabel dari NetBox
    LOG.info("Mengambil data relasi kabel (links) dari NetBox...")
    nb_interfaces = netbox.get_interfaces(nb_dev["id"])
    unregistered_peers = []

    for intf in nb_interfaces:
        nb_name = intf["name"]
        peers = intf.get("link_peers", [])
        if peers:
            peer = peers[0]
            peer_dev_name = peer.get("device", {}).get("name")
            peer_port_name = peer.get("name")
            
            if peer_dev_name:
                peer_oql = f"SELECT ConnectableCI WHERE name = '{peer_dev_name}'"
                peer_id, peer_data = itop.find("ConnectableCI", peer_oql)
                
                if peer_id:
                    link_oql = (f"SELECT lnkConnectableCIToNetworkDevice "
                                f"WHERE networkdevice_id = {itop_id} AND connectableci_id = {peer_id} "
                                f"AND network_port = '{nb_name}' AND device_port = '{peer_port_name}'")
                    link_fields = {
                        "networkdevice_id": f"SELECT NetworkDevice WHERE id = {itop_id}",
                        "connectableci_id": f"SELECT ConnectableCI WHERE id = {peer_id}",
                        "network_port": nb_name,
                        "device_port": peer_port_name,
                        "connection_type": "downlink",
                    }
                    itop.upsert("lnkConnectableCIToNetworkDevice", link_oql, link_fields, comment="Synced from NetBox")
                else:
                    unregistered_peers.append({
                        "switch_port": nb_name,
                        "peer_device": peer_dev_name,
                        "peer_port": peer_port_name
                    })

    if unregistered_peers:
        LOG.warning("=" * 60)
        LOG.warning("⚠️ TERDAPAT PERANGKAT LAWAN YANG BELUM TERDAFTAR DI ITOP!")
        LOG.warning("=" * 60)
        for p in unregistered_peers:
            LOG.warning("Port %s terhubung ke %s (Port: %s) -> [NOT FOUND IN iTop]", 
                        p['switch_port'], p['peer_device'], p['peer_port'])
        LOG.warning("Harap daftarkan perangkat di atas ke iTop terlebih dahulu.")

    LOG.info("Sinkronisasi selesai! (Interfaces dari Mikrotik, Kabel dari NetBox).")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--device", required=True, help="Network device name")
    parser.add_argument("--mikrotik-user", default=MIKROTIK_USER, help="Mikrotik API username")
    parser.add_argument("--mikrotik-pass", default=MIKROTIK_PASS, help="Mikrotik API password")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying iTop")
    args = parser.parse_args()

    sync_device(args.device, args.mikrotik_user, args.mikrotik_pass, args.dry_run)
