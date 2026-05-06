import logging
import uuid
from datetime import datetime, timezone
from src.tools.protocols.redfish_client import RedfishClient
from src.tools.storage.postgres_client import PostgresClient
from src.schemas.transformers.server_inventory import transform_redfish_to_inventory

class RedfishScannerExecutor:
    """
    SINGLE RESPONSIBILITY:
    - Collect hardware data via Redfish protocol.
    - Transform to standardized inventory schema.
    - Persist RAW/NORMALIZED hardware state.
    """
    def __init__(self):
        self.db = PostgresClient()

    def run_scan(self, ip, user, password):
        logging.info(f"Capability: Redfish Scan -> {ip}")
        client = RedfishClient(ip, user, password)
        
        # 1. Fetch
        raw_payloads = self._fetch_all_data(client)
        if not raw_payloads.get("systems"):
            return None

        # 2. Transform
        inventory_data = transform_redfish_to_inventory(ip, raw_payloads)
        if not inventory_data["serial_number"]:
            return None

        # 3. Store normalized hardware state (No CMDB enrichment here)
        self._persist_hardware_state(inventory_data)
        
        return inventory_data

    def _fetch_all_data(self, client):
        data = {
            "systems": client.get("Systems/1"),
            "chassis": client.get("Chassis/1"),
            "managers": client.get("Managers/1"),
            "processors": [], "memory": [], "ethernets": [], "disks": []
        }
        # (Logika fetch yang sama seperti sebelumnya...)
        procs = client.get("Systems/1/Processors")
        if procs:
            for m in procs.get("Members", []):
                data["processors"].append(client.get(m['@odata.id']))
        mems = client.get("Systems/1/Memory")
        if mems:
            for m in mems.get("Members", []):
                data["memory"].append(client.get(m['@odata.id']))
        eths = client.get("Systems/1/EthernetInterfaces")
        if eths:
            for m in eths.get("Members", []):
                data["ethernets"].append(client.get(m['@odata.id']))
        storage = client.get("Systems/1/Storage")
        if storage:
            for ctrl in storage.get("Members", []):
                ctrl_data = client.get(ctrl['@odata.id'])
                if ctrl_data:
                    for drive in ctrl_data.get("Drives", []):
                        data["disks"].append(client.get(drive['@odata.id']))
        return data

    def _persist_hardware_state(self, data):
        """Skill responsibility: Orchestrate persistence via tools."""
        ip = data["ip"]
        batch = []
        
        # Prepare Batch Queries
        batch.append(("DELETE FROM dcim_server_disks WHERE server_ip = %s", (ip,)))
        for d in data["disks"]:
            batch.append(("INSERT INTO dcim_server_disks (server_ip, serial_number, model_name, size_gb, slot, firmware_version) VALUES (%s, %s, %s, %s, %s, %s)",
                         (ip, d.get("serial_number"), d.get("model_name"), d.get("size_gb"), d.get("slot"), d.get("firmware_version"))))
        
        batch.append(("DELETE FROM dcim_server_ram WHERE server_ip = %s", (ip,)))
        for r in data["memory"]:
            batch.append(("INSERT INTO dcim_server_ram (server_ip, model_name, size_mb, speed_mhz) VALUES (%s, %s, %s, %s)",
                         (ip, r.get("model_name"), r.get("size_mb"), r.get("speed_mhz"))))
        
        # Execute via Tool
        self.db.execute_batch(batch)
