import logging
from src.skills.inventory.redfish_scanner.executor import RedfishScannerExecutor
from src.skills.security.cctv_poller.executor import CCTVPollerExecutor
from src.skills.cmdb.asset_enricher.executor import AssetEnricherExecutor
from src.skills.telemetry.event_logger.executor import EventLoggerExecutor
from src.schemas.output.influx_formatter import format_cctv_to_influx

class DCIMPipelineWorkflow:
    """
    WORKFLOW LAYER:
    Restores the mental model of the pipeline by orchestrating atomic skills.
    This is the high-level representation of the DCIM business logic.
    """
    def __init__(self):
        # Initialize atomic skills
        self.server_scanner = RedfishScannerExecutor()
        self.cctv_poller    = CCTVPollerExecutor()
        self.asset_enricher = AssetEnricherExecutor()
        self.event_logger   = EventLoggerExecutor()

    def run_server_pipeline(self, ip, user, password):
        """
        Flow: Hardware Scan -> CMDB Enrichment -> Persistence
        """
        logging.info(f"Workflow: Server Pipeline Start -> {ip}")
        
        # Step 1: Collect hardware inventory via Redfish
        inventory = self.server_scanner.run_scan(ip, user, password)
        if not inventory:
            return None

        # Step 2: Enrich with CMDB context (Site, Rack, Status)
        enriched_data = self.asset_enricher.enrich(inventory)

        # Step 3: Log historical event to database
        event_id = self.event_logger.log_event(enriched_data)
        
        logging.info(f"Workflow: Server Pipeline Success. EventID: {event_id}")
        return enriched_data

    def run_cctv_pipeline(self, ip, user, password, nvr_mapping=None):
        """
        Flow: Camera Poll -> NVR Proxy Mapping (if needed) -> Enrichment -> Output
        """
        logging.info(f"Workflow: CCTV Pipeline Start -> {ip}")

        # Step 1: Collect camera telemetry via ISAPI
        metrics = self.cctv_poller.poll_device(ip, user, password)

        # Step 2: Apply NVR mapping if direct serial number is missing
        if metrics.get("serial_number") == "NO_SN" and nvr_mapping and ip in nvr_mapping:
            metrics["serial_number"] = nvr_mapping[ip]

        # Step 3: Enrich with CMDB context
        enriched_data = self.asset_enricher.enrich(metrics)

        # Step 4: Format to InfluxDB Line Protocol (for Telegraf consumption)
        influx_line = format_cctv_to_influx(enriched_data)
        
        logging.info(f"Workflow: CCTV Pipeline Complete -> {ip}")
        return influx_line

    def discover_cctv_topology(self, nvr_ip, user, password):
        """
        Flow: Identify sub-devices connected via NVR proxy
        """
        return self.cctv_poller.discover_nvr_channels(nvr_ip, user, password)
