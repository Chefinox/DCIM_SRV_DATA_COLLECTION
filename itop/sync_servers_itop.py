#!/usr/bin/env python3
import json
import logging
import requests
import sys
import argparse
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==============================================================================
# CONFIGURATION
# ==============================================================================
ITOP_URL = 'http://localhost:8080/webservices/rest.php?version=1.3'
ITOP_USER = 'admin'
ITOP_PASS = 'Inovasi@0918'

NETBOX_URL = "http://10.70.0.20:9008"
NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

# Target Servers and their Redfish (XCC) IPs
SERVERS = [
    {"name": "FALAH01-SERVER-HCI-01", "ip": "10.50.0.2"},
    {"name": "FALAH01-SERVER-HCI-02", "ip": "10.50.0.3"},
    {"name": "FALAH01-SERVER-HCI-03", "ip": "10.50.0.4"},
    {"name": "FALAH01-SERVER-RENDER-01", "ip": "10.50.0.5"},
    {"name": "FALAH01-SERVER-RENDER-02", "ip": "10.50.0.6"},
]

# Mapping Redfish NIC Id/Name ke NetBox Interface Name
REDFISH_TO_NETBOX_NIC_MAP = {
    # HCI-01/02/03 (Broadcom 4-port)
    "Port 1": "Ethernet 1",
    "Port 2": "Ethernet 2",
    "Port 3": "Ethernet 3",
    "Port 4": "Ethernet 4",
    # Render-01/02 (Onyx 2-port) - assuming they might be different, but let's standardise on MAC if needed.
    # Alternatively we just rely on matching NetBox interface count. For now we use generic mappings.
}

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s %(message)s",
    level=logging.INFO,
    datefmt="%Y-%m-%d %H:%M:%S",
)
LOG = logging.getLogger("sync_servers")

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
        first_id = next(iter(objs.keys())).split("::")[-1]
        return first_id, objs[f"{class_name}::{first_id}"]["fields"]

    def upsert(self, class_name: str, find_oql: str, fields: dict, comment: str = "sync_servers") -> str | None:
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

    def update(self, class_name: str, obj_id: str, fields: dict, comment: str = "sync_servers") -> bool:
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

    def get_server_interfaces_with_uplinks(self, server_name: str) -> list[dict]:
        """Fetch NetBox interfaces and their connected switch ports."""
        # 1. Get Device ID
        r = requests.get(f"{NETBOX_URL}/api/dcim/devices/?name={server_name}", headers=self.headers)
        res = r.json().get('results', [])
        if not res:
            return []
        dev_id = res[0]['id']

        # 2. Get Interfaces
        r = requests.get(f"{NETBOX_URL}/api/dcim/interfaces/?device_id={dev_id}", headers=self.headers)
        interfaces = []
        for intf in r.json().get('results', []):
            name = intf['name']
            mac = intf.get('mac_address', '')
            uplink_device = None
            uplink_port = None
            
            peers = intf.get('link_peers', [])
            if peers:
                peer = peers[0]
                uplink_device = peer.get('device', {}).get('name')
                uplink_port = peer.get('name')
                
            interfaces.append({
                "name": name,
                "mac": mac,
                "uplink_switch_name": uplink_device,
                "uplink_switch_port": uplink_port,
            })
        return interfaces


# ==============================================================================
# REDFISH CLIENT
# ==============================================================================
class RedfishClient:
    def __init__(self, ip: str, user: str = "hndept", pwd: str = "F!tech@0918"):
        self.base_url = f"https://{ip}"
        self.auth = (user, pwd)

    def get(self, endpoint: str, timeout: int = 15) -> dict:
        url = self.base_url + endpoint
        r = requests.get(url, auth=self.auth, verify=False, timeout=timeout)
        r.raise_for_status()
        return r.json()

    def get_nics(self) -> list[dict]:
        try:
            col = self.get("/redfish/v1/Systems/1/EthernetInterfaces")
        except Exception as e:
            LOG.error("Failed to get EthernetInterfaces: %s", e)
            return []
            
        nics = []
        for member in col.get("Members", []):
            try:
                idata = self.get(member["@odata.id"])
                nics.append({
                    "id":    idata.get("Id", ""),
                    "name":  idata.get("Name", ""),
                    "mac":   (idata.get("MACAddress") or "").upper(),
                    "speed": idata.get("SpeedMbps"),
                    "state": idata.get("Status", {}).get("State", ""),
                })
            except Exception as e:
                pass
        return nics

    def get_physical_disks_with_raid(self) -> list[dict]:
        try:
            storage = self.get("/redfish/v1/Systems/1/Storage")
        except Exception as e:
            LOG.error("Cannot get storage list: %s", e)
            return []
            
        disks = []
        for ctrl_member in storage.get("Members", []):
            try:
                ctrl = self.get(ctrl_member["@odata.id"])
                ctrl_name = ctrl.get("Name", ctrl_member["@odata.id"].split("/")[-1])
                
                # Fetch Volumes to map RAID levels
                raid_map = {} # Drive URL -> RAID Level
                vols_link = ctrl.get("Volumes", {}).get("@odata.id")
                if vols_link:
                    try:
                        vols = self.get(vols_link)
                        for vol_member in vols.get("Members", []):
                            vdata = self.get(vol_member["@odata.id"])
                            raid_type = vdata.get("Oem", {}).get("Lenovo", {}).get("RaidLevel") or vdata.get("RAIDType")
                            for drive_link in vdata.get("Links", {}).get("Drives", []):
                                raid_map[drive_link["@odata.id"]] = raid_type
                    except Exception as e:
                        pass
                
                # Fetch Drives
                for drive in ctrl.get("Drives", []):
                    try:
                        d = self.get(drive["@odata.id"])
                        state = d.get("Status", {}).get("State", "")
                        if state == "Absent":
                            continue
                            
                        size_gb = round((d.get("CapacityBytes") or 0) / 1e9, 1)
                        raid_level = raid_map.get(drive["@odata.id"], "")
                        
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
                            "raid":        raid_level,
                        })
                    except Exception as e:
                        pass
            except Exception as e:
                pass
        return disks

# ==============================================================================
# SYNC LOGIC
# ==============================================================================
def process_server(itop: ITopClient, server_name: str, redfish_ip: str, dry_run: bool):
    LOG.info("=" * 60)
    LOG.info("Mulai memproses server: %s (IP: %s)", server_name, redfish_ip)
    
    # 1. Pastikan Server ada di iTop
    server_oql = f"SELECT Server WHERE name = '{server_name}'"
    server_itop_id, _ = itop.find("Server", server_oql)
    if not server_itop_id:
        LOG.error("Server %s tidak ditemukan di iTop! Skip.", server_name)
        return

    # 2. Fetch Netbox & Redfish Data
    netbox = NetboxClient()
    nb_interfaces = netbox.get_server_interfaces_with_uplinks(server_name)
    if not nb_interfaces:
        LOG.warning("Tidak ada interface NetBox untuk %s", server_name)
        return
        
    redfish = RedfishClient(redfish_ip)
    LOG.info("Mengambil data NIC dari Redfish...")
    rf_nics = redfish.get_nics()
    LOG.info("Mengambil data Storage dari Redfish...")
    rf_disks = redfish.get_physical_disks_with_raid()
    
    # 3. Process Physical Interfaces & Network Connections
    for nb_intf in nb_interfaces:
        nb_name = nb_intf["name"]
        
        # Match Redfish MAC and Speed if possible
        # Default speed is 1Gbps or 10Gbps depending on name if not matched.
        mac = nb_intf["mac"] or ""
        speed = "10 Gbps" if "10G" in nb_name or "Ethernet 2" in nb_name or "Ethernet 3" in nb_name or "Ethernet 4" in nb_name else "1 Gbps"
        
        # Coba match redfish untuk MAC
        for rf in rf_nics:
            if REDFISH_TO_NETBOX_NIC_MAP.get(rf["name"]) == nb_name or ("XCC" in nb_name and "ToManager" in rf["id"]):
                mac = rf["mac"]
                if rf["speed"]:
                    speed = f"{int(rf['speed']/1000)} Gbps" if rf['speed'] >= 1000 else f"{rf['speed']} Mbps"
                break
        
        # 3a. Upsert Server Physical Interface
        intf_itop_name = f"{server_name}:{nb_name}"
        pi_oql = f"SELECT PhysicalInterface WHERE name = '{intf_itop_name}'"
        pi_fields = {
            "name": intf_itop_name,
            "connectableci_id": f"SELECT Server WHERE id = {server_itop_id}",
            "macaddress": mac,
            "speed": speed,
        }
        itop.upsert("PhysicalInterface", pi_oql, pi_fields, comment="sync_servers - Server NIC")
        
        # 3b. Upsert Switch Uplink and Connection
        if nb_intf["uplink_switch_name"] and nb_intf["uplink_switch_port"]:
            sw_name = nb_intf["uplink_switch_name"]
            sw_port = nb_intf["uplink_switch_port"]
            
            # Find switch in iTop
            sw_oql = f"SELECT NetworkDevice WHERE name = '{sw_name}'"
            sw_itop_id, _ = itop.find("NetworkDevice", sw_oql)
            
            if sw_itop_id:
                # BUAT PhysicalInterface di Switch
                sw_intf_name = f"{sw_name}:{sw_port}"
                sw_pi_oql = f"SELECT PhysicalInterface WHERE name = '{sw_intf_name}' AND connectableci_id = {sw_itop_id}"
                sw_pi_fields = {
                    "name": sw_intf_name,
                    "connectableci_id": f"SELECT NetworkDevice WHERE id = {sw_itop_id}",
                    "macaddress": "", # We don't necessarily know switch MAC
                }
                itop.upsert("PhysicalInterface", sw_pi_oql, sw_pi_fields, comment="sync_servers - Switch NIC")
                
                # BUAT Link
                link_oql = f"SELECT lnkConnectableCIToNetworkDevice WHERE connectableci_id = {server_itop_id} AND networkdevice_id = {sw_itop_id} AND device_port = '{nb_name}' AND network_port = '{sw_port}'"
                link_fields = {
                    "networkdevice_id": f"SELECT NetworkDevice WHERE id = {sw_itop_id}",
                    "connectableci_id": f"SELECT Server WHERE id = {server_itop_id}",
                    "network_port": sw_port,
                    "device_port": nb_name,
                    "connection_type": "downlink",
                }
                itop.upsert("lnkConnectableCIToNetworkDevice", link_oql, link_fields, comment="sync_servers - Switch link")
            else:
                LOG.warning("Switch %s tidak ditemukan di iTop!", sw_name)

    # 4. Process Storage and Logical Volumes
    if rf_disks:
        # Create StorageSystem parent
        ss_name = f"{server_name}:Internal RAID Storage"
        ss_oql = f"SELECT StorageSystem WHERE name = '{ss_name}'"
        ss_fields = {
            "name":        ss_name,
            "org_id":      "SELECT Organization WHERE id = 1",
            "description": f"Internal RAID Storage for {server_name}",
            "location_id": "SELECT Location WHERE name = \"Ruang Server\"",
            "status":      "production",
        }
        ss_id = itop.upsert("StorageSystem", ss_oql, ss_fields, comment="sync_servers - StorageSystem")
        
        if ss_id and ss_id != "dry-run":
            for disk in rf_disks:
                disk_id = disk["id"]
                size_str = f"{disk['size_gb']} GB"
                raid_str = disk.get("raid", "")
                disk_label = f"{server_name}:{disk_id} ({size_str} {disk['media_type']} {disk['protocol']})"
                
                desc = (
                    f"Physical Disk | Controller: {disk['controller']} | "
                    f"Model: {disk['model']} | SN: {disk['serial']} | "
                    f"Size: {size_str} | Type: {disk['media_type']} | Protocol: {disk['protocol']}"
                )
                
                # Upsert LogicalVolume
                lv_oql = f"SELECT LogicalVolume WHERE name = '{disk_label}'"
                lv_fields = {
                    "name": disk_label,
                    "lun_id": disk_id,
                    "storagesystem_id": f"SELECT StorageSystem WHERE id = {ss_id}",
                    "description": desc,
                    "size": size_str,
                    "raid_level": raid_str,
                }
                lv_id = itop.upsert("LogicalVolume", lv_oql, lv_fields, comment="sync_servers - disk")
                
                if lv_id and lv_id != "dry-run":
                    # update existing if changed
                    _, lv_cur = itop.find("LogicalVolume", f"SELECT LogicalVolume WHERE id = {lv_id}")
                    updates = {}
                    if lv_cur.get("size") != size_str: updates["size"] = size_str
                    if lv_cur.get("raid_level") != raid_str: updates["raid_level"] = raid_str
                    if updates:
                        itop.update("LogicalVolume", lv_id, updates)
                    
                    # Link server to volume
                    link_oql = f"SELECT lnkServerToVolume WHERE server_id = {server_itop_id} AND volume_id = {lv_id}"
                    link_fields = {
                        "server_id": f"SELECT Server WHERE id = {server_itop_id}",
                        "volume_id": f"SELECT LogicalVolume WHERE id = {lv_id}",
                        "size_used": size_str,
                    }
                    lnk_id = itop.upsert("lnkServerToVolume", link_oql, link_fields, comment="sync_servers - lnkServerToVolume")
                    
                    if lnk_id and lnk_id != "dry-run":
                        _, lnk_cur = itop.find("lnkServerToVolume", f"SELECT lnkServerToVolume WHERE id = {lnk_id}")
                        if lnk_cur.get("size_used") != size_str:
                            itop.update("lnkServerToVolume", lnk_id, {"size_used": size_str})
                            
    LOG.info("Selesai memproses %s", server_name)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Print actions without modifying iTop")
    args = parser.parse_args()

    itop = ITopClient(dry_run=args.dry_run)
    
    for srv in SERVERS:
        process_server(itop, srv["name"], srv["ip"], dry_run=args.dry_run)
