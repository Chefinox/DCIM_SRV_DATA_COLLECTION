#!/usr/bin/env python3
import json
import logging
import requests
import sys

ITOP_URL = 'http://localhost:8080/webservices/rest.php?version=1.3'
ITOP_USER = 'admin'
ITOP_PASS = 'Inovasi@0918'

NETBOX_URL = "http://10.70.0.20:9008"
NETBOX_TOKEN = "w6ik0rigeZ9q0OfKL0dgiUvTUXhl4bR8We7dHgLS"

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-8s %(message)s")
LOG = logging.getLogger("sync_pdus")

class ITopClient:
    def __init__(self):
        self.session = requests.Session()

    def _post(self, payload: dict) -> dict:
        r = self.session.post(ITOP_URL, data={"auth_user": ITOP_USER, "auth_pwd": ITOP_PASS, "json_data": json.dumps(payload)})
        r.raise_for_status()
        return r.json()

    def find(self, class_name: str, oql: str) -> tuple[str | None, dict]:
        body = self._post({"operation": "core/get", "class": class_name, "key": oql, "output_fields": "*"})
        objs = body.get("objects")
        if not objs: return None, {}
        first_key = next(iter(objs.keys()))
        return first_key.split("::")[-1], objs[first_key]["fields"]

    def upsert(self, class_name: str, find_oql: str, fields: dict) -> str | None:
        obj_id, _ = self.find(class_name, find_oql)
        if obj_id:
            return obj_id
        body = self._post({"operation": "core/create", "class": class_name, "fields": fields, "comment": "sync_pdus"})
        objs = body.get("objects") or {}
        if objs:
            return next(iter(objs.keys())).split("::")[-1]
        return None

    def update(self, class_name: str, obj_id: str, fields: dict):
        self._post({"operation": "core/update", "class": class_name, "key": obj_id, "fields": fields, "comment": "sync_pdus"})


def main():
    itop = ITopClient()
    headers = {"Authorization": f"Token {NETBOX_TOKEN}"}
    
    LOG.info("Fetching PDUs from NetBox...")
    r = requests.get(f"{NETBOX_URL}/api/dcim/devices/?role=pdu&limit=1000", headers=headers)
    pdus = r.json().get("results", [])
    
    # Filter only PDU devices
    # Actually NetBox device role 'pdu' is standard. Let's just fetch devices with PDU in name.
    r_all = requests.get(f"{NETBOX_URL}/api/dcim/devices/?limit=1000", headers=headers)
    all_devs = r_all.json().get("results", [])
    pdu_devs = [d for d in all_devs if "PDU" in d["name"]]
    
    for pdu in pdu_devs:
        name = pdu["name"]
        LOG.info(f"Processing PDU: {name}")
        
        rack_name = pdu.get("rack", {}).get("name") if pdu.get("rack") else "Unknown"
        # iTop needs a rack. Let's find or create a dummy rack if needed, or better, find the real rack
        rack_id = None
        if rack_name != "Unknown":
            rack_id, _ = itop.find("Rack", f"SELECT Rack WHERE name='{rack_name}'")
            if not rack_id:
                # We need org_id for Rack, assuming org_id 1
                rack_id = itop.upsert("Rack", f"SELECT Rack WHERE name='{rack_name}'", {"name": rack_name, "org_id": "1"})
        
        if not rack_id:
            LOG.warning(f"PDU {name} tidak memiliki Rack di NetBox, menempatkan di Rack default 'Unknown'")
            rack_id = itop.upsert("Rack", "SELECT Rack WHERE name='Unknown'", {"name": "Unknown", "org_id": "1"})
            
        u_height = 0
        if pdu.get("device_type", {}).get("url"):
            try:
                dt = requests.get(pdu["device_type"]["url"], headers=headers).json()
                if dt.get("u_height"): u_height = dt["u_height"]
            except: pass
            
        # Get uplink power connection
        p_ports = requests.get(f"{NETBOX_URL}/api/dcim/power-ports/?device_id={pdu['id']}", headers=headers).json().get("results", [])
        ups_itop_id = None
        for port in p_ports:
            if port.get("link_peers"):
                for peer in port["link_peers"]:
                    if peer.get("device"):
                        peer_dev = peer["device"]["name"]
                        if "UPS" in peer_dev:
                            # Found UPS!
                            ups_itop_id, _ = itop.find("PowerSource", f"SELECT PowerSource WHERE name='{peer_dev}'")
                            if ups_itop_id:
                                LOG.info(f"  Terhubung ke UPS: {peer_dev}")
        
        # Create or update PDU
        fields = {
            "name": name,
            "org_id": "1",
            "rack_id": rack_id,
            "nb_u": str(int(u_height))
        }
        if ups_itop_id:
            fields["powerA_id"] = ups_itop_id
            
        pdu_itop_id, _ = itop.find("PDU", f"SELECT PDU WHERE name='{name}'")
        if not pdu_itop_id:
            pdu_itop_id = itop.upsert("PDU", f"SELECT PDU WHERE name='{name}'", fields)
            LOG.info(f"  ✅ CREATED PDU id={pdu_itop_id}")
        else:
            itop.update("PDU", pdu_itop_id, fields)
            LOG.info(f"  ✅ UPDATED PDU id={pdu_itop_id}")

if __name__ == "__main__":
    main()
