import logging
from src.tools.storage.postgres_client import PostgresClient
from src.schemas.transformers.asset_metadata import extract_metadata

class AssetEnricherExecutor:
    """
    SINGLE RESPONSIBILITY:
    - Enrich any inventory object with CMDB metadata (Site, Rack, Status).
    - Decoupled from hardware collection protocols.
    """
    def __init__(self):
        self.db = PostgresClient()

    def enrich(self, inventory_data):
        """
        Takes an inventory dict and returns an enriched version.
        Required keys in inventory_data: serial_number OR hostname
        """
        sn = inventory_data.get("serial_number")
        hostname = inventory_data.get("hostname")
        
        logging.info(f"Capability: Asset Enrichment -> SN:{sn} / Host:{hostname}")
        
        query = """
            SELECT hostname, serial_number, site, raw_payload 
            FROM unified_assets 
            WHERE (serial_number IS NOT NULL AND LOWER(serial_number) = LOWER(%s)) 
               OR (hostname IS NOT NULL AND LOWER(hostname) = LOWER(%s))
            LIMIT 1
        """
        rows = self.db.execute_query(query, (sn, hostname))
        
        enriched_info = {}
        if rows:
            # Use standardized transformer
            row_data = (rows[0]['hostname'], rows[0]['serial_number'], rows[0]['site'], rows[0]['raw_payload'])
            enriched_info = extract_metadata(row_data)
        else:
            logging.warning(f"No CMDB record found for SN:{sn} / Host:{hostname}")
            enriched_info = {
                "site": "Unknown", 
                "rack_name": "Unknown", 
                "manufacturer": inventory_data.get("manufacturer", "Unknown"),
                "asset_status": "Unknown", 
                "enrichment_status": "NOT_IN_CMDB"
            }
            
        # Merge enrichment into inventory data
        inventory_data.update(enriched_info)
        return inventory_data
