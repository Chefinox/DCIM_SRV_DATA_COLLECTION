#!/usr/bin/env python3
"""
Manual sync: Render server logical volumes ke iTop.
Dipakai ketika consumer belum memproses data baru dari Kafka.

Usage: python3 sync_render_storage.py
"""

import sys
import logging
sys.path.insert(0, "/home/infra/dcim_metrics_project")
sys.path.insert(0, "/home/infra/dcim_metrics_project/scripts")

from itop_sync_utils import get_server_hardware
from dcim_itop_unified_consumer import ITopClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("sync_render_storage")

AUTO_ORG_ID = "1"
RENDER_SERVERS = ["SERVER-Render-01", "SERVER-Render-02"]

def main():
    itop = ITopClient()
    
    for hostname in RENDER_SERVERS:
        logger.info(f"=== Processing {hostname} ===")
        
        # Get hardware from PostgreSQL (with ILIKE fix)
        hw = get_server_hardware(hostname)
        if not hw:
            logger.error(f"  No hardware data found for {hostname}")
            continue
        
        logger.info(f"  Disks: {len(hw.get('disk_comps', []))}, NICs: {len(hw.get('nic_comps', []))}")
        
        # Find server in iTop
        for cls in ["Server"]:
            body = itop._post({
                "operation": "core/get",
                "class": cls,
                "key": f"SELECT {cls} WHERE name = '{hostname}'",
                "output_fields": "id,org_id,location_id"
            })
            objs = body.get("objects", {})
            if objs:
                key = list(objs.keys())[0]
                server_id = key.split("::")[-1]
                fields = objs[key]["fields"]
                org_id = fields.get("org_id", AUTO_ORG_ID)
                location_id = fields.get("location_id", "0")
                
                logger.info(f"  Found in iTop: ID={server_id}, org={org_id}, location={location_id}")
                
                # Call the same sync function the consumer uses
                from dcim_itop_unified_consumer import sync_server_nics_and_disks
                sync_server_nics_and_disks(itop, server_id, hostname, org_id, location_id, hw, "Server")
                logger.info(f"  ✅ Sync completed for {hostname}")
                break
        else:
            logger.error(f"  {hostname} not found in iTop!")

if __name__ == "__main__":
    main()
