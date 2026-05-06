import logging
import uuid
import json
from datetime import datetime, timezone
from src.tools.storage.postgres_client import PostgresClient

class EventLoggerExecutor:
    """
    SINGLE RESPONSIBILITY:
    - Persist enriched DCIM objects to historical event table (dcim_events).
    """
    def __init__(self):
        self.db = PostgresClient()

    def log_event(self, data):
        logging.info(f"Capability: Event Logging -> {data.get('hostname')}")
        conn = self.db.connect()
        now = datetime.now(timezone.utc)
        event_id = str(uuid.uuid4())

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO dcim_events (
                    event_id, event_time, inserted_at, device_type, hostname, ip, serial_number, model,
                    site, rack_name, manufacturer, asset_status, environment, business_unit,
                    srv_firmware, srv_bios_version, srv_system_name, srv_management_ip,
                    srv_cpu_components, srv_memory_components, srv_nic_components, srv_disk_components
                ) VALUES (%s, %s, %s, 'server', %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                event_id, now, now, data.get("hostname"), data.get("ip"), data.get("serial_number"), data.get("model"),
                data.get("site"), data.get("rack_name"), data.get("manufacturer"), data.get("asset_status"), 
                data.get("environment"), data.get("business_unit"),
                data.get("firmware"), data.get("bios_version"), data.get("system_name"), data.get("ip"),
                json.dumps(data.get("processors", [])), json.dumps(data.get("memory", [])), 
                json.dumps(data.get("ethernets", [])), json.dumps(data.get("disks", []))
            ))
        conn.commit()
        return event_id
