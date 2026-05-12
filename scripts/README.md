# Scripts Directory

Production scripts for DCIM pipeline operations.

## Active Production Scripts

### Data Collection
- **hikvision_poller.py** - CCTV/NVR data collector via ISAPI HTTP
- **server_inventory_to_pg.py** - Server inventory collector via Redfish (Daily 01:00)

### Data Processing
- **dcim_normalizer.py** - Layer 2: Normalize raw Kafka messages to unified schema
- **dcim_sql_consumer.py** - Layer 4: Consume enriched events to PostgreSQL
- **dcim_dlq_consumer.py** - Dead letter queue handler for failed messages
- **kafka_to_es_sync.py** - Sync Kafka messages to Elasticsearch

### CMDB Integration
- **ralph_cmdb_sync.py** - Unified sync: PostgreSQL → Ralph CMDB (Daily 02:00)
- **ralph_sync_agent.py** - Alternative Ralph sync implementation

### Utilities
- **manage_partitions.py** - PostgreSQL partition management
- **audit_pipeline_quality.py** - Pipeline data quality auditor
- **create_kibana_dashboard.py** - Kibana dashboard generator
- **init_custom_fields.py** - Initialize Ralph custom fields

## Deprecated Scripts

Moved to `_archived/deprecated_scripts/`:
- `server_deep_sync.py` - Direct Ralph sync (superseded by unified pipeline)
- `server_redfish_to_pg.py` - Broken skill-based architecture

## Usage

Most scripts are run as systemd services or cron jobs. For manual execution:

```bash
# Run normalizer
python3 dcim_normalizer.py

# Collect server inventory
python3 server_inventory_to_pg.py

# Sync to Ralph CMDB
python3 ralph_cmdb_sync.py
```

## Logs

Check logs in `../logs/` directory:
- `dcim_normalizer.log`
- `server_inventory_to_pg.log`
- `ralph_cmdb_sync.log`
