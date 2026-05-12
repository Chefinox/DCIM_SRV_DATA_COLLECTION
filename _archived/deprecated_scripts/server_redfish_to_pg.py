#!/usr/bin/env python3
import logging
import sys
import os

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.skills.inventory.redfish_scanner.executor import RedfishScannerExecutor
from src.skills.cmdb.asset_enricher.executor import AssetEnricherExecutor
from src.skills.telemetry.event_logger.executor import EventLoggerExecutor

# --- CONFIGURATION ---
REDFISH_SERVERS = ["10.50.0.2", "10.50.0.3", "10.50.0.4", "10.50.0.5", "10.50.0.6"]
REDFISH_USER = "poller"
REDFISH_PASS = "F!tech0918"

LOG_FILE = "/home/infra/dcim_metrics_project/logs/server_redfish_to_pg.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format='%(asctime)s %(levelname)s: %(message)s'
)

def run():
    logging.info("=== SERVER INVENTORY PIPELINE (Multi-Skill): START ===")
    
    # Initialize Skills
    scanner  = RedfishScannerExecutor()
    enricher = AssetEnricherExecutor()
    logger   = EventLoggerExecutor()

    for ip in REDFISH_SERVERS:
        logging.info(f"Processing target: {ip}")
        try:
            # Step 1: Scan (Hardware Context)
            inventory = scanner.run_scan(ip, REDFISH_USER, REDFISH_PASS)
            if not inventory:
                logging.warning(f"  {ip}: Scan failed.")
                continue

            # Step 2: Enrich (Business Context)
            enriched_data = enricher.enrich(inventory)

            # Step 3: Log (Historical Context)
            event_id = logger.log_event(enriched_data)
            
            logging.info(f"  {ip}: Pipeline complete. EventID: {event_id}")

        except Exception as e:
            logging.error(f"  {ip}: Pipeline crash — {e}")

    logging.info("=== SERVER INVENTORY PIPELINE: DONE ===")

if __name__ == "__main__":
    run()
